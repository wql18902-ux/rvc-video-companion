# RVC 视频伴侣 · 全面工程审查 + 事故响应复盘（组合报告）

**日期**：2026-08-01
**工作流**：工作流 1（全面代码审查）+ 工作流 3（事故响应）组合，并并入工作流 5（技术债）的架构债/测试债/文档债
**参与成员**：科迪（Cody · 代码审查）/ 阿奇（Archi · 架构）/ 雷克斯（Rex · SRE）/ 泰莎（Tessa · 测试）/ 多库（Docu · 文档）
**触发**：用户请求对系统进行全面工程审查，并对 2026-08-01 系列事故运行完整事故响应流程。
**主理人**：甄宇航（Zhen · 工程督导）—— 编排、亲验硬事实、去重汇编。

---

## 📌 TL;DR（执行摘要）

- **整体结论**：运行时架构成熟克制（进程隔离/端口幂等/秒挂探测/SSE 保活），安全修复扎实（4 Critical 已闭环，MTTR≈20min）；真正的系统性病灶在**构建/分发/一致性这条工程管线**，根因一句话——**「做完了 ≠ 做对了」，缺少出包/上线前的自动化门禁**。
- **严重度分布（去重合并后）**：🔴严重(P0) **6** 项 / 🟠高 **9** 项 / 🟡中 **11** 项 / 🟢低 **7** 项。
- **阻塞 / 非阻塞**：6 个 P0 中 **2 个直接阻断真实用户**（.app 产物未重建=下载即坏；热键 IME 脏值=改键即失灵且救不回），必须本轮闭环；其余为治本项。
- **最高优先级**：① 重建 .app 产物（SEV1 暴露面至今未关闭）；② 修复热键 IME P0；③ 建立出包门禁（签名/安全/一致性三道）。
- **诚实记录**：本报告两位成员的初稿均出现硬事实偏差（测试专家一度误判"测试体系不存在"、代码审查一度把 pick-folder 误定性为"鉴权豁免"），均经主理人磁盘亲验拦截更正，详见「已知局限」。

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| 整体评级 | 🟡 **有条件通过**（运行时可用、安全已闭环；但分发产物未重建 + 2 个用户可感知 P0 未修，不具备对外发布条件） |
| 阻塞项数量 | **6（P0）**，其中 2 个直接阻断用户 |
| 关键行动项 | **18 条**（P0×6 / 高×6 / 中×4 / 低×2，见行动清单） |
| 建议下一步 | 用户拍板 D1（国内分发主路径）+ D2（是否本轮重建 .app）→ 按行动清单 1→6 顺序一次性落地，不再分批改 |

---

# 第一部分 · 全面代码审查（工作流 1）

## 🔍 审查发现（五成员去重合并 · 按严重度排序）

> 说明：五人独立排查，主理人去重合并并按磁盘亲验校准行号与定性。来源标注：Cody=代码审查 / Archi=架构 / Rex=SRE / Tessa=测试 / Docu=文档 / 整=整顿报告既有项。

