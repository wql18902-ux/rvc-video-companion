#!/bin/bash
# RVC 流式播放器 - 一键启动脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER="$SCRIPT_DIR/server.py"

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
echo "启动 RVC 流式播放器..."
python3 "$SERVER"
