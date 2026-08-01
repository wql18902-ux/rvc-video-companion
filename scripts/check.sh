#!/bin/bash
# RVC 统一检查 —— 进入主干的唯一通路
#
# 静态检查（秒级）+ 验收脚本 tests/acceptance.py（分钟级）
#   scripts/check.sh             全量（静态 + 验收），pre-push 使用
#   scripts/check.sh --static    仅静态，pre-commit 使用
#   scripts/check.sh --no-retry  验收失败不自动重试（B9 F 步 flaky 默认重试一次）
#
# 回滚/紧急绕过（详见 CLAUDE.md「检查与回滚」节）：
#   紧急绕过：git commit --no-verify / git push --no-verify（绕过即失去唯一通路）
#   永久卸载：bash scripts/install-hooks.sh --uninstall（scripts/ 仍在仓库，可随时重装）
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

STATIC_ONLY=0
ALLOW_RETRY=1
for arg in "$@"; do
  case "$arg" in
    --static) STATIC_ONLY=1 ;;
    --no-retry) ALLOW_RETRY=0 ;;
    *) echo "[WARN] 未知参数: $arg" ;;
  esac
done

# TRAE 会注入 PYTHONHOME/PYTHONPATH 导致 "No module named 'encodings'"，跑 python 一律清掉
if [ -x /opt/homebrew/bin/python3 ]; then
  PY_BIN=/opt/homebrew/bin/python3
else
  PY_BIN=python3
fi
run_py() { env -u PYTHONHOME -u PYTHONPATH "$PY_BIN" "$@"; }

FAIL=0
pass() { echo "[PASS] $*"; }
fail() { echo "[FAIL] $*"; FAIL=1; }

echo "===== RVC 检查：静态 ====="

# 1. 判卷三文件 sha256 冻结（acceptance.py/test.html/sample.mp4，碰都不许碰）
FROZEN="tests/acceptance.py:c1965638 test.html:4b79893e tests/fixtures/sample.mp4:9b4a8281"
for entry in $FROZEN; do
  f="${entry%%:*}"; want="${entry##*:}"
  if [ -f "$f" ]; then
    got="$(shasum -a 256 "$f" | cut -c1-8)"
    if [ "$got" = "$want" ]; then pass "sha256 冻结 $f ($got)"; else fail "sha256 冻结 $f 期望 $want 实测 $got（判卷文件不许改！）"; fi
  else
    fail "sha256 冻结 $f 文件缺失"
  fi
done
if git diff --quiet HEAD -- tests/acceptance.py test.html tests/fixtures/sample.mp4; then
  pass "冻结文件工作区/暂存区无改动"
else
  fail "冻结文件在工作区或暂存区被改动（git diff HEAD 非空）"
fi

# 2. JS 语法检查
if command -v node >/dev/null 2>&1; then
  if node -c reader-video-companion/content.js >/dev/null 2>&1; then
    pass "node -c content.js"
  else
    fail "node -c content.js 语法错误"
  fi
else
  fail "node 未安装，无法做 JS 语法检查"
fi

# 3. bash 语法检查
for sh in start.sh stream-server/start.sh packaging/make-distro.sh stream-server/packaging/build.sh; do
  if [ -f "$sh" ]; then
    if bash -n "$sh" 2>/dev/null; then pass "bash -n $sh"; else fail "bash -n $sh 语法错误"; fi
  fi
done

# 4. Python 语法检查（py_compile 产物在 __pycache__/，已被 .gitignore 忽略）
if run_py -m py_compile stream-server/server.py >/dev/null 2>&1; then
  pass "py_compile server.py"
else
  fail "py_compile server.py 语法错误"
fi
rm -rf stream-server/__pycache__/server.*.pyc 2>/dev/null

# 5. emoji 检查（CLAUDE.md 硬约束：server.py/start.sh 不许含 emoji）
EMOJI_OUT="$(run_py - <<'PYEOF'
import pathlib, re
EMOJI_RE = re.compile(
    '[\U0001F000-\U0001FAFF\u2190-\u21FF\u2300-\u23FF\u25A0-\u25FF'
    '\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u20E3]')
bad = []
for f in ['stream-server/server.py', 'stream-server/start.sh']:
    hits = EMOJI_RE.findall(pathlib.Path(f).read_text(encoding='utf-8'))
    if hits:
        bad.append('%s: %d 个 %s' % (f, len(hits), hits[:8]))
print('|'.join(bad))
PYEOF
)"
if [ -z "$EMOJI_OUT" ]; then
  pass "emoji 检查 server.py/start.sh"
else
  fail "emoji 残留 $EMOJI_OUT"
fi