| # | 严重度 | 类别 | 文件:行 | 问题描述 | 建议修复 | 来源 |
|---|--------|------|---------|---------|---------|------|
| 1 | 🔴P0 | 正确性 | content.js:1320-1327 | 改键捕获未过滤 IME 合成态（`e.isComposing`/keyCode 229）、未校验单字符 ASCII，中文候选词「一个」被录入 storage，致「后退」乱码且按 A 失效 | 捕获前加 `if(e.isComposing\|\|e.keyCode===229)return;` + `/^[a-z0-9]$/` 单字符校验 + 修饰键过滤 | Cody+Rex+整 |
| 2 | 🔴P0 | 正确性 | content.js:1304-1308 | 恢复键值用 `saved.x\|\|默认`，脏值「一个」是 truthy 致兜底失效，「恢复默认」也救不回 | 改 `isValidKey(saved.x)?saved.x:DEFAULT`，合法性校验替代 truthy 兜底；写入端统一 normalize | Cody+Rex+整 |
| 3 | 🔴P0 | 体验/品牌 | manifest.json:3 | 扩展名 `"Reader 视频伴侣"` 混英文触发 Chrome 机翻成「视频合作伙伴」 | name 改纯中文 `"RVC 视频伴侣"` | Docu+Cody+整 |
| 4 | 🔴P0 | 分发 | Release v3.2.2 | 穿马甲冗余资产：`RVC.zip` 用 label 伪装成 `RVC-Video-Companion.zip`，页面两个同名包用户不知下哪个 | 删 `RVC.zip`（**不可删** RVC-Video-Companion.zip）；落上传三铁律 | Rex+整 |
| 5 | 🔴P0 | 签名/分发 | stream-server/packaging/dist | build.sh 签名修复已提交(f2530c0)，但**产物未重建**，dist 仍是 18:01 损坏旧版 → 用户下载双击报「已损坏」死路（SEV1 暴露面未关闭） | 沙箱外重跑 build.sh + 签名验收门禁 + 重打 zip 覆盖 Release | Rex+整 |
| 6 | 🔴P0 | 一致性/SSOT | manifest.json:4 / build.sh:166-167 / make-distro.sh:189 / content.js:56 | 版本号四处硬编码互不一致（3.2.0 / 3.2.2），改一处忘三处是「整体乱」根因 | manifest.json#version 为唯一源，构建期读取注入 + L0 一致性校验脚本 | Archi+Cody+整 |
| 7 | 🟠高 | 安全 | stream-server/server.py:291,434 | `/api/pick-folder` 过 check_origin 但无 action/频控，白名单 Origin 或 XSS 攻陷的 aim-read.top 可反复触发系统级 NSOpenPanel 弹窗 = **白名单内 DoS 放大点**（主理人校准：非"鉴权豁免"，所有 /api/* 均过 check_origin） | 加调用频控/节流；或要求用户手势 token | Cody（主理人校准定性） |
| 8 | 🟠高 | 安全/分发 | packaging/install.sh:6,15,34 | `curl\|bash` 全管道无 checksum/签名校验；ZIP_URL 指向 GitHub release 国内不通；下载即 unzip 执行 | 加 sha256 校验 + 国内镜像 fallback；install-source.sh 同理 | Cody+Rex+整 |
| 9 | 🟠高 | 一致性 | 用户所装 .app 内嵌扩展 | 内嵌扩展是旧快照（含 Reader 旧版），是「撞全不一致」直接体现 | 改源后重跑 build.sh+make-distro.sh 同步；内嵌扩展改构建期现打禁拷快照 | Docu+Rex+整 |
| 10 | 🟠高 | 品牌 | content.js:102 / player.html / start.sh / build.sh / rvc-server.spec | 品牌名三套写法（视频伴侣 / RVC 流式播放器 / RVC 视频伴侣） | 统一 `RVC 视频伴侣`，定 BRAND 常量派生 | Docu+整 |
| 11 | 🟠高 | 文档/分发 | README.md:35-53 | 把国内走不通的 `curl\|raw.githubusercontent` 列「方式一（推荐）」，真主路径「手动下载」被排方式三 | 手动下载提为方式一，curl 降「开发者/海外可选」附注 | Docu+整 |
| 12 | 🟠高 | 分发 | 发版无单一入口 | build/make-distro/upload 各跑各的，全靠记忆，已酿成穿马甲资产事故 | 落 release.sh 串联 11 步 + 上传三铁律（禁 --clobber/--label、uniq 核验计数=1） | Archi+整 |
| 13 | 🟠高 | 流程 | scripts/install-hooks.sh:28 / .git/hooks/pre-push | pre-push 跑全量验收（分钟级、需 server+Playwright），B9 flaky~1/3 误拦，push 脆弱被 --no-verify 击穿 | pre-push 降为 `check.sh --static`；验收移 release.sh 发版前门禁 | Archi+Rex+整 |
| 14 | 🟠高 | 测试 | tests/（整体） | 无 CI，回归全靠手动；打包版 .app 从未被自动化验证；冻结指纹无自动校验（B14 存档曾过期） | 建 GitHub Actions macOS runner：sha256+语法+acceptance.py；中期加 build→.app→smoke | Tessa+Rex |
| 15 | 🟠高 | 文档 | README-内部版.md:3,23,31 | 版本标 v3.2.0（应 3.2.2）；「已知缺陷修复进行中」过期（热键隔离已完成 b3fb30b）；.crx 拖拽仍当主路径（Chrome 117+ 已限） | 更新版本/删过期缺陷/.crx 降「管理员参考」，主路径统一「加载已解压」 | Docu |
| 16 | 🟡中 | 分发 | make-distro.sh:44-91 | 「首次打开-点我.command」自身也被 Gatekeeper 拦（鸡生蛋） | 删 .command，清隔离统一为终端一行 `xattr -cr` | Docu+整 |
| 17 | 🟡中 | 健壮性 | packaging/install.sh:52,59-60 | unzip 解 .app 中文/资源叉支持差；`mv "$NESTED"/.*` 匹配 `.`/`..` 报错被吞（L60 磁盘确认） | 改 `ditto -xk`；嵌套移动改 `find -mindepth 1 -exec mv` | Rex+Cody |
| 18 | 🟡中 | 健壮性 | packaging/install.sh:87 | 启动校验仅 sleep 2 易误报；后台进程脚本退出后可能被回收 | 轮询重试 + 端口占用检测 | Rex |
| 19 | 🟡中 | 可运维性 | start.sh:12 / check.sh / install.sh | 健康探测复用业务接口 `/api/files?dir=~`，语义耦合（鉴权/参数变更即误判「没起」）；日志 print 到 /tmp 无轮转、无结构化 | 加 `GET /api/health` 返回 {ok,version,pid,ffmpeg}；日志加时间戳前缀 | Archi |
| 20 | 🟡中 | 安全 | stream-server/server.py (control-key) | `POST /api/control-key` 不校验 action 白名单（残留低危，可广播任意 action 字符串） | 校验 action ∈ {toggle_play,back,forward} | Cody |
| 21 | 🟡中 | 测试 | tests/acceptance.py F步 | B9 flaky~33%：storageReady 异步竞态，reload 后 pinnedDirs 未恢复即渲染 0 chip | showFolderOverlay() 加 `await storageReady`（storageReady Promise 已存在） | Tessa+整 |
| 22 | 🟡中 | 测试 | run_tests.sh / 手动 | B1 profile 跨 run 污染，需手动 `rm -rf /tmp/rvc-pw-profile-accept` | 建 run_acceptance.sh wrapper 自动清 profile+起 server+跑测+汇总 | Tessa+整 |
| 23 | 🟡中 | 测试 | tests/（整体） | MKV/MOV 转码路径零覆盖（sample.mp4 走直读，从未触发真实 ffmpeg 正向流）；负向路径虽有 e2e-error-path.py 但场景有限 | 生成 <5s MKV fixture 验 /api/stream 输出 MPEG-TS；补服务器离线/无权限/畸形 Range 用例 | Tessa |
| 24 | 🟡中 | 文档 | PROGRESS.md:5-19 vs 197-207 | 顶部「PENDING 阻塞」与后文「已完成」自相矛盾；哈希基准 PROGRESS 与 BLOCKED 两套说法 | 顶部 PENDING 标「已解决」；哈希以 git HEAD 实测统一 | Docu |
| 25 | 🟡中 | 文档 | README.md:123 | 目录树把 build.sh 画在 `packaging/` 下，实际在 `stream-server/packaging/` | 修正路径 | Docu |
| 26 | 🟡中 | 文档 | README-内部版.md:57 | FAQ 重复过期缺陷症状描述（主理人校准：「修复进行中」字样在 L23，L57 仅症状，方向对行号略偏） | 同步 L23 修正 | Docu（主理人校准行号） |
| 27 | 🟡中 | 文档 | README.md vs README-内部版.md | 两份 README 职责边界模糊，读者不知看哪份 | README=终端用户；内部版=维护者，各加「本文面向」声明 | Docu |
| 28 | 🟢低 | 治理 | packaging/ vs stream-server/packaging/ | 两打包目录职责重叠、命名近似 | 不物理合并，README 厘清分工表 | Archi+整 |
| 29 | 🟢低 | 扩展性 | server.py (current_proc) | 全局单 ffmpeg 单例 + kill_current_proc 全局互斥，不支持并发流（单用户 OK，多标签互抢） | 当前接受，标注「单机单流」约束；演进按 req_id→proc 注册表 | Archi |
| 30 | 🟢低 | 可运维性 | server.py (hotkey-child) | 子进程生命周期靠「自检 10 次自尽 + pkill 兜底」，无 supervisor | 当前接受；若上 launchd 用 KeepAlive 托管 | Archi |
| 31 | 🟢低 | 测试 | tests/e2e-wasm-test.py / e2e-wasm2.py | 死代码，引用已删除的 wasm 目录/不存在路径 | 删除或移入 archive/，PROGRESS 记录 | Tessa |
| 32 | 🟢低 | 测试 | tests/（整体） | 无 requirements.txt / 依赖锁定；acceptance.py 硬编码端口 8899/8765、profile 路径；无 JUnit/JSON 结构化输出 | 建 tests/requirements.txt；参数化端口；加结构化报告 | Tessa |
| 33 | 🟢低 | 文档 | PROGRESS.md（361行） | 进度流水账与长期参考（接口约定/历史经验/当前状态）混杂，无目录锚点 | 拆 STATUS.md（当前状态+接口约定）+ 日志留 2 周 + 历史归 iterations/ | Docu |

---

## 🏗️ 架构影响评估（阿奇 · Archi）

**整体判断**：作为「本机单用户工具」，运行时架构合理且克制——hotkey 子进程隔离（躲 macOS 输入监控 SIGKILL）、端口幂等启动、ffmpeg 秒挂探测、SSE 心跳保活+连接上限、结构化错误码透传，均为成熟手法。**真正的债不在运行时，而在构建/分发/一致性这条工程管线**（与整顿报告结论一致）。

### 关键 ADR（决策记录）

- **ADR-001 · 版本号与品牌名单一事实源（SSOT）**：manifest.json#version 为唯一源，build/make-distro 运行时读取注入；新增 L0 一致性校验 grep 全仓比对。（对应 #6/#10）
- **ADR-002 · 统一发版管线 release.sh + 门禁前移**：release.sh 串联 11 步（bump→full test→build→distro→tag→清同名 asset→上传→uniq 核验）；pre-push 降 --static，验收移发版门禁。（对应 #12/#13）
- **ADR-003 · .app 签名策略**：短期维持 ad-hoc + 删 .command 解鸡生蛋、固化「一行 xattr」；当用户量上升时升级 Apple Developer ID + notarization（$99/yr）彻底消除 Gatekeeper 拦截与权限漂移。（对应 #5/#16）
- **ADR-004 · 可观测性**：加 /api/health、启动横幅打印版本、日志加时间戳；健康探测改用 /api/health。（对应 #19）
- **ADR-005 · 进程模型约束记录**：单 ffmpeg 单例 + 子进程无 supervisor，标注为已知约束，演进方向为 req_id→proc 注册表 / launchd KeepAlive。（对应 #29/#30）

### 风险与权衡（诚实标注）

1. **门禁前移的风险**：验收从 pre-push 移到 release.sh = push 不再保证验收绿；权衡为确定性静态门禁（秒级）+ 发版强制验收，比 flaky 全量钩子更可能被真正遵守。
2. **ad-hoc 签名的体验天花板**：不上 Developer ID，「下载被拦」是结构性的，脚本兜底只是补丁——不要给用户「改完一劳永逸」的错误预期。
3. **SSOT vs 灵活性**：content.js LAYOUT_SCHEMA 等语义化版本标记建议纳入校验白名单而非强行派生。

---

## 🧪 测试覆盖评估（泰莎 · Tessa，已基于磁盘实测更正）

> ⚠️ 更正说明：初稿误判「L0/L1/L2 测试体系不存在」，经主理人磁盘核实推翻（scripts/check.sh、tests/test_server_api.py 29 用例、e2e_extra.py 5 用例、e2e-error-path.py、run_tests.sh 均真实存在），以下为基于逐行阅读的重算结论。

### 分层测试实况（磁盘确认）

| 层 | 文件 | 用例 | 状态 |
|----|------|------|------|
| L0 静态 | scripts/check.sh | 11 项（sha256 冻结+node -c+bash -n×4+py_compile+emoji） | ✅ 存在且可用 |
| L1 单测/集成 | tests/test_server_api.py | 29（鉴权/穿越/Range/列表/树/时长/control-key/SSE/转码失败/端口） | ✅ 存在 |
| L2 真实 E2E | tests/e2e_extra.py | 5（转码失败/端口占用/播放中断/正向对照） | ✅ 存在 |
| 失败路径 | tests/e2e-error-path.py | 8（坏 MKV 注入） | ✅ 存在 |
| L3 验收（冻结） | tests/acceptance.py | 12（Playwright，sha256 冻结不可改） | ✅ 存在 |
| 统一入口 | run_tests.sh | L0→L1→L2→汇总 | ✅ 存在 |

### 覆盖缺口（仍成立的真问题）

- **后端**：`/api/pick-folder`（NSOpenPanel）、`/api/health`（尚不存在）、ffmpeg 命令构建（seek/编码参数）、PyInstaller find_ffmpeg_bin、信号处理——零自动化覆盖。
- **前端新功能**：keys-panel（恰是热键 IME P0 所在模块！）、目录树弹窗、8 方向缩放、进度条 seek、自动续播、Media Session——零测试。
- **负向路径**：服务器离线时前端行为、无权限目录、畸形 Range 头——未覆盖。

### 测试维度评分（更正后）

| 维度 | 评分 | 说明 |
|------|------|------|
| 测试覆盖率 | 6/10 | 后端核心 API 有 L1 守护，但转码正向流/前端新功能/pick-folder 缺 |
| 层级完整性 | 7/10 | L0-L3 四层真实存在（初稿误判为 1 层） |
| 测试可靠性 | 5/10 | B9 F步 flaky~33%、B1 需手动清 profile |
| 负向路径 | 4/10 | 有 e2e-error-path 但场景有限 |
| CI/自动化 | 2/10 | 无 CI，全手动（真实短板） |
| 冻结策略 | 6/10 | 判卷价值有效，但缺自动校验且阻碍演进 |

---

# 第二部分 · 事故响应复盘（工作流 3）

## 📋 事故汇总表（雷克斯 · Rex）

| # | 事故 | SEV | 状态 | 根因（一句话） | 关键预防 |
|---|------|-----|------|--------------|---------|
| 1 | .app 签名链路断裂（「已损坏」死路） | **SEV1** | 源码已修(f2530c0)，**产物未重建（dist 仍损坏）** | build.sh 把 `_internal/` 平铺进 Frameworks，codesign 把数据文件当代码签 → bundle 不完整 → spctl 判损坏 | 出包强制 codesign/spctl 门禁，未过不许出包；产物重建纳入受控环境 |
| 2 | 热键 IME 输入法 bug（脏值持久化） | **SEV2** | **P0 待修** | 改键捕获未过滤 isComposing/229、未校验单 ASCII；恢复用 truthy 兜底使脏值绕过 | 输入白名单 + 落盘前 schema 校验 + 兜底用合法性而非 truthy |
| 3 | 分发一致性失控（版本/品牌/扩展漂移） | **SEV3** | 整顿报告已出，待拍板 D1/D2 | 无 SSOT，多处手工同步改一漏三 | 版本 SSOT + 出包自动派生，禁手工拷快照 |
| 4 | 4 个 Critical 安全漏洞 | **SEV2（安全）** | 已修复并验收 12/12 全绿(138b11e) | 无鉴权 + CORS `*` + 无路径校验 + innerHTML 直拼 + SSE 无上限 | 安全基线门禁（CORS/innerHTML/safe_join）纳入必跑 |

> **SEV 标准**（多库建议补充，本报告采纳）：SEV1=用户完全不可用/数据丢失且无自助逃生；SEV2=核心功能降级或安全暴露；SEV3=流程/一致性偏差。

## 🕐 关键事故时间线与 5-Why

### 事故 1 · .app 签名断裂（SEV1，最高优先级）
- **时间线**：发现（用户反馈「已损坏」区别于未公证 app 可绕过）→ 定位（codesign 逐数据文件报 unrecognized）→ 修复（官方布局+4步分步签名，提交 f2530c0）→ **验证未完成**（产物重建被沙箱拦 `rm -rf staging` >50 文件）。
- **5-Why**：打不开 → Gatekeeper 判损坏 → codesign verify 失败 → 数据文件混进 Frameworks 被当代码签 → build.sh 未按 Apple 官方布局分离 → **打包流程无签名验收门禁，build 成功=出包成功**。
- **当前态**：源码已修但用户能下载到的产物仍坏 → **暴露面未关闭**。

### 事故 2 · 热键 IME（SEV2，P0 待修）
- **代码定位（磁盘确认）**：捕获处 content.js:1320-1327 未判 isComposing/keyCode 229、未校验单 ASCII；恢复处 1304-1308 `saved.x||默认` truthy 短路；匹配处 1352-1366 多字符绑定永不匹配。
- **5-Why**：按 A 失效 → keybindings.back 被写中文候选词 → 捕获直接取 e.key 未过滤 IME → 实现只考虑修饰键/Escape → 刷新不恢复因 truthy 兜底 → **持久化数据无 schema 校验（写端不校验、读端不校验）**。

### 事故 4 · 4 Critical 安全（SEV2，已修复 · 正面模板）
- **时间线（精确）**：19:45 核对基线 → 19:55 鉴权+CORS+safe_join → 19:57 escapeHtml → 20:00 SSE 单例+心跳+上限 → 20:05 回归 12/12 提交 138b11e。**MTTR≈20min，教科书级响应**。
- **5-Why（路径穿越）**：读 /etc/passwd → 路径直拼无规范化 → 无鉴权 CORS `*` → 初版「本地自用」假设未做威胁建模 → **无安全门禁**。
- **沉淀**：20min MTTR + 12/12 回归 + 白名单冻结纪律，可作为团队响应模板。

## 🛡️ 系统性预防措施（四起事故根因同源）

**三层防线**：
1. **流程层**：定义「完成」= 源码修复 + 产物重建 + 门禁验收三者齐备（事故 1 正卡在产物重建）；持久化数据规范「写前校验 + 读时合法性兜底（禁 truthy）」。
2. **工具层**：scripts/check.sh 扩展为 ① 签名门禁 ② 安全门禁（CORS/innerHTML/路径）③ 一致性 lint（版本/品牌）。
3. **自动化层**：打包/发布迁出易被沙箱拦截的手工环境进 CI；产物未过门禁禁止进 dist/release。

## ✅ 部署（出包/发布）检查清单

**Pre-build**：工作区干净+目标 commit 已提交；版本号在 SSOT 唯一来源；依赖锁定（pyinstaller/pynput）；ffmpeg/ffprobe 可用。
**Build gate（任一失败即 exit 1）**：`codesign --verify --deep --strict` 全绿；`spctl -a -vv --type execute`=rejected 且非 sealed resource；.app 启动冒烟 /api/* 全 200 + 热键子进程 kill -9 后主进程仍活；acceptance.py 12/12（跑前清 profile）。
**Security gate**：CORS `*` 残留=0；innerHTML 用户可控直拼=0；路径穿越回归 etc/passwd→404；SSE 并发上限生效。
**Consistency gate**：内嵌扩展构建期现打；版本/品牌全仓一致；产物命名带版本+日期无同名包；附 sha256 清单+来源 commit。
**Post-release**：干净环境下载→解压→双击冒烟（真实用户路径）；安装说明含权限授权；保留上一版产物+一键回退。

---

# 第三部分 · 技术债优先级（工作流 5 公式排序）

> 公式：`Priority = (Impact + Risk) × (6 - Effort)`，Impact/Risk 取 1-5，Effort 取 1-5（越小越省）。

| 排名 | 债务 | Impact | Risk | Effort | Priority | 来源 |
|------|------|:---:|:---:|:---:|:---:|------|
| 1 | 重建 .app 产物 + 签名门禁（#5） | 5 | 5 | 2 | **40** | Rex+整 |
| 2 | 热键 IME P0 修复（#1#2） | 4 | 4 | 1 | **40** | Cody+Rex |
| 3 | 版本/品牌 SSOT（#6#10，ADR-001） | 4 | 4 | 2 | **32** | Archi |
| 4 | release.sh 统一发版 + 上传铁律（#12#13，ADR-002） | 4 | 4 | 3 | **24** | Archi+Rex |
| 5 | 无 CI（#14） | 4 | 4 | 3 | **24** | Tessa+Rex |
| 6 | manifest 机翻名（#3） | 3 | 3 | 1 | **30** | Docu+Cody |
| 7 | install.sh 校验+国内 fallback（#8） | 4 | 4 | 3 | **24** | Cody+Rex |
| 8 | README 安装路径排序（#11） | 3 | 3 | 1 | **30** | Docu |
| 9 | 删 .command + xattr 一行（#16） | 2 | 3 | 1 | **25** | Docu |
| 10 | B9 flaky 修复（#21） | 3 | 2 | 1 | **25** | Tessa |

---

## ✅ 行动清单（按优先级排序）

| # | 行动 | 负责角色 | 紧急度 | 依赖 | 预期完成 |
|---|------|---------|--------|------|---------|
| 1 | 沙箱外重跑 build.sh 重建 .app + 签名验收门禁 + 重打 zip 覆盖 Release（闭环 SEV1） | 用户终端 + Rex 清单 | **P0** | D2 | 本轮 |
| 2 | content.js 改键 IME 过滤 + 恢复合法性校验（修 #1#2） | 开发 | **P0** | — | 本轮 |
| 3 | manifest name 去 Reader + 全仓品牌统一（修 #3#10） | 开发 | **P0** | — | 本轮 |
| 4 | 接单一版本源 + 四处版本号对齐 + L0 校验脚本（修 #6，ADR-001） | 开发 | **P0** | — | 本轮 |
| 5 | 删 Release 冗余 RVC.zip（修 #4，**不可删** RVC-Video-Companion.zip） | 开发(gh) | **P0** | 需确认 | 本轮 |
| 6 | 重跑 build.sh + make-distro.sh 让 .app/zip/内嵌扩展同步（修 #9） | 用户终端 | **P0** | #1-5, D2 | 本轮 |
| 7 | release.sh 串联 11 步 + 上传三铁律 + pre-push 降 --static（修 #12#13，ADR-002） | 开发 | 高 | — | 下周 |
| 8 | install.sh 多源 fallback + sha256 校验 + ditto 解压 + 启动轮询（修 #8#17#18） | 开发 | 高 | D1 | 下周 |
| 9 | README 安装路径重排（手动下载提方式一）+ 内部版清过期（修 #11#15#25#26#27） | Docu | 高 | — | 下周 |
| 10 | 建 GitHub Actions macOS runner：sha256+语法+acceptance.py（修 #14） | 开发 | 高 | — | 2 周内 |
| 11 | 加 /api/health + 日志时间戳前缀（修 #19，ADR-004） | 开发 | 中 | — | 2 周内 |
| 12 | 删 .command + 清隔离统一一行 xattr（修 #16，ADR-003 短期） | 开发 | 中 | — | 下周 |
| 13 | B9 flaky：showFolderOverlay 加 await storageReady（修 #21） | 开发 | 中 | — | 下周 |
| 14 | run_acceptance.sh wrapper 自动清 profile+起 server（修 #22） | 开发 | 中 | — | 下周 |
| 15 | /api/control-key 校验 action 白名单（修 #20） | 开发 | 中 | — | 下周 |
| 16 | MKV fixture 转码正向流测试 + 负向路径补充（修 #23） | Tessa | 中 | — | 2-4 周 |
| 17 | 评估 Apple Developer ID + notarization（ADR-003 中期，$99/yr） | 用户决策 | 低 | 用户量 | 里程碑 |
| 18 | PROGRESS.md 拆 STATUS.md + 死代码清理（修 #31#33） | Docu | 低 | — | 本月 |

---

## ⚠️ 待完善 / 已知局限

1. **D1/D2 待用户拍板**：D1（国内分发主路径：专家排序 top1=微信/QQ 直传 zip，人多升蓝奏云；curl|bash 降附注）；D2（是否本轮重建 .app 并清 Release 冗余）。
2. **build.sh 重建受沙箱拦截**：`rm -rf staging`（>50 文件）触发批量删除保护，需用户终端执行或授权——这是事故 1 暴露面至今未关闭的直接环境因素。
3. **主理人亲验拦截记录（诚实披露）**：
   - 测试专家初稿误判「测试体系不存在」，把 TD1/TD2/TD6 评 P0——经磁盘核实 scripts/check.sh、test_server_api.py(29) 等均真实存在，初稿被拦下重算。
   - 代码审查把 `/api/pick-folder` 误定性为「鉴权豁免」——实测所有 /api/* 均过 check_origin，已校准为「白名单内 DoS 放大点」（#7）。
   - 这两起偏差与阿奇/雷克斯强调的主线互为印证：**缺乏自动化核验，人工判断易漂移**。最终报告所有硬事实（行号/用例数/文件存在性）均已主理人磁盘复核。
4. **一人维护无 CI**：release.sh 仍需人手触发；治理设计已诚实标注「哪步还得手做」。
5. **ghproxy 等公共镜像不稳定**：仅作加速尝试不作唯一依赖。
6. **B13 选目录前置**：测试环境 Electron 抢焦点，frontmost 机器半验受限，待真实场景（Chrome 前台）亲验，不阻塞。

---

## 📚 数据来源 & 成员产出索引

- **科迪（Cody · 代码审查）**：33 项发现中的安全/正确性/可维护性条目；认证 4 Critical 修复扎实；新发现 pick-folder DoS 放大（经主理人校准定性）、curl|bash 无校验、control-key action 白名单残留。
- **阿奇（Archi · 架构）**：10 项架构债 + 5 份 ADR（SSOT/release.sh/签名策略/可观测性/进程模型）；补整顿报告未充分展开的健康探针语义耦合与单 ffmpeg 扩展边界。
- **雷克斯（Rex · SRE）**：4 起事故 SEV 评级 + 时间线 + 5-Why + 部署检查清单；SEV1 产物重建为最高优先级。
- **泰莎（Tessa · 测试）**：测试覆盖矩阵 + 测试债（基于磁盘实测更正版）；确认 L0-L3 四层真实存在，真缺口在转码正向流/前端新功能/pick-folder/CI。
- **多库（Docu · 文档）**：复盘文档清晰度评审 7.5/10（15 条改进建议）+ 14 项文档债 + 安装路径国内友好性评估 + 文档重构路线图。

---

> 本报告由工程保障团队 AI 协作生成，关键决策（D1/D2、Developer ID 投入）请由人类工程负责人复核后拍板。报告中所有硬事实（行号、用例数、文件存在性、SEV 定性）均经主理人磁盘亲验。
