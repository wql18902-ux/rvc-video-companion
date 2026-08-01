# RVC 视频伴侣 · 项目整顿报告（四方一致性 + 热键 bug + 分发治理）

**日期**：2026-08-01
**工作流**：技术债评估 + 代码审查（组合）
**参与成员**：Cody（代码审查）/ Archi（架构治理）/ Rex（SRE·分发）/ Docu（文档）
**触发**：用户作为真实 macOS 用户实测，发现"热键改不了、.app 启动有问题、标题怪、Release 两个包分不清、整体乱、安装麻烦"。

---

## 📌 TL;DR

- **整体结论**：项目功能本身没问题，崩在"四个副本各停在不同版本 + 一个真实输入 bug + 分发链路自相矛盾"。这是编排失职（为赶进度让源码/打包内嵌/Release/文档各说各话），不是用户操作问题。
- **严重度分布**：🔴 P0 共 4 项 / 🟠 高 5 项 / 🟡 中 6 项 / 🟢 低 4 项（去重合并后 19 条，见下）。
- **阻塞 / 非阻塞**：4 个 P0 里 2 个直接让用户"装上也用不了/看着像坏的"（热键、机翻标题），必须本轮修；其余为治本项。
- **核心病灶一句话**：没有"单一事实源"——版本号、品牌名、扩展副本、Release 资产各自维护，改一处其余三处忘跟，于是越攒越乱。

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| 整体评级 | 🟡 有条件通过（功能可用，但分发与一致性需整顿后才能对外） |
| 阻塞项数量 | 4（P0） |
| 关键行动项 | 19 条（含 2 项需用户拍板） |
| 建议下一步 | 用户确认 D1/D2 两个拍板点 → 我一次性落地"改源码→重打 .app→清 Release→推 GitHub"，不再分批改 |

---

## 🔍 审查发现（去重合并 · 按严重度排序）

> 说明：四人独立排查，下表已合并重复项（版本号/品牌名/旧产物三处被多人命中，合并为一条并标多来源）。行号经主理人核实。

