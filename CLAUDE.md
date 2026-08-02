# CLAUDE.md — 浏览器播放器系统

Chrome 扩展（MV3）+ 本地 ffmpeg 服务器，在 aim-read.top 阅读站嵌入视频播放器，支持 MKV/MOV 实时转码。纯 Vanilla JS，无构建工具链。

## 怎么跑

```bash
# 启服务器（端口 8765）
bash stream-server/start.sh
# 或双击 packaging/dist/RVC视频伴侣.app

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

v3.2.2（manifest.json 唯一版本源；main 最新 = 10949c2，已推送 origin/main；工作区另有未提交的 CLAUDE.md 规则收敛 + CI 改动）。
- **2026-08-02 技术方案 P0-P2 全量落地（commit 10949c2）**：
  - P0 安全稳定性：signal_handler 清理 hotkey_proc（防孤儿进程）；POST 请求体 1MB 限制（read_body）；SSE 空闲 30min 超时（MAX_SSE_IDLE）；B9 竞态根治（loadFileList dirOverride）；删除 /tmp/rvc-pick-folder.log
  - P1 架构体验：转码 Seek 支持（进度条拖动重新请求 /api/stream?start=）；热键看门狗（120s 检测 + 自动重启）；打包版 version 修复（_MEIPASS 路径）；background.js 指数退避
  - P2 可维护性：content.js api 命名空间（封装所有 fetch 调用）；state.currentDir 新增；player.css 分节注释
- **2026-08-02 swift-thunder-newton 方案 P0-P2 已落地（commit 0152371）**：
  - P0 文件选择 UX：删 `openFolderViaFinder()`，btnFolder/btnLoadMain 只 `showFolderOverlay()`（不自动弹 Finder）；浮层自动列上次目录 + loadFileList 带 seq 令牌守卫；dirPickBtn=「访达选择目录（macOS 高级选项）」；serve_pick_folder 用 `open -a Finder --hide` + Standard Additions choose folder
  - P1 转码竞态：`/api/stream-error` 服务端长轮询（未就绪最多等 5s）；serve_stream finally 只 kill 本请求进程；客户端转码兜底超时 15s→10s
  - P2 清理：删 LAYOUT_SCHEMA 迁移（restoreLayout 守卫兜底）；content.js 顶部模块注释
  - P3 状态机简化**未做**（Archi ADR：单独立项，验收稳定后再评估）
- **2026-08-02 启动脚本（6fbb3f9 + fc0e50b）**：.command 双击场景补 brew PATH；start.sh 增加 pynput 自检（缺失仅 WARN 不阻塞）
- **2026-08-02 规则收敛（AGENTS.md 随 10949c2 入库；CLAUDE.md 收敛修改在工作区待提交）**：新增 AGENTS.md 硬约束唯一权威源（sha256 冻结 / emoji 禁令 / 版本唯一源 / 验收通路 / git 代理规则）；CLAUDE.md 硬约束 / 检查回滚 / 验收环境 / 代理规则改为指向 AGENTS.md 的指针，不再重复约束
- **核心配置**：player.css `position: fixed; left:50%; margin-left:-210px; top:100px; z-index:45`（图层模式，不挤压文字，低于弹窗 z-50）；server.py pick-folder 用 `open -a Finder --hide` 两步弹窗；server.py 编码器 `libx264 -preset fast -crf 23`；content.js keys-panel 恢复（state.keybindings + chrome.storage.local）
- **播放器定位演进**：sticky+float（挤压文字，flex/grid 下 float 失效）→ fixed 悬浮（被拒要夹心）→ 回退 sticky+float + wrapper（wrapper 破坏 sticky）→ 回退 sticky+float + findArticleContainer 跳过 flex/grid（SPA 时序导致插错容器）→ 最终确认 fixed 居中图层（用户要图层不挤压，z-index=45 低于弹窗 z-50）
- **新增修复（定位方案最终轮）**：播放器隐藏时不自动播放（防出声不见画面）；服务端无 SSE 客户端时忽略热键（不抢键）；restoreLayout transform 边界检查（防旧偏移推偏位置）；rvc-toggle 用 container.contains(player) 检查容器（防 SPA 挪位）
- **历史根因（保留备查）**：pynput 全局热键与 HTTP 服务同进程，无「输入监控」权限时被 macOS SIGKILL。已拆 `--hotkey-child` 子进程隔离。每次重打包 .app 后输入监控权限失效（adhoc 签名按二进制哈希记账），需重新授权
- **验收环境（2026-08-02 实测）**：坑位与必守命令（清 profile / 清代理 env / 同命令拉起 8765 / TRAE PYTHONHOME / H 步 emoji 扫描）已收敛至 AGENTS.md「验收通路」，此处不重复
- **打包版待办**：dist 的 .app/zip 仍是 04:45 旧版（不含 0152371/6fbb3f9/fc0e50b），**需重建**（跑 build.sh + make-distro.sh，沙箱拦 rm -rf 需用户终端跑）后发新 release。Release 现有：v3.2.2（Latest，10:03）+ v3.2.2-test（Pre-release，19:25）
- 运行态：双击 .app **无终端窗口**（后台运行），重复双击无副作用（端口检测后退出）；停止 `lsof -ti:8765 | xargs kill`
- **git 代理规则**（三态命令 / 禁 HTTPS_PROXY env 推送 / gh CLI 走 env / workflow scope）：权威源为 AGENTS.md「git 代理规则」，此处不重复（设备流程，需 TTY，agent 内后台跑不出验证码，让用户在终端跑或前台跑等浏览器授权）
