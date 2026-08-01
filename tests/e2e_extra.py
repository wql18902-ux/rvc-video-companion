#!/usr/bin/env python3
"""RVC 服务器 E2E 分层测试 · L2 真实进程集成（不触碰 sha256 冻结基准）

覆盖负向路径（真实 server.py 代码 + 真实 ffmpeg）：
- 转码失败：损坏文件请求 /api/stream -> 200 空流 + /api/stream-error 返回结构化错误码 + 服务器不崩溃
- 端口占用：8765 被占时启动 server.py -> 打印「已在运行」并退出 0（幂等启动）
- 播放中断：/api/stream 读一半断开 -> 服务器存活、/api/stop 正常；/api/control SSE 断连 -> 广播仍正常
- 正向对照组：sample.mp4 真实转码出流 >0 字节（证明 L2 自身链路有效）

双模式：
- 8765 空闲：直接起真实 server.py 子进程（最真实）
- 8765 已被占用（用户服务器在跑）：集成用例改在独立测试端口起同一份 server.py
  代码（launcher 方式），绝不打断用户播放；端口占用用例仍针对 8765 验证

运行：python3 tests/e2e_extra.py（需要真实 ffmpeg；fixtures/sample.mp4 只读）
"""
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_DIR = os.path.join(ROOT, 'stream-server')
SERVER_PY = os.path.join(SERVER_DIR, 'server.py')
FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'sample.mp4')
PORT = 8765
BASE = f'http://127.0.0.1:{PORT}'


def clean_env():
    return {k: v for k, v in os.environ.items() if k not in ('PYTHONHOME', 'PYTHONPATH')}


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('127.0.0.1', port)) == 0


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def http_get(path, timeout=15, read_all=True):
    port = int(BASE.rsplit(':', 1)[1])
    # 请求行必须 ASCII：路径参数中的非 ASCII（如中文目录名）统一 percent-encode
    path = quote(path, safe='/?&=:')
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    conn.request('GET', path, headers={'Host': f'127.0.0.1:{port}'})
    resp = conn.getresponse()
    data = resp.read() if read_all else b''
    conn.close()
    return resp.status, resp.getheaders(), data


def http_get_json(path, timeout=10):
    """GET 并解析 JSON（如 /api/stop 是 GET 路由，无 POST 版）"""
    status, _, data = http_get(path, timeout=timeout)
    return status, json.loads(data)


def http_post(path, body):
    port = int(BASE.rsplit(':', 1)[1])
    path = quote(path, safe='/?&=:')
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    conn.request('POST', path, body=json.dumps(body).encode(),
                 headers={'Host': f'127.0.0.1:{port}',
                          'Content-Type': 'application/json'})
    resp = conn.getresponse()
    data = json.loads(resp.read())
    conn.close()
    return resp.status, data


