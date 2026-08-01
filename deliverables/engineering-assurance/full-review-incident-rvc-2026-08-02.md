# RVC 视频伴侣 全面工程审查 + 事故响应 + 修复实施报告

**日期**：2026-08-02
**工作流**：工作流 1（全面代码审查）+ 工作流 3（事故响应）组合
**参与成员**：Cody（代码审查师）/ Rex（SRE 工程师）/ Tessa（测试专家）/ Archi（系统架构师）
**方案来源**：`/Users/Zhuanz/.workbuddy/plans/swift-thunder-newton.md`（v3.2.2 全面工程审查与事故响应计划）
**实施提交**：`0152371`（已推送 origin/main，f8fe12a..0152371）

---

## 📌 TL;DR（执行摘要）

- 整体结论：方案 Phase D2（P0）/D3（P1）/D4（P2）已按成员修正意见全部实施完成，**P3 状态机简化按架构师 ADR 决策单独立项**（本次不做）。
- 严重度分布：🔴严重 0 项 / 🟠高 1 项（验收环境代理 + 服务器生命周期问题，非代码缺陷，已在报告中记录） / 🟡中 2 项（Cody 指出 D2#4 竞态需 seq 守卫——已修复；方案 L0 数量过时——已修正）/ 🟢低 2 项（dir-browse-btn 不可删——已纠正；header/control hover 差异是有意的——保留）。
- 阻塞 / 非阻塞：**非阻塞**。全部测试门禁通过，代码已推送。

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| 整体评级 | 🟢 通过 |
| 阻塞项数量 | 0 |
| 关键行动项 | 5 条（见行动清单） |
| 建议下一步 | ① P3 状态机简化单独立项（Archi ADR）② 手动验证新文件选择 UX ③ 重打包发布 v3.2.2 |

---

## 🔍 审查发现（按严重度排序）

### 方案审查阶段（成员独立产出汇总）

| # | 严重度 | 类别 | 位置 | 问题描述 | 建议修复 | 来源 |
|---|--------|------|------|---------|---------|------|
| 1 | 🟠高 | 竞态 | content.js showFolderOverlay | D2#4「自动 loadFileList」与验收 C 步并发，陈旧响应会覆盖 FIXTURE_DIR 列表 | 加 seq 令牌守卫丢弃陈旧响应（**已实施**） | Cody |
| 2 | 🟡中 | 测试基线 | 方案 E4 | 方案写 L0「11/11」，实际为 14 项 | 门禁按 14/14 执行（**已按实际执行**） | Tessa |
| 3 | 🟡中 | 事故修复 | server.py serve_stream | D3「写入时机前移」写法几乎无效；finally 用全局 kill_current_proc 可能误杀新请求进程 | 服务端长轮询 + finally 只 kill 本请求进程（**已实施**） | Rex |
| 4 | 🟢低 | 清理 | player.css | 方案建议删 `.rvc-dir-browse-btn` 样式，但该按钮是目录树浏览（L600 绑定 showTreeOverlay） | 保留（**已纠正，未删**） | Cody |
| 5 | 🟢低 | 清理 | player.css | header-btn 与 control-btn hover 相似 | 差异是有意的（header 带 translateY 动效），合并会破坏视觉反馈 | Archi |

### 实施阶段引入并修复的问题

| # | 严重度 | 问题 | 处理 |
|---|--------|------|------|
| 6 | 🟡中 | H 步 emoji 检查失败：新增注释含 `→`（U+2192，在 EMOJI_RE 范围内） | 改为文字描述（**已修复**） |
| 7 | 🟢低 | 验收环境：HTTP_PROXY=127.0.0.1:52577 导致 Chromium 内 fetch 8765 失败 + Bash 跨调用清后台进程致服务器假死 | 清代理 + 单次调用内启动服务器（**环境问题，非代码缺陷**） |

---

## 🏗️ 架构影响评估（Archi）

**ADR 决策：本次只做 P0-P2，P3 状态机简化单独立项，待验收稳定后再做。**

