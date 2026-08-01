# CLAUDE.md — 浏览器播放器系统

Chrome 扩展（MV3）+ 本地 ffmpeg 服务器，在 aim-read.top 阅读站嵌入视频播放器，支持 MKV/MOV 实时转码。纯 Vanilla JS，无构建工具链。

## 怎么跑

```bash
# 启服务器（端口 8765）
bash stream-server/start.sh
# 或双击 packaging/dist/RVC视频伴侣.app

# 加载扩展：chrome://extensions → 开发者模式 → 加载已解压 → reader-video-companion/
# 使用：访问 aim-read.top，点扩展图标唤出浮窗播放器

# 跑验收（必须先清 profile，否则 G2 残留致 C 超时）
rm -rf /tmp/rvc-pw-profile-accept
env -u PYTHONHOME -u PYTHONPATH /opt/homebrew/bin/python3 tests/acceptance.py
```

TRAE 会注入 PYTHONHOME/PYTHONPATH 导致 python 报 "No module named 'encodings'"，跑 python 一律加 `env -u PYTHONHOME -u PYTHONPATH`。

## 技术栈

Chrome MV3 扩展（Vanilla JS）/ Python 3 aiohttp 服务器 / ffmpeg+ffprobe / mpegts.js / PyInstaller 打包 .app

## 目录与约定

- `reader-video-companion/` — 唯一维护的扩展（content.js/player.css/background.js/manifest.json）
- `stream-server/` — 本地服务器（server.py/start.sh）
- `tests/` — 验收脚本 acceptance.py + fixtures/；**根目录 `test.html`** — 验收测试页；三者 **sha256 冻结，不许改**（注意 test.html 在根目录，不在 tests/ 内）
- `packaging/` — 打包脚本（make-distro.sh / build-crx.sh）
- `PROGRESS.md` 现役状态真相源；`BLOCKED.md` 待决项；`iterations/history.md` 版本记录

## 硬约束

- 验收脚本 sha256 冻结：acceptance.py=c1965638… / test.html=4b79893e…，碰都不许碰
- server.py/start.sh 不许含 emoji（已清理，保持文字标签 [WARN]/[OK]/[INFO] 等）
- 改完立即 git 提交（v3.0.0 曾四天未提交丢失教训）

## 当前状态

v3.2.0 + 访达选目录 + 自定义按键面板（keys-panel，已恢复）。播放列表已回退。
- **2026-08-01 根因查明**：打包版「浏览」无反应的真凶 = pynput 全局热键与 HTTP 服务同进程，无「输入监控」权限时被 macOS SIGKILL，服务器启动数秒即死、全功能瘫痪；adhoc 签名按二进制哈希记权限，重打包即失效。此前 NSOpenPanel↔osascript 两轮改动均未触根因。
- **已修复（2026-08-01，commit 24b44ad）**：热键拆独立子进程（`--hotkey-child`，主进程不被 SIGKILL 拖死）/ pick-folder 单段 AppleScript 前置 + stderr 分流报错 / build.sh venv 装 pynput / 安装说明加授权指引。验收 12/12，.app 与 zip 已重建（13:06/13:08）。前置 frontmost 机器半验受限见 BLOCKED B13 待领导亲验。
- server.py 用 `libx264 -preset fast -crf 23`（h264_videotoolbox 已回滚，用户确认 libx264 可正常看）
- content.js 无框模式等比缩放（state.videoRatio）；拖拽角标 hover 圆点；keys-panel 用 state.keybindings + chrome.storage.local 持久化
- 打包版 .app 与 zip（Aug 1 11:25/11:27 构建）**含旧缺陷**：无输入监控权限启动数秒即死，且是 keys-panel 删除版——任务书执行完必须重建才可用
- 运行态实测（2026-08-01）：双击 .app **无终端窗口**（后台运行），重复双击无副作用（L550 端口检测后退出）；停止方法 `lsof -ti:8765 | xargs kill`
- fixed 定位重构（v3.2.1）已回滚——用户验证 sticky 打包版无问题
