#!/bin/bash
# ============================================================
# RVC 视频伴侣 - 一键安装脚本
#
# 用法（粘贴到终端回车即可）：
#   curl -fsSL https://raw.githubusercontent.com/wql18902-ux/rvc-video-companion/main/packaging/install.sh | bash
#
# 原理：curl 下载不会给文件打 macOS quarantine 隔离标记，
#       因此 .app 不会被 Gatekeeper 拦截，双击即可运行。
# ============================================================
set -euo pipefail

# --- 配置 ---
GITHUB_REPO="wql18902-ux/rvc-video-companion"
ZIP_URL="https://github.com/${GITHUB_REPO}/releases/latest/download/RVC-Video-Companion.zip"
INSTALL_DIR="$HOME/Applications/RVC视频伴侣"
ZIP_FILE="/tmp/RVC-Video-Companion.zip"

echo ""
echo "============================================"
echo "  RVC 视频伴侣 - 一键安装"
echo "============================================"
echo ""

# --- 1. 检查 macOS ---
if [ "$(uname)" != "Darwin" ]; then
  echo "[错误] 此脚本仅支持 macOS。"
  exit 1
fi

# --- 2. 下载 ---
echo "[1/4] 正在从 GitHub 下载..."
if command -v curl &>/dev/null; then
  curl -fSL --progress-bar -o "$ZIP_FILE" "$ZIP_URL"
elif command -v wget &>/dev/null; then
  wget -q --show-progress -O "$ZIP_FILE" "$ZIP_URL"
else
  echo "[错误] 需要 curl 或 wget，但都找不到。"
  exit 1
fi

if [ ! -f "$ZIP_FILE" ]; then
  echo "[错误] 下载失败，请检查网络连接。"
  exit 1
fi
echo "      下载完成 ($(du -sh "$ZIP_FILE" | cut -f1))"

# --- 3. 解压安装 ---
echo "[2/4] 解压到 ~/Applications/..."
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
unzip -qo "$ZIP_FILE" -d "$INSTALL_DIR"
rm -f "$ZIP_FILE"

# 处理 zip 内可能有的嵌套目录（zip 解压后可能多一层文件夹）
NESTED="$(find "$INSTALL_DIR" -maxdepth 1 -type d -name "RVC视频伴侣*" | head -1)"
if [ -n "$NESTED" ] && [ "$NESTED" != "$INSTALL_DIR" ]; then
  # 把嵌套内容提上来
  mv "$NESTED"/* "$INSTALL_DIR"/ 2>/dev/null || true
  mv "$NESTED"/.* "$INSTALL_DIR"/ 2>/dev/null || true
  rmdir "$NESTED" 2>/dev/null || true
fi

# --- 4. 验证 .app 存在 ---
echo "[3/4] 验证安装..."
APP_PATH="$INSTALL_DIR/RVC视频伴侣.app"
if [ ! -d "$APP_PATH" ]; then
  # 尝试找任何 .app
  APP_PATH="$(find "$INSTALL_DIR" -name "*.app" -maxdepth 2 | head -1)"
fi
if [ -z "$APP_PATH" ] || [ ! -d "$APP_PATH" ]; then
  echo "[错误] 解压后未找到 .app，请手动检查 $INSTALL_DIR"
  exit 1
fi

# 确认没有 quarantine（理论上 curl 下载不会有，但保险起见清一下）
xattr -cr "$APP_PATH" 2>/dev/null || true

echo "      已安装到：$INSTALL_DIR"

# --- 5. 启动 ---
echo "[4/4] 启动 RVC 视频伴侣..."
open "$APP_PATH"
sleep 2

# 检查是否启动成功
if curl -s "http://127.0.0.1:8765/api/files?dir=~" > /dev/null 2>&1; then
  echo ""
  echo "============================================"
  echo "  安装成功，服务器已启动！"
  echo ""
  echo "  下一步："
  echo "  1. 打开 Chrome → chrome://extensions"
  echo "  2. 开启「开发者模式」"
  echo "  3. 点「加载已解压的扩展程序」"
  echo "  4. 选择：$INSTALL_DIR/reader-video-companion"
  echo "  5. 打开 https://aim-read.top 点扩展图标"
  echo ""
  echo "  以后每次使用：双击 ~/Applications/RVC视频伴侣/RVC视频伴侣.app"
  echo "============================================"
else
  echo ""
  echo "============================================"
  echo "  安装完成！服务器正在启动中..."
  echo ""
  echo "  如果 10 秒后仍无法使用，请手动双击："
  echo "  $APP_PATH"
  echo ""
  echo "  Chrome 扩展目录："
  echo "  $INSTALL_DIR/reader-video-companion"
  echo "============================================"
fi

echo ""
