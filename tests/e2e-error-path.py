#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RVC 转码失败路径端到端用例（注入错误路径）
制造 ffmpeg 必然失败的坏 MKV（非媒体内容）注入播放流程，验证：
  1. 服务器把 ffmpeg stderr 落盘：logs/transcode-<req>.log（按时间戳+请求关联命名）
  2. 播放端错误回调透传结构化错误码 + 用户可读提示（.rvc-transcode-error 横幅）
  3. /api/stream-error 查询接口返回 {ok, code, message, log}
“日志与提示同时产生”即用例最终判定。
用法: python3 tests/e2e-error-path.py
前提: stream-server 运行中 (127.0.0.1:8765)
退出码: 0 = 全部通过, 1 = 有失败
"""
import asyncio
import http.server
import json
import pathlib
import re
import socketserver
import sys
import threading
import urllib.request

from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXT = str(ROOT / 'reader-video-companion')
LOG_DIR = ROOT / 'stream-server' / 'logs'
SERVER = 'http://127.0.0.1:8765'
BAD_MKV = '/tmp/rvc-broken-input.mkv'
PROFILE = '/tmp/rvc-pw-profile-error'
PORT = 8899   # manifest content_scripts 唯一匹配的本地端口，不能换

HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>RVC error-path e2e</title></head>
<body><article style="height:1200px;padding:20px"><h1>错误路径测试页</h1>
<p>验证转码失败时：日志落盘 + 播放端结构化错误提示</p></article></body></html>"""

# console 输出格式见 content.js showTranscodeError：
# [RVC] transcode failed: <code> - <message> (log: <log名>) (req: <req_id>)
CONSOLE_RE = re.compile(
    r'\[RVC\] transcode failed: (\S+) - (.+?)(?: \(log: ([^)]+)\))? \(req: ([^)]+)\)')

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print(('PASS' if ok else 'FAIL'), name, ('- ' + str(detail) if detail else ''), flush=True)


class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        b = HTML.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass


async def main():
    # 前置：stream-server 必须运行
    try:
        urllib.request.urlopen(SERVER + '/api/files?dir=~', timeout=3)
    except Exception:
        print('FATAL: stream-server 未运行，请先执行 stream-server/start.sh')
        return 1

    # 注入错误路径：写一个 ffmpeg 必然失败的坏 MKV（纯文本非媒体内容）
    pathlib.Path(BAD_MKV).write_bytes(b'definitely not a video file - ' * 400)
    before = set(LOG_DIR.glob('transcode-*.log')) if LOG_DIR.is_dir() else set()

    # 8899 已被其他进程占用（如历史测试残留）时直接复用，内容不影响注入
    httpd = None
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/', timeout=2)
    except Exception:
        httpd = socketserver.TCPServer(('127.0.0.1', PORT), H)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()

    console_lines = []
    banner_text = None
    banner_req = None
    try:
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=PROFILE, channel='chromium', headless=True,
                args=[f'--disable-extensions-except={EXT}', f'--load-extension={EXT}', '--mute-audio'])
            page = await ctx.new_page()
            page.on('console', lambda m: console_lines.append(f'[{m.type}] {m.text}'))

            await page.goto(f'http://127.0.0.1:{PORT}/', wait_until='load')
            await page.wait_for_timeout(1500)

            injected = await page.evaluate("!!document.getElementById('rvc-player')")
            check('1.播放器注入', injected)
            if not injected:
                return 1
            await page.evaluate("document.getElementById('rvc-player').style.display='flex'")
            await page.wait_for_timeout(300)

            # 打开目录浮层 -> 切到 /tmp -> 点坏文件触发转码失败
            await page.click('.rvc-btn-folder')
            await page.wait_for_selector('.rvc-folder-overlay', state='visible', timeout=5000)
            await page.fill('.rvc-dir-input', '/tmp')
            await page.click('.rvc-dir-btn')
            await page.wait_for_selector('.rvc-folder-item', timeout=15000)
            await page.locator('.rvc-folder-item', has_text='rvc-broken-input.mkv').first.click()

            # 等待错误横幅出现（转码失败 -> mpegts ERROR -> 查询服务器 -> 展示）
            await page.wait_for_selector('.rvc-transcode-error', state='visible', timeout=30000)
            banner_text = await page.locator('.rvc-transcode-error').inner_text()
            banner_req = await page.locator('.rvc-transcode-error').get_attribute('data-req')
            await page.wait_for_timeout(500)   # 等 console 消息全部派发到 Python 侧
            await ctx.close()
    finally:
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()   # 释放监听端口，否则残留进程会占用 8899
        pathlib.Path(BAD_MKV).unlink(missing_ok=True)

    check('2.错误横幅出现', bool(banner_text), f'text={banner_text[:80]!r}')

    # 从 console 提取结构化错误码 / 用户可读提示 / 日志文件名 / 请求 ID
    m = None
    for line in console_lines:
        m = CONSOLE_RE.search(line)
        if m:
            break
    if not m:
        check('3.console 透传错误码与日志名', False, 'console tail: ' + str(console_lines[-5:]))
        return 1
    code, message, log_name, req_id = m.group(1), m.group(2), m.group(3), m.group(4)
    check('3.console 透传错误码与日志名', True, f'{code} / req={req_id}')

    # 横幅同时含结构化错误码与用户可读提示
    check('4.横幅含结构化错误码', bool(banner_text) and code in banner_text,
          f'banner={banner_text[:80]!r} code={code!r}')
    check('5.横幅含用户可读提示', bool(banner_text) and message in banner_text,
          f'message={message!r}')

    # 日志落盘：logs/ 下新增 transcode-*.log 且非空，内容为 ffmpeg stderr
    log_path = LOG_DIR / (log_name or '')
    new_logs = set(LOG_DIR.glob('transcode-*.log')) - before
    exists = log_path.is_file()
    size = log_path.stat().st_size if exists else 0
    content = log_path.read_text(errors='replace') if exists else ''
    has_err = ('Invalid data' in content or 'invalid' in content.lower() or 'rror' in content)
    check('6.日志落盘（新增文件）', log_path in new_logs, f'{log_name} size={size}')
    check('7.日志内容为 ffmpeg stderr', exists and size > 0 and has_err,
          f'head={content[:120]!r}')

    # 查询接口返回结构化结果，与横幅/日志一致
    try:
        with urllib.request.urlopen(f'{SERVER}/api/stream-error?req={req_id}', timeout=5) as r:
            data = json.loads(r.read().decode())
        ok = (data.get('ok') and data.get('code') == code
              and data.get('message') == message and data.get('log') == log_name)
        check('8./api/stream-error 结构化透传', ok, json.dumps(data, ensure_ascii=False))
    except Exception as e:
        check('8./api/stream-error 结构化透传', False, str(e))

    n_pass = sum(1 for _, ok in results if ok)
    print(f'\n共 {len(results)} 项: {n_pass} 过 / {len(results) - n_pass} 挂', flush=True)
    return 0 if n_pass == len(results) else 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
