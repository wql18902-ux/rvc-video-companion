# CLAUDE.md — 浏览器播放器系统

Chrome 扩展（MV3）+ 本地 ffmpeg 服务器，在 aim-read.top 阅读站嵌入视频播放器，支持 MKV/MOV 实时转码。纯 Vanilla JS，无构建工具链。

## 怎么跑

```bash
# 启服务器（端口 8765）
bash stream-server/start.sh
# 或双击 stream-server/packaging/dist/RVC-Video-Companion.app

# 加载扩展：chrome://extensions → 开发者模式 → 加载已解压 → reader-video-companion/
# 使用：访问 aim-read.top，点扩展图标唤出浮窗播放器

# 跑验收（必须先清 profile，否则 G2 残留致 C 超时；且需同一命令内拉起 8765 服务器 + 清 HTTP_PROXY，详见 AGENTS.md「验收通路」）
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

TRAE 会注入 PYTHONHOME/PYTHONPATH 导致 python 报 "No module named 'encodings'"，跑 python 一律加 `env -u PYTHONHOME -u PYTHONPATH`（规避细节见 [AGENTS.md](AGENTS.md)「验收通路」）。

## 技术栈

Chrome MV3 扩展（Vanilla JS）/ Python 3 标准库 http.server（BaseHTTPRequestHandler，**非 aiohttp**）/ ffmpeg+ffprobe / mpegts.js / PyInstaller 打包 .app

## 目录与约定

- `reader-video-companion/` — 唯一维护的扩展（content.js/player.css/background.js/manifest.json）
- `stream-server/` — 本地服务器（server.py/start.sh）
- `tests/` — 分层测试：验收脚本 acceptance.py + fixtures/ + L1 单测 test_server_api.py + L2 真实进程 e2e_extra.py；**根目录 `test.html`** — 验收测试页（不在 tests/ 内）。判卷基准三文件（acceptance.py/test.html/sample.mp4）的 sha256 冻结约束与完整哈希见 [AGENTS.md](AGENTS.md)，此处不重复
- `packaging/` — 分发包打包脚本（make-distro.sh 打 zip / install.sh 一键安装 / install-source.sh 源码版 / build-crx.sh [已弃用]）
- `stream-server/packaging/` — .app 构建脚本（build.sh，PyInstaller 打包 + 分步签名；版本号自动从 manifest.json 注入）
- `AGENTS.md` 硬约束唯一权威源（sha256 冻结 / emoji 禁令 / 版本唯一源 / 验收通路 / git 代理规则）；`PROGRESS.md` 现役状态真相源；`BLOCKED.md` 待决项；`iterations/history.md` 版本记录

## 硬约束

唯一权威源：[AGENTS.md](AGENTS.md)（判卷基准 sha256 冻结 / emoji 禁令 / 版本唯一源与资产英文命名 / 验收通路 / git 代理规则）。本文件不再重复约束细节，任何约束变更必须先改 AGENTS.md。

## 检查与回滚（进入主干的唯一通路）

唯一通路规则（钩子行为、绕过代价、验收环境）见 [AGENTS.md](AGENTS.md)「验收通路」，此处只留命令：
- 安装钩子：`bash scripts/install-hooks.sh`（pre-commit 静态秒级 / pre-push 静态+验收全量，推送 main 前必须通过）
- 手动检查：`bash scripts/check.sh`（全量）/ `bash scripts/check.sh --static`（静态）/ `--no-retry`（B9 F 步 flaky 默认自动重试一次）
- 紧急绕过（不推荐，绕过即失去唯一通路，事后必须补跑检查）：`git commit --no-verify` / `git push --no-verify`
- 卸载钩子：`bash scripts/install-hooks.sh --uninstall`（scripts/ 仍在仓库，随时重装；钩子只做前置检查，不改变 git 历史）

## 当前状态

v3.2.3（manifest.json 唯一版本源；main 待推送 b29531b→d13b711，tag v3.2.3 发布后同步）。
- **v3.2.3 新增（2026-08-02 晚间，b29531b → d13b711 共 3 commit）**：
  - **MP3/音频播放**（b29531b）：server.py 按扩展名分流——.mp3/.m4a/.aac/.wav/.flac/.ogg 直接回原始字节流（浏览器原生播放，零转码，含 Range），视频转码路径一字未动；content.js 音频模式（video.src 直连 + 音频占位 UI），控制条/倍速/热键/进度全复用；L1 +8、L2 +3 用例
  - **热键过渡期不灵敏修复**（6e7a01e）：togglePlay 加 playPending 过渡锁，play() 异步 pending 期间忽略重复触发
  - **热键双触发修复**（d13b711）：本地 keydown 与 SSE 全局热键双通道去重不对称导致一次按键两次切换（时灵时不灵/图标闪跳），双通道对称去重
- **Release 状态**：v3.2.2 为 Latest（旧构建，不含以上 3 commit）；v3.2.3 打包发布后更新此节
- **核心配置**：player.css `position: fixed; left:50%; margin-left:-210px; top:100px; z-index:45`（图层模式，不挤压文字，低于弹窗 z-50）；server.py pick-folder 用纯 osascript `choose folder`（系统级对话框，无需激活 Finder）；server.py 编码器 `libx264 -preset fast -crf 23`；content.js keys-panel（state.keybindings + chrome.storage.local）；音频分流 AUDIO_EXTS
- **历史根因（保留备查）**：pynput 全局热键与 HTTP 服务同进程，无「输入监控」权限时被 macOS SIGKILL。已拆 `--hotkey-child` 子进程隔离。每次重打包 .app 后输入监控权限失效（adhoc 签名按二进制哈希记账），需重新授权
- **验收环境**：坑位与必守命令已收敛至 AGENTS.md「验收通路」，此处不重复
- 运行态：双击 .app **无终端窗口**（后台运行），重复双击无副作用（端口检测后退出）；停止 `lsof -ti:8765 | xargs kill`
- **git 代理规则**：权威源为 AGENTS.md「git 代理规则」，此处不重复
