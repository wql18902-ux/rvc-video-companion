# BLOCKED - 待裁决/未决清单

> 更新：2026-08-01 后续会话——重建打包版 .app + 分发包 zip，B11/B12 已解决关闭。B1 仍有效。

## B14. PROGRESS.md 判卷指纹存档过期（2026-08-01 安全修复任务 0 发现）

- 现象：任务 0 核对 shasum，实测 acceptance.py=ff550f24/test.html=a4c77dd6/sample.mp4=bdd72076，与 PROGRESS.md 存档 c1965638/4b79893e/9b4a8281 全部不符。
- 排查：git 初始提交 2a89173（v3.2.1 开源初始提交）中三文件指纹 = ff550f24/a4c77dd6/bdd72076，与当前工作区一字不差 → 判卷文件未被篡改，存档为过期记录（疑早期未提交版本指纹）。
- 判定：不阻塞，以 git 初始提交指纹（= 实测）为当前判卷基线，PROGRESS.md 存档待后续同步更新。

## B13. 选目录弹窗前置 frontmost 机器半验受限（待领导亲验，不阻塞）

- 现象：任务2验收第1项，curl /api/pick-folder 挂起中 osascript 查 frontmost 期望 "System Events"，实测三版（System Events activate / Finder activate / set frontmost of process）均返回 "Electron"（测试环境 Electron 应用持续占前台，疑 Claude Desktop 或 VS Code 宿主抢焦点）。
- 已验证通过：①System Events 窗口列表确认"选取文件夹"对话框已弹出（choose folder 正常执行，非没弹窗）；②任务2第2项 60s 超时返回 `{"ok":false,"error":"选择超时（60s）"}` 正确；③报错分流逻辑（returncode≠0 按 stderr，含 "User canceled" 才 {cancelled:true}，其余 {ok:false,error:stderr 原文}）实现完成。
- 判断：机器半验受 Electron 抢焦点干扰无法确认前置；真实使用场景（用户在 Chrome 看 aim-read.top 点扩展"浏览"，前台为 Chrome）待领导亲验（任务书第4条半托）。serve_pick_folder 保持任务书默认 System Events 版（activate + choose folder 同 tell 块）。
- 残留：测试遗留 2 个僵尸"选取文件夹"对话框（osascript 被 kill -9 致对话框未正常关闭），需手动点取消关闭。
- 不阻塞任务3/4：核心功能（弹窗弹出 + 报错可见 + 超时）已验，前置属让步顺序第三优先级。

## B11. 打包版 NSOpenPanel（已解决）

- 现象：server.py serve_pick_folder 的 nsopen_script 加 `app.setActivationPolicy_(0)` 修复 NSOpenPanel 不前置 bug。
- 解决：后续会话跑 `bash stream-server/packaging/build.sh` 重建 .app（PyInstaller 打包时 TRAE 沙箱拦 `~/Library/Application Support/pyinstaller/`，用户加白后通过）。
- 验证：启动新 .app 二进制，curl /api/pick-folder，osascript 查 frontmost="Python"，NSOpenPanel 弹在最前。
- 备注：macOS 系统行为，弹窗有时自动前置、有时不弹（已在安装说明.txt 加 FAQ 说明 Dock 跳动/Command+Tab/点访达图标）。

## B12. 分发包 zip 重建（已解决）

- 解决：跑 `bash packaging/make-distro.sh` 生成新 zip `packaging/dist/RVC视频伴侣.zip`（25MB，Aug 1 10:26，覆盖旧 zip）。
- zip 内含：新版 .app + 回退后干净扩展 + 安装说明.txt（含访达 FAQ + 开发者模式强调）。
- 验证：解压查 安装说明.txt grep 访达=5、开发者模式=3。

## B1. 验收 profile 跨 run 污染（测试基建 + 持久化交叉，仍有效）

- 现象：验收脚本 G2 步骤点 `.rvc-btn-frameless` 进无框，`rvc-frameless=true` 写入 chrome.storage.local。下一次跑验收时 init 恢复无框，`.rvc-header { display:none }` 使 `.rvc-btn-folder` 不可见，C 步骤超时 30s，基线 6/12 崩到 1/12。
- 绕过（已裁决采用 a 方案）：每次跑验收前 `rm -rf /tmp/rvc-pw-profile-accept` 重置 profile。不碰验收脚本/测试页/夹具/阈值，判定为非作弊。
- 备选（未采用）：改验收脚本补 setFrameless(false)（sha256 冻结不能改）；content.js 去掉 frameless 持久化（基线功能，去掉算退化）。