class TestE2EExtra(unittest.TestCase):
    """L2：真实进程负向路径（转码失败 / 端口占用 / 播放中断）"""

    @classmethod
    def setUpClass(cls):
        global BASE
        cls.tmp = tempfile.mkdtemp(prefix='rvc-l2-')
        cls.proc = None
        cls.external = port_in_use(PORT)
        if cls.external:
            # 用户服务器在跑：集成用例改到独立测试端口起同一份 server.py 代码
            cls.test_port = find_free_port()
            launcher = os.path.join(cls.tmp, 'launcher.py')
            with open(launcher, 'w') as f:
                f.write(
                    'import sys\n'
                    f'sys.path.insert(0, {SERVER_DIR!r})\n'
                    'import server\n'
                    f'server.PORT = {cls.test_port}\n'
                    # 随机测试端口需加入 Host 白名单（否则无 Origin 请求被 403）
                    f'server.ALLOWED_HOSTS = server.ALLOWED_HOSTS | '
                    f"{{f'127.0.0.1:{cls.test_port}', f'localhost:{cls.test_port}'}}\n"
                    'httpd = server.ThreadedHTTPServer(('
                    f"'127.0.0.1', server.PORT), server.StreamHandler)\n"
                    'httpd.serve_forever()\n')
            cls.proc = subprocess.Popen(
                [sys.executable, launcher],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, env=clean_env())
            BASE = f'http://127.0.0.1:{cls.test_port}'
        else:
            # 空闲：直接起真实 server.py（清 PYTHONHOME/PYTHONPATH，TRAE 注入会崩）
            cls.proc = subprocess.Popen(
                [sys.executable, SERVER_PY],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, env=clean_env())
            BASE = f'http://127.0.0.1:{PORT}'
        ok = False
        for _ in range(40):
            if cls.proc.poll() is not None:
                break
            try:
                status, _, _ = http_get('/api/files?dir=/tmp', timeout=2)
                if status == 200:
                    ok = True
                    break
            except Exception:
                pass
            time.sleep(0.25)
        if not ok:
            out = ''
            try:
                out = (cls.proc.stdout.read() if cls.proc.stdout else '')[:2000]
            except Exception:
                pass
            cls.proc.terminate()
            raise RuntimeError(f'测试服务器启动失败，输出: {out}')

    @classmethod
    def tearDownClass(cls):
        if cls.proc is not None:
            cls.proc.terminate()
            try:
                cls.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.proc.kill()
            if cls.proc.stdout:
                try:
                    cls.proc.stdout.close()
                except Exception:
                    pass
        # 清理本测试产生的转码日志（e2e- 前缀）
        log_dir = os.path.join(ROOT, 'stream-server', 'logs')
        if os.path.isdir(log_dir):
            for name in os.listdir(log_dir):
                if name.startswith('transcode-e2e-') and name.endswith('.log'):
                    try:
                        os.remove(os.path.join(log_dir, name))
                    except OSError:
                        pass
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        pass

    # ---------- 负向：转码失败（受影响路由：/api/stream /api/stream-error） ----------
    def test_transcode_failure_damaged_file(self):
        bad = os.path.join(self.tmp, 'damaged.mkv')
        with open(bad, 'wb') as f:
            f.write(os.urandom(4096))   # 非媒体垃圾数据
        req_id = 'e2e-fail-%d' % int(time.time() * 1000)
        status, headers, body = http_get(
            f'/api/stream?dir={self.tmp}&file=damaged.mkv&req={req_id}', timeout=30)
        # 契约：转码失败可诊断（错误码经 /api/stream-error 查询），状态码兼容竞态：
        #  - 秒挂探测（250ms）内 poll 到退出 -> 500 JSON（send_transcode_error，
        #    mpegts 对非 2xx 必触发 ERROR 回调，播放端再凭 req_id 查错误提示）
        #  - 未 poll 到 -> 200 空流（黑屏），流结束时 finally 写错误码
        self.assertIn(status, (200, 500))
        if status == 200:
            self.assertEqual(body, b'')
        rid = dict(headers).get('X-RVC-Request-Id')
        self.assertEqual(rid, req_id)

        # 结构化错误码可经 /api/stream-error 查询（与生产播放端重试逻辑一致）
        result = None
        for _ in range(5):
            status, _, data = http_get(f'/api/stream-error?req={req_id}')
            if status == 200:
                payload = json.loads(data)
                if payload.get('ok'):
                    result = payload
                    break
            time.sleep(0.3)
        self.assertIsNotNone(result, 'stream-error 结果未就绪')
        self.assertIn(result['code'], ('INVALID_DATA', 'TRANSCODE_FAILED'))
        self.assertTrue(result['message'])

        # 服务器不崩溃：后续请求正常
        status, _, _ = http_get('/api/files?dir=/tmp')
        self.assertEqual(status, 200)

    # ---------- 负向：端口占用（受影响路由：服务器启动路径） ----------
    def test_port_in_use_startup(self):
        # 8765 必然已被占用（外部模式=用户服务器；空闲模式=本测试自起服务器）
        # 此时再启动 server.py 应幂等退出：打印「已在运行」且退出码 0
        proc = subprocess.Popen(
            [sys.executable, SERVER_PY],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, env=clean_env())
        try:
            out, _ = proc.communicate(timeout=15)
        finally:
            if proc.poll() is None:
                proc.kill()
        self.assertEqual(proc.returncode, 0)          # 幂等启动：不崩
        self.assertIn('已在运行', out)                 # 明确提示已有实例

    # ---------- 负向：播放中断（受影响路由：/api/stream /api/control /api/stop） ----------
    def test_playback_interrupt_stream(self):
        # 真实转码 sample.mp4，读少量字节后主动断开（模拟用户关页面/跳转）
        port = int(BASE.rsplit(':', 1)[1])
        req_id = 'e2e-int-%d' % int(time.time() * 1000)
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=30)
        conn.request('GET', quote(
            f'/api/stream?dir={ROOT}/tests/fixtures&file=sample.mp4&req={req_id}',
            safe='/?&=:'),
            headers={'Host': f'127.0.0.1:{port}'})
        resp = conn.getresponse()
        first = resp.read(4096)
        conn.close()   # 播放中断
        self.assertGreater(len(first), 0)    # 中断前已出流

        time.sleep(1)
        # 服务器存活 + 转码进程已清理（/api/stop 正常返回；注意 stop 是 GET 路由）
        status, _, _ = http_get('/api/files?dir=/tmp')
        self.assertEqual(status, 200)
        status, data = http_get_json('/api/stop')
        self.assertEqual(status, 200)
        self.assertTrue(data['ok'])

    def test_playback_interrupt_sse(self):
        # SSE 连接建立后断开（模拟播放器页面关闭）
        port = int(BASE.rsplit(':', 1)[1])
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        conn.request('GET', '/api/control', headers={'Host': f'127.0.0.1:{port}'})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        conn.close()   # 断连

        time.sleep(1)
        # 新连接 + 热键广播仍正常（旧连接清理未破坏广播链路）
        conn2 = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        conn2.request('GET', '/api/control', headers={'Host': f'127.0.0.1:{port}'})
        resp2 = conn2.getresponse()
        self.assertEqual(resp2.status, 200)
        status, data = http_post('/api/control-key', {'action': 'toggle_play'})
        self.assertEqual(status, 200)
        self.assertTrue(data['ok'])
        conn2.close()

    # ---------- 正向对照组：真实转码链路有效（L2 自身有效性） ----------
    def test_transcode_smoke_positive(self):
        req_id = 'e2e-ok-%d' % int(time.time() * 1000)
        status, _, body = http_get(
            f'/api/stream?dir={ROOT}/tests/fixtures&file=sample.mp4&req={req_id}', timeout=60)
        self.assertEqual(status, 200)
        self.assertGreater(len(body), 4096)   # sample.mp4 转码出流
        status, data = http_get_json('/api/stop')
        self.assertEqual(status, 200)
        self.assertTrue(data['ok'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
