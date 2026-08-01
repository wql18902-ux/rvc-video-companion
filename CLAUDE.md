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

# 分层测试（改动常规验证：L0 哈希/静态 + L1 单测 + L2 真实进程 E2E）
bash run_tests.sh            # L0+L1+L2（默认）
bash run_tests.sh --full     # 加 L3 验收（进主干前必跑）

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
- `tests/` — 分层测试：验收脚本 acceptance.py + fixtures/ + L1 单测 test_server_api.py + L2 真实进程 e2e_extra.py；**根目录 `test.html`** — 验收测试页；三者 **sha256 冻结，不许改**（注意 test.html 在根目录，不在 tests/ 内）。哈希冻结范围只覆盖判卷基准三文件（acceptance.py/test.html/sample.mp4），content.js/player.css/server.py 等实现文件不受哈希约束，由 run_tests.sh 分层行为验证覆盖
- `packaging/` — 分发包打包脚本（make-distro.sh 打 zip / install.sh 一键安装 / install-source.sh 源码版 / build-crx.sh [已弃用]）
- `stream-server/packaging/` — .app 构建脚本（build.sh，PyInstaller 打包 + 分步签名；版本号自动从 manifest.json 注入）
- `PROGRESS.md` 现役状态真相源；`BLOCKED.md` 待决项；`iterations/history.md` 版本记录

## 硬约束

- 判卷基准 sha256 冻结（范围收窄到三文件，防漂移）：acceptance.py=c1965638… / test.html=4b79893e… / sample.mp4=9b4a8281…，碰都不许碰（run_tests.sh L0 核对）；实现文件不再哈希冻结，靠分层测试验证行为
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
- **v3.2.2 改动**：fixed→sticky 回滚修复挤压正文 / System Events→NSOpenPanel(setActivationPolicy_ 前置) / 恢复 keys-panel / README 加「方式二：让 AI Agent 帮你装」+ 功能截图 / 安装说明.txt 重写（解决 macOS quarantine「已损坏」UX 问题）
- **v3.2.2 后续整顿（本次）**：热键 IME 脏值修复（捕获加 isComposing 过滤+单 ASCII 校验，兜底改合法性校验）/ 品牌统一 RVC 视频伴侣 / 版本单一源 ADR-001（manifest.json 为唯一源，build/make-distro 自动注入）/ 删 .command 鸡生蛋（清隔离统一终端一行 xattr）/ install.sh 多源 fallback+ditto 解压+轮询探活 / README 重排（手动下载提方式一，curl 降可选）/ check.sh 加版本号一致性校验
- **打包版**：dist 的 .app/zip 仍是 18:58 旧版（含已删除的 .command），**需重建**（跑 build.sh + make-distro.sh）才含本次整顿。Release asset 名 `RVC-Video-Companion.zip`（GitHub 不支持中文 asset 名）。Release: https://github.com/wql18902-ux/rvc-video-companion/releases/tag/v3.2.2
- **历史根因（保留备查）**：pynput 全局热键与 HTTP 服务同进程，无「输入监控」权限时被 macOS SIGKILL。已拆 `--hotkey-child` 子进程隔离。每次重打包 .app 后输入监控权限失效（adhoc 签名按二进制哈希记账），需重新授权
- 运行态：双击 .app **无终端窗口**（后台运行），重复双击无副作用（端口检测后退出）；停止 `lsof -ti:8765 | xargs kill`
- git push 受全局 7890 代理影响，代理未开时用 `git -c http.proxy= -c https.proxy= push origin main` 临时绕过
