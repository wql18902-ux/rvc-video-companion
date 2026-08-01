# PROGRESS - Reader 视频伴侣（浏览器播放器系统）

> 更新：2026-08-01 安全修复（4 Critical）开工——任务 0 完成，基线 12/12 全绿。

## 2026-08-01 安全修复：4 个 Critical（任务书-修复4个Critical安全项）

### 开工回执（任务 0，2026-08-01 19:45）
- 目标：修 4 个 Critical（CORS 通配+无鉴权→任意文件读取、路径穿越、XSS、SSE 连接泄漏）。让步：安全正确 > 功能不动（12/12 仍绿）> 代码整洁。
- 顺序：0 核对 → 1 server.py 鉴权 → 2 content.js XSS → 3 SSE 泄漏 → 4 回归。
- 白名单：server.py / content.js / PROGRESS.md / BLOCKED.md。tests/ 全冻结。
- 任务 0 核对：CORS `*` 4 处（L209/409/438/478）✓；innerHTML=22 处基线 ✓；服务器起 8765 探活 200 ✓；基线验收 12/12 全绿 ✓。
- **关键发现 B14**：判卷指纹实测 ff550f24/a4c77dd6/bdd72076 与 PROGRESS 存档 c1965638/4b79893e/9b4a8281 全部不符；git 初始提交 2a89173 指纹 = 实测，证判卷文件未被篡改，存档过期。已写 BLOCKED.md。
- 最大风险：鉴权改动可能误伤热键子进程（无 Origin POST）；CORS 改白名单后 127.0.0.1:8899 测试页 Origin 必须放行（否则验收全挂）。

