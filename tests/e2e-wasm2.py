#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RVC 上架版全链路端到端测试（CSP 修复后）
真实用户路径：加载扩展 -> 打开网页 -> 塞 MKV 进隐藏 file input
-> content 转码通道 -> background 桥 -> offscreen ffmpeg.wasm -> MP4 blob 播放
"""
import asyncio
import http.server
import pathlib
import shutil
import socketserver
import sys
import threading
import time

ROOT = pathlib.Path("/Users/Zhuanz/ai-brain/浏览器播放器系统")
EXT = str(ROOT / "reader-video-companion-wasm")
MKV = "/tmp/rvc-test-720p.mkv"
PROFILE = "/tmp/rvc-pw-profile-wasm4"

HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>RVC e2e</title></head>
<body><article style="height:1200px;padding:20px">
<h1>端到端测试页</h1><p>用于 RVC 上架版全链路验证</p>
</article></body></html>"""

class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/test-720p.mkv":
            data = pathlib.Path(MKV).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "video/x-matroska")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        b = HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def log_message(self, *a):
        pass


async def main():
    shutil.rmtree(PROFILE, ignore_errors=True)

    httpd = socketserver.TCPServer(("127.0.0.1", 0), H)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(f"[e2e] 本地服务器 :{port}")

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE, channel="chromium", headless=False,
            args=[f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"])
        page = await ctx.new_page()

        console_msgs = []
        page.on("console", lambda m: console_msgs.append(f"[{m.type}] {m.text[:200]}"))

        # 1. 打开测试页，等 content script 注入
        await page.goto(f"http://127.0.0.1:{port}/")
        for _ in range(30):
            if await page.locator(".rvc-btn-folder").count() > 0:
                break
            await asyncio.sleep(0.3)
        if await page.locator(".rvc-btn-folder").count() == 0:
            print("FAIL: content script 未注入（播放器不存在）")
            sys.exit(1)
        print("[e2e] 播放器已注入")

        # 2. 真实用户路径：文件选择浮层 -> 塞 MKV
        # （播放器默认 display:none，等用户点扩展图标才显示；测试里直接触发浮层显示）
        await page.evaluate("document.querySelector('.rvc-folder-overlay').style.display = 'flex'")
        await page.wait_for_selector(".rvc-folder-panel", state="visible", timeout=3000)
        print("[e2e] 文件选择浮层已打开")

        t0 = time.time()
        await page.set_input_files(".rvc-file-input", MKV)
        print("[e2e] MKV 已提交，等待转码...")

        # 3. 等待结果：视频加载成功 或 转码错误
        result = {"state": "unknown"}
        for _ in range(240):
            if await page.locator(".rvc-transcode-error").count() > 0:
                err = await page.locator(".rvc-transcode-error").inner_text()
                result = {"state": "error", "msg": err[:300]}
                break
            v = await page.evaluate("""() => {
                const el = document.querySelector('.rvc-video');
                return el && el.src ? {src: el.src.slice(0, 40), dur: el.duration || 0, ready: el.readyState} : null;
            }""")
            if v and v["src"].startswith("blob:"):
                result = {"state": "playing", **v}
                break
            await asyncio.sleep(0.5)
        elapsed = time.time() - t0

        # 4. 验证视频真的能播：等 readyState >= 2 或 duration > 0
        if result["state"] == "playing":
            for _ in range(40):
                v = await page.evaluate("""() => {
                    const el = document.querySelector('.rvc-video');
                    return {dur: el.duration || 0, ready: el.readyState};
                }""")
                if v["dur"] > 5 and v["ready"] >= 2:
                    result["playable"] = True
                    break
                await asyncio.sleep(0.5)
            result["playable"] = result.get("playable", False)
            print(f"[e2e] ✅ 转码成功 {elapsed:.1f}s: duration={result['dur']:.1f}s readyState={result['ready']} playable={result['playable']}")
        else:
            print(f"[e2e] ❌ 失败 {elapsed:.1f}s: {result}")

        # 5. 收集关键 console 日志
        print("--- console 日志（筛选） ---")
        for line in console_msgs:
            if "RVC" in line or "ffmpeg" in line.lower() or "error" in line.lower():
                print(line)

        await ctx.close()

    httpd.shutdown()
    if result.get("state") == "playing":
        print("E2E_RESULT: PASS")
    else:
        print("E2E_RESULT: FAIL")
        sys.exit(1)


asyncio.run(main())
