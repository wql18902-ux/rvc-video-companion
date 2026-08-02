#!/usr/bin/env python3
"""RVC 服务器 API 分层测试 · L1 单测/集成（不触碰 sha256 冻结基准）

覆盖（对应受影响路由）：
- 鉴权/CORS -> 全部 /api/*：白名单 Origin 放行、evil Origin 403、扩展 ID 精确匹配、无 Origin 时 Host 校验
- 路径校验 -> /api/file /api/stream /api/duration：safe_join 穿越、非视频扩展、越界 404
- 目录列表 -> /api/files /api/tree：缺失目录、仅视频文件、音频文件入列
- 时长探测 -> /api/duration：文件不存在
- 音频分流 -> /api/stream：音频扩展名原生直发（原始字节流 + 不触发 ffmpeg）、Range 206、鉴权不绕过、穿越/缺失 404、视频仍走转码
- 热键 -> POST /api/control-key：合法 action、bad json、unknown action
- 转码错误查询 -> /api/stream-error：未知 req、fake ffmpeg 失败后的结构化错误码
- 负向-转码失败 -> /api/stream /api/stop：fake ffmpeg（立即退出 / 二进制缺失）-> 200 空流 + 错误码可查 + 服务器存活
- 负向-SSE 中断 -> /api/control：MAX_SSE_CLIENTS 上限 503、断连后 control_clients 清理
- 负向-端口占用 -> 启动路径：is_port_in_use（socket 占位）

方式：随机端口起真实 ThreadedHTTPServer + StreamHandler，纯 stdlib，无 Playwright/真实 ffmpeg。
运行：python3 tests/test_server_api.py
"""
import http.client
import json
import os
import shutil
import socket
import stat
import sys
import tempfile
import threading
import time
import unittest
from http.server import HTTPServer
from socketserver import ThreadingMixIn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_DIR = os.path.join(ROOT, 'stream-server')
sys.path.insert(0, SERVER_DIR)

import server  # noqa: E402

# CRX 打包版扩展 ID（与 server.ALLOWED_ORIGINS 一致）
CRX_EXT_ID = 'chrome-extension://ojddpeamckomnllokngoghkdocijghhj'


class ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class TestServerApi(unittest.TestCase):
    """L1：鉴权 / 路径 / 列表 / SSE / 转码失败 / 端口占用"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='rvc-l1-')
        cls._orig_ffmpeg_cmd = server.ffmpeg_cmd
        cls._orig_hosts = server.ALLOWED_HOSTS

        # fake ffmpeg：模拟「进程启动成功但立即失败退出」（输出流为空）
        cls.fake_ffmpeg = os.path.join(cls.tmp, 'fake-ffmpeg')
        with open(cls.fake_ffmpeg, 'w') as f:
            f.write('#!/bin/sh\nexit 1\n')
        os.chmod(cls.fake_ffmpeg, stat.S_IRWXU)
        cls.fake_ffmpeg_missing = os.path.join(cls.tmp, 'no-such-binary-xyz')

        cls.httpd = ThreadedServer(('127.0.0.1', 0), server.StreamHandler)
        cls.port = cls.httpd.server_address[1]
        # 随机端口需加入 Host 白名单，否则无 Origin 请求被 403
        server.ALLOWED_HOSTS = server.ALLOWED_HOSTS | {
            f'127.0.0.1:{cls.port}', f'localhost:{cls.port}'}
        cls.th = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.th.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        server.ALLOWED_HOSTS = cls._orig_hosts
        server.ffmpeg_cmd = cls._orig_ffmpeg_cmd
        # 清理测试产生的转码日志（本套用例 req_id 前缀 l1fail-，生成 transcode-l1fail-*.log）
        log_dir = server.LOG_DIR
        if os.path.isdir(log_dir):
            for name in os.listdir(log_dir):
                if name.startswith('transcode-l1') and name.endswith('.log'):
                    try:
                        os.remove(os.path.join(log_dir, name))
                    except OSError:
                        pass
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ---------- 请求辅助 ----------
    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        hdrs = dict(headers or {})
        hdrs.setdefault('Host', f'127.0.0.1:{self.port}')
        if body is not None:
            hdrs.setdefault('Content-Type', 'application/json')
            body = body if isinstance(body, bytes) else json.dumps(body).encode()
        conn.request(method, path, body=body, headers=hdrs)
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp.status, data

    def get_json(self, path, headers=None):
        status, data = self.request('GET', path, headers=headers)
        return status, json.loads(data)

    def post_json(self, path, body):
        status, data = self.request('POST', path, body=body)
        return status, json.loads(data)

    # ---------- 鉴权 / CORS（受影响路由：全部 /api/*） ----------
    def test_origin_whitelist_allowed(self):
        status, _ = self.request('GET', '/api/files?dir=/tmp',
                                 headers={'Origin': 'https://aim-read.top'})
        self.assertEqual(status, 200)

    def test_origin_crx_ext_id_allowed(self):
        status, _ = self.request('GET', '/api/files?dir=/tmp',
                                 headers={'Origin': CRX_EXT_ID})
        self.assertEqual(status, 200)

    def test_origin_other_ext_id_forbidden(self):
        status, _ = self.request('GET', '/api/files?dir=/tmp',
                                 headers={'Origin': 'chrome-extension://abc123'})
        self.assertEqual(status, 403)

    def test_origin_evil_forbidden(self):
        status, _ = self.request('GET', '/api/files?dir=/tmp',
                                 headers={'Origin': 'https://evil.com'})
        self.assertEqual(status, 403)

    def test_host_ok_without_origin(self):
        status, _ = self.request('GET', '/api/files?dir=/tmp')
        self.assertEqual(status, 200)

    def test_host_evil_without_origin(self):
        status, _ = self.request('GET', '/api/files?dir=/tmp',
                                 headers={'Host': 'evil.com'})
        self.assertEqual(status, 403)

    def test_post_api_also_authed(self):
        status, _ = self.request('POST', '/api/control-key',
                                 body={'action': 'toggle_play'},
                                 headers={'Origin': 'https://evil.com'})
        self.assertEqual(status, 403)

    # ---------- 路径校验（受影响路由：/api/file /api/stream /api/duration） ----------
    def test_safe_join_rejects_traversal(self):
        base, full = server.StreamHandler.safe_join(None, '/tmp', '../../etc/passwd')
        self.assertIsNone(full)

    def test_safe_join_allows_inside(self):
        base, full = server.StreamHandler.safe_join(None, '/tmp', 'x.mp4')
        self.assertEqual(full, os.path.realpath('/tmp/x.mp4'))

    def test_file_traversal_404(self):
        status, _ = self.request('GET', '/api/file?dir=/&file=etc/passwd')
        self.assertEqual(status, 404)

    def test_file_non_video_ext_404(self):
        status, _ = self.request('GET', '/api/file?dir=/tmp&file=fake.mkv')
        self.assertEqual(status, 404)

    def test_file_missing_404(self):
        status, _ = self.request('GET', '/api/file?dir=/tmp&file=nope.mp4')
        self.assertEqual(status, 404)

    def test_file_range_206(self):
        p = os.path.join(self.tmp, 'range.mp4')
        with open(p, 'wb') as f:
            f.write(os.urandom(65536))
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        conn.request('GET', f'/api/file?dir={self.tmp}&file=range.mp4',
                     headers={'Host': f'127.0.0.1:{self.port}',
                              'Range': 'bytes=0-99'})
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        self.assertEqual(resp.status, 206)
        self.assertEqual(len(data), 100)
        self.assertEqual(resp.getheader('Content-Range'), f'bytes 0-99/65536')

    # ---------- 音频分流（受影响路由：/api/stream，音频原生直发不触发 ffmpeg） ----------
    def test_audio_stream_native_no_ffmpeg(self):
        # 音频扩展名走 /api/stream 原生直发：返回原始字节流 + 正确 Content-Type，
        # 且 ffmpeg_cmd 全程不被调用（证明不启动 ffmpeg）
        audio = os.path.join(self.tmp, 'audio.mp3')
        payload = b'ID3\x04\x00\x00\x00\x00\x00\x00' + os.urandom(4096)
        with open(audio, 'wb') as f:
            f.write(payload)
        calls = []

        def boom(name):
            calls.append(name)
            raise AssertionError('音频分流不应调用 ffmpeg')

        server.ffmpeg_cmd = boom
        try:
            conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
            conn.request('GET', f'/api/stream?dir={self.tmp}&file=audio.mp3',
                         headers={'Host': f'127.0.0.1:{self.port}'})
            resp = conn.getresponse()
            data = resp.read()
            conn.close()
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.getheader('Content-Type'), 'audio/mpeg')
            self.assertEqual(resp.getheader('Accept-Ranges'), 'bytes')
            self.assertEqual(data, payload)   # 原始字节流，非 MPEG-TS
        finally:
            server.ffmpeg_cmd = self._orig_ffmpeg_cmd
        self.assertEqual(calls, [])

    def test_audio_stream_multiple_exts(self):
        # 至少覆盖 mp3/m4a/aac/wav/flac/ogg 六种扩展名全部走原生直发
        for ext, ctype in [('.mp3', 'audio/mpeg'), ('.m4a', 'audio/mp4'),
                           ('.aac', 'audio/aac'), ('.wav', 'audio/wav'),
                           ('.flac', 'audio/flac'), ('.ogg', 'audio/ogg')]:
            p = os.path.join(self.tmp, 't' + ext)
            with open(p, 'wb') as f:
                f.write(b'x' * 128)
            status, data = self.request('GET', f'/api/stream?dir={self.tmp}&file=t{ext}')
            self.assertEqual(status, 200, f'{ext} 应返回 200')
            self.assertEqual(data, b'x' * 128, f'{ext} 应返回原始字节流')

    def test_audio_stream_range_206(self):
        audio = os.path.join(self.tmp, 'audio.flac')
        payload = os.urandom(65536)
        with open(audio, 'wb') as f:
            f.write(payload)
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        conn.request('GET', f'/api/stream?dir={self.tmp}&file=audio.flac',
                     headers={'Host': f'127.0.0.1:{self.port}',
                              'Range': 'bytes=100-199'})
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        self.assertEqual(resp.status, 206)
        self.assertEqual(len(data), 100)
        self.assertEqual(data, payload[100:200])
        self.assertEqual(resp.getheader('Content-Range'), f'bytes 100-199/65536')

    def test_audio_stream_auth_not_bypassed(self):
        # 音频分流同样过鉴权：evil Origin 一律 403，不允许绕过
        audio = os.path.join(self.tmp, 'audio.wav')
        with open(audio, 'wb') as f:
            f.write(b'RIFF' + os.urandom(256))
        status, _ = self.request('GET', f'/api/stream?dir={self.tmp}&file=audio.wav',
                                 headers={'Origin': 'https://evil.com'})
        self.assertEqual(status, 403)

    def test_audio_stream_traversal_404(self):
        status, _ = self.request('GET', '/api/stream?dir=/&file=etc/audio.mp3')
        self.assertEqual(status, 404)

    def test_audio_stream_missing_404(self):
        status, _ = self.request('GET', f'/api/stream?dir={self.tmp}&file=nope.mp3')
        self.assertEqual(status, 404)

    def test_video_stream_still_transcodes(self):
        # 视频扩展名走 /api/stream 仍走转码通道（fake ffmpeg 立即退出 -> 错误可查），
        # 证明音频分流没有改变视频路径
        v = os.path.join(self.tmp, 'video.mp4')
        with open(v, 'wb') as f:
            f.write(os.urandom(4096))
        req_id = 'l1vid-%d' % int(time.time() * 1000)
        server.ffmpeg_cmd = lambda name: self.fake_ffmpeg  # noqa: E731
        try:
            conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
            conn.request('GET', f'/api/stream?dir={self.tmp}&file=video.mp4&req={req_id}',
                         headers={'Host': f'127.0.0.1:{self.port}'})
            resp = conn.getresponse()
            data = resp.read()
            conn.close()
            self.assertIn(resp.status, (200, 500))
            if resp.status == 200:
                self.assertEqual(data, b'')
            self.assertEqual(resp.getheader('X-RVC-Request-Id'), req_id)
            # 错误结果落盘可查（与生产播放端重试逻辑一致）
            result = None
            for _ in range(5):
                status, payload = self.get_json(f'/api/stream-error?req={req_id}')
                if payload.get('ok'):
                    result = payload
                    break
                time.sleep(0.2)
            self.assertIsNotNone(result, 'stream-error 结果未就绪')
            self.assertEqual(result['code'], 'TRANSCODE_FAILED')
        finally:
            server.ffmpeg_cmd = self._orig_ffmpeg_cmd

    def test_files_lists_audio_too(self):
        # /api/files 现在同时列出音频文件（列表入口支持音频选择）
        with open(os.path.join(self.tmp, 'song.mp3'), 'wb') as f:
            f.write(b'ID3')
        status, data = self.get_json(f'/api/files?dir={self.tmp}')
        self.assertEqual(status, 200)
        names = [x['name'] for x in data['files']]
        self.assertIn('song.mp3', names)

    # ---------- 目录列表 / 树 / 时长 ----------
    def test_files_missing_dir(self):
        status, data = self.get_json('/api/files?dir=/no/such/dir/rvc')
        self.assertEqual(status, 200)
        self.assertIn('error', data)

    def test_files_lists_video_only(self):
        with open(os.path.join(self.tmp, 'a.mp4'), 'wb') as f:
            f.write(b'x')
        with open(os.path.join(self.tmp, 'b.txt'), 'w') as f:
            f.write('not video')
        status, data = self.get_json(f'/api/files?dir={self.tmp}')
        self.assertEqual(status, 200)
        names = [x['name'] for x in data['files']]
        self.assertIn('a.mp4', names)
        self.assertNotIn('b.txt', names)

    def test_tree_missing_dir(self):
        status, data = self.get_json('/api/tree?dir=/no/such/dir/rvc')
        self.assertEqual(status, 200)
        self.assertIn('error', data)

    def test_duration_missing_file(self):
        status, data = self.get_json('/api/duration?dir=/tmp&file=nope.mkv')
        self.assertEqual(status, 200)
        self.assertIn('error', data)

    # ---------- 热键（受影响路由：POST /api/control-key） ----------
    def test_control_key_valid(self):
        status, data = self.post_json('/api/control-key', {'action': 'toggle_play'})
        self.assertEqual(status, 200)
        self.assertTrue(data['ok'])

    def test_control_key_bad_json(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        conn.request('POST', '/api/control-key', body=b'{not json',
                     headers={'Host': f'127.0.0.1:{self.port}',
                              'Content-Type': 'application/json'})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        self.assertEqual(resp.status, 200)
        self.assertFalse(data['ok'])

    def test_control_key_unknown_action(self):
        status, data = self.post_json('/api/control-key', {'action': 'explode'})
        self.assertEqual(status, 200)
        self.assertFalse(data['ok'])

    # ---------- stop / 静态 / 404 ----------
    def test_stop_ok(self):
        status, data = self.get_json('/api/stop')
        self.assertEqual(status, 200)
        self.assertTrue(data['ok'])

    def test_root_html(self):
        status, data = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'<', data)

    def test_mpegts_static(self):
        status, _ = self.request('GET', '/mpegts.min.js')
        self.assertEqual(status, 200)

    def test_unknown_route_404(self):
        status, _ = self.request('GET', '/no/such/route')
        self.assertEqual(status, 404)

    # ---------- 转码错误查询（受影响路由：/api/stream-error） ----------
    def test_stream_error_unknown_req(self):
        status, data = self.get_json('/api/stream-error?req=no-such-req-xyz')
        self.assertEqual(status, 200)
        self.assertFalse(data['ok'])

    # ---------- 负向：转码失败（受影响路由：/api/stream /api/stream-error /api/stop） ----------
    def _transcode_fail(self, fake_bin, expect_code):
        bad = os.path.join(self.tmp, 'bad.mkv')
        with open(bad, 'wb') as f:
            f.write(os.urandom(4096))
        req_id = 'l1fail-%s' % int(time.time() * 1000)
        server.ffmpeg_cmd = lambda name: fake_bin  # noqa: E731
        try:
            conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
            conn.request('GET', f'/api/stream?dir={self.tmp}&file=bad.mkv&req={req_id}',
                         headers={'Host': f'127.0.0.1:{self.port}'})
            resp = conn.getresponse()
            data = resp.read()
            conn.close()
            # 契约：转码失败可诊断（错误码可经 /api/stream-error 查询），状态码兼容竞态：
            #  - 秒挂探测（250ms）内 poll 到退出 -> 500 JSON（send_transcode_error）
            #  - 未 poll 到 -> 200 空流（黑屏），流结束时 finally 写错误码
            self.assertIn(resp.status, (200, 500))
            if resp.status == 200:
                self.assertEqual(data, b'')
            self.assertEqual(resp.getheader('X-RVC-Request-Id'), req_id)
            # 错误结果落盘可查（播放端需重试几次，与生产行为一致）
            result = None
            for _ in range(5):
                status, payload = self.get_json(
                    f'/api/stream-error?req={req_id}')
                if payload.get('ok'):
                    result = payload
                    break
                time.sleep(0.2)
            self.assertIsNotNone(result, 'stream-error 结果未就绪')
            self.assertEqual(result['code'], expect_code)
            self.assertTrue(result['log'].endswith('.log'))
            # 转码日志文件落盘
            log_path = os.path.join(server.LOG_DIR, result['log'])
            self.assertTrue(os.path.isfile(log_path))
            # 服务器仍存活
            status, _ = self.request('GET', '/api/files?dir=/tmp')
            self.assertEqual(status, 200)
        finally:
            server.ffmpeg_cmd = self._orig_ffmpeg_cmd

    def test_transcode_failure_process_exits_immediately(self):
        self._transcode_fail(self.fake_ffmpeg, 'TRANSCODE_FAILED')

    def test_transcode_failure_binary_missing(self):
        self._transcode_fail(self.fake_ffmpeg_missing, 'FFMPEG_NOT_FOUND')

    # ---------- 负向：SSE 中断（受影响路由：/api/control /api/control-key） ----------
    def test_sse_max_clients_and_cleanup(self):
        conns = []
        ready = threading.Event()
        lock = threading.Lock()
        results = []

        def open_one():
            c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=15)
            try:
                c.request('GET', '/api/control',
                          headers={'Host': f'127.0.0.1:{self.port}'})
                r = c.getresponse()
                with lock:
                    results.append(r.status)
                    conns.append(c)
            except Exception as e:
                with lock:
                    results.append(('err', str(e)))
            finally:
                ready.set()

        threads = []
        for _ in range(server.MAX_SSE_CLIENTS):
            ready.clear()
            t = threading.Thread(target=open_one, daemon=True)
            t.start()
            threads.append(t)
            # 每个连接都注册完成后再开下一个
            if not ready.wait(10):
                self.fail('SSE 连接注册超时')

        self.assertEqual(results, [200] * server.MAX_SSE_CLIENTS)

        # 第 11 个连接 -> 503（连接数上限）
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=15)
        conn.request('GET', '/api/control',
                     headers={'Host': f'127.0.0.1:{self.port}'})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 503)

        # 全部断开 -> 广播事件触发各服务端线程写循环（首次写入缓冲、二次写触发 EPIPE）-> control_clients 清空
        for c in conns:
            c.close()
        for _ in range(4):
            self.post_json('/api/control-key', {'action': 'toggle_play'})
            time.sleep(0.2)
        deadline = time.time() + 5
        while time.time() < deadline:
            if len(server.control_clients) == 0:
                break
            time.sleep(0.2)
        self.assertEqual(len(server.control_clients), 0)

    # ---------- 负向：端口占用（受影响路由：服务器启动路径） ----------
    def test_is_port_in_use(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        port = s.getsockname()[1]
        try:
            self.assertTrue(server.is_port_in_use(port))
        finally:
            s.close()
        time.sleep(0.2)
        self.assertFalse(server.is_port_in_use(port))


if __name__ == '__main__':
    unittest.main(verbosity=2)
