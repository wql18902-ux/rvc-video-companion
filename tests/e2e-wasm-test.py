#!/usr/bin/env python3
# RVC 上架版（ffmpeg.wasm）端到端验收脚本
# 用 Playwright 加载未打包扩展，验证：
#   1. 播放器注入（任意 http 页面）
#   2. 原生 MP4 本地文件播放
#   3. MKV 720p 经 offscreen ffmpeg.wasm 转码后播放（B1 PoC）
#   4. 无框模式进度条 + 毛玻璃截图（商店素材）
# 用法：python3 tests/e2e-wasm-test.py
import asyncio
import http.server
import json
import os
import pathlib
import socketserver
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXT_PATH = str(ROOT / "reader-video-companion-wasm")
TEST_MKV = "/tmp/rvc-test-720p.mkv"
TEST_MP4 = "/Users/Zhuanz/Downloads/狸花猫办公室摸鱼视频.mp4"
SCREENSHOT = "/tmp/rvc-wasm-screenshot.png"

TEST_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>RVC E2E</title>
<style>body{font-family:sans-serif;max-width:900px;margin:0 auto;padding:20px;}
article{height:900px;background:#f5f5f5;padding:16px;}</style></head>
<body><article><h1>E2E 测试页</h1><p>这是一段用于测试嵌入播放器的文章内容。</p>
<p>重复文本用于撑高页面。</p></article></body></html>"""

PORT = 8899


def serve_test_page():
    handler = http.server.SimpleHTTPRequestHandler

    class H(handler):
        def do_GET(self):
            body = TEST_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), H) as httpd:
        httpd.serve_forever()


async def main():
    from playwright.async_api import async_playwright

    results = []
    def check(name, ok, detail=""):
        results.append((name, ok, detail))
        print(f"  {'✅' if ok else '❌'} {name} {detail}")

    srv = threading.Thread(target=serve_test_page, daemon=True)
    srv.start()
    time.sleep(0.5)

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir="/tmp/rvc-pw-profile-wasm",
            channel="chromium",
            headless=False,
            args=[
                f"--disable-extensions-except={EXT_PATH}",
                f"--load-extension={EXT_PATH}",
            ],
        )
        try:
            page = await ctx.new_page()
            await page.goto(f"http://127.0.0.1:{PORT}/", wait_until="domcontentloaded")
            await page.wait_for_selector("#rvc-player", state="attached", timeout=8000)
            check("播放器注入", True, "(任意 http 页面 #rvc-player 出现)")

            # 显示播放器（内容脚本注入后默认隐藏，点 load-btn 前先显示）
            await page.evaluate("document.getElementById('rvc-player').style.display='flex'")
            await page.wait_for_selector(".rvc-btn-folder", timeout=3000)

            # ---- 1. 原生 MP4 ----
            await page.click(".rvc-btn-folder")
            await page.wait_for_selector(".rvc-folder-overlay[style*='flex'], .rvc-folder-overlay:visible", timeout=3000)
            await page.set_input_files(".rvc-file-input", TEST_MP4)
            await page.wait_for_function(
                "() => { const v=document.querySelector('.rvc-video'); return v && v.duration > 5 && !document.querySelector('.rvc-loading') }",
                timeout=15000)
            dur = await page.evaluate("document.querySelector('.rvc-video').duration")
            check("原生 MP4 播放", dur > 5, f"(duration={dur:.1f}s)")

            # ---- 2. MKV 转码（B1 PoC 核心）----
            t0 = time.time()
            await page.click(".rvc-btn-folder")
            await page.wait_for_selector(".rvc-folder-overlay:visible", timeout=3000)
            await page.set_input_files(".rvc-file-input", TEST_MKV)
            # 转码中应出现 loading
            try:
                await page.wait_for_selector(".rvc-loading:visible", timeout=5000)
                check("转码 loading 出现", True)
            except Exception:
                check("转码 loading 出现", False, "(转码太快或未出现)")
            # 等转码完成并播放（最长 120s）
            await page.wait_for_function(
                "() => { const v=document.querySelector('.rvc-video'); return v && v.duration > 5 && v.currentSrc.startsWith('blob:') && !document.querySelector('.rvc-loading') }",
                timeout=120000)
            tdur = await page.evaluate("document.querySelector('.rvc-video').duration")
            elapsed = time.time() - t0
            check("MKV 720p 转码播放", tdur > 5, f"(duration={tdur:.1f}s, 转码+加载 {elapsed:.1f}s)")

            # 点击播放提示（S1 行为：加载但暂停）
            await page.wait_for_selector(".rvc-play-hint", state="attached", timeout=5000)
            await page.click(".rvc-play-hint")
            await page.wait_for_function("() => !document.querySelector('.rvc-video').paused", timeout=5000)
            check("点击播放提示可播", True)

            # ---- 3. 无框模式进度条 ----
            await page.click(".rvc-btn-frameless")
            await page.wait_for_selector(".rvc-frameless", timeout=3000)
            fb = await page.evaluate("document.querySelector('.rvc-fb-progress') !== null && document.querySelector('.rvc-fb-time') !== null")
            check("无框进度条 DOM", fb)

            # ---- 4. 毛玻璃截图（商店素材候选） ----
            await page.evaluate("document.getElementById('rvc-player').style.display='none'")
            await page.evaluate("document.getElementById('rvc-player').style.display='flex'")
            await page.set_viewport_size({"width": 1280, "height": 800})
            await page.screenshot(path=SCREENSHOT)
            check("截图已存", os.path.exists(SCREENSHOT), SCREENSHOT)
        finally:
            await ctx.close()

    failed = [r for r in results if not r[1]]
    print()
    print("=" * 50)
    if failed:
        print(f"❌ 失败 {len(failed)}/{len(results)}: {[f[0] for f in failed]}")
        sys.exit(1)
    print(f"✅ 全部通过 {len(results)}/{len(results)}")
    print(f"截图: {SCREENSHOT}")


if __name__ == "__main__":
    asyncio.run(main())
