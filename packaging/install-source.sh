#!/bin/bash
# ============================================================
# RVC 视频伴侣 - 源代码版一键安装
#
# 用法（粘贴到终端回车即可）：
#   curl -fsSL https://raw.githubusercontent.com/wql18902-ux/rvc-video-companion/main/packaging/install-source.sh | bash
#
# 适合：有 Homebrew 的开发者/技术用户
# 原理：源代码（Python + bash）不触发 Gatekeeper，零拦截
# ============================================================
set -euo pipefail

GITHUB_REPO="wql18902-ux/rvc-video-companion"
ZIP_URL="https://github.com/${GITHUB_REPO}/archive/refs/heads/main.zip"
INSTALL_DIR="$HOME/Applications/RVC视频伴侣-源码版"
ZIP_FILE="/tmp/rvc-source.zip"

echo ""
echo "============================================"
echo "  RVC 视频伴侣 - 源代码版安装"
echo "============================================"
echo ""

# --- 1. 检查 macOS ---
if [ "$(uname)" != "Darwin" ]; then
  echo "[错误] 此脚本仅支持 macOS。"
  exit 1
fi

# --- 2. 检查依赖 ---
echo "[1/5] 检查依赖..."

MISSING=()
if ! command -v python3 &>/dev/null; then
  MISSING+=("python3")
fi
if ! command -v ffmpeg &>/dev/null; then
  MISSING+=("ffmpeg")
fi
if ! command -v ffprobe &>/dev/null; then
  MISSING+=("ffprobe")
fi

if [ ${#MISSING[@]} -gt 0 ]; then
  echo ""
  echo "  缺少以下依赖：${MISSING[*]}"
  echo ""
  if command -v brew &>/dev/null; then
    echo "  正在用 Homebrew 自动安装..."
    for dep in "${MISSING[@]}"; do
      case "$dep" in
        python3) brew install python3 ;;
        ffmpeg|ffprobe) brew install ffmpeg ;;
      esac
    done
    echo "  依赖安装完成。"
  else
    echo "  请先安装 Homebrew（https://brew.sh），然后运行："
    echo "    brew install python3 ffmpeg"
    echo ""
    echo "  或者手动安装以上依赖后重新运行此脚本。"
    exit 1
  fi
fi

# 检查 Python 依赖：服务器仅用标准库（http.server），无需 pip 包；
# pynput 为全局热键可选依赖（缺失时仅热键失效，服务器其余功能正常）
python3 -c "import pynput" 2>/dev/null || {
  echo "      安装 Python 依赖 (pynput)..."
  python3 -m pip install --quiet pynput 2>/dev/null || pip3 install --quiet pynput
}

echo "      依赖检查通过。"

# --- 3. 下载源码 ---
echo "[2/5] 从 GitHub 下载源代码..."
if command -v curl &>/dev/null; then
  curl -fSL --progress-bar -o "$ZIP_FILE" "$ZIP_URL"
else
  wget -q --show-progress -O "$ZIP_FILE" "$ZIP_URL"
fi

if [ ! -f "$ZIP_FILE" ]; then
  echo "[错误] 下载失败，请检查网络连接。"
  exit 1
fi
echo "      下载完成。"

# --- 4. 解压安装 ---
echo "[3/5] 解压到 ~/Applications/..."
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
unzip -qo "$ZIP_FILE" -d /tmp/rvc-source-extract
rm -f "$ZIP_FILE"

# GitHub archive zip 内有一层 rvc-video-companion-main/ 目录
EXTRACTED="$(find /tmp/rvc-source-extract -maxdepth 1 -type d -name "rvc-video-companion*" | head -1)"
if [ -n "$EXTRACTED" ]; then
  cp -R "$EXTRACTED/." "$INSTALL_DIR/"
else
  cp -R /tmp/rvc-source-extract/. "$INSTALL_DIR/"
fi
rm -rf /tmp/rvc-source-extract

# 清理不需要的文件
rm -rf "$INSTALL_DIR/.git" "$INSTALL_DIR/__pycache__" "$INSTALL_DIR"/*/__pycache__
find "$INSTALL_DIR" -name ".DS_Store" -delete 2>/dev/null || true
find "$INSTALL_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# 确保脚本有执行权限
chmod +x "$INSTALL_DIR/start.sh" 2>/dev/null || true
chmod +x "$INSTALL_DIR/stream-server/start.sh" 2>/dev/null || true

echo "      已安装到：$INSTALL_DIR"

# --- 5. 写入启动快捷命令 ---
echo "[4/5] 创建启动脚本..."
cat > "$INSTALL_DIR/启动.command" <<'CMD'
#!/bin/bash
cd "$(dirname "$0")"
bash start.sh
echo ""
echo "[INFO] 按任意键关闭此窗口（服务器在后台继续运行）"
read -n 1
CMD
chmod +x "$INSTALL_DIR/启动.command"

# --- 6. 测试启动（轮询等待就绪）---
echo "[5/5] 测试启动服务器..."
cd "$INSTALL_DIR"
bash start.sh &
SERVER_PID=$!

echo "      等待服务器就绪..."
READY=0
for i in $(seq 1 15); do
  if curl -s --max-time 2 "http://127.0.0.1:8765/api/files?dir=~" > /dev/null 2>&1; then
    READY=1; break
  fi
  sleep 1
done

if [ "$READY" -eq 1 ]; then
  echo ""
  echo "============================================"
  echo "  安装成功，服务器已启动！"
  echo ""
  echo "  下一步：安装 Chrome 扩展"
  echo "  1. Chrome 打开 chrome://extensions"
  echo "  2. 开启「开发者模式」"
  echo "  3. 点「加载已解压的扩展程序」"
  echo "  4. 选择：$INSTALL_DIR/reader-video-companion"
  echo "  5. 打开 https://aim-read.top 点扩展图标"
  echo ""
  echo "  以后每次使用："
  echo "    cd $INSTALL_DIR && bash start.sh"
  echo "  或双击：$INSTALL_DIR/启动.command"
  echo "============================================"
else
  echo ""
  echo "  服务器可能未启动成功。请手动运行："
  echo "    cd $INSTALL_DIR && bash start.sh"
  echo "  查看具体错误信息。"
fi

echo ""
