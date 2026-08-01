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

> 浮窗播放器嵌入 aim-read.top 阅读页右侧

## 技术栈

- **Chrome 扩展（MV3）**：Vanilla JS，无构建工具链
- **本地服务器**：Python 3 aiohttp + ffmpeg/ffprobe
- **流式播放**：mpegts.js（浏览器端 MPEG-TS 解码）
- **打包分发**：PyInstaller 打包 .app（含 ffmpeg 二进制，用户无需装 Python/ffmpeg）

## 快速开始

### 方式一：下载打包版（推荐，无需装环境）

1. 到 [Releases](../../releases) 下载 `RVC视频伴侣.zip`
2. 解压
3. 双击「RVC视频伴侣.app」启动服务器（首次右键打开）
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
| 自动化 | 点「浏览」选目录 | 无法弹选目录对话框 |

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
