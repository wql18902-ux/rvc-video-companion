# 资深开发复审：全局热键可自定义 + 输入监控引导

> 复审对象：`~/.claude/plans/nested-waddling-riddle.md`（Plan Agent 给出的设计）
> 复审方式：所有"硬事实"均回仓库代码逐行核对，不采信口头结论。
> 日期：2026-08-02

## 0. 结论速览
- **根因分析：准确**（两通道键位脱节，已核对 server.py / content.js 真实代码）
- **方案方向：正确、务实**，但落地前需补 **3 项 P1 加固** + 若干 P2
- **整体评分：82 / 100**
  - 好：根因定位准、带行号可查证、主动抓到 CLAUDE.md 的 aiohttp 文档漂移
  - 不好：方案偏"能用就行"，缺对**双进程一致性**与**热重载 vs 重启**的工程权衡；CORS 预检这种老坑要靠 plan 自己补才暴露

## 1. 落盘结论的磁盘复核
| 结论 | 代码位置 | 复核 |
| --- | --- | --- |
| 全局热键 pynput 硬编码 s/a/d | `server.py:195-200` `if key.char=='s'...=='a'...=='d'` | ✅ 成立 |
| 页面内热键读 `state.keybindings`（chrome.storage）可改 | `content.js:1316-1319` 载入、`1373-1383` 匹配 | ✅ 成立 |
| 校验口径为单字符 a-z0-9 | `content.js:1210-1212` `/^[a-z0-9]$/` | ✅ 成立 |
| server 用 `BaseHTTPRequestHandler`（非 aiohttp） | `server.py:286` `class StreamHandler(http.server.BaseHTTPRequestHandler)` | ✅ 成立；CLAUDE.md 写 aiohttp 是**文档漂移** |
| `--hotkey-child` 子进程分支 | `server.py:840` + `start_hotkey_listener:145-158` | ✅ 成立 |
| 跨域 POST 缺 OPTIONS 预检 | 全文件无 `do_OPTIONS` | ✅ 成立（plan 已识别，确认必做） |
| 三条跨项目坑（bash set -u / git 代理 / 中文 asset） | `learned.md` + `CLAUDE.md` 代理三态 | ✅ 与 CLAUDE.md 自洽 |

## 2. 方案的硬伤（按优先级）

### P1 — 必须改
1. **改键即 kill + respawn pynput 子进程太脆弱**
   - 每次改键重启全局监听：会重新触发 macOS TCC 权限弹窗、存在"键位空窗期"（kill 到 respawn 之间全局键全死）、子进程起不来就静默丢全局热键。
   - 且当前 `start_hotkey_listener` 里 `proc = subprocess.Popen(...)` 是**局部变量**，没存全局句柄，restart 缺 plumbing。
   - **建议**：保持 pynput listener 长生命周期，键位用闭包内 `bindings` 字典，**热重载**（子进程轮询 JSON / 父进程 pipe 写入 → 子进程线程安全更新字典），永不重启。

2. **server JSON 与 chrome.storage 双源真理 → 会失同步**
   - content.js 写 chrome.storage，server 写自己的 JSON。若 server 宕机期间改键，下次 server 启动读自己旧 JSON，和页面侧分叉。
   - **建议**：server 为权威源；content.js 在 SSE 重连时把 chrome.storage 推回 server 做 **reconcile**（幂等）；server 宕机时页面侧仍能用 chrome.storage 兜底。

3. **CORS OPTIONS 预检缺失（已识别，确认必做）**
   - content.js 跨域（`aim-read.top` → `127.0.0.1:8765`）`fetch POST {Content-Type:application/json}` 必触发 OPTIONS 预检，当前 server 无 `do_OPTIONS` → 预检失败 → POST 被浏览器拦截。
   - **必须**：加 `do_OPTIONS`（回 `Access-Control-Allow-Methods/Headers/Origin`），且 `check_origin` 对 OPTIONS 也放行。

### P2 — 建议改
4. **启动即 auto-open 系统设置太侵入**：每次重签 .app（adhoc 按哈希记账，权限必失效）都会弹设置页。改为**仅 keys-panel 按钮触发**跳转，不打扰启动。
5. **`on_press` 抽成 `action_for_char(char, bindings)` 可单测函数**：headless CI 无法按真实键盘，把"字符→动作"映射从 pynput 回调里抽出，单测才能覆盖，防回归。
6. **修 CLAUDE.md 文档漂移**：`aiohttp` → `http.server.BaseHTTPRequestHandler`（同步阻塞单线程，注意并发上限）。
7. **威胁面标注**：`/api/keybindings` 任何 allowlist-origin 页面可改你全局键；本地单用户工具风险低，但文档注明，避免未来放宽为通配 Origin。
8. **已知限制写进方案**：全局通道只支持单字符（`key.char`），不支持修饰键/功能键；两端校验**正则必须逐字符一致**（JS `/^[a-z0-9]$/` ↔ Python `re.fullmatch(r'[a-z0-9]', k)`）。

### 一个好消息（不是坑）
`pyobjc/Quartz` 已被 `pynput._util.darwin` 依赖自动带进 PyInstaller 打包（build cache 的 `Analysis-00.toc` 已含 Quartz，`.app` 内 `_CodeSignature` 也签名了 `Quartz/*.so`）。所以 `CGPreflightListenEventAccess()` 在 .app 内**可用**，不必额外加 hiddenimports。仅需确认 `import Quartz` 包在 `try/except` 内（开发机 vs .app 环境一致）。

## 3. 给团队的技术提升要点（本次暴露的共性短板）
1. **双进程/双通道架构必须有"单一事实源 + 对账"意识**：server 与扩展各存一份配置，迟早分叉。要么一端为权威 + 另一端镜像，要么加 reconcile。
2. **跨进程通信要先想"对端不在线"的失败模式**：配置写入要对 server 宕机有兜底（chrome.storage），恢复后要主动对账。
3. **改键/改配置要有"热重载 vs 重启"的取舍意识**：能热重载就不重启长生命周期进程（权限、句柄、空窗期都是成本）。
4. **浏览器跨域是高频坑**：content script 调 localhost 也逃不掉 CORS 预检；`application/json` POST 必预检，别等上线才爆。
5. **文档与代码漂移要定期核对**：CLAUDE.md 写 aiohttp 实际不是——根因分析报告里能抓到，说明有人复核；但应在 CI/钩子里固化"文档 vs 代码"检查。
6. **端到端验证要覆盖"全局通道"**：无头 Playwright 默认绕过 Karabiner/全局键盘拦截，测不出全局键问题（history 里已有这条教训）。全局热键必须真机或 mock 权限后实测。
7. **可测试性优先**：把业务逻辑（键位映射、校验）从 IO/框架里抽出纯函数，CI 才能覆盖；否则只能靠手测，回归无保障。

## 4. 下一步建议
- 实现会话直接读本文件 + `nested-waddling-riddle.md` + `CLAUDE.md` 即可续上。
- 实现时按 P1→P2 顺序：先补 `do_OPTIONS` + 抽 `action_for_char` + 改热重载 + 加 reconcile，再处理 auto-open 与文档。
- 验证：`tests/test_server_api.py` 补 keybindings 端点用例（合法/非法键、GET、health 字段、映射单测）；Playwright 补"改键后 pynput 子进程用新键"（mock `CGPreflightListenEventAccess`）。
