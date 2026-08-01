# RVC 视频伴侣

> 专为 [aim-read.top](https://aim-read.top) 双语阅读站设计的本地视频播放器 Chrome 扩展。

在阅读站页面右侧嵌入浮窗播放器，支持 MKV/MOV/AVI/FLV 等浏览器原生不支持的格式——通过本地 ffmpeg 服务器实时转码为 MPEG-TS 流式播放，**无文件大小限制**。

## 特性

- **实时转码**：MKV/MOV/AVI/FLV 自动转 MPEG-TS 流，边转边播无需等待整文件
- **无大小限制**：基于本地 ffmpeg，突破浏览器 WASM 内存限制
- **浮动浮窗**：sticky 定位贴在阅读内容旁，支持拖拽 / 缩放 / 无框模式
- **键盘控制**：S 播放/暂停、A 后退1秒、D 前进1秒（支持全局热键）
- **目录浏览**：点「浏览」选本地目录，列出所有视频文件
- **纯本地**：服务器只监听 127.0.0.1，不联网、不上传任何数据

## 截图

**浮动播放器 + 键盘快捷键面板**

![浮动播放器与键盘控制面板](screenshots/player-with-keyboard-panel.png)

**与阅读站单词查询共存** — 点单词弹出释义，直接覆盖在视频上方，互不干扰

![单词查询弹窗覆盖在视频播放器上方](screenshots/word-lookup-over-video.png)

## 技术栈

- **Chrome 扩展（MV3）**：Vanilla JS，无构建工具链
- **本地服务器**：Python 3 aiohttp + ffmpeg/ffprobe
- **流式播放**：mpegts.js（浏览器端 MPEG-TS 解码）
- **打包分发**：PyInstaller 打包 .app（含 ffmpeg 二进制，用户无需装 Python/ffmpeg）

## 快速开始

### 方式零：让 AI Agent 帮你装（推荐）

如果你在用 Claude Code / Cursor / Trae / Cline 等 AI 编程助手，把下面这段话**原样复制**发给你的 Agent，它会自动帮你下载和安装：

```
帮我安装 RVC 视频伴侣。按以下步骤执行，每步完成后告诉我进度：

1. 从 https://github.com/wql18902-ux/rvc-video-companion/releases/latest 下载最新的 RVC-Video-Companion.zip 到 ~/Downloads/
2. 解压到 ~/Downloads/RVC视频伴侣/（如果解压出 __MACOSX 文件夹忽略它）
3. 移除 macOS 隔离标记（否则双击会报「已损坏，无法打开」）：
   xattr -cr ~/Downloads/RVC视频伴侣/RVC视频伴侣.app
4. 启动 ~/Downloads/RVC视频伴侣/RVC视频伴侣.app
   - 如果仍被拦截：用 `open -R ~/Downloads/RVC视频伴侣/RVC视频伴侣.app` 在访达定位，右键 → 打开 → 确认
5. 用默认浏览器打开 chrome://extensions
   - 如果用户用的是 Edge，改用 edge://extensions
   - 开启右上角「开发者模式」
   - 点「加载已解压的扩展程序」，选 ~/Downloads/RVC视频伴侣/reader-video-companion 文件夹
6. 系统会弹「输入监控」权限请求 —— 用于全局热键 S/A/D
   - 建议允许（不授权也能用页面内热键，但全局热键失效）
   - 在 系统设置 → 隐私与安全性 → 输入监控 里勾选 RVC视频伴侣
7. 访问 https://aim-read.top
   - 点 Chrome 工具栏右上角拼图图标，找到「RVC 视频伴侣」并点固定图标钉到工具栏
   - 点 RVC 图标唤出浮窗播放器
8. 点播放器标题栏的文件夹图标 → 弹层里点「浏览」按钮 → 选一个含视频文件的本地目录
   - macOS 可能在 Dock 闪烁访达图标，点一下切到访达就能看到选目录对话框
9. 列表里点任意视频文件，应自动开始播放
10. 验证：键盘 S 暂停/播放、A 后退1秒、D 前进1秒
   - 鼠标必须悬停在播放器上方，页面内热键才生效

任何一步失败就停下来，告诉我具体错误信息（终端输出 / 浏览器控制台 / 系统弹窗文字），不要自己重试或绕过。
```

> Agent 装完后，日常使用只需双击 `.app` 启动服务器 + 访问 aim-read.top 点扩展图标。

### 方式一：下载打包版手动安装（无需装环境）

1. 到 [Releases](../../releases) 下载 `RVC-Video-Companion.zip`
2. 解压
3. 终端执行 `xattr -cr RVC视频伴侣.app`（移除隔离标记，否则报「已损坏」）
4. 双击「RVC视频伴侣.app」启动服务器
4. Chrome 打开 `chrome://extensions` → 开启「开发者模式」→「加载已解压的扩展程序」→ 选解压出的 `reader-video-companion` 文件夹
5. 访问 [aim-read.top](https://aim-read.top)，点扩展图标唤出播放器

### 方式二：从源码运行（开发者）

```bash
# 启服务器（端口 8765）
bash stream-server/start.sh

# 加载扩展：chrome://extensions → 开发者模式 → 加载已解压 → reader-video-companion/

# 跑验收
rm -rf /tmp/rvc-pw-profile-accept
env -u PYTHONHOME -u PYTHONPATH python3 tests/acceptance.py
```

**前置依赖**：Python 3.10+、ffmpeg、ffprobe、aiohttp、pynput

## 首次使用权限授权（macOS）

| 权限 | 用途 | 不授权影响 |
|------|------|-----------|
| 输入监控 | 全局热键 S/A/D | 仅全局热键失效，其余功能正常 |

> 选目录用的是 `osascript choose folder`（Standard Additions），**不需要自动化权限**。
> 每次更新 .app 后，输入监控权限会失效（系统按签名记账），需重新勾选。

## 目录结构

```
.
├── reader-video-companion/   # Chrome 扩展（唯一维护的扩展）
│   ├── content.js            # 内容脚本（播放器主体逻辑）
│   ├── player.css            # 播放器样式
│   ├── background.js         # 后台脚本（消息中转）
│   ├── manifest.json         # MV3 清单
│   └── mpegts.min.js         # MPEG-TS 解码库
├── stream-server/            # 本地转码服务器
│   ├── server.py             # aiohttp 服务器（含 SSE 热键通道）
│   └── start.sh              # 启动脚本
├── tests/                    # 验收脚本
│   ├── acceptance.py         # 端到端验收（sha256 冻结）
│   └── fixtures/             # 测试样本
├── test.html                 # 验收测试页（sha256 冻结）
└── packaging/                # 打包脚本
    ├── make-distro.sh        # 生成分发包 zip
    └── build.sh              # PyInstaller 打包 .app
```

## 支持的视频格式

| 格式 | 处理方式 |
|------|----------|
| MP4/M4V/WebM | 浏览器直接播放 |
| MKV/MOV/AVI/FLV | ffmpeg 实时转 MPEG-TS 流 |

## 隐私

所有视频只在你的电脑本地处理。服务器只监听 `127.0.0.1`，不联网、不上传任何数据。

## 系统要求

- macOS 12+
- Chrome / Edge / 其他 Chromium 浏览器

## License

MIT

## 致谢

- [mpegts.js](https://github.com/xqq/mpegts.js) — MPEG-TS 解码
- [ffmpeg](https://ffmpeg.org/) — 视频转码
- [aiohttp](https://docs.aiohttp.org/) — 异步 HTTP 服务器
