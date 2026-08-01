#!/bin/bash
# RVC 视频转码脚本：把 MKV/MOV 转成 Chrome 可播放的 MP4 + H.264 + AAC
# 用法：
#   转单个文件：./convert.sh /path/to/video.mkv
#   批量转：    ./convert.sh /path/to/folder
# 依赖：ffmpeg（macOS: brew install ffmpeg）

set -e

if ! command -v ffmpeg &> /dev/null; then
  echo "❌ 未安装 ffmpeg。macOS 安装：brew install ffmpeg"
  exit 1
fi

if [ -z "$1" ]; then
  echo "用法："
  echo "  转单个文件：$0 /path/to/video.mkv"
  echo "  批量转：    $0 /path/to/folder"
  exit 1
fi

convert_one() {
  local input="$1"
  local dir
  dir="$(dirname "$input")"
  local base
  base="$(basename "$input")"
  local name="${base%.*}"
  local output="$dir/${name}.mp4"

  # 如果输出已存在且比输入新，跳过
  if [ -f "$output" ] && [ "$output" -nt "$input" ]; then
    echo "⏭  已存在且最新，跳过：$output"
    return 0
  fi

  echo "🔄 转码中：$base → ${name}.mp4"
  # -c:v libx264：视频用 H.264（Chrome 完美支持）
  # -c:a aac：音频用 AAC（Chrome 完美支持）
  # -preset fast：速度/质量平衡
  # -crf 23：质量（18-28，越小质量越好，23 是默认）
  # -movflags +faststart：网页播放友好（moov atom 前置）
  # -map 0:v:0 -map 0:a:0：只取第一条视频流和第一条音频流，避免字幕流干扰
  if ffmpeg -i "$input" \
    -c:v libx264 -preset fast -crf 23 \
    -c:a aac -b:a 192k \
    -movflags +faststart \
    -map 0:v:0 -map 0:a:0? \
    -y "$output" 2>&1 | tail -5; then
    echo "✅ 完成：$output"
  else
    echo "❌ 失败：$input"
    return 1
  fi
}

target="$1"
if [ -f "$target" ]; then
  convert_one "$target"
elif [ -d "$target" ]; then
  echo "📂 批量转码目录：$target"
  echo "----------------------------------------"
  count=0
  fail=0
  # 递归找所有 mkv/mov/avi/flv/webm
  while IFS= read -r -d '' file; do
    count=$((count + 1))
    convert_one "$file" || fail=$((fail + 1))
  done < <(find "$target" \( -iname '*.mkv' -o -iname '*.mov' -o -iname '*.avi' -o -iname '*.flv' \) -print0)
  echo "----------------------------------------"
  echo "总计：$count 个，成功 $((count - fail)) 个，失败 $fail 个"
  if [ "$count" -eq 0 ]; then
    echo "（目录下没有 mkv/mov/avi/flv 文件）"
  fi
else
  echo "❌ 路径不存在：$target"
  exit 1
fi
