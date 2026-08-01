#!/bin/bash
# RVC git hooks 安装/回滚 —— 把 scripts/check.sh 接入本地 git 作为进入主干的唯一通路
#
#   bash scripts/install-hooks.sh           安装：pre-commit（静态秒级）+ pre-push（静态+验收全量）
#   bash scripts/install-hooks.sh --uninstall  回滚：卸载两个钩子（scripts/ 仍在仓库，可随时重装）
#
# 注意：git 不跟踪 .git/hooks/，钩子只在本机生效；机制本体随 scripts/ 提交进仓库可传播。
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_DIR="$ROOT/.git/hooks"
CHECK="$ROOT/scripts/check.sh"

install() {
  mkdir -p "$HOOK_DIR"
  cat > "$HOOK_DIR/pre-commit" <<EOF
#!/bin/bash
# RVC pre-commit：静态检查（秒级）。全量（静态+验收）在 pre-push。
# 紧急绕过：git commit --no-verify
# 回滚：bash scripts/install-hooks.sh --uninstall
exec bash "$CHECK" --static
EOF
  cat > "$HOOK_DIR/pre-push" <<EOF
#!/bin/bash
# RVC pre-push：静态 + 验收全量检查，进入主干的唯一通路，推送前必须通过。
# 紧急绕过（不推荐，绕过即失去唯一通路）：git push --no-verify
# 回滚：bash scripts/install-hooks.sh --uninstall
exec bash "$CHECK"
EOF
  chmod +x "$HOOK_DIR/pre-commit" "$HOOK_DIR/pre-push"
  echo "[OK] 已安装 hooks："
  echo "     $HOOK_DIR/pre-commit  （静态检查，提交前必过）"
  echo "     $HOOK_DIR/pre-push     （静态 + 验收全量，主干推送前必过）"
  echo ""
  echo "预演：bash scripts/check.sh --static"
  echo "回滚：bash scripts/install-hooks.sh --uninstall"
}

uninstall() {
  rm -f "$HOOK_DIR/pre-commit" "$HOOK_DIR/pre-push"
  echo "[OK] 已卸载 hooks（回滚完成）。"
  echo "     scripts/ 仍留在仓库，随时可 bash scripts/install-hooks.sh 重装。"
  echo "     钩子只做前置检查，不改变 git 历史，已推送内容不受影响。"
}

case "${1:-}" in
  --uninstall) uninstall ;;
  "" | install) install ;;
  *) echo "用法: $0 [--uninstall]"; exit 1 ;;
esac