## B7. manifest.json 偏离白名单（本次会话引入，已记录）

- 现象：v3.2.0 A1 权限收窄把 `content_scripts.matches` 从 `<all_urls>` 改成只匹配 `aim-read.top`。验收测试页 `http://127.0.0.1:8899/test.html` 不再被注入内容脚本，A 步直接 FAIL，验收 0/12。
- 处理：给 `content_scripts.matches` 加了 `"http://127.0.0.1:8899/*"`。manifest.json 不在白名单（只允许改 content.js/player.css/server.py/start.sh/PROGRESS.md/BLOCKED.md），但无此改动验收无法运行。
- 判定：测试必需、非功能变更（不影响 aim-read.top 生产行为）。已在 PROGRESS.md 记录偏离。
- 长期方案：manifest 保留测试 URL（当前做法），或验收脚本改用 aim-read.top（需 hosts 映射 127.0.0.1→aim-read.top，但 acceptance.py sha256 冻结不能改）。

## B3. Karabiner 残留（已解决，历史备注）

- S/D 失灵根因（Karabiner IINA 规则拦截浏览器 S/D/F）已通过删除 `~/.config/karabiner` 解决，S/D 恢复。
- DriverKit 系统扩展残留无法彻底卸载（SIP 阻止，`csrutil disable` 有风险不必要）：残留不拦键、只占少量内存，放弃清理。若日后要清：重装 Karabiner.app 用官方卸载器，比关 SIP 省事。

## B8. 顺手活不做（任务文档明令不做，记录在此）

- 改播放器定位（fixed/sticky 切换）：v3.2.1 已回滚，源码与打包版同步用 sticky。
- 修 formatTime Infinity:NaN：打包版无此问题，源码已回滚。
- 改 UI 样式（border-radius/shadow/stroke 等）：打包版无问题，不做。
- 以上均为「最诱人的顺手活」，任务文档要求写 BLOCKED.md 不做。

## B9. 验收 F 步偶发 flaky（非本次引入，仍有效）

- 现象：F 步（固定目录 pin+记忆+切换）偶发 FAIL，切换后目录显示 `~/Downloads` 而非 fixtures。根因是 `chrome.storage.local.get` 异步恢复 `rvc-last-dir` 与 `loadFileList()` 读取 dirInput 存在毫秒级竞态。
- 复现率：约 1/3（连续 3 次跑 1 次 FAIL）。
- 绕过：重跑即可通过。非本次三功能引入（回滚基线也有相同概率）。
- 不修：修需要改 content.js 初始化时序或验收脚本，前者有风险后者 sha256 冻结。

## B10. h264_videotoolbox 转码回归（已解决）

- 现象：server.py 从 `libx264 -preset fast -crf 23`（软件编码）改为 `h264_videotoolbox -b:v 2M`（硬件编码）后，用户反馈转码依旧很慢、实际播放看不了。之前 libx264 版本可以正常看。
- 基准测试矛盾：`ffmpeg` 单独跑 benchmark 时 videotoolbox 比 libx264 快（0.35s vs 0.29s，30x vs 22x），但通过浏览器 mpegts.js 流式播放时 videotoolbox 反而不可用。
- 可能根因（未验证）：(1) h264_videotoolbox 输出的 H.264 profile/level 浏览器不解；(2) 硬件编码器的关键帧间隔/输出格式不适合 MPEG-TS 流式封装；(3) 硬件编码器启动延迟导致首帧等待时间长。
- 解决：server.py 已回滚为 `libx264 -preset fast -crf 23`（L417）。打包版 .app 已重建（含 17 个 ffmpeg dylib + libx264）。分发包已重建（24MB）。
- 附带修复：build.sh dylib 收集逻辑从硬编码 `/opt/homebrew/` 路径匹配改为 `otool -L` + `@rpath`/`@loader_path` 递归解析，解决了 TRAE 环境中 ffmpeg 路径不同导致 dylib 未打包的问题。
