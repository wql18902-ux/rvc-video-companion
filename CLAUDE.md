# CLAUDE.md — 浏览器播放器系统

Chrome 扩展（MV3）+ 本地 ffmpeg 服务器，在 aim-read.top 阅读站嵌入视频播放器，支持 MKV/MOV 实时转码。纯 Vanilla JS，无构建工具链。

## 怎么跑

```bash
# 启服务器（端口 8765）
bash stream-server/start.sh
# 或双击 packaging/dist/RVC视频伴侣.app

# 加载扩展：chrome://extensions → 开发者模式 → 加载已解压 → reader-video-companion/
# 使用：访问 aim-read.top，点扩展图标唤出浮窗播放器

# 跑验收（必须先清 profile，否则 G2 残留致 C 超时；且需同一命令内拉起 8765 服务器 + 清 HTTP_PROXY，详见「验收环境」）
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

Chrome MV3 扩展（Vanilla JS）/ Python 3 标准库 http.server（BaseHTTPRequestHandler，**非 aiohttp**）/ ffmpeg+ffprobe / mpegts.js / PyInstaller 打包 .app

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
- **软件名 / 资产名一律英文**：项目名、.app 名、zip 名、GitHub Release asset 名、CLI 参数名等全程用 ASCII 英文，禁止中文。中文名不稳定：GitHub 会把 `RVC视频伴侣.zip` 剥成 `RVC.zip`、macOS 路径含中文易踩 xattr/codesign 坑、跨平台脚本传参易乱码。对内可叫中文品牌「RVC 视频伴侣」，但**文件名 / asset 名 / 标识符**一律英文（如 `RVC-Video-Companion.zip`）
- 改完先过检查再提交（v3.0.0 曾四天未提交丢失教训）：本地钩子强制 pre-commit 静态检查 + pre-push 全量验收，检查通过才允许提交/推送（见「检查与回滚」）

## 检查与回滚（进入主干的唯一通路）

- 安装：`bash scripts/install-hooks.sh` → pre-commit（静态秒级）+ pre-push（静态+验收全量，推送 main 前必须通过）
- 手动跑：`bash scripts/check.sh`（全量）/ `bash scripts/check.sh --static`（静态）/ `--no-retry`（B9 F 步 flaky 默认自动重试一次）
- 紧急绕过（不推荐，绕过即失去唯一通路，事后必须补跑检查）：`git commit --no-verify` / `git push --no-verify`
- 回滚：`bash scripts/install-hooks.sh --uninstall` 卸载钩子（scripts/ 仍在仓库，随时重装）；钩子只做前置检查，不改变 git 历史，已推送内容不受影响

## 当前状态

v3.2.2（manifest.json 唯一版本源；main 最新 = fc0e50b，已推送 origin/main）。
- **2026-08-02 swift-thunder-newton 方案 P0-P2 已落地（commit 0152371）**：
  - P0 文件选择 UX：删 `openFolderViaFinder()`，btnFolder/btnLoadMain 只 `showFolderOverlay()`（不自动弹 Finder）；浮层自动列上次目录 + loadFileList 带 seq 令牌守卫；dirPickBtn=「访达选择目录（macOS 高级选项）」；serve_pick_folder 用 `open -a Finder --hide` + Standard Additions choose folder
  - P1 转码竞态：`/api/stream-error` 服务端长轮询（未就绪最多等 5s）；serve_stream finally 只 kill 本请求进程；客户端转码兜底超时 15s→10s
  - P2 清理：删 LAYOUT_SCHEMA 迁移（restoreLayout 守卫兜底）；content.js 顶部模块注释
  - P3 状态机简化**未做**（Archi ADR：单独立项，验收稳定后再评估）
- **2026-08-02 启动脚本（6fbb3f9 + fc0e50b）**：.command 双击场景补 brew PATH；start.sh 增加 pynput 自检（缺失仅 WARN 不阻塞）
- **核心配置**：player.css `position: sticky + float:right`（fixed 已回滚）；server.py pick-folder 用 `open -a Finder --hide` 两步弹窗（分步签名的打包版无 TCC 自动化权限，不能用 tell Finder/System Events）；server.py 编码器 `libx264 -preset fast -crf 23`；content.js keys-panel 恢复（state.keybindings + chrome.storage.local）
- **历史根因（保留备查）**：pynput 全局热键与 HTTP 服务同进程，无「输入监控」权限时被 macOS SIGKILL。已拆 `--hotkey-child` 子进程隔离。每次重打包 .app 后输入监控权限失效（adhoc 签名按二进制哈希记账），需重新授权
- **验收环境两坑（2026-08-02 实测）**：
  1. WorkBuddy/IDE 注入 `HTTP_PROXY=127.0.0.1:52577` 会让 Playwright Chromium 内 fetch 8765 全挂（curl 直连却正常）——跑 L3 必须 `env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy`
  2. Bash 工具跨调用清后台进程——L3 的 8765 服务器必须与验收**同一条命令内**启动：`cd stream-server && nohup /usr/local/bin/python3 -u server.py & sleep 2 && cd .. && bash scripts/check.sh`
  3. 验收 H 步 EMOJI_RE 含 U+2190-21FF：content.js/player.css 注释里写 `→` 会 FAIL，一律用文字描述
- **打包版待办**：dist 的 .app/zip 仍是 04:45 旧版（不含 0152371/6fbb3f9/fc0e50b），**需重建**（跑 build.sh + make-distro.sh，沙箱拦 rm -rf 需用户终端跑）后发新 release。Release 现有：v3.2.2（Latest，10:03）+ v3.2.2-test（Pre-release，19:25）
- 运行态：双击 .app **无终端窗口**（后台运行），重复双击无副作用（端口检测后退出）；停止 `lsof -ti:8765 | xargs kill`
- git push 代理三态规则（2026-08-02 实测卡点链复盘）：
  - 代理未开：`git -c http.proxy= -c https.proxy= push origin main`（清空代理直连）
  - 代理已开（7890）：`NO_PROXY=127.0.0.1,localhost git -c http.proxy=http://127.0.0.1:7890 -c https.proxy=http://127.0.0.1:7890 push origin main`
  - ⚠️ **禁止用 `HTTPS_PROXY=...` env 推送**：env 会泄漏进 pre-push 钩子的 acceptance.py 子进程，urllib 把 `127.0.0.1:8765` localhost 探活也送进代理 → 误判 "server 未运行" → 验收挂。给 git 设代理只走 `git -c http.proxy=`（不进子进程 env）
  - `gh` CLI **不走** git 全局 `http.proxy`，只认 `HTTPS_PROXY/HTTP_PROXY/ALL_PROXY` env；代理环境下 `gh auth refresh`/`gh api` 要显式带 env
  - 推送含 `.github/workflows/*` 的 commit：gh token 必须带 `workflow` scope（仅 `repo` 会被远端拒）；缺时跑 `HTTPS_PROXY=http://127.0.0.1:7890 gh auth refresh -h github.com -s workflow`（设备流程，需 TTY，agent 内后台跑不出验证码，让用户在终端跑或前台跑等浏览器授权）
