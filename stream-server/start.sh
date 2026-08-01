#!/bin/bash
# RVC 视频伴侣 - 一键启动脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER="$SCRIPT_DIR/server.py"

# Finder 双击 .command 时 PATH 是 launchd 精简版（/usr/bin:/bin:/usr/sbin:/sbin），
# 找不到 brew 的 ffmpeg/python3 导致启动即失败。这里把 brew bin 补回 PATH。
for p in /opt/homebrew/bin /usr/local/bin; do
  if [ -d "$p" ] && [[ ":$PATH:" != *":$p:"* ]]; then
    export PATH="$p:$PATH"
  fi
done

# 检查 ffmpeg
if ! command -v ffmpeg &> /dev/null; then
  echo "[ERROR] 未安装 ffmpeg，请先安装：brew install ffmpeg"
  exit 1
fi

# 检查 ffprobe
if ! command -v ffprobe &> /dev/null; then
  echo "[ERROR] 未安装 ffprobe，请先安装：brew install ffmpeg"
  exit 1
fi

# 检查 mpegts.js
if [ ! -f "$SCRIPT_DIR/mpegts.min.js" ]; then
  echo "[ERROR] 缺少 mpegts.min.js，请重新安装"
  exit 1
fi

# 启动服务器
echo "启动 RVC 视频伴侣..."
python3 "$SERVER"
