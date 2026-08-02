所有编码代理（Claude Code / Qoder / Codex / Cursor / TRAE 等）的统一规则入口。本文件是**规则唯一权威源**：CLAUDE.md 等其他指令文件不再重复硬约束，只保留指针与操作命令。任何约束变更必须先改本文件。

# AGENTS.md — 浏览器播放器系统（RVC 视频伴侣）

Chrome 扩展（MV3，Vanilla JS，无构建工具链）+ 本地 ffmpeg 服务器（Python 3 标准库 http.server，非 aiohttp），在 aim-read.top 阅读站嵌入视频播放器，支持 MKV/MOV 实时转码。当前分支 main。

## 硬约束（唯一权威源）

### 1. 判卷基准 sha256 冻结

判卷基准三文件哈希冻结，碰都不许碰（run_tests.sh L0 核对）：

- `tests/acceptance.py` = `c1965638b39ca16723260aa51788a734facab227671485e272404748b5e07d5e`
- `test.html`（注意在仓库根目录，不在 tests/ 内）= `4b79893e101a4111a138d29093fe91119282469141eea7b761e6e66182b433fe`
- `tests/fixtures/sample.mp4` = `9b4a8281dde260dfcd4639147446ef2451836b3ec881a4e0c737b90137c4e3ce`

实现文件（content.js/player.css/server.py 等）不受哈希约束，由 run_tests.sh 分层行为验证覆盖。

### 2. emoji 禁令

- `server.py` / `start.sh` 不得含 emoji，一律用文字标签（[WARN]/[OK]/[INFO] 等）
- 验收 H 步扫描 `reader-video-companion/content.js` + `player.css` 全文件（含注释），EMOJI_RE 覆盖 U+1F000-1FAFF、U+2190-21FF、U+2300-23FF、U+25A0-25FF、U+2600-27BF、U+2B00-2BFF、U+FE0F、U+20E3——注释里写 `→` 等字形符号会 FAIL，一律用文字描述

### 3. 版本唯一源与命名

- 版本号唯一源 = `reader-video-companion/manifest.json`（打包版 version 自动从 manifest 注入，禁止他处另维护版本号）
- 软件名 / 资产名 / 标识符一律 ASCII 英文：项目名、.app 名、zip 名、GitHub Release asset 名、CLI 参数名等。中文名会触发 GitHub 剥离（`RVC视频伴侣.zip` 被剥成 `RVC.zip`）、macOS 路径含中文易踩 xattr/codesign 坑、跨平台脚本传参易乱码。对内可叫中文品牌「RVC 视频伴侣」，文件名 / asset 名 / 标识符必须英文（如 `RVC-Video-Companion.zip`）

### 4. 验收通路（进入主干的唯一通路）

- 分层测试：`bash run_tests.sh`（L0 哈希/静态 + L1 单测 + L2 真实进程 E2E）；`bash run_tests.sh --full` 加 L3 验收（进主干前必跑）
- 统一检查：`bash scripts/check.sh`（静态 + 验收全量）/ `bash scripts/check.sh --static`（静态秒级）/ `--no-retry`（B9 F 步 flaky 默认自动重试一次）
- git 钩子：`bash scripts/install-hooks.sh` 安装后得到 pre-commit（静态秒级）+ pre-push（静态 + 验收全量）；检查通过才允许提交/推送
- 紧急绕过（不推荐，绕过即失去唯一通路，事后必须补跑全量检查）：`git commit --no-verify` / `git push --no-verify`
- 回滚：`bash scripts/install-hooks.sh --uninstall` 卸载钩子（scripts/ 仍在仓库，随时重装；钩子只做前置检查，不改变 git 历史，已推送内容不受影响）
- 验收环境（2026-08-02 实测坑，L3 必守）：
  1. 先清 profile：`rm -rf /tmp/rvc-pw-profile-accept`，否则 G2 残留致 C 步超时
  2. 跑 python 一律 `env -u PYTHONHOME -u PYTHONPATH`（TRAE 注入 PYTHONHOME/PYTHONPATH 导致 "No module named 'encodings'"）
  3. 清代理 env：`env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy`（IDE 注入 `HTTP_PROXY=127.0.0.1:52577` 会让 Playwright Chromium 内 fetch 8765 全挂，curl 直连却正常）
  4. 8765 服务器必须与验收**同一条命令内**启动：`cd stream-server && nohup /usr/local/bin/python3 -u server.py & sleep 2 && cd .. && bash scripts/check.sh`（Bash 工具跨调用清后台进程）

### 5. git 代理规则

- 代理未开：`git -c http.proxy= -c https.proxy= push origin main`（清空代理直连）
- 代理已开（本地 7890）：`NO_PROXY=127.0.0.1,localhost git -c http.proxy=http://127.0.0.1:7890 -c https.proxy=http://127.0.0.1:7890 push origin main`
- 禁止用 `HTTPS_PROXY=...` env 推送：env 会泄漏进 pre-push 钩子的 acceptance.py 子进程，urllib 把 `127.0.0.1:8765` localhost 探活也送进代理，导致误判 "server 未运行" 而验收挂。给 git 设代理只走 `git -c http.proxy=`（不进子进程 env）
- `gh` CLI **不走** git 全局 `http.proxy`，只认 `HTTPS_PROXY/HTTP_PROXY/ALL_PROXY` env；代理环境下 `gh auth refresh`/`gh api` 要显式带 env
- 推送含 `.github/workflows/*` 的 commit：gh token 必须带 `workflow` scope（仅 `repo` 会被远端拒）；缺时跑 `HTTPS_PROXY=http://127.0.0.1:7890 gh auth refresh -h github.com -s workflow`

## 指令文件分工（无重复约束）

- AGENTS.md — 硬约束唯一权威源（本文件）
- CLAUDE.md — 运行/验收操作命令 + 迭代状态备忘，硬约束一律指向本文件
- PROGRESS.md — 现役状态真相源；BLOCKED.md — 待决项；iterations/history.md — 版本记录
