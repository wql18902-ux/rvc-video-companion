#!/usr/bin/env python3
"""RVC 扩展验收脚本（Playwright 端到端，判卷标准，冻结）
用法: /opt/homebrew/bin/python3 tests/acceptance.py
前提: stream-server 运行中 (127.0.0.1:8765)
退出码: 0 = 全过, 1 = 有失败
"""
import asyncio
import pathlib
import re
import subprocess
import sys
import time

from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXT = str(ROOT / 'reader-video-companion')
FIXTURE_DIR = str(ROOT / 'tests' / 'fixtures')
HTTP_PORT = 8899
PROFILE = '/tmp/rvc-pw-profile-accept'
PY = sys.executable

EMOJI_RE = re.compile(
    '[\U0001F000-\U0001FAFF\u2190-\u21FF\u2300-\u23FF\u25A0-\u25FF'
    '\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u20E3]')

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print(('PASS' if ok else 'FAIL'), name, ('- ' + str(detail) if detail else ''), flush=True)


def ensure_http():
    import urllib.request
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{HTTP_PORT}/test.html', timeout=2)
        return None
    except Exception:
        srv = subprocess.Popen(
            [PY, '-m', 'http.server', str(HTTP_PORT), '--bind', '127.0.0.1'],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(30):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{HTTP_PORT}/test.html', timeout=2)
                return srv
            except Exception:
                time.sleep(0.3)
        raise RuntimeError('8899 静态服务起不来')
    return None


def rect_of(page, sel):
    return page.eval_on_selector(
        sel, 'el => { const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; }')


async def main():
    import urllib.request
    try:
        urllib.request.urlopen('http://127.0.0.1:8765/api/files?dir=~', timeout=3)
    except Exception:
        print('FATAL: stream-server 未运行，请先执行 stream-server/start.sh')
        return 1

    srv = ensure_http()
    try:
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                PROFILE, headless=True, channel='chromium',
                args=[f'--disable-extensions-except={EXT}', f'--load-extension={EXT}',
                      '--autoplay-policy=no-user-gesture-required', '--mute-audio'])
            page = await ctx.new_page()

            async def show_player():
                await page.evaluate(
                    "document.getElementById('rvc-player').style.display='flex'")
                await page.wait_for_timeout(200)

            await page.goto(f'http://127.0.0.1:{HTTP_PORT}/test.html', wait_until='load')
            await page.wait_for_timeout(1500)

            # A. 注入：播放器存在且默认隐藏
            injected = await page.evaluate("!!document.getElementById('rvc-player')")
            check('A.注入', injected)
            if not injected:
                await ctx.close()
                return 1
            await show_player()

            # B. 空载紧凑：未加载视频时播放器高度 <= 80px
            h0 = (await rect_of(page, '#rvc-player'))['h']
            check('B.空载紧凑(<=80px)', h0 <= 80, f'实际 {h0:.0f}px')

            # C. 加载播放：标题栏文件夹按钮开弹层，选 fixtures 目录里的 sample.mp4
            await page.click('.rvc-btn-folder')
            await page.wait_for_selector('.rvc-folder-overlay', state='visible')
            await page.fill('.rvc-dir-input', FIXTURE_DIR)
            await page.click('.rvc-dir-btn')
            await page.wait_for_selector('.rvc-folder-item', timeout=8000)
            await page.click('.rvc-folder-item')
            playing = False
            for _ in range(40):
                playing = await page.evaluate(
                    "(() => { const v = document.querySelector('video.rvc-video');"
                    " return v && !v.paused && v.currentTime > 0.2; })()")
                if playing:
                    break
                await page.wait_for_timeout(250)
            check('C.加载播放', playing)

            # D. 键盘 A/D/S
            t1 = await page.evaluate("document.querySelector('video.rvc-video').currentTime")
            await page.keyboard.press('d')
            await page.wait_for_timeout(300)
            t2 = await page.evaluate("document.querySelector('video.rvc-video').currentTime")
            check('D1.D前进1秒', 0.4 < (t2 - t1) < 1.9, f'{t1:.2f}->{t2:.2f}')
            await page.keyboard.press('a')
            await page.wait_for_timeout(300)
            t3 = await page.evaluate("document.querySelector('video.rvc-video').currentTime")
            check('D2.A后退1秒', -1.9 < (t3 - t2) < -0.4, f'{t2:.2f}->{t3:.2f}')
            await page.keyboard.press('s')
            await page.wait_for_timeout(300)
            check('D3.S暂停', await page.evaluate("document.querySelector('video.rvc-video').paused"))
            await page.keyboard.press('s')
            await page.wait_for_timeout(300)

            # E. 倍速：按钮弹面板 -> 选档位 -> 滑杆 -> 刷新记忆
            e_detail = ''
            try:
                await page.click('.rvc-btn-speed', timeout=3000)
                await page.wait_for_selector('.rvc-speed-panel', state='visible', timeout=3000)
                await page.click('.rvc-speed-option[data-rate="1.5"]', timeout=3000)
                await page.wait_for_timeout(200)
                r1 = await page.evaluate("document.querySelector('video.rvc-video').playbackRate")
                btn_txt = await page.text_content('.rvc-btn-speed')
                ok1 = abs(r1 - 1.5) < 0.01 and '1.5' in (btn_txt or '')
                await page.evaluate(
                    "(() => { const s = document.querySelector('.rvc-speed-slider');"
                    " s.value = 0.5; s.dispatchEvent(new Event('input', { bubbles: true })); })()")
                await page.wait_for_timeout(200)
                r2 = await page.evaluate("document.querySelector('video.rvc-video').playbackRate")
                ok2 = abs(r2 - 0.5) < 0.06
                await page.reload(wait_until='load')
                await page.wait_for_timeout(1500)
                await show_player()
                btn_txt2 = await page.text_content('.rvc-btn-speed')
                ok3 = '0.5' in (btn_txt2 or '')
                check('E.倍速(档位+滑杆+记忆)', ok1 and ok2 and ok3,
                      f'档位{r1} {ok1} / 滑杆{r2:.2f} {ok2} / 记忆「{btn_txt2}」{ok3}')
            except Exception as ex:
                check('E.倍速(档位+滑杆+记忆)', False, f'{type(ex).__name__}: {str(ex)[:120]}')

            # F. 固定目录：固定当前目录 -> chip 出现 -> 刷新仍在 -> 点击切换
            try:
                await page.click('.rvc-btn-folder')
                await page.wait_for_selector('.rvc-folder-overlay', state='visible')
                await page.click('.rvc-pin-btn', timeout=3000)
                await page.wait_for_selector('.rvc-pinned-chip', timeout=3000)
                ok1 = True
                await page.click('.rvc-folder-close')
                await page.reload(wait_until='load')
                await page.wait_for_timeout(1500)
                await show_player()
                await page.click('.rvc-btn-folder')
                await page.wait_for_selector('.rvc-folder-overlay', state='visible')
                chips = await page.query_selector_all('.rvc-pinned-chip')
                ok2 = len(chips) >= 1
                await chips[0].click()
                await page.wait_for_timeout(1200)
                dir_val = await page.input_value('.rvc-dir-input')
                ok3 = 'fixtures' in dir_val
                check('F.固定目录(pin+记忆+切换)', ok1 and ok2 and ok3,
                      f'pin {ok1} / 记忆 {len(chips)}个 / 切换后目录 {dir_val}')
                await page.click('.rvc-folder-close')
            except Exception as ex:
                check('F.固定目录(pin+记忆+切换)', False, f'{type(ex).__name__}: {str(ex)[:120]}')

            # G. 拖拽
            b1 = await rect_of(page, '#rvc-player')
            hb = await rect_of(page, '.rvc-header')
            await page.mouse.move(hb['x'] + hb['w'] / 2, hb['y'] + hb['h'] / 2)
            await page.mouse.down()
            await page.mouse.move(hb['x'] + hb['w'] / 2 + 120, hb['y'] + hb['h'] / 2 + 90, steps=6)
            await page.mouse.up()
            await page.wait_for_timeout(300)
            b2 = await rect_of(page, '#rvc-player')
            moved1 = abs(b2['x'] - b1['x']) + abs(b2['y'] - b1['y'])
            check('G1.有框标题栏拖拽(>=50px)', moved1 >= 50, f'位移 {moved1:.0f}px')

            await page.click('.rvc-btn-frameless')
            await page.wait_for_timeout(400)
            vb = await rect_of(page, 'video.rvc-video')
            cx, cy = vb['x'] + vb['w'] / 2, vb['y'] + vb['h'] / 2
            await page.mouse.move(cx, cy)
            await page.mouse.down()
            await page.mouse.move(cx + 100, cy + 80, steps=6)
            await page.mouse.up()
            await page.wait_for_timeout(300)
            b3 = await rect_of(page, '#rvc-player')
            moved2 = abs(b3['x'] - b2['x']) + abs(b3['y'] - b2['y'])
            check('G2.无框视频本体拖拽(>=50px)', moved2 >= 50, f'位移 {moved2:.0f}px')

            paused_before = await page.evaluate("document.querySelector('video.rvc-video').paused")
            vb2 = await rect_of(page, 'video.rvc-video')
            await page.mouse.click(vb2['x'] + vb2['w'] / 2, vb2['y'] + vb2['h'] / 2)
            await page.wait_for_timeout(300)
            paused_after = await page.evaluate("document.querySelector('video.rvc-video').paused")
            check('G3.无框单击仍切播放', paused_before != paused_after,
                  f'{paused_before} -> {paused_after}')

            # H. Emoji 扫描：content.js + player.css 全文件（含注释）无 emoji
            hits = []
            for f in ['reader-video-companion/content.js', 'reader-video-companion/player.css']:
                text = (ROOT / f).read_text(encoding='utf-8')
                found = EMOJI_RE.findall(text)
                if found:
                    hits.append(f'{f}: {len(found)} 个 {found[:8]}')
            check('H.无emoji(含字形符号)', not hits, '; '.join(hits) if hits else '')

            await ctx.close()
    finally:
        if srv:
            srv.terminate()

    failed = [n for n, ok in results if not ok]
    print(f'\n===== {len(results) - len(failed)}/{len(results)} 通过 =====')
    if failed:
        print('未过:', ', '.join(failed))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