1. **B1 按钮合并 + C1 Web 优先设计方向正确**：经实读 acceptance.py 验证，C 步测试路径是「手动输入路径 + 刷新」，从不走 Finder，Web 优先设计与验收门禁天然对齐；所有 acceptance 依赖选择器（.rvc-btn-folder / .rvc-dir-input / .rvc-dir-btn / .rvc-pin-btn / .rvc-pinned-chip / .rvc-btn-frameless / .rvc-btn-speed）全部保留。
2. **P3 高估了问题、低估了风险**：事实核查发现 isResizing/drag.active/capturingAction 本就是 DOM 事件瞬态，非持久顶层状态；真正有价值的 overlay 显示集中化无测试护栏且触及多数 handler。
3. **拆模块路径**：MV3 content script 多文件按序加载、同隔离世界，顶层 const/let 不跨文件可见——用**命名空间模式**（非 ES module），一次一个模块 + 每次跑门禁。

## 🧪 测试覆盖评估（Tessa）

- **当前基线**（实际运行确认）：L0 静态 **14 项**（方案文档写 11 项，过时）、L1 = 29、L2 = 5、L3 = 12。
- **E1 回归命令**：`rm -rf /tmp/rvc-pw-profile-accept && bash scripts/check.sh --static && bash run_tests.sh --full` 完整正确。
- **E4 门禁修正后**：静态 14/14 + 分层 L0 14/L1 29/L2 5 + 全量验收 12/12 + 判卷基准 sha256 不变。
- **3 个未覆盖回归点**（列入后续手动清单）：重开浮层自动列目录、LAYOUT_SCHEMA 删除后的旧 profile 兼容、慢速合法转码在 10s 窗口内不误杀。

## 🚨 事故响应评估（Rex）

- **SEV 评级**：SEV2（转码错误误报，功能可用但体验受损）。
- **修复方案**：`/api/stream-error` 改服务端长轮询（至多等 5s，200ms 间隔）替代客户端 2s 重试窗口；`serve_stream` finally 只终止本请求进程（规避全局 kill 误杀新请求）；客户端 fetchTranscodeError 简化单次请求 + 网络异常重试 3 次；转码兜底超时 15s→10s。
- **预期 SLO**：误报率 <1%、错误结果 P95 ≤5s、正常播放零回归（L2 转码用例 + L3 验收全绿验证）。

---

## ✅ 行动清单（按优先级排序）

| # | 行动 | 负责角色 | 紧急度 | 预期完成 |
|---|------|---------|--------|---------|
| 1 | 手动验证新文件选择 UX：点「加载视频」只弹浮层（不弹访达）、浮层自动列上次目录、点「浏览」才弹访达 | 用户/开发 | P1 | 下次使用前 |
| 2 | P3 状态机简化（overlay 集中化 + toggleMode('frameless')）单独立项，验收稳定后做 | Archi + 开发 | P2 | 下个迭代 |
| 3 | 手动回归：旧 profile 升级兼容（LAYOUT_SCHEMA 删除后） | 用户 | P2 | 下个版本前 |
| 4 | 手动回归：慢速合法转码（大 MKV）在 10s 窗口内正常播放不误杀 | 用户 | P2 | 下个版本前 |
| 5 | 重打包发布 v3.2.2（release.sh，需用户终端跑，沙箱拦 rm -rf） | 用户 | P1 | 方便时 |

---

## ⚠️ 待完善 / 已知局限

- **P3 未做**：按 Archi ADR 单独立项，理由见「架构影响评估」。
- **验收环境两坑**（记录备查，非代码缺陷）：① WorkBuddy 注入 `HTTP_PROXY=127.0.0.1:52577` 会让 Playwright Chromium 内 fetch 8765 失败，跑验收需 `env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy`；② Bash 工具跨调用清理后台进程，L3 需在**单次调用内**启动 8765 服务器。
- **手动测试清单**（方案 E2/E3）尚未在真实用户环境执行，依赖用户实际操作确认。

---

## 📚 数据来源 & 成员产出索引

- **Cody（代码审查师）**：P0/P2 审查——确认删除 openFolderViaFinder 安全（acceptance C 步不依赖 Finder）、D2#4 需 seq 守卫、dir-browse-btn 不可删、dirPickBtn title 需同步 updatePickBtnState。
- **Rex（SRE 工程师）**：P1 事故评估——长轮询优于 SSE 复用、finally 误杀隐患、SEV2 评级。
- **Tessa（测试专家）**：测试门禁核对——L0 14 项修正、E1 命令确认、3 个未覆盖回归点。
- **Archi（系统架构师）**：B/C/D5 架构评估——本次只做 P0-P2、命名空间模式拆模块路径。
- **方案原文**：`/Users/Zhuanz/.workbuddy/plans/swift-thunder-newton.md`

---

> 本报告由工程保障团队 AI 协作生成，关键决策请由人类工程负责人复核。