### 任务 1：server.py 鉴权+CORS 白名单+路径校验（已完成，2026-08-01 19:55）
- server.py 新增：ALLOWED_ORIGINS（aim-read.top http/https、127.0.0.1:8899）+ ALLOWED_HOSTS（127.0.0.1:8765/localhost:8765）+ SERVE_FILE_EXTS；StreamHandler 新增 check_origin()（有 Origin 走白名单，无 Origin 校验 Host，兼容热键子进程）+ safe_join()（realpath+前缀校验）+ _cors_header()（白名单回显）；do_GET/do_POST 对 /api/* 统一鉴权；serve_file/duration/stream 改 safe_join；serve_file 限扩展名。
- 附带修复预存 bug：send_error(404, "中文") 的 HTTP reason phrase 需 latin-1 编码会崩（路径校验触发 404 分支才暴露），全部改无 message 版本。
- 验收 6 条全过：dir=/&file=etc/passwd→404（旧代码能读 /etc/passwd 红→绿）、evil Origin→403、aim-read.top→200、evil Host→403、热键无 Origin POST→200、CORS `*` 残留=0。

### 任务 2：content.js XSS 修复（已完成，2026-08-01 19:57）
- 新增 escapeHtml()（转义 &<>"'）；替换全部用户可控拼接点：folderStatus/treeStatus 的 data.error、e.message（L407/410/462/493/592/602）、文件名渲染（L479 f.name/f.ext）、目录树名（L611 node.name）。纯 HTML 模板与 ICON 常量拼接未动。
- 验收：node -c 通过；grep 确认无未转义直拼；恶意文件名 `<img onerror>` 经转义无真实标签边界（PASS）。

### 任务 3：SSE 连接泄漏修复（已完成，2026-08-01 20:00）
- content.js：SSE 改模块级单例 sseSource，connectControlSSE 入口先 close 旧实例，onerror 先置空再 close 再 setTimeout 重连。
- server.py：serve_control_sse 心跳保活（15s 写 `: ping` 注释行替代 30s 主动断）；MAX_SSE_CLIENTS=10 超限 503。
- 验收：POST control-key→SSE 收到 toggle_play 事件 ✓；连接跨 20s 仍活跃（收到 : ping）✓；并发 12 连接 9×200+3×503（上限生效）✓。

### 任务 4：回归（已完成，2026-08-01 20:05）
- 验收回归 12/12 全绿（A-H，CORS 白名单未误伤 8899 测试页、XSS 修复未破坏 DOM、SSE 单例不影响本地热键）。
- 任务 1 六条 curl 复核全符合（404/403/200/403/200/0）。
- 判卷三文件指纹与任务 0 实测一字不差（ff550f24/a4c77dd6/bdd72076），tests/ 零 diff。
- git 提交 138b11e（fix(security)，白名单 4 文件：server.py/content.js/PROGRESS.md/BLOCKED.md）。
- 白名单外 CLAUDE.md 的 M 为先前会话遗留（19:18 修改，非本次引入），未动未提交，待用户处理。

## 2026-08-01 打包版「浏览」无反应修复（任务书-打包版浏览修复）

### 开工回执（任务 0）
- 目标：热键隔离让服务器永不死（任务1）+ 选目录弹窗前置&报错可见（任务2）+ 重建分发不签名（任务3）+ 回归提交（任务4）。让步顺序：服务器永远活 > 核心功能不变 > 弹窗前置可靠 > 速度。
- 顺序：0 核对 -> 1 热键隔离 -> 2 选目录前置 -> 3 重建分发 -> 4 回归提交。
- 白名单：server.py / stream-server/packaging/build.sh / packaging/make-distro.sh / PROGRESS.md / BLOCKED.md。tests/ + reader-video-companion/ 全冻结。
- 任务0核对：grep start_hotkey_listener=2行(L74 def / L506 调用)✓；grep "choose folder"=2行(L241注释/L248代码)✓。
- sha256 存档：content.js=7a9f03f5… / player.css=6713769f… / acceptance.py=c1965638… / test.html=4b79893e…（注：test.html 在根目录，任务书写 tests/test.html 是路径笔误，哈希与历史指纹一致，不影响冻结）。
- 最大风险：①任务1本会话终端 python3 进程可能无「输入监控」权限，pynput 子进程被 SIGKILL，pgrep -P 验收可能找不到子进程（实测定，失败写 BLOCKED）；②任务3 PyInstaller 打包需 pynput 进 frozen 包，spec 要含 hiddenimports（待核），TRAE 沙箱历史曾拦 pyinstaller 缓存目录。

### 任务 1：热键隔离，服务器永不死（已完成，源码版验收）
- start_hotkey_listener 改为 subprocess.Popen 独立子进程：frozen 用 [sys.executable,'--hotkey-child']，源码用 [sys.executable, os.path.abspath(__file__),'--hotkey-child']。主进程不 wait 不重启。
- 新增 run_hotkey_child()：子进程入口，pynput Listener 监听 S/A/D，按键 POST http://127.0.0.1:{PORT}/api/control-key；连续 POST 失败 10 次 listener.stop() 自行退出。S/A/D 语义一字未改（s/S->toggle_play, a/A->back, d/D->forward）。
- 新增 do_POST + serve_control_key：/api/control-key 收 {action} -> broadcast_control_event 转手广播给 SSE 客户端。
- --hotkey-child 入口分发放在 if __name__ 最前，子进程不走 signal/HTTP。
- 验收（源码版主 pid=29637，子 pid=29639）：①60s 内 /api/files 探活 ×5 全 200 ✓；②kill -9 子 29639 后再探 ×3 全 200，主 29637 仍活（STAT=SN）✓；③curl -N /api/control 挂起，POST /api/control-key {toggle_play}->SSE 收到 `data: {"action":"toggle_play","t":...}`，再 POST {forward}->SSE 累计两条 ✓。
- 旁证：本机旧打包版 rvc-server(29433) 主进程内 pynput 活着，说明本机有输入监控权限；源码版子进程 29639 启动后未被 SIGKILL（pgrep -P 可见），与预期一致。

### 任务 2：选目录前置 + 报错不装死（已完成，前置半验受限见 B13）
- serve_pick_folder 改单段 AppleScript：`tell application "System Events"` 内 activate + set f to choose folder + end tell + return POSIX path of f（6 段 -e 拼一次 osascript 调用）。choose folder 与 activate 同 tell 块。
- returncode≠0 按 stderr 分流：含 "User canceled" 才 {cancelled:true}，其余 {ok:false,error:stderr 原文或退出码}。60s 超时（TimeoutExpired）与 CORS（send_json）保持。
- 验收：①frontmost 机器半验不符（=Electron，测试环境 Electron 抢焦点），但 System Events 窗口"选取文件夹"确认弹出；System Events/Finder/set frontmost 三版均被压住，记 B13 待领导亲验；②60s 超时返回 `{"ok":false,"error":"选择超时（60s）"}` ✓；③反向验证：'osascript'->'osascript-notexist' 重启 curl 返回 `{"ok":false,"error":"[Errno 2] No such file..."}`（红），还原重启 curl --max-time 3 exit=28 挂起（绿）✓。
- 让步记录：任务书给 System Events/Finder 两版 frontmost 均不符，第三版 set frontmost 亦不符，根因是测试环境 Electron 持续占前台（非代码问题），serve_pick_folder 保持任务书默认 System Events 版。

### 任务 3：重建分发 + 授权指引（已完成）
- build.sh 修复：venv 装 pynput（之前 venv 只装 pyinstaller 致 PyInstaller `Hidden import 'pynput.*' not found`，打包版热键子进程 import 失败退出）。现 `pip install --quiet pynput` 后 PyInstaller 正确收集 pynput.keyboard._darwin 等（hook-pynput.py 触发）。
- 跑 build.sh 重建 .app（含 17 ffmpeg dylib + libx264 + pynput）；跑 make-distro.sh 重打 zip（25MB）。
- make-distro.sh 安装说明加「权限授权（首次使用必看）」段：输入监控（系统设置->隐私与安全性->输入监控->勾选）+ 自动化（首次点浏览系统弹窗选允许）+ 每次更新 .app 后重新勾选输入监控说明。
- 验收：①bash -n make-distro.sh 通过；②新 .app 启动主 33034 活、热键子 33037 活、探活 ×5 全 200；③kill -9 子 33037 后探 ×3 全 200、主进程仍活（热键隔离在打包版验证）；④解压 zip 安装说明 grep 输入监控=4(≥2)✓、自动化=1(≥1)✓。
- 旁证：重打包后输入监控权限仍有效（子进程 33037 未被 SIGKILL），与本机 TCC 记账方式有关（任务书预期按哈希失效需重授权，实测本机继承--领导亲验为准）。

### 任务 4：回归 + 提交（已完成）
- acceptance.py 12/12 全绿（A-H，F 步本次通过非 flaky，清 profile 后一次过）。
- 完成条件核对：①打包版探活×5全200 + kill-9子进程×3全200 + 第二次重建仍全活 ✓；②shasum四文件与任务0存档一字不差（content.js=7a9f03f5/player.css=6713769f/acceptance.py=c1965638/test.html=4b79893e）✓；③git diff --stat reader-video-companion/ tests/ 为空 ✓。
- 唯一半验项：pick-folder 挂起 frontmost 机器半验=Electron（三版均不符），记 B13 待领导亲验（任务书第4条半托）。
- git 提交 b3fb30b（白名单5文件：server.py/build.sh/make-distro.sh/PROGRESS.md/BLOCKED.md）。
- 遗留：CLAUDE.md/README-内部版.md 有之前会话遗留 M（含过期"修复进行中"描述），不在白名单未提交未还原，待用户处理；.trae/ 与任务书未跟踪未提交。
- 测试启动的打包版 .app（pid 33034）仍在 8765 运行，方便领导亲验前置；停用 `lsof -ti:8765 | xargs kill`。

## 2026-08-01 回退脏代码 + 无框等比缩放 + 重建分发包

### 开工回执（任务 0）
- 基线核对通过：009fa56 content.js=1112 行，HEAD=2db0a72，与任务文档一致。
- 目标：回退播放列表+按键面板脏代码；修 NSOpenPanel 前置；加无框等比缩放；美化角标；重建分发包。
- 顺序：0 核对→1 回退→2 访达→3 无框缩放→4 角标→5 分发包→6 收尾。
- 最大风险：Task 3 改缩放手柄逻辑可能影响拖拽；Task 2 打包版无法本会话验证。

### 任务 1：回退播放列表 + 按键面板（已完成）
- content.js：删 playlist 状态/HTML/renderPlaylist/addToPlaylist/playNextInPlaylist/removeFromPlaylist/事件绑定、keys-panel HTML/事件/keybindings 状态、ICON list/plus/trash、.rvc-btn-keys 按钮。
- keydown 监听改回硬编码 's'/'a'/'d'。
- player.css：删全部 .rvc-playlist* 和 .rvc-keys*（含 .rvc-key-btn/.rvc-key-capturing/.rvc-keys-reset）规则。
- 保留：dirPickBtn、storageReady、serve_pick_folder。
- 行数：content.js 1371→1119，player.css 943→753。
- 验收：grep playlist/keybindings = 0；renderPlaylist 无输出；node -c 通过；dirPickBtn/storageReady/pick-folder grep = 15。

### 任务 2：NSOpenPanel 前置（已完成，源码版验证）
- server.py serve_pick_folder 的 nsopen_script：在 `app.activateIgnoringOtherApps_(True)` 前加 `app.setActivationPolicy_(0)`（NSApplicationActivationPolicyRegular），让 Python 子进程成为常规应用抢焦点。
- 验证：启动源码版 server.py，curl /api/pick-folder，osascript 查 frontmost application 返回 "Python"，证明 NSOpenPanel 弹在最前（修复前会躲在浏览器后面）。
- curl 因 osascript 缺辅助功能权限无法发 Escape 取消对话框，返回空 body；frontmost=Python 已是核心证据。对话框关闭后 frontmost 查询恢复。
- 打包版（sys.frozen）待 .app 重建后验证 → 见 BLOCKED.md B11。

### 任务 3：一键无边框 + 等比缩放（已完成）
- state 新增 `videoRatio: null`。
- video `loadedmetadata`：若 videoWidth/videoHeight>0，更新 state.videoRatio = w/h。
- setFrameless(true)：若 videoWidth>0，算 r=w/h，设 player 宽=视口50%、高=宽/r，去黑边；无视频跳过。
- 缩放 mousemove：state.videoRatio 存在时等比（e/w 用 dx 算 newWidth、纯 n/s 用 dy 反算 newWidth=newHeight*r、newHeight=newWidth/r 联动、n 方向补偿 top）；无视频保持原自由缩放。
- 验收：grep videoWidth=4、grep videoRatio=4、node -c 通过。

### 任务 4：美化拖拽角标（已完成）
- player.css 删 4 条 .rvc-resize-handle[data-dir]::after 的 border 三角（se/nw/ne/sw）+ hover border-color 高亮。
- 改为：四角 ::after 共用 6px 圆点（transparent 默认、border-radius:50%），按角定位 top/bottom/left/right:4px，hover 时 background:rgba(10,132,255,0.7)。
- 验收：grep 'border-right.*#888|border-bottom.*#888' = 0；border-left/top #888 = 0；border-radius:50% 存在；rgba(10,132,255,0.7) 存在。

### 任务 5：安装说明 + 重建分发包（已完成）
- make-distro.sh 安装说明第 2 步重写：【必须开启开发者模式】方括号强调（.txt 不支持 markdown），写明开关位置（页面右上角）、原因（不开则无法加载已解压扩展）、看不到开关检查 Chrome 版本。
- 去 emoji：❌→[错误]、📺→[提示]、🧩删除、✅→[完成]。
- 验收：bash -n 通过；grep 开发者模式=3；emoji 扫描 0 个。

## 2026-08-01 打包版 .app + 分发包 zip 重建（后续会话）

### 打包版 .app 重建（已完成）
- 跑 `bash stream-server/packaging/build.sh`（首次因 TRAE 沙箱拦 `~/Library/Application Support/pyinstaller/` 失败，用户在 Settings→Conversation→Custom Sandbox Configuration 加白后重跑通过）。
- 新 .app：`stream-server/packaging/dist/RVC视频伴侣.app`（57MB，rvc-server 二进制修改时间 Aug 1 10:19），含本次 NSOpenPanel `setActivationPolicy_(0)` 修复 + 17 个 ffmpeg dylib + libx264。
- 验证：启动 .app 二进制，curl /api/pick-folder，osascript 查 frontmost="Python"（NSOpenPanel 前置）。B11 关闭。

### 分发包 zip 重建（已完成）
- 跑 `bash packaging/make-distro.sh`，新 zip：`packaging/dist/RVC视频伴侣.zip`（25MB，修改时间 Aug 1 10:26），覆盖旧 zip。
- zip 内含：RVC视频伴侣.app（新版）+ reader-video-companion/（回退后干净扩展）+ 安装说明.txt（2.9KB，含访达 FAQ + 开发者模式强调）。
- 验证：解压查 安装说明.txt grep 访达=5、开发者模式=3。B12 关闭。

### 访达行为说明（已写入安装说明.txt）
- macOS NSOpenPanel 弹窗有时自动切到最前面、有时躲在浏览器后面不自动弹出。
- 安装说明.txt 常见问题加 FAQ：看不到窗口时看 Dock 跳动图标 / Command+Tab / 点 Dock 访达图标。
- 这是 macOS 系统行为，不影响功能，选完目录后自动返回路径。

### 待提交（git status）
- 修改：BLOCKED.md、CLAUDE.md、PROGRESS.md、packaging/make-distro.sh、reader-video-companion/content.js、reader-video-companion/player.css、stream-server/server.py
- 未跟踪：.trae/specs/revert-playlist-frameless-scaling/（spec 三件套，本次会话产物）

## 2026-08-01 恢复 keys-panel 自定义按键功能（用户改主意）

### 背景
- 用户改主意：原任务文档要求"播放列表 + 自定义按键面板彻底删除"，用户明确"就恢复自定义按键那个功能就好了，其他的都不用调整"。
- 只恢复 keys-panel，不恢复 playlist。

### 改动
- content.js：从 git 2db0a72 检出 keys-panel 代码加回——state.keybindings、HTML 模板（.rvc-keys-panel）、elements（btnKeys/keysPanel/keysToggleBtn/keyBtns/keysReset）、keyState/capturingAction 逻辑、keydown 改用 state.keybindings 判断（录入模式 + 开关 + 面板打开时不响应）。
- player.css：加回 .rvc-keys-panel 及子元素规则（.rvc-keys-row/.rvc-keys-toggle-btn/.rvc-key-btn/.rvc-key-capturing/.rvc-keys-reset）+ .rvc-player.rvc-frameless .rvc-keys-panel。
- 保留：无框等比缩放、dirPickBtn、storageReady、hover 圆点角标（均未动）。
- 未恢复：playlist 相关代码（仍保持删除）。

### 验证
- grep keys-panel/keybindings content.js = 14（≥5 ✓）
- grep playlist content.js = 0（仍删除 ✓）
- grep rvc-keys-panel/rvc-key-btn player.css = 5（≥3 ✓）
- node -c content.js 通过
- 既有功能：videoRatio=4、dirPickBtn=10、hover 圆点 rgba(10,132,255,0.7) 存在

### 行数
- content.js 1148 → 1305（+157）
- player.css 734 → 829（+95）

### 待办
- .app 和 zip 需重建才含 keys-panel 恢复（当前 zip 是 keys-panel 删除版）。
- 用户未指示是否重建，等待确认。

### 完成条件复核（原任务文档，keys-panel 恢复后部分作废）
1. ~~grep playlist/keybindings content.js = 0~~ → keybindings 已恢复（用户改主意），现 keybindings=14，playlist=0
2. bash -n make-distro.sh 通过；安装说明含「开发者模式」✓

## 当前状态

- **内部版（v3.2.0）✅ 唯一方案，已完成**：共享基线 S1-S4 + A1 权限收窄 + A2 PyInstaller .app + A3 .crx + 分发包打包脚本
  - 产物：`stream-server/packaging/dist/RVC视频伴侣.app`（57MB，内置 ffmpeg/ffprobe）+ `packaging/reader-video-companion.crx`
  - 一键分发包：`packaging/make-distro.sh` → `packaging/dist/RVC视频伴侣.zip`（24MB，含 .app + 扩展 + 安装说明）
  - manifest v3.2.0：`<all_urls>` 清零，只留 aim-read.top + 127.0.0.1:8765
- **WASM 上架版 ❌ 已废弃并删除（2026-07-31）**：5 轮修复全部失败，根因 Emscripten MEMFS 无法处理 >200MB 文件。目录已清理，历史详见 `iterations/history.md`「已验证无效方案」

## 接口约定（tests/acceptance.py 依赖，改名即失败）

- 倍速：`.rvc-btn-speed`(文字含速率如「1.5×」) / `.rvc-speed-panel` / `.rvc-speed-option[data-rate="1.5"]` / `input.rvc-speed-slider`(监听 input)
- 固定目录（仅 A 路）：`.rvc-pin-btn`(弹层目录行) / `.rvc-pinned-chip`(点击切目录刷新) / `.rvc-dir-input`(目录输入框)
- 拖拽：G1 拖标题栏、G2 无框拖视频本体，位移>=50px；G3 单击视频仍切播放
- 判卷指纹 sha256：acceptance.py=c1965638… test.html=4b79893e… sample.mp4=9b4a8281…（验收跑之前核对）

## 历史经验（v3.1.0 验收时代，已交付 12/12，评分 90）

- **验收 profile 跨 run 污染**：持久化 profile 里 `rvc-frameless=true` 残留会让下一次验收 C 步骤超时（无框模式标题栏 display:none）。每次跑验收前 `rm -rf /tmp/rvc-pw-profile-accept`
- **S/D 失灵曾因 Karabiner**：Karabiner 的 IINA 控制规则在浏览器前台拦截 S/D/F（A 不拦），IINA 未开时按键被白吞。已删 `~/.config/karabiner` 解决，S/D 恢复（环境问题非代码 bug，详见 BLOCKED.md B3）
- v3.0.0 曾四天未提交（a497ed1 才入库）→ 教训：改完立即提交，否则会话切换就丢

## 2026-07-31 fixed 定位重构（已回滚）

> 本次会话尝试把 sticky+float 改为 fixed 定位，并完成 12/12 验收。但用户实际使用的 `packaging/dist/` 打包版（sticky 定位）验证无问题，fixed 版本未被采用。源码已回滚至 v3.2.0（commit e55c8cc），与打包版完全一致。

### 回滚原因
- 用户验证 packaging/dist 打包版（sticky）无问题
- fixed 版本改了源码但未打包验证，存在风险
- 回滚后源码与打包版 diff 一致（content.js/player.css/manifest.json 三文件 diff 通过）

### fixed 版改动记录（已回滚，仅供未来参考）
- `.rvc-player` sticky+float → fixed + z-index:2147483640，初始视口居中偏上 1/3
- 删 sentinel/IntersectionObserver(stuck)/MutationObserver(body)/fixAncestorOverflow
- 拖动 transform→left/top 直接赋值；backdrop-filter 14 行→2 行
- formatTime 加 isFinite 返回 '--:--'；emoji 换文字标签
- 验收 12/12 通过（G1=210px G2=180px）

### 建议
- 如需引入 fixed 定位，应先打包验证再替换打包版，避免源码与打包版版本不一致

## 2026-07-31 三功能开发（访达选目录 / 播放列表 / 自定义按键）

### 开工回执（任务 0）
- 验收基线：12/12 通过（A-H 全绿，G1=210px G2=180px）。
- 基线两处预存缺陷已修：(1) manifest.json 补回 `http://127.0.0.1:8899/*` 测试 URL（B7，回滚误删，非功能变更）；(2) content.js finishLoad 恢复 `play()` 优先 + 失败降级 showPlayHint——v3.2.0「加载但暂停」改造删了 play()，致 C/D3/G2 三项 FAIL（持久 playHint 遮住视频中心致 G2 拖拽 0px）。判卷标准冻结不可改，故代码须服从验收。
- 现开始任务 1/2/3。

### 任务 1：访达选目录（已完成）
- server.py 新增 `GET /api/pick-folder`：NSOpenPanel（AppKit），activateIgnoringOtherApps 确保窗口前置（osascript choose folder 会躲在浏览器后面，已替换），成功 `{ok,dir}` / 取消 `{cancelled:true}` / 超时报错 `{ok:false,error}`，带 CORS。
- content.js `.rvc-folder-dir` 加 `.rvc-dir-pick-btn`（ICON.folder + "浏览"），点击→fetch→填入 dirInput→loadFileList；服务器离线 disabled+title"需启动服务器"。
- 验收 12/12 仍全绿；curl /api/pick-folder 返回 `{"cancelled":true}`（取消路径）。

### 任务 2：播放列表（已完成）
- content.js state 新增 `playlist:[]` + `playlistIndex:-1`（不持久化，刷新清空）。
- `.rvc-folder-item` 加 `.rvc-add-playlist` 按钮（ICON.plus），stopPropagation 不触发直接播放。
- 播放器控制条下方 `.rvc-playlist` 面板（默认折叠，有内容时显示），列表项显示文件名+删除按钮，当前播放项高亮。
- video `ended` 事件 → `playNextInPlaylist()` 自动播下一个；最后一个播完停止。
- player.css 新增 `.rvc-playlist` 样式（暗色、紧凑、max-height 120px 可滚动）。
- 验收方法：加入 2 个文件到列表 → 播第一个 → ended 后自动播第二个（Playwright 脚本验证通过）。

### 任务 3：自定义按键（已完成）
- content.js state 新增 `keybindings:{toggle_play:'s',back:'a',forward:'d'}`（默认值）。
- `.rvc-btn-keys` 点击行为改为弹 `.rvc-keys-panel` 面板（不再直接开关）。
- 面板内容：键盘控制开关（`.rvc-keys-toggle-btn`）+ 三个按键录入按钮（`.rvc-key-btn`）+ 恢复默认按钮（`.rvc-keys-reset`）。
- 按键录入：点击按钮 → `capturingAction` 标记 → 下次 keydown 捕获 → `e.key.toLowerCase()` 存入 keybindings → chrome.storage.local `rvc-keybindings` 持久化。
- keydown 监听改用绑定表判断（`e.key.toLowerCase() === state.keybindings.toggle_play` 等），不再硬编码 a/s/d。
- 启动时从 chrome.storage.local 恢复 `rvc-keys-enabled` + `rvc-keybindings`，覆盖默认。
- Escape 取消录入；点击面板外部关闭面板；面板打开时不响应播放快捷键。
- player.css 新增 `.rvc-keys-panel` 及子元素样式（absolute 定位、暗色背景、blur）。
- 验收 D1/D2/D3 全绿（默认绑定 a/s/d 不变）；Playwright 脚本验证面板可交互（开/关、录入、恢复默认、外部点击关闭）。

### 完成条件验证
- `python3 tests/acceptance.py` → 12/12 通过（A-H 全绿）。
- `grep -c "pick-folder" stream-server/server.py` → 1（>=1）。
- `grep -c "rvc-playlist" reader-video-companion/content.js` → 12（>=1）。
- `grep -c "rvc-keys-panel" reader-video-companion/content.js` → 2（>=1）。

## 2026-07-31 VideoToolbox 转码改动（已回滚 + dylib 修复）

> 本次会话将 server.py 转码编码器从 `libx264 -preset fast -crf 23`（软件编码）改为 `h264_videotoolbox -b:v 2M`（硬件编码），用户反馈实际播放反而更慢/看不了。已回滚。

### 事实
- ffmpeg 单独 benchmark：videotoolbox 0.35s vs libx264 0.29s（30x vs 22x），videotoolbox 更快。
- 用户实测：libx264 可以正常看视频，videotoolbox 看不了/转码慢。
- 验收 12/12 通过（但验收用的是 sample.mp4 小文件，未覆盖真实大 MKV 流式播放场景）。

### 已完成
- server.py 已回滚为 `libx264 -preset fast -crf 23`（L417）。
- build.sh 修复 dylib 收集逻辑：旧版硬编码匹配 `/opt/homebrew/` 路径，在 TRAE 环境中 ffmpeg 路径不同导致 `staging/ffmpeg/lib/` 为空，用户独立运行时加载不匹配版本的 dylib。新版用 `otool -L` + `@rpath`/`@loader_path` 解析递归收集，17 个 dylib 正确打包。
- 打包版 .app 已重建（57MB，含 17 个 ffmpeg dylib + libx264 编码器）。
- 分发包已重建：`packaging/dist/RVC视频伴侣.zip`（24MB）。
- 验收 11/12 通过（F 步为已知 flaky B9，非本次引入）。

### 教训
- 验收脚本 sample.mp4 太小（几秒），无法暴露转码性能问题。未来改编码器时应手动用真实大 MKV 文件测试浏览器流式播放。
- 打包 ffmpeg 必须递归收集所有 `@rpath`/`@loader_path` 依赖 dylib，不能硬编码 brew 路径匹配。

## 2026-08-01 一键启动 + emoji 清理 + 洁癖收尾

### 一键启动（已完成）
- 根目录 `start.sh`：检查服务器是否在跑 → 没跑则 nohup 启动 stream-server/start.sh → 等待就绪 → 打开 Chrome 访问 aim-read.top。
- `启动视频伴侣.command`：macOS 双击入口，cd 到脚本目录后调用 start.sh。
- 两个文件均已 git 跟踪。

### emoji 清理（已完成）
- server.py 中 6 处 emoji（⚠️🌐✅📺🎬📁）替换为文字标签（[WARN]/[OK]/[INFO]）。
- 符合 CLAUDE.md 硬约束「server.py/start.sh 不许含 emoji」。
- 改动 7 行（+7/-7），待提交。

### 洁癖收尾（本次）
- PROGRESS.md：修正 pick-folder 描述（osascript→NSOpenPanel）、zip 大小（25→24MB）。
- 发现 CLAUDE.md / README-内部版.md 有过期内容，但不在白名单内，已列入待确认。
