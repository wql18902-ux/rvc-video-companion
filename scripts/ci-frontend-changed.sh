#!/bin/bash
# CI 前端变更检测 —— 判定本次推送/PR 是否触及前端（reader-video-companion/ 全部文件）
#
# 用途：作为 CI 回退闸门的判据。前端（content.js/player.css/manifest/background.js）
#       的行为验证只有 L3 acceptance（冻结基准）能覆盖；本地 pre-push 钩子可被
#       --no-verify 绕过，CI 必须独立判定「前端是否变更」并强制跑 L3。
#
# 用法: bash scripts/ci-frontend-changed.sh <base-sha>
#   <base-sha> 由调用方传入：push 事件用 github.event.before，PR 用 base.sha
#   （无效 base = 首次推送/手动触发，保守按「前端变更」处理）
#
# 输出（stdout，key=value）:
#   changed=yes|no          前端是否变更
#   reason=...              判定依据（可审计）
#   changed_files=...       changed=yes 时的前端文件列表（逗号分隔）
# 退出码恒为 0（判定结果通过 changed= 传递，不把检测失败伪装成 CI 失败）
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

BASE="${1:-}"
ZERO="0000000000000000000000000000000000000000"

if [ -z "$BASE" ] || [ "$BASE" = "$ZERO" ]; then
  echo "changed=yes"
  echo "reason=no-valid-base（首次推送或手动触发，无法 diff，保守按前端变更处理）"
  exit 0
fi

MB="$(git merge-base "$BASE" HEAD 2>/dev/null || true)"
if [ -z "$MB" ]; then
  echo "changed=yes"
  echo "reason=merge-base($BASE) 不可得，保守按前端变更处理"
  exit 0
fi

CHANGED="$(git diff --name-only "$MB" HEAD 2>/dev/null || true)"
FRONT="$(echo "$CHANGED" | grep '^reader-video-companion/' || true)"
if [ -n "$FRONT" ]; then
  echo "changed=yes"
  echo "reason=merge-base $MB .. HEAD 触及 reader-video-companion/"
  echo "changed_files=$(echo "$FRONT" | tr '\n' ',' | sed 's/,$//')"
else
  echo "changed=no"
  echo "reason=merge-base $MB .. HEAD 未触及 reader-video-companion/"
fi
