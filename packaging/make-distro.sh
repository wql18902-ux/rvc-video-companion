#!/bin/bash
# ============================================================
# RVC 视频伴侣 - 一键生成分发包
#
# 产物：dist/RVC-Video-Companion.zip
# 内容：.app（本地服务器）+ Chrome 扩展 + 安装说明
# ============================================================
set -euo pipefail

PKG_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$PKG_DIR/.." && pwd)"
APP="$PROJECT_ROOT/stream-server/packaging/dist/RVC-Video-Companion.app"
EXT_DIR="$PROJECT_ROOT/reader-video-companion"
DIST="$PKG_DIR/dist"
STAGING="$DIST/RVC-Video-Companion"

# ADR-001: 版本号唯一源 = reader-video-companion/manifest.json（构建期读取注入）
VER="$(python3 -c "import json;print(json.load(open('$EXT_DIR/manifest.json'))['version'])")"
echo "==> 版本号（源 manifest.json）：$VER"

# 检查 .app 是否存在
if [ ! -d "$APP" ]; then
  echo "[错误] 未找到 .app，请先运行：bash stream-server/packaging/build.sh"
  exit 1
fi

# 检查扩展目录
if [ ! -f "$EXT_DIR/manifest.json" ]; then
  echo "[错误] 未找到 Chrome 扩展目录：$EXT_DIR"
  exit 1
fi

echo "==> [1/4] 清理旧产物"
rm -rf "$STAGING"
mkdir -p "$STAGING"

echo "==> [2/4] 复制 .app 和扩展"
cp -R "$APP" "$STAGING/"
cp -R "$EXT_DIR" "$STAGING/reader-video-companion"

# 清理 .DS_Store 等系统文件
find "$STAGING" -name ".DS_Store" -delete
find "$STAGING" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

echo "==> [3/4] 写入安装说明"

# --- 安装说明 ---
cat > "$STAGING/安装说明.txt" <<INSTRUCTIONS
RVC 视频伴侣 v$VER - 安装指南
macOS 12+ (Apple Silicon / Intel)


== 包内容 ==

  RVC-Video-Companion.app    本地视频服务器（含 ffmpeg，后台运行）
  reader-video-companion/    Chrome 扩展（MV3，无需编译）
  安装说明.txt               本文件


== 快速开始（3 步） ==

  第 1 步：清隔离标记
  -------------------
  从浏览器下载的文件会被 macOS 标记为「隔离」，首次必须清除：

    打开「终端」(Spotlight 搜 Terminal)，粘贴：
    xattr -cr ~/Downloads/RVC-Video-Companion/RVC-Video-Companion.app

  [注意] 路径根据你实际解压位置调整。不做这步，双击 .app 会报
  「已损坏，无法打开」或「无法验证开发者」。

  第 2 步：启动服务器
  -------------------
  双击 RVC-Video-Companion.app

  - 首次如果仍提示拦截：右键点它 -> 打开 -> 仍要打开
  - 没有终端窗口弹出 = 正常运行（后台模式）
  - Dock 栏图标会跳几下，这是正常的（等它跳完就好）
  - 验证：浏览器访问 http://127.0.0.1:8765 能看到页面就 OK

  第 3 步：安装 Chrome 扩展
  -------------------------
  1. Chrome 地址栏输入 chrome://extensions 回车
  2. 打开右上角「开发者模式」开关
  3. 点「加载已解压的扩展程序」
  4. 选择本文件夹里的 reader-video-companion 文件夹
  5. 扩展列表出现「RVC 视频伴侣」= 装好了


== 使用方法 ==

  1. 确保 .app 在运行（Dock 有图标 或 127.0.0.1:8765 能访问）
  2. 打开 https://aim-read.top
  3. 点 Chrome 工具栏的 RVC 图标（拼图形状里找）
  4. 播放器浮窗出现 -> 点文件夹图标 -> 点「浏览」-> 选视频目录
  5. 列表里点视频文件开始播放

  快捷键：S = 暂停/播放，A = 后退1秒，D = 前进1秒
  鼠标滚轮：滚动剧本文字（播放器不动）
  拖拽：标题栏可拖动播放器位置（自动记忆）


== 权限说明 ==

  输入监控（全局热键 S/A/D 用）：
  - 首次使用系统会弹窗请求，点「允许」
  - 或手动：系统设置 -> 隐私与安全性 -> 输入监控 -> 勾选 RVC-Video-Companion
  - 不授权：全局热键失效（切到别的 app 按 S/A/D 无反应），
    但页面内热键和其余功能不受影响
  - [注意] 每次更新 .app 后此权限会重置，需重新勾选


== 常见问题 ==

  Q: 双击 .app 提示「已损坏」或「无法验证开发者」？
  A: 跑第 1 步的 xattr -cr 命令。或右键 -> 打开 -> 仍要打开。

  Q: 点「浏览」没反应？
  A: 确认 .app 在运行。按钮灰色 = 服务器未连接，等几秒自动亮起。

  Q: 支持什么格式？
  A: MP4/M4V/WebM 直接播放；MKV/MOV/AVI/FLV 自动实时转码，大小不限。

  Q: 想用源码版（不用 .app）？
  A: 从 GitHub 下载源码，终端跑：
     cd rvc-video-companion && bash start.sh
  [注意] 源码版首次运行 macOS 也可能提示安全警告（.command 文件），
  右键 -> 打开 即可。或直接终端跑 bash start.sh 不经过 .command。

  Q: 怎么关闭服务器？
  A: 活动监视器搜 rvc-server，结束进程。或终端跑：
     pkill -f rvc-server


== 隐私 ==

  所有视频只在你电脑本地处理。
  服务器只监听 127.0.0.1（本机），不联网、不上传任何数据。
  无遥测、无追踪、无广告。


== 源码 ==

  GitHub: https://github.com/wql18902-ux/rvc-video-companion
  协议: MIT
INSTRUCTIONS

echo "==> [4/4] 打包 zip"
cd "$DIST"
ZIP_NAME="RVC-Video-Companion.zip"
rm -f "$ZIP_NAME"
ditto -c -k --sequesterRsrc --keepParent "RVC-Video-Companion" "$ZIP_NAME"

ZIP_SIZE=$(du -sh "$ZIP_NAME" | cut -f1)
echo ""
echo "  [完成] 分发包已生成：$DIST/$ZIP_NAME ($ZIP_SIZE)"
echo ""
echo "  内容："
echo "    RVC-Video-Companion.app       ← 本地服务器（含 ffmpeg）"
echo "    reader-video-companion/      ← Chrome 扩展"
echo "    安装说明.txt                  ← 使用指南（含第 0 步 xattr 清隔离）"
echo ""
echo "  发给别人后：解压 → 终端跑 xattr -cr → 双击 .app → Chrome 加载扩展 → 开用"
