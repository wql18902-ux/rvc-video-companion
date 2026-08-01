#!/bin/bash
# ============================================================
# RVC 视频伴侣 - 一键发布流水线
# 用法：bash packaging/release.sh [--dry-run]
# 流程：build.sh → make-distro.sh → gh release (draft)
# ============================================================
set -euo pipefail

PKG_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$PKG_DIR/.." && pwd)"
EXT_DIR="$PROJECT_ROOT/reader-video-companion"
ZIP="$PKG_DIR/dist/RVC视频伴侣.zip"

# ADR-001: 版本号唯一源 = manifest.json
VER="$(python3 -c "import json;print(json.load(open('$EXT_DIR/manifest.json'))['version'])")"
TAG="v$VER"

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    *) echo "[WARN] 未知参数: $arg（仅支持 --dry-run）" ;;
  esac
done

run() {
  if [ "$DRY_RUN" = 1 ]; then
    echo "[DRY-RUN] $*"
  else
    echo "==> $*"
    "$@"
  fi
}

echo "=== RVC 发布流水线：$TAG ==="
echo ""

# --- 步骤 1：构建 .app ---
echo "[1/3] 构建 .app"
run bash "$PROJECT_ROOT/stream-server/packaging/build.sh"

# --- 步骤 2：打包发行 zip ---
echo ""
echo "[2/3] 打包发行 zip"
run bash "$PKG_DIR/make-distro.sh"

# --- 步骤 3：上传 GitHub Release（草稿）---
echo ""
echo "[3/3] 上传 GitHub Release"

if [ "$DRY_RUN" = 1 ]; then
  # dry-run：只打印将执行的命令
  if gh release view "$TAG" >/dev/null 2>&1; then
    run gh release upload "$TAG" "$ZIP" --clobber
  else
    run gh release create "$TAG" "$ZIP" --title "$TAG" --draft --generate-notes
  fi
else
  # 真实执行
  if ! [ -f "$ZIP" ]; then
    echo "[错误] 未找到 $ZIP，构建可能失败"
    exit 1
  fi
  if gh release view "$TAG" >/dev/null 2>&1; then
    echo "==> Release $TAG 已存在，覆盖上传资产"
    gh release upload "$TAG" "$ZIP" --clobber
  else
    echo "==> 创建草稿 Release $TAG"
    gh release create "$TAG" "$ZIP" --title "$TAG" --draft --generate-notes
  fi
fi

echo ""
echo "=== 完成 ==="
echo "草稿已创建：gh release edit $TAG --draft=false 即可发布"
