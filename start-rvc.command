#!/bin/bash
# RVC 视频伴侣 - 双击启动（macOS .command 文件）
# 双击此文件 = 启动服务器 + 打开 aim-read.top

cd "$(dirname "$0")"
bash "$(dirname "$0")/start.sh"
echo ""
echo "[INFO] 按任意键关闭此窗口（服务器在后台继续运行）"
read -n 1
