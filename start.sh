#!/bin/bash
# RVC 视频伴侣 - 一键启动（本地自用版）
# 用法：在项目根目录运行 bash start.sh
# 功能：启动本地转码服务器 + 自动打开 aim-read.top

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8765
SERVER_URL="http://127.0.0.1:$PORT"
LOG_FILE="/tmp/rvc-server.log"

# --- 1. 检查服务器是否已在运行 ---
if curl -s "$SERVER_URL/api/files?dir=~" > /dev/null 2>&1; then
  echo "[OK] 服务器已在运行 ($SERVER_URL)"
else
  echo "[INFO] 启动本地转码服务器..."

  # 后台启动，日志输出到文件
  nohup bash "$SCRIPT_DIR/stream-server/start.sh" > "$LOG_FILE" 2>&1 &
  echo "[INFO] 服务器日志：$LOG_FILE"

  # 等待就绪（最多 15 秒）
  ready=false
  for i in $(seq 1 30); do
    if curl -s "$SERVER_URL/api/files?dir=~" > /dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 0.5
  done

  if [ "$ready" = true ]; then
    echo "[OK] 服务器已启动 ($SERVER_URL)"
  else
    echo "[ERROR] 服务器启动失败，请查看日志：$LOG_FILE"
    echo "[ERROR] 或手动运行 bash stream-server/start.sh 查看错误信息"
    exit 1
  fi
fi

# --- 2. 打开 aim-read.top ---
echo "[INFO] 打开 aim-read.top..."
if open -a "Google Chrome" "https://aim-read.top" 2>/dev/null; then
  :
else
  open "https://aim-read.top" 2>/dev/null
fi

echo "[OK] 完成！在 aim-read.top 页面点浏览器右上角扩展图标唤出播放器"