# 6. 版本号一致性（ADR-001：manifest.json 为唯一源，构建脚本/文档不许硬编码不同版本）
SRC_VER="$(run_py -c "import json;print(json.load(open('reader-video-companion/manifest.json'))['version'])" 2>/dev/null)"
if [ -n "$SRC_VER" ]; then
  pass "版本源 manifest.json = $SRC_VER"
  # 检查 Info.plist heredoc 是否已改为 $VER 注入（不再硬编码版本号）
  if grep -q 'CFBundleShortVersionString.*[0-9]\+\.[0-9]\+\.[0-9]\+' stream-server/packaging/build.sh 2>/dev/null; then
    fail "build.sh Info.plist 仍硬编码版本号（应使用 \$VER 注入，ADR-001）"
  else
    pass "build.sh Info.plist 版本号已走 \$VER 注入"
  fi
  # 检查 make-distro.sh 安装说明是否已改为 v$VER（不再硬编码）
  if grep -q '版本 v[0-9]\+\.[0-9]\+\.[0-9]\+' packaging/make-distro.sh 2>/dev/null; then
    fail "make-distro.sh 安装说明仍硬编码版本号（应使用 v\$VER，ADR-001）"
  else
    pass "make-distro.sh 安装说明版本号已走 v\$VER 注入"
  fi
else
  fail "无法从 manifest.json 读取版本号"
fi

if [ "$FAIL" -ne 0 ]; then
  echo ""
  echo "[ABORT] 静态检查未通过，修复后重跑 scripts/check.sh --static"
  echo "[HINT]  紧急绕过（不推荐）：git commit --no-verify"
  exit 1
fi

if [ "$STATIC_ONLY" = 1 ]; then
  echo ""
  echo "[OK] 静态检查全部通过（check.sh --static）"
  exit 0
fi

echo ""
echo "===== RVC 检查：验收（tests/acceptance.py）====="

# 6. 清验收 profile（B1 残留污染：rvc-frameless=true 致 C 步超时）
rm -rf /tmp/rvc-pw-profile-accept

# 7. 确保 8765 可用：up 则复用；down 则自动拉起（验后若为本次拉起则清理）
STARTED_BY_CHECK=0
ensure_server() {
  if curl -s --max-time 2 "http://127.0.0.1:8765/api/files?dir=~" >/dev/null 2>&1; then
    return 0
  fi
  if [ "$STARTED_BY_CHECK" = 0 ]; then
    echo "[INFO] 8765 未运行，自动启动 stream-server/start.sh（日志 /tmp/rvc-check-server.log）"
    nohup bash stream-server/start.sh > /tmp/rvc-check-server.log 2>&1 &
    STARTED_BY_CHECK=1
  fi
  for _ in $(seq 1 30); do
    if curl -s --max-time 2 "http://127.0.0.1:8765/api/files?dir=~" >/dev/null 2>&1; then
      echo "[INFO] 8765 就绪"
      return 0
    fi
    sleep 0.5
  done
  echo "[ABORT] 8765 启动失败，日志见 /tmp/rvc-check-server.log；或手动 bash stream-server/start.sh 查看错误"
  return 1
}
ensure_server || exit 1

run_acceptance() {
  run_py tests/acceptance.py
}

# 8. 验收（B9 已知 F 步 flaky 约 1/3，失败自动重试一次，仍失败才拦截）
#    重试前再次 ensure_server：环境若拉起了不稳定的 8765 实例，验收中途可能死掉，需换回自管实例
acceptance_run() {
  local rc=0
  run_acceptance
  rc=$?
  if [ "$rc" -ne 0 ] && [ "$ALLOW_RETRY" = 1 ]; then
    echo ""
    echo "[INFO] 验收未过（已知 B9 F 步 flaky 约 1/3，重跑大概率过），自动重试一次..."
    ensure_server || return 1
    rm -rf /tmp/rvc-pw-profile-accept
    run_acceptance
    rc=$?
  fi
  return "$rc"
}
acceptance_run
rc=$?

if [ "$STARTED_BY_CHECK" = 1 ]; then
  echo ""
  echo "[INFO] 清理本次自动拉起的 8765 服务器（含热键子进程）"
  lsof -ti:8765 2>/dev/null | xargs kill 2>/dev/null
  sleep 1
  # 主进程被杀后热键子进程可能残留（父进程死亡后未自行退出），一并清理
  pkill -f 'stream-server/server.py --hotkey-child' 2>/dev/null
fi

if [ "$rc" -eq 0 ]; then
  echo ""
  echo "[OK] 验收通过（check.sh 全量完成），可以推送"
  exit 0
else
  echo ""
  echo "[ABORT] 验收未通过，禁止推送。重跑 scripts/check.sh 复查"
  echo "[HINT]  紧急绕过（不推荐，绕过即失去唯一通路）：git push --no-verify，事后必须补跑检查"
  exit 1
fi
