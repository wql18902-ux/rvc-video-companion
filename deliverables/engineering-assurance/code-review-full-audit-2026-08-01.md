# RVC 视频伴侣 · 全面工程审查 + 事故响应报告

**日期**：2026-08-01
**工作流**：工作流 1（全面代码审查）+ 工作流 3（事故响应）
**参与成员**：Cody（代码审查师）/ Archi（架构师）/ Rex（SRE 工程师）/ Tessa（测试专家）/ Docu（文档师）

---

## 📌 TL;DR（执行摘要）

- **整体结论**：代码质量 🔴 不通过（存在 Critical 级安全问题），但系统**当前不处于事故状态**——核心链路（服务器/转码/播放/热键）均正常，B10/B11/B12/B3 已解决。
- **严重度分布**：🔴严重 4 项 / 🟠高 6 项 / 🟡中 9 项 / 🟢低 4 项
- **最重风险**：本地 HTTP 服务器 CORS `*` + 无鉴权 + `/api/file` 路径穿越 → **任意网页可读取本机任意文件**（本地文件泄露，Cody 与 Archi 双重确认）。
- **阻塞 / 非阻塞**：4 项 Critical 安全项为阻塞项（修复前不建议交付/合并）；其余为高/中/低改进项与事故遗留项。
- **新增 SEV3 事故隐患**：分发产物（.app/zip）为 keys-panel 删除版，与已恢复的源码不同步。

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| 整体评级 | 🔴 不通过（安全项未修复前）；事故状态：🟢 无开放事故 |
| 阻塞项数量 | 4（Critical 安全） |
| 关键行动项 | 10 条（P0×3 / P1×4 / P2×3） |
| 建议下一步 | 先修 4 个 Critical 安全项（鉴权+CORS 白名单+路径校验+XSS），再决策 keys-panel 分发产物重建 |

---

## 🔍 审查发现（工作流 1 · 按严重度排序）