| # | 严重度 | 类别 | 文件:行 | 问题 | 修复方向 | 来源 |
|---|--------|------|---------|------|---------|------|
| 1 | 🔴P0 | 正确性 | content.js:1320-1327 | 改键捕获未过滤中文输入法合成态、未校验单字符 ASCII，中文候选词"一个"被录进 storage，致"后退"显示乱码且按 A 失效 | 捕获前加 `if(e.isComposing\|\|e.keyCode===229)return;` + 单字符校验 + 修饰键过滤 | Cody |
| 2 | 🔴P0 | 正确性 | content.js:1304-1308 | 恢复键值用 `saved.x\|\|默认`，脏值"一个"是 truthy 致兜底失效，"恢复默认"也救不回 | 加 `isValid(k)` 合法性校验，非法回退默认 | Cody |
| 3 | 🔴P0 | 体验/品牌 | manifest.json:3 | 扩展名 `"Reader 视频伴侣"` 混英文 `Reader`，触发 Chrome 机翻成"视频合作伙伴"（全库 grep 该词 0 命中，证实为翻译产物） | name 改纯中文 `"RVC 视频伴侣"`，机翻不触发 | Docu+Cody |
| 4 | 🔴P0 | 分发 | Release v3.2.2 | 穿马甲冗余资产：`name=RVC.zip` 但 `label` 伪装成 `RVC-Video-Companion.zip`，页面显示两个同名包，用户不知下哪个（`--clobber`+label 制造） | 删 `RVC.zip`（**不可删** RVC-Video-Companion.zip）；定上传纪律 | Rex |
| 5 | 🟠高 | 一致性 | manifest.json:4 / build.sh:166-167 / README-内部版.md:3 | 版本号 `3.2.0` 残留三处，与 Release/文档的 3.2.2 不符 | 接单一版本源（见 A1） | Cody+Docu+Archi |
| 6 | 🟠高 | 品牌 | content.js:102 / player.html:6,186,276 / start.sh:2,26 / build.sh:3 / rvc-server.spec:2 | 品牌名三套写法（视频伴侣 / RVC 流式播放器 / RVC 视频伴侣） | 统一 `RVC 视频伴侣` | Docu |
| 7 | 🟠高 | 一致性 | 用户所装 .app 内嵌扩展 | 内嵌扩展是旧快照（停在含 Reader 的旧版），是"撞全不一致"的直接体现 | 改源后必须重跑 build.sh+make-distro.sh（见 A3） | Docu+主理人裁 |
| 8 | 🟠高 | 分发/国内 | install.sh:15 / install-source.sh:14 | ZIP_URL 指向 GitHub，国内慢/超时，无 fallback；脚本入口自身也走 raw.githubusercontent.com，国内 curl\|bash 基本走不通 | 多源 fallback + 国内改主路径（见 D1） | Rex |
| 9 | 🟠高 | 文档 | README.md:35-53 vs 71-78 | 把"curl 一行装"列方式一（国内走不通=误导），真主路径"手动下载"被排方式三 | 手动下载提为方式一，curl 降附注 | Docu |
| 10 | 🟡中 | 分发 | make-distro.sh:44-91 | 「首次打开-点我.command」自身也被 Gatekeeper 拦（鸡生蛋），与新方案理念冲突 | 删 .command，清隔离统一为终端一行 xattr | Docu（主理人采） |
| 11 | 🟡中 | 健壮性 | install.sh:52 | 用 unzip 解 .app，中文/资源叉支持差，可能丢签名结构 | 改 `ditto -xk`（与打包对称） | Rex |
| 12 | 🟡中 | 健壮性 | install.sh:59-60 | `mv $NESTED/.*` 匹配到 `.` `..` 报错（被吞） | 用 `find -mindepth 1 -exec mv` 或 ditto | Rex |
| 13 | 🟡中 | 健壮性 | install.sh:87 / install-source.sh:134 | 启动校验仅 sleep 2 易误报；后台进程脚本退出后可能被回收 | 轮询重试 + 端口占用检测 | Rex |
| 14 | 🟡中 | 文档 | README-内部版.md:23,57 / :全文 | "已知缺陷修复中"过期未删；.crx 拖拽仍当主路径 | 删过期缺陷说明；.crx 降级 | Docu |
| 15 | 🟡中 | 流程 | scripts/install-hooks.sh:28 / .git/hooks/pre-push:5 | pre-push 跑全量验收，需 server+Playwright，B9 flaky~1/3 误拦，push 脆弱 | 降为 `check.sh --static`，验收移发版前手动 | Archi |
| 16 | 🟢低 | 治理 | packaging/ vs stream-server/packaging/ | 两打包目录职责重叠 | 不物理合并，README 厘清分工（建议项） | Archi |
| 17 | 🟢低 | 文档 | README.md 结构 | 四套安装平铺、技术栈插中间打断阅读 | 重排：是什么→装(国内优先)→用→FAQ→开发者参考 | Docu |
| 18 | 🟢低 | 治理 | 发版无单一入口 | build/make-distro/upload 各跑各的 | 落 release.sh 串起 11 步 + 上传三铁律 | Archi |
| 19 | 🟢低 | 一致性 | content.js:56 / CLAUDE.md | 版本注释与文档版本标注 | 随 A1 单一源顺带对齐 | Cody |

---

## 🏗️ 治本设计（Archi · 单一事实源）

**版本号唯一源** = `reader-video-companion/manifest.json` L4。统一读法：
`VER=$(python3 -c "import json;print(json.load(open('reader-video-companion/manifest.json'))['version'])")`
派生四处：build.sh L156 heredoc 去引号 `<<'EOF'`→`<<EOF`、L166-167 `3.2.0`→`$VER`；make-distro.sh L94 去引号、L189 `v3.2.2`→`v$VER`；README-内部版.md L3 手动（checklist 提醒）；git tag 自动 `v$VER`。

**发版 11 步 + 上传三铁律**（防再出穿马甲资产）：上传前必 `delete-asset` 清同名、**禁用 `--clobber`、禁用 `--label`**、上传后 `uniq -c` 核验每个资产计数=1。

