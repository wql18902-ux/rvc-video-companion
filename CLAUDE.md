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

# 统一检查（静态 + 验收，进主干的唯一通路，详见「检查与回滚」）
bash scripts/check.sh --static   # 秒级静态检查
bash scripts/check.sh            # 全量：静态 + 验收
bash scripts/install-hooks.sh    # 把检查接入 git hooks（pre-commit 静态 / pre-push 全量）
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
- 改完先过检查再提交（v3.0.0 曾四天未提交丢失教训）：本地钩子强制 pre-commit 静态检查 + pre-push 全量验收，检查通过才允许提交/推送（见「检查与回滚」）

## 检查与回滚（进入主干的唯一通路）

- 安装：`bash scripts/install-hooks.sh` → pre-commit（静态秒级）+ pre-push（静态+验收全量，推送 main 前必须通过）
- 手动跑：`bash scripts/check.sh`（全量）/ `bash scripts/check.sh --static`（静态）/ `--no-retry`（B9 F 步 flaky 默认自动重试一次）
- 紧急绕过（不推荐，绕过即失去唯一通路，事后必须补跑检查）：`git commit --no-verify` / `git push --no-verify`
- 回滚：`bash scripts/install-hooks.sh --uninstall` 卸载钩子（scripts/ 仍在仓库，随时重装）；钩子只做前置检查，不改变 git 历史，已推送内容不受影响

## 当前状态

v3.2.2（2026-08-01 发布，GitHub Release v3.2.2 + commit dea5ef6）。播放列表已回退。
- **核心配置**：player.css 用 `position: sticky + float:right`（fixed 已回滚，违反硬约束）；server.py pick-folder 用 `activate me`（纯 Standard Additions，无自动化权限）；server.py 编码器 `libx264 -preset fast -crf 23`（h264_videotoolbox 已回滚）；content.js keys-panel 已恢复（state.keybindings + chrome.storage.local）
- **v3.2.2 改动**：fixed→sticky 回滚修复挤压正文 / System Events→activate me 修复 -1743 权限错误 / 恢复 keys-panel / README 加「方式零：让 AI Agent 帮你装」+ 功能截图 / zip 含「首次打开-点我.command」+ 重写安装说明.txt（解决 macOS quarantine「已损坏」UX 问题）
- **打包版**：.app 与 zip（Aug 1 18:58 重建，含 .command 脚本）是最新版。Release asset 名 `RVC-Video-Companion.zip`（GitHub 不支持中文 asset 名）。Release: https://github.com/wql18902-ux/rvc-video-companion/releases/tag/v3.2.2
- **已知待修**：zip 解压后 .command 文件可能丢失执行权限（`permission denied`），需在打包流程中验证 ditto 权限保留或安装说明补充 `chmod +x` 提示
- **历史根因（保留备查）**：pynput 全局热键与 HTTP 服务同进程，无「输入监控」权限时被 macOS SIGKILL。已拆 `--hotkey-child` 子进程隔离。每次重打包 .app 后输入监控权限失效（adhoc 签名按二进制哈希记账），需重新授权
- 运行态：双击 .app **无终端窗口**（后台运行），重复双击无副作用（端口检测后退出）；停止 `lsof -ti:8765 | xargs kill`
- git push 受全局 7890 代理影响，代理未开时用 `git -c http.proxy= -c https.proxy= push origin main` 临时绕过