| # | 严重度 | 类别 | 文件:行 | 问题描述 | 建议修复 | 来源 |
|---|--------|------|---------|---------|---------|------|
| 1 | 🔴严重 | 安全 | server.py:209,409,438,478 + 359-427 | 所有 JSON/文件/SSE 响应均 `Access-Control-Allow-Origin:*`，无鉴权、无 Origin/Host 校验。任意网页可 fetch 本地端口读取任意文件、枚举目录、杀 ffmpeg | 加共享 token；CORS 白名单仅 aim-read.top + chrome-extension://；校验 Origin/Host 防 DNS rebinding；serve_file 限扩展名 | Cody + Archi |
| 2 | 🔴严重 | 安全 | server.py:361-367,464-465 | `os.path.join(dir,file)` 未规范化，dir 可传 `/`、`..` 逃逸 → 任意文件读取（配合上条可被远程利用） | `os.path.realpath` + `commonpath` 前缀校验，禁止 `..`，限制在选定目录内 | Cody + Tessa |
| 3 | 🔴严重 | 安全 | content.js:397,400,444,452,469-474,483,574,582,592,601-603 | 文件名/目录名/`data.error` 直接拼 `innerHTML` 未转义 → 文件系统内恶意文件名可触发 XSS（content script 具 aim-read.top 全站权限） | 一律 `textContent` 或 HTML 转义后插入 | Cody |
| 4 | 🔴严重 | 性能/正确性 | content.js:1283-1314 + server.py:56,429-455 | SSE onerror 中 setTimeout 新建 EventSource 未先 close 旧实例；服务端 30s 空闲主动断开触发双连接累积；control_clients 无上限、每连接占一线程 → 线程耗尽 | 重连前 close 旧实例；服务端心跳保活不主动断；加连接数上限 | Cody |
| 5 | 🟠高 | 交付一致性 | packaging/dist/* | 分发产物与源码不同步：当前 .app/zip 为 keys-panel 删除版，源码已恢复自定义按键；领导重装分发包将丢功能（SEV3） | 决策后重建 .app + zip，产物指纹对齐 | Rex |
| 6 | 🟠高 | 安全 | server.py:177-179,190-204,298-337 | /api/stop、/api/control-key、/api/pick-folder 无鉴权 + CORS `*`：任意站点可终止转码、伪造热键、反复弹访达选择框 | token 校验 + CORS 白名单；pick-folder 限频 | Cody |
| 7 | 🟠高 | 正确性 | server.py:504 | ffmpeg `stderr=DEVNULL` + 流读循环吞异常 → 转码失败零反馈、黑屏难排障（B10 类事故难以提前发现） | stderr 落日志/环形缓冲；加首帧超时；失败回 4xx | Cody + Archi |
| 8 | 🟠高 | 测试缺口 | tests/acceptance.py | 转码路径零覆盖：sample.mp4 走 /api/file 直发（MP4 原生播放），MKV 流式转码完全未测——B10 事故根因 | 新增 ≥50MB 真实 MKV 流式冒烟（首帧/seek/断连），作为编码器变更门禁 | Tessa + Rex |
| 9 | 🟠高 | 测试缺口 | tests/ | SSE 全局热键 E2E、热键子进程崩溃恢复、pick-folder 取消/超时均无自动化（PROGRESS 仅手工验证） | 新增独立 e2e_extra.py + 集成测试（不碰冻结文件） | Tessa |
| 10 | 🟠高 | 架构 | server.py:500-524 | /api/stream 单全局 `current_proc` + 持锁 kill，并发/重复请求互相 kill，无并发上限 | 改 per-session 进程管理；局部变量引用 proc | Archi + Cody |
| 11 | 🟡中 | 正确性 | content.js:38,808-866,1014-1019 | `state.videoRatio` 换文件不重置，换音频/无视频源后仍用旧宽高比缩放 | loadFile 开头置 null，loadedmetadata 再设 | Cody |
| 12 | 🟡中 | 性能 | content.js:997-1011 | 倍速滑杆每个 input 事件都 `chrome.storage.local.set`，高频写盘 | 防抖 / change 或 mouseup 时持久化 | Cody |
| 13 | 🟡中 | 可维护性 | manifest.json:19 vs background.js:4-17 | content_scripts 匹配含 `http://127.0.0.1:8899/*`，但 background isSupportedUrl / host_permissions 不含 → 死配置不一致 | 三处同步或删除 | Cody |
| 14 | 🟡中 | 功能 | content.js + server.py | 转码流 seek 不完整：前端从不传 start 参数，靠 mpegts.js 缓冲内 seek，大文件拖进度条卡死 | 明确支持/不支持；支持则补 restart-stream?start= 协议，否则前端降级 | Archi |
| 15 | 🟡中 | 打包 | stream-server/packaging/build.sh | 打包链路脆弱：dylib 递归改写致签名失效、PyInstaller 布局硬编码、非 universal 二进制 | 打包后自动冒烟（启动 .app→转码 sample→SSE 联通）；锁定依赖版本 | Archi |
| 16 | 🟡中 | 权限 | 系统 | TCC 输入监控随 .app 重建失效（按签名记账），全局热键静默失效 | 启动探测+引导授权；文档已提示；长期考虑稳定签名 | Archi + Rex |
| 17 | 🟡中 | 测试基建 | tests/acceptance.py | B1 profile 跨 run 污染（rvc-frameless 持久化致下次验收 C 步超时）+ B9 F 步 flaky（storage 竞态 ~1/3） | B1 换唯一临时 profile；B9 走基线变更流程修 content.js 时序（storageReady 后再 loadFileList） | Tessa + Rex |
| 18 | 🟡中 | 测试基建 | tests/acceptance.py H 步 | emoji 扫描漏 server.py/start.sh（CLAUDE.md 同样禁 emoji） | 静态扫描扩展覆盖全部文件 | Tessa |
| 19 | 🟡中 | 待验证 | B13 | 选目录弹窗 frontmost 机器半验受限（测试环境 Electron 抢焦点），SEV4，待领导亲验 | 真实 Chrome 前台场景验收 | Rex |
| 20 | 🟢低 | 安全 | server.py:305-307 | `/tmp/rvc-pick-folder.log` 无界追加、/tmp 可被本机其他用户 symlink 覆盖 | 移到 ~/Library/Logs 并限大小 | Cody |
| 21 | 🟢低 | 可维护性 | content.js:935-940,973-979,1266-1275,1303-1307 | 后退/前进 ±1s 逻辑重复约 8 处 | 抽 `seek(delta)` 辅助函数 | Cody |
| 22 | 🟢低 | 文档 | README.md 等 | 热键作用范围三种说法（README"必须悬停"/安装说明"需在播放器上方"/内部版"任意位置"），代码证明为 document 级无悬停判断 | 统一为"页面任意位置" | Docu |
| 23 | 🟢低 | 文档 | README-内部版.md | 版本 v3.2.0 过期（实际 v3.2.2）、"修复进行中"描述已修复未删、.crx 主路径与分发 zip 冲突 | 逐条清理（详见 Docu 原始产出） | Docu |

## 🏗️ 架构影响评估

- **信任边界缺陷（高危）**：架构依赖"只监听 127.0.0.1"作为唯一信任边界，但 CORS `*` + 无 Origin/Host 校验 + 无 token 使该边界形同虚设——任意恶意网页（用户访问后）即可当"本地客户端"使用全部 API。Archi 建议：短期限 Origin 白名单 + token；中远期记 ADR-02（本地信任边界与鉴权模型）。
- **架构优点**：热键隔离设计正确（子进程被 SIGKILL 不影响主服务）、边转边播取舍正确（规避 WASM 内存上限）、manifest 权限最小化到位、事故记忆结构化（BLOCKED/PROGRESS 回滚路径清晰）。
- **文档漂移**：README 声称 aiohttp，实际 server.py 为 `http.server` + `ThreadingMixIn`（线程模型叠加 SSE 无上限 → 放大 #4）。
- **ADR 建议**：ADR-01 转码基线（libx264 + MPEG-TS，禁止未经真实大 MKV 流式验证的编码器切换，固化 B10 教训）；ADR-02 本地信任边界与鉴权模型；ADR-03 热键隔离事件链选型记录。

## 🧪 测试覆盖评估

- **覆盖矩阵**（Tessa）：A-H 12 项全过，但多项为"弱/中"——A 只查 DOM 存在、C 走 MP4 直发不测转码、D 只测本地 keydown 不测 SSE、G 零覆盖等比缩放。
- **基建缺陷**：B1（profile 污染，6/12→1/12 崩）与 B9（F 步 flaky ~1/3）根因明确，短期沿用 rm -rf 裁决，中期走 sha256 解冻流程修复 content.js 时序。
- **高风险缺口（优先级排序）**：①路径穿越（安全）②真实大 MKV 流式转码（B10）③SSE 热键 E2E ④转码失败/损坏文件 ⑤并发 stream 竞态。
- **分层建议**：新增 `tests/test_server_api.py`（单测/集成，fake ffmpeg）+ `tests/e2e_extra.py`（Playwright 独立）+ `run_tests.sh` 统一入口——全部不触碰 sha256 冻结文件。

---

## 🚨 事故响应（工作流 3）

### 事故时间线（B10 转码回归，已解决）
- **引入**：某会话将转码命令改为 `h264_videotoolbox -b:v 2M`（硬件编码）
- **基准**：ffmpeg 单独 benchmark videotoolbox 更快（0.35s/30x vs libx264 0.29s/22x）
- **验收**：12/12 通过（sample.mp4 过小，未覆盖真实大 MKV 流式播放）
- **发现**：用户实测「转码依旧慢 / 实际播放看不了」
- **回滚**：server.py 回滚 libx264（L492）+ 重建 .app（17 dylib + libx264）+ 重建分发包；附带修复 build.sh dylib 递归收集

### 影响范围
- 事发时 SEV2（主要功能受损：播放看不了/转码慢）；仅影响本地用户（领导本人），无多人影响；已解决。

### SEV 评级（当前）
| 编号 | 问题 | SEV | 状态 |
|------|------|-----|------|
| B10 | videotoolbox 转码回归 | 已解决（事发 SEV2） | 已回滚+重建产物 |
| 新增 | 分发产物与源码不同步（keys-panel 删除版） | SEV3 | 待领导决策是否重建 |
| B13 | 选目录弹窗 frontmost 待亲验 | SEV4 | 待领导亲验，不阻塞 |
| B1 | 验收 profile 跨 run 污染 | SEV4 | 已裁决绕过，技术债 |
| B7 | manifest 偏离白名单（+127.0.0.1:8899） | SEV4 | 已记录，建议豁免文档化 |
| B9 | 验收 F 步 flaky | SEV4 | 已记录，sha256 冻结期不修 |

### 根因（B10 · 5-Why）
1. 播放看不了？→ videotoolbox 输出的 H.264 流 mpegts.js 无法解码/播放
2. 为何无法解码？→ 硬件编码 profile/level、GOP 关键帧间隔或输出格式不适配 MPEG-TS 流式（三候选，未验证）
3. 为何 benchmark 没暴露？→ **benchmark 测的是"编码速度"而非"输出流可播放性"**，两套指标
4. 为何验收 12/12 没暴露？→ sample.mp4 过小 + 未做真实浏览器长时间流式播放
5. 为何无端到端验证？→ 缺「改编码器必须用真实大文件过浏览器」的强制检查清单

**教训**：benchmark 快 ≠ 播放器能用；验收通过 ≠ 真实可用；高风险变更（编码器/打包）必须端到端冒烟通过后才替换产物。

### 预防措施
1. **真实大文件冒烟测试**：≥1GB 真实 MKV（含 AC3/DTS 音频）+ 浏览器 mpegts.js 实测播放 ≥30s、可 seek，作为编码器/转码参数变更强制门禁（固化为 check.sh 并入 build.sh）
2. **启动自检增强**：加 `ffmpeg -encoders | grep libx264` 编码器可用性检查（现有探活已覆盖 /api/files）
3. **产物一致性检查**：源码 ↔ .app ↔ zip 三方指纹对齐（git diff 为空 + 关键文件 sha256），防 SEV3 类漂移
4. **单机监控现实**：依赖三件事——/tmp/rvc-server.log 异常关键字检查、一键启动探活、变更门禁（冒烟+指纹）

---

## ✅ 行动清单（按优先级排序）

| # | 行动 | 负责角色 | 紧急度 | 预期完成 |
|---|------|---------|--------|---------|
| 1 | 修 Critical#1/#2：加共享 token + CORS 白名单（aim-read.top + chrome-extension://）+ Origin/Host 校验 + `/api/file` realpath/commonpath 路径校验 | 开发（Cody 规格） | P0 | 下个迭代 |
| 2 | 修 Critical#3：content.js 所有 innerHTML 拼接改 textContent / 转义（文件名/目录名/error） | 开发（Cody 规格） | P0 | 下个迭代 |
| 3 | 修 Critical#4：SSE 单例管理（重连前 close 旧实例）+ 服务端心跳保活 + 连接数上限 | 开发（Cody 规格） | P0 | 下个迭代 |
| 4 | 决策 keys-panel 恢复版是否重建 .app + zip（消除 SEV3 分发漂移） | 领导 | P0（决策） | 待确认 |
| 5 | 落地编码器变更端到端冒烟清单（check.sh 并入 build.sh）+ 启动自检 libx264 检查 | Rex + 开发 | P1 | 下次改编码器前 |
| 6 | 新增 test_server_api.py（路径穿越/API 分支/fake ffmpeg）+ e2e_extra.py（SSE 热键 E2E/大 MKV 流式） | Tessa | P1 | 下一迭代 |
| 7 | 领导亲验 B13 选目录前置（真实 Chrome 前台） | 领导 | P1（半托验收） | 下次实际使用 |
| 8 | 补 server.py 关键路径 pytest + ffmpeg stderr 可观测 + 首帧超时 | 开发 + Archi | P1 | 下一迭代 |
| 9 | B9 根因修复走 sha256 解冻流程（storageReady 后再 loadFileList）；B1 换唯一临时 profile | Tessa + 团队 | P2 | 解冻后 |
| 10 | 文档清理：版本号单一事实源、热键作用范围统一"页面任意位置"、README-内部版过期描述删除、补排障 Runbook | Docu | P2 | 后续会话 |

---

## ⚠️ 待完善 / 已知局限

- **只读审查**：本次未修改任何系统文件，未运行验收（acceptance.py 需起服务器 + Playwright 环境），覆盖基于静态分析与成员领域经验。
- **B10 三候选根因未实证**：videotoolbox 与 mpegts.js 不兼容的具体机制（profile/level vs GOP vs 封装）未复现验证，预防措施以门禁为主。
- **sha256 冻结约束**：content.js / acceptance.py / test.html 冻结，B9 等修复必须走基线变更流程（记 BLOCKED → 改 → 重算哈希 → 判卷方认可 → 全量回归）。
- **分发产物待重建**：源码已含 keys-panel 恢复，但 .app/zip 为删除版，本次未重建（领导未确认）。
- **B13 半验**：弹窗前置受测试环境 Electron 抢焦点干扰，需领导在真实使用场景亲验。

---

## 📚 数据来源 & 成员产出索引

- **Cody（代码审查师）**原始产出：整体 🔴 不通过；4 Critical + 4 High + 5 Medium + 3 Low；给出文件:行号级证据（server.py:209/361/464、content.js:397-603/1283-1314 等）。
- **Archi（架构师）**原始产出：架构总览（http.server 非 aiohttp 文档漂移）、6 项风险表、3 条 ADR 建议、短/中期演进方向。
- **Rex（SRE 工程师）**原始产出：SEV 评级表（新增 SEV3 分发漂移）、B10 时间线 + 5-Why、6 条行动项、6 条预防措施。
- **Tessa（测试专家）**原始产出：A-H 覆盖矩阵（弱/中评价）、B1/B9 根因与解冻流程、12 项缺口清单、分层测试策略。
- **Docu（文档师）**原始产出：6 文档健康度评级、13 条准确性偏差、README-内部版逐条过期清单、4 类文档债。

---

> 本报告由工程保障团队 AI 协作生成，关键决策请由人类工程负责人复核。