**pre-push 钩子**：降为 `--static`，验收移发版前手动跑（理由：验收重、B9 flaky 误拦、一人无 CI 高频 push 被打断心流）。

---

## ⚖️ 主理人裁决（两处成员冲突，已裁，不甩给用户）

1. **.command 删留** → **采 Docu，删**。Rex 的"微信 3 步"第②步又用 .command，与多库"鸡生蛋"结论打架；删 .command，清隔离统一为终端一行 `xattr -cr`。
2. **aim-read.top 引导删留** → **采保留，驳回 Rex#6**。Rex 把"aim-read.top 不能当 CDN"误读成"不能引导访问"；插件本就是给该站用的，引导用户打开它**正确**。仅 install.sh 的"下载源"不能依赖它，引导访问保留。

---

## ❓ 需用户拍板的 2 个决策点

- **D1（国内分发主路径）**：专家排序 top1=微信/QQ 直传 zip（少量朋友、25MB 远低于上限、零成本），人多了升蓝奏云；curl\|bash 因国内连 raw 慢，降为"能翻墙者可选"附注。**是否按此定？** 或你要 Gitee 镜像 / 对象存储？
- **D2（.app 何时重建）**：热键+品牌+版本都改在源码，**必须重跑 build.sh+make-distro.sh** 才能让 .app/zip/内嵌扩展同步（否则用户装到的还是旧快照）。重建 .app 需你在终端跑（沙箱拦 rm -rf staging）。**是否本轮一并重建并清 Release 冗余？**

---

## ✅ 行动清单（落地顺序，含负责方）

| # | 行动 | 负责 | 紧急度 | 依赖 |
|---|------|------|--------|------|
| 1 | content.js 改键 IME 过滤 + 恢复合法性校验（修 #1#2） | 我 | P0 | — |
| 2 | manifest name 去 Reader + 全仓品牌统一（修 #3#6） | 我 | P0 | — |
| 3 | 接单一版本源 + 三处版本号对齐（修 #5，含 build.sh heredoc） | 我 | 高 | — |
| 4 | 删 .command + 清隔离改一行 xattr（修 #10） | 我 | 中 | — |
| 5 | install.sh 多源 fallback + ditto 解压 + 启动轮询（修 #8#11#12#13） | 我 | 高 | D1 |
| 6 | README 重排 + 安装说明换新稿 + 内部版清过期（修 #9#14#17） | 我 | 高 | — |
| 7 | pre-push 钩子降 --static（修 #15） | 我 | 中 | — |
| 8 | 落 release.sh + 上传三铁律 + README 分工说明（修 #16#18） | 我 | 低 | — |
| 9 | 删 Release 冗余 RVC.zip（修 #4，**不可删** RVC-Video-Companion.zip） | 我（gh 写） | P0 | 需确认 |
| 10 | 重跑 build.sh + make-distro.sh，产物同步（修 #7） | 你终端跑 | P0 | D2 |
| 11 | 验收 12/12 + 推 GitHub | 我 | P0 | 1-10 |

---

## ⚠️ 待完善 / 已知局限

- build.sh 重建 .app 受沙箱 rm -rf 保护拦截，需用户终端执行或授权。
- ghproxy 等公共镜像不稳定，仅作加速尝试不作唯一依赖。
- 一人维护无 CI，release.sh 仍需人手触发；治理设计已诚实标注"哪步还得手做"。

---

## 📚 数据来源 & 成员产出索引

- Cody（代码审查）：热键 IME 根因 + 修复清单 + 版本/品牌不一致。
- Docu（文档）：一致性审计表 + "视频合作伙伴"=Chrome 机翻实锤 + 安装指南重写稿 + README 重排。
- Rex（SRE）：Release 穿马甲资产真相 + 去重命令 + install.sh 问题清单 + 国内分发排序。
- Archi（架构）：单一版本源派生矩阵 + 发版 11 步 + 上传三铁律 + pre-push 取舍 + 目录分工。

> 本报告由工程保障团队 AI 协作生成，关键决策（D1/D2）请由人类负责人拍板后再落地。
