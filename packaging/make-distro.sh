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

echo "==> [3/4] 写入安装说明和首次打开脚本"

# --- 首次打开脚本（解决 macOS「已损坏」拦截）---
cat > "$STAGING/首次打开-点我.command" <<'COMMAND_SCRIPT'
#!/bin/bash
# RVC 视频伴侣 - 清除 macOS 隔离标记
# 作用：解决从浏览器下载后双击 .app 报「已损坏，无法打开」的问题
# 原理：删除 macOS 给下载文件打的 quarantine 隔离属性

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_PATH="$APP_DIR/RVC视频伴侣.app"

echo ""
echo "============================================"
echo "  RVC 视频伴侣 - 首次打开修复工具"
echo "============================================"
echo ""

if [ ! -d "$APP_PATH" ]; then
    echo "[错误] 找不到 RVC视频伴侣.app"
    echo "请确保此脚本和 RVC视频伴侣.app 在同一个文件夹里。"
    echo ""
    read -p "按回车键关闭窗口..."
    exit 1
fi

echo "正在清除 macOS 隔离标记..."
xattr -cr "$APP_PATH" 2>/dev/null

# 验证是否清除成功
if xattr -l "$APP_PATH" 2>/dev/null | grep -q "com.apple.quarantine"; then
    echo ""
    echo "[警告] 隔离标记未能完全清除，请尝试手动执行："
    echo "  打开「终端」app，粘贴以下命令后回车："
    echo ""
    echo "  xattr -cr \"$APP_PATH\""
    echo ""
else
    echo ""
    echo "============================================"
    echo "  清除完成！"
    echo ""
    echo "  现在可以双击「RVC视频伴侣.app」启动了。"
    echo "  （本脚本以后不需要再运行）"
    echo "============================================"
fi

echo ""
read -p "按回车键关闭窗口..."
COMMAND_SCRIPT
chmod +x "$STAGING/首次打开-点我.command"

# --- 安装说明 ---
cat > "$STAGING/安装说明.txt" <<'INSTRUCTIONS'
╔══════════════════════════════════════════════╗
║         RVC 视频伴侣 - 安装指南              ║
╚══════════════════════════════════════════════╝

只需 4 步，3 分钟搞定。


━━ 第 0 步：清除隔离标记（首次必做）━━

  从浏览器下载的文件会被 macOS 标记为「隔离」，
  直接双击 .app 会报「已损坏，无法打开」。

  解决方法（二选一）：

  方法 A（推荐）：双击「首次打开-点我.command」
    - 如果系统提示「无法打开」或「无法验证开发者」：
      右键点它 → 选「打开」→ 点确认
    - 如果右键也没有「打开」选项：
      打开 系统设置 → 隐私与安全性 → 往下滚
      会看到「已阻止使用 首次打开-点我.command」
      点旁边的「仍要打开」按钮
    - 终端窗口会闪一下，显示「清除完成」即可

  方法 B（手动）：打开「终端」app，粘贴这行命令后回车：
    xattr -cr ~/Downloads/RVC视频伴侣/RVC视频伴侣.app
    （路径根据你实际解压位置调整）

  做完第 0 步后，以后每次打开 .app 都不会再被拦截。


━━ 第 1 步：启动服务器 ━━

  1. 双击「RVC视频伴侣.app」
  2. 首次打开如果还提示拦截：右键 → 打开 → 确认
  3. 没有终端窗口弹出 = 正常运行（后台模式）
  4. 验证：打开浏览器访问 http://127.0.0.1:8765
     能看到页面就说明服务器在跑


━━ 第 2 步：安装 Chrome 扩展 ━━

  1. 打开 Chrome 浏览器
  2. 地址栏输入 chrome://extensions 回车
  3. 打开右上角「开发者模式」开关
  4. 点左上角「加载已解压的扩展程序」
  5. 选择本文件夹里的「reader-video-companion」文件夹
  6. 扩展列表里出现「RVC 视频伴侣」就装好了


━━ 第 3 步：开始使用 ━━

  1. 打开 https://aim-read.top
  2. 点浏览器右上角扩展图标栏（拼图形状）
  3. 找到「RVC 视频伴侣」，点固定图标钉到工具栏
  4. 点 RVC 图标唤出浮窗播放器
  5. 点播放器标题栏的文件夹图标 → 「浏览」→ 选本地视频目录
  6. 列表里点视频文件开始播放

  之后每次使用：先双击 .app 启动服务器，再打开网页点图标。


━━ 权限说明 ━━

  输入监控（全局热键 S/A/D 用）：
    - 首次使用时系统会弹窗请求，点「允许」
    - 或手动开启：系统设置 → 隐私与安全性 → 输入监控 → 勾选 RVC视频伴侣
    - 不授权：全局热键失效，页面内热键和其余功能不受影响

  [提示] 每次更新 .app 后输入监控权限会失效，需重新勾选。


━━ 常见问题 ━━

  Q: 双击 .app 报「已损坏，无法打开」？
  A: 你没做第 0 步。双击「首次打开-点我.command」或手动跑 xattr -cr。

  Q: 提示"服务器未启动"？
  A: 确认 .app 在运行（活动监视器搜 RVC），或访问 127.0.0.1:8765 看有无响应

  Q: 点「浏览」选目录时没弹窗？
  A: 看 Dock 栏访达图标是否跳动，点一下即可。或按 Cmd+Tab 切到访达。

  Q: 支持什么格式？
  A: MP4/M4V/WebM 直接播放；MKV/MOV/AVI/FLV 自动实时转码，大小不限

  Q: 键盘快捷键？
  A: S = 播放/暂停，A = 后退1秒，D = 前进1秒（鼠标需在播放器上方）


━━ 隐私说明 ━━

  所有视频只在你的电脑本地处理。
  服务器只监听 127.0.0.1，不联网、不上传任何数据。

  版本 v3.2.2 · macOS 12+
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
echo "    RVC视频伴侣.app              ← 本地服务器（含 ffmpeg）"
echo "    reader-video-companion/      ← Chrome 扩展"
echo "    首次打开-点我.command         ← 清除隔离标记（首次必跑）"
echo "    安装说明.txt                  ← 使用指南"
echo ""
echo "  发给别人后：解压 → 双击 .command → 双击 .app → Chrome 加载扩展 → 开用"
