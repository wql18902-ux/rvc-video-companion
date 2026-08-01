#!/bin/bash
# ============================================================
# RVC 内部版 - 打 .crx 脚本
# 产物：packaging/reader-video-companion.crx + rvc-key.pem
# 首次运行自动生成 key，后续复用（同一 key 保证升级安装不丢数据）
# ============================================================
set -euo pipefail

PKG_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$PKG_DIR/.." && pwd)"
EXT_DIR="$PROJECT_ROOT/reader-video-companion"
KEY="$PKG_DIR/rvc-key.pem"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

[ -x "$CHROME" ] || { echo "❌ 未找到 Google Chrome（$CHROME）"; exit 1; }

# 打包前清理 .DS_Store 等系统文件，避免混入包内
find "$EXT_DIR" -name ".DS_Store" -delete

echo "==> 打包扩展: $EXT_DIR"
if [ -f "$KEY" ]; then
  "$CHROME" --pack-extension="$EXT_DIR" --pack-extension-key="$KEY" >/dev/null 2>&1
  echo "    复用已有 key: $KEY"
else
  "$CHROME" --pack-extension="$EXT_DIR" >/dev/null 2>&1
  # Chrome 把 key 生成在扩展目录旁，名为 <扩展名>.pem
  if [ -f "$PROJECT_ROOT/reader-video-companion.pem" ]; then
    mv "$PROJECT_ROOT/reader-video-companion.pem" "$KEY"
    echo "    首次打包，key 已保存: $KEY"
  elif [ -f "$EXT_DIR/key.pem" ]; then
    mv "$EXT_DIR/key.pem" "$KEY"
    echo "    首次打包，key 已保存: $KEY"
  fi
fi

if [ -f "$PROJECT_ROOT/reader-video-companion.crx" ]; then
  mv "$PROJECT_ROOT/reader-video-companion.crx" "$PKG_DIR/reader-video-companion.crx"
fi

echo ""
echo "  ✅ 产物：$PKG_DIR/reader-video-companion.crx"
ls -lh "$PKG_DIR/reader-video-companion.crx"
echo ""
echo "  注意：.crx 只能在「开发者模式」下拖入 chrome://extensions 安装"
echo "  （未上架商店的 crx 新版本 Chrome 默认拒绝直接安装，开发者模式可绕过）"
