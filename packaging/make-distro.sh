#!/bin/bash
# ============================================================
# RVC 视频伴侣 - 一键生成分发包
#
# 产物：dist/RVC视频伴侣.zip
# 内容：.app（本地服务器）+ Chrome 扩展 + 安装说明
# ============================================================
set -euo pipefail

PKG_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$PKG_DIR/.." && pwd)"
APP="$PROJECT_ROOT/stream-server/packaging/dist/RVC视频伴侣.app"
EXT_DIR="$PROJECT_ROOT/reader-video-companion"
DIST="$PKG_DIR/dist"
STAGING="$DIST/RVC视频伴侣"

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
cat > "$STAGING/安装说明.txt" <<'INSTRUCTIONS'
╔══════════════════════════════════════════════╗
║         RVC 视频伴侣 - 安装指南              ║
╚══════════════════════════════════════════════╝

只需 3 步，2 分钟搞定。


━━ 第 1 步：启动服务器 ━━

  1. 双击「RVC视频伴侣.app」
  2. 首次打开如果提示"无法打开"：
     右键点它 → 选「打开」→ 确认
     （以后双击就能直接开）
  3. 会弹出终端窗口，看到这行字就说明成功了：
     [提示] 地址：http://127.0.0.1:8765
  4. 这个窗口别关！关掉就等于关服务器


━━ 第 2 步：安装 Chrome 扩展 ━━

  1. 打开 Chrome 浏览器
  2. 地址栏输入 chrome://extensions 回车

  3. 【必须开启开发者模式】
     - 位置：页面右上角
     - 原因：不开开发者模式，无法加载已解压的扩展程序
     - 看不到开关时：检查 Chrome 版本是否过旧，
       或确认页面右上角是否有「开发者」字样的开关

  4. 打开「开发者模式」开关
  5. 点左上角「加载已解压的扩展程序」
  6. 选择文件夹里的「reader-video-companion」文件夹
  7. 扩展列表里出现「Reader 视频伴侣」就装好了


━━ 第 3 步：开始使用 ━━

  1. 打开 https://aim-read.top
  2. 点浏览器右上角的扩展图标栏（拼图形状）
  3. 找到「Reader 视频伴侣」图标，点一下
  4. 播放器出现在页面右侧
  5. 点「加载视频」选择你电脑里的视频文件

  之后每次使用：先双击 .app 启动服务器，再打开网页点图标。


━━ 权限授权（首次使用必看）━━

  macOS 首次使用需授权两项权限，否则对应功能不可用：

  1. 输入监控（全局热键 S/A/D 用）
     - 打开：系统设置 -> 隐私与安全性 -> 输入监控
     - 找到「RVC视频伴侣」并开启开关
     - 不授权：全局热键失效，浏览/播放等其余功能不受影响

  2. 自动化（点「浏览」选目录用）
     - 首次点播放器「浏览」按钮时，系统弹窗询问
       「是否允许 RVC视频伴侣 控制 System Events」
     - 点「允许」即可
     - 不授权：无法弹出选目录对话框

  [重要] 每次更新 .app 后，输入监控权限会失效（系统按程序签名记账），
     需重新到「系统设置 -> 隐私与安全性 -> 输入监控」勾选 RVC视频伴侣。
     不重新勾选仅影响全局热键，浏览/播放不受影响。


━━ 常见问题 ━━

  Q: 提示"服务器未启动"？
  A: 先确认 .app 的终端窗口还开着，且 http://127.0.0.1:8765 能打开

  Q: 点视频不播放？
  A: 这是"加载但暂停"设计，点一下视频中间的提示文字即可播放

  Q: 支持什么格式？
  A: MP4/M4V/WebM 直接播放；MKV/MOV/AVI/FLV 自动实时转码
     文件大小不限，本地转码很快

  Q: 键盘快捷键？
  A: S = 播放/暂停，A = 后退1秒，D = 前进1秒

  Q: 点「浏览」选目录时，访达窗口没弹出来？
  A: macOS 的访达弹窗有时会自动切到最前面，有时会躲在浏览器后面
     不自动弹出。如果点了「浏览」没看到窗口：
     - 看 Dock 栏的访达图标是否在跳动，点一下即可弹出
     - 或按 Command + Tab 切换到访达
     - 或点 Dock 栏最左侧的访达图标
     这是 macOS 系统行为，不影响功能，选完目录后会自动返回路径


━━ 隐私说明 ━━

  所有视频只在你的电脑本地处理。
  服务器只监听 127.0.0.1，不联网、不上传任何数据。

  版本 v3.2.0 · macOS 12+
INSTRUCTIONS

echo "==> [4/4] 打包 zip"
cd "$DIST"
ZIP_NAME="RVC视频伴侣.zip"
rm -f "$ZIP_NAME"
ditto -c -k --sequesterRsrc --keepParent "RVC视频伴侣" "$ZIP_NAME"

ZIP_SIZE=$(du -sh "$ZIP_NAME" | cut -f1)
echo ""
echo "  [完成] 分发包已生成：$DIST/$ZIP_NAME ($ZIP_SIZE)"
echo ""
echo "  内容："
echo "    RVC视频伴侣.app          ← 本地服务器（含 ffmpeg）"
echo "    reader-video-companion/  ← Chrome 扩展"
echo "    安装说明.txt              ← 使用指南"
echo ""
echo "  发给别人后：解压 → 双击 .app → Chrome 加载扩展 → 开用"
