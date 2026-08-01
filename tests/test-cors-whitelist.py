#!/usr/bin/env python3
"""CORS 白名单断言（server.py 四处响应路径：JSON / 文件 / SSE / 转码流）
用法: /opt/homebrew/bin/python3 tests/test-cors-whitelist.py
前提: stream-server 运行中 (127.0.0.1:8765)
退出码: 0 = 全过, 1 = 有失败
"""
import http.client
import pathlib
import sys
import urllib.parse

HOST = '127.0.0.1'
PORT = 8765
ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE_DIR = str(ROOT / 'tests' / 'fixtures')
FIXTURE_Q = urllib.parse.quote(FIXTURE_DIR, safe='')

# 与 server.py ALLOWED_ORIGINS 保持一致的本地来源白名单
ALLOWED = {
    'https://aim-read.top',
    'http://aim-read.top',
    'http://127.0.0.1:8899',
    'chrome-extension://ojddpeamckomnllokngoghkdocijghhj',
}
EVIL = 'http://evil.example'

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print(('PASS' if ok else 'FAIL'), name, ('- ' + str(detail) if detail else ''), flush=True)


def headers_of(path, origin=None, stream=False):
    """发起 GET，返回 (status, headers_dict)。stream=True 时只读响应头即断开
    （SSE/转码流为无限响应，不能读 body）。"""
    conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
    hdrs = {}
    if origin is not None:
        hdrs['Origin'] = origin
    try:
        conn.request('GET', path, headers=hdrs)
        resp = conn.getresponse()
        if not stream:
            # 有限响应读掉 body（释放连接）
            try:
                resp.read()
            except http.client.IncompleteRead:
                pass
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}
    finally:
        conn.close()


def main():
    try:
        status, _ = headers_of('/api/files?dir=~')
        if status not in (200, 403):
            print('FATAL: stream-server 未运行或响应异常，请先执行 stream-server/start.sh')
            return 1
    except Exception:
        print('FATAL: stream-server 未运行，请先执行 stream-server/start.sh')
        return 1

    # ========== 1. 白名单内 Origin：回显跨域头（含播放器页面来源） ==========
    for origin in sorted(ALLOWED):
        st, h = headers_of('/api/files?dir=~', origin)
        check(f'白名单内 {origin}', st == 200 and h.get('access-control-allow-origin') == origin,
              f'status={st} ACAO={h.get("access-control-allow-origin")!r}')

    # ========== 2. 白名单外 Origin：拒绝且不返回跨域头（核心断言） ==========
    st, h = headers_of('/api/files?dir=~', EVIL)
    check('白名单外 /api/files -> 403 且无 ACAO',
          st == 403 and 'access-control-allow-origin' not in h,
          f'status={st} ACAO={h.get("access-control-allow-origin")!r}')

    # ========== 3. 无 Origin（本地进程/热键子进程）：放行但无跨域头 ==========
    st, h = headers_of('/api/files?dir=~')
    check('无 Origin 放行且无 ACAO', st == 200 and 'access-control-allow-origin' not in h,
          f'status={st} ACAO={h.get("access-control-allow-origin")!r}')

    # ========== 4. 四处响应路径 × 白名单内：全部回显跨域头 ==========
    paths = {
        'JSON(/api/files)': f'/api/files?dir={FIXTURE_Q}',
        '文件(/api/file)': f'/api/file?dir={FIXTURE_Q}&file=sample.mp4',
        'SSE(/api/control)': '/api/control',
        '转码流(/api/stream)': f'/api/stream?dir={FIXTURE_Q}&file=sample.mp4&start=0',
    }
    for name, path in paths.items():
        st, h = headers_of(path, 'https://aim-read.top',
                           stream=name.startswith(('SSE', '转码流')))
        check(f'白名单内 {name} -> 200 + ACAO',
              st == 200 and h.get('access-control-allow-origin') == 'https://aim-read.top',
              f'status={st} ACAO={h.get("access-control-allow-origin")!r}')

    # ========== 5. 四处响应路径 × 白名单外：全部拒绝且无跨域头 ==========
    for name, path in paths.items():
        st, h = headers_of(path, EVIL,
                           stream=name.startswith(('SSE', '转码流')))
        check(f'白名单外 {name} -> 403 且无 ACAO',
              st == 403 and 'access-control-allow-origin' not in h,
              f'status={st} ACAO={h.get("access-control-allow-origin")!r}')

    failed = [n for n, ok in results if not ok]
    print(f'\n===== {len(results) - len(failed)}/{len(results)} 通过 =====')
    if failed:
        print('未过:', ', '.join(failed))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
