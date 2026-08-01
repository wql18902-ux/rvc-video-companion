#!/bin/bash
# ============================================================
# RVC 流式播放器 - Mac 一键打包脚本（内部版）
# 产物：packaging/dist/RVC视频伴侣.app（约 100-150MB）
# 依赖：python3 + brew ffmpeg（或 PATH 中的 ffmpeg/ffprobe）
# ============================================================
set -euo pipefail

PKG_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$PKG_DIR/../.." && pwd)"
STREAM_DIR="$PROJECT_ROOT/stream-server"
BUILD_DIR="$PKG_DIR/build"
STAGING="$BUILD_DIR/staging"
VENV="$PKG_DIR/.venv"

echo "==> [1/4] 准备 PyInstaller venv"
if [ ! -x "$VENV/bin/pyinstaller" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet pyinstaller
fi
# pynput 是 server.py 热键子进程依赖，装进 venv 供 PyInstaller 收集（防 hidden import not found）
"$VENV/bin/pip" install --quiet pynput

echo "==> [2/4] 收集 ffmpeg/ffprobe 及依赖 dylib（改写为 @executable_path 相对路径）"
FFMPEG_SRC="$(command -v ffmpeg)"
FFPROBE_SRC="$(command -v ffprobe)"
[ -n "$FFMPEG_SRC" ] || { echo "❌ 未找到 ffmpeg，请先 brew install ffmpeg"; exit 1; }
[ -n "$FFPROBE_SRC" ] || { echo "❌ 未找到 ffprobe"; exit 1; }

rm -rf "$STAGING"
mkdir -p "$STAGING/ffmpeg/bin" "$STAGING/ffmpeg/lib"
cp "$FFMPEG_SRC" "$STAGING/ffmpeg/bin/ffmpeg"
cp "$FFPROBE_SRC" "$STAGING/ffmpeg/bin/ffprobe"
chmod +x "$STAGING/ffmpeg/bin/ffmpeg" "$STAGING/ffmpeg/bin/ffprobe"

# 阶段1：递归复制所有非系统依赖 dylib（用源二进制解析 @rpath/@loader_path）
resolve_dep_path() {
  local dep="$1"
  local src_binary="$2"
  local binary_dir
  binary_dir="$(dirname "$src_binary")"
  if [[ "$dep" == @rpath/* ]]; then
    local libname="${dep#@rpath/}"
    for rpath in $(otool -l "$src_binary" | awk '/LC_RPATH/{getline; print $2}'); do
      local resolved_dir
      if [[ "$rpath" == @loader_path* ]]; then
        resolved_dir="${binary_dir}/${rpath#@loader_path}"
      else
        resolved_dir="$rpath"
      fi
      resolved_dir="$(cd "$resolved_dir" 2>/dev/null && pwd)"
      if [ -n "$resolved_dir" ] && [ -f "$resolved_dir/$libname" ]; then
        echo "$resolved_dir/$libname"
        return
      fi
    done
  elif [[ "$dep" == @loader_path/* ]]; then
    local real_path="${binary_dir}/${dep#@loader_path/}"
    if [ -f "$real_path" ]; then
      echo "$real_path"
      return
    fi
  elif [[ "$dep" == /* ]] && [ -f "$dep" ]; then
    echo "$dep"
    return
  fi
}

# 用源路径解析 dylib，复制到 staging
queue_src=("$FFMPEG_SRC" "$FFPROBE_SRC")
while [ ${#queue_src[@]} -gt 0 ]; do
  src_f="${queue_src[0]}"
  queue_src=("${queue_src[@]:1}")
  while IFS= read -r dep; do
    resolved="$(resolve_dep_path "$dep" "$src_f")"
    [ -z "$resolved" ] && continue
    name="$(basename "$resolved")"
    target="$STAGING/ffmpeg/lib/$name"
    if [ ! -e "$target" ] && [ -f "$resolved" ]; then
      cp "$resolved" "$target"
      chmod +w "$target"
      queue_src+=("$resolved")
    fi
  done < <(otool -L "$src_f" | awk '/^\t.*\.dylib/{print $1}' | grep -v '^/usr/lib/' | grep -v '^/System/')
done

# 阶段2：统一改写引用（@rpath/@loader_path/绝对路径 → @executable_path）
ALL_DYLIB_PREFIX="@executable_path/../Resources/_internal/ffmpeg/lib"
for f in "$STAGING/ffmpeg/bin/ffmpeg" "$STAGING/ffmpeg/bin/ffprobe" "$STAGING"/ffmpeg/lib/*.dylib; do
  [ -f "$f" ] || continue
  while IFS= read -r dep; do
    name="$(basename "$dep")"
    install_name_tool -change "$dep" "$ALL_DYLIB_PREFIX/$name" "$f" 2>/dev/null || true
  done < <(otool -L "$f" | awk '/^\t.*\.dylib/{print $1}' | grep -v '^/usr/lib/' | grep -v '^/System/')
  if [[ "$f" == *.dylib ]]; then
    install_name_tool -id "$ALL_DYLIB_PREFIX/$(basename "$f")" "$f" 2>/dev/null || true
  fi
done

echo "    收集到 $(ls "$STAGING/ffmpeg/lib" | wc -l | tr -d ' ') 个 dylib"

echo "==> [3/4] 生成 .app 图标（icns）"
ICON_PNG="$PROJECT_ROOT/reader-video-companion/icons/icon128.png"
ICONSET="$BUILD_DIR/icon.iconset"
if [ -f "$ICON_PNG" ]; then
  rm -rf "$ICONSET"; mkdir -p "$ICONSET"
  for size in 16 32 64 128 256 512; do
    sips -z $size $size "$ICON_PNG" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null 2>&1
    sips -z $((size*2)) $((size*2)) "$ICON_PNG" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null 2>&1
  done
  iconutil -c icns "$ICONSET" -o "$BUILD_DIR/rvc.icns"
  echo "    icns 已生成"
fi

echo "==> [4/4] PyInstaller onedir 打包 + 手动组装 .app"
"$VENV/bin/pyinstaller" --clean --noconfirm \
  --distpath "$BUILD_DIR/dist" --workpath "$BUILD_DIR/pyinstaller" \
  "$PKG_DIR/rvc-server.spec"

APP="$PKG_DIR/dist/RVC视频伴侣.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Frameworks" "$APP/Contents/Resources"
cp "$BUILD_DIR/dist/rvc-server/rvc-server" "$APP/Contents/MacOS/rvc-server" 2>/dev/null || \
  cp "$BUILD_DIR/pyinstaller/rvc-server/rvc-server" "$APP/Contents/MacOS/rvc-server"
chmod +x "$APP/Contents/MacOS/rvc-server"
# PyInstaller 6.21 macOS .app 布局：pylib 目录 = Contents/Frameworks（sys._MEIPASS endswith Contents/Frameworks）。
# onedir 的 _internal 内容平铺进 Frameworks；其中 Python -> Python.framework/Versions/3.14/Python 的
# symlink 由 cp -R 原样保留，bootloader 据此 dlopen Frameworks/Python。
cp -R "$BUILD_DIR/dist/rvc-server/_internal/." "$APP/Contents/Frameworks/"
# Resources 侧放数据文件（图标等），并交叉链接 _internal 供规范布局
if [ -f "$BUILD_DIR/rvc.icns" ]; then
  cp "$BUILD_DIR/rvc.icns" "$APP/Contents/Resources/rvc.icns"
fi

# 图标
if [ -f "$BUILD_DIR/rvc.icns" ]; then
  cp "$BUILD_DIR/rvc.icns" "$APP/Contents/Resources/rvc.icns"
fi

# Info.plist
cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>rvc-server</string>
  <key>CFBundleIdentifier</key><string>com.rvc.stream-server</string>
  <key>CFBundleName</key><string>RVC视频伴侣</string>
  <key>CFBundleDisplayName</key><string>RVC视频伴侣</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>3.2.0</string>
  <key>CFBundleShortVersionString</key><string>3.2.0</string>
  <key>CFBundleIconFile</key><string>rvc.icns</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
EOF

echo ""
echo "=============================================="
echo "  ✅ 打包完成：$APP"
echo ""
echo "  安装/使用（内部版三步走）："
echo "  1. 双击 RVC视频伴侣.app 启动服务器（首次需右键 -> 打开）"
echo "  2. 浏览器加载 reader-video-companion 扩展（.crx 或开发者模式加载）"
echo "  3. 打开 aim-read.top 点扩展图标即可使用"
echo "=============================================="
