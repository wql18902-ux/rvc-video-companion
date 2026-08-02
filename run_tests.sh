#!/bin/bash
# RVC 分层测试统一入口 —— 验证与改动面一一对应
#
# 哈希冻结范围（已收窄到判卷基准三文件，防漂移手段保留）：
#   tests/acceptance.py / test.html / tests/fixtures/sample.mp4
#   sha256 前 8 位：c1965638 / 4b79893e / 9b4a8281（与 CLAUDE.md/PROGRESS.md 存档一致）
#   content.js / player.css / server.py 等实现文件不再受哈希冻结约束，
#   由 L1/L2/L3 行为验证覆盖（冻结只锁判卷基准，不锁实现）。
#
# 分层（从快到慢，从隔离到真实）：
#   L0 静态 + 哈希核对：scripts/check.sh --static（冻结校验 + 语法 + emoji）
#   L1 单测/集成：tests/test_server_api.py（随机端口 + fake ffmpeg，29 用例）
#   L2 真实进程 E2E：tests/e2e_extra.py（真实 server.py + 真实 ffmpeg，8 用例；
#      8765 被占用时自动改独立测试端口，绝不打断用户播放）
#   L3 验收（--full 才跑）：scripts/check.sh 全量（acceptance.py 冻结基准，分钟级）
#
# 变更 -> 受影响路由 -> 验证层 映射表（改哪类代码就认哪层的结论）：
#   鉴权/CORS（ALLOWED_ORIGINS/HOSTS/check_origin/_cors_header）
#       -> 全部 /api/*                          -> L1 鉴权组 + L3
#   路径校验（safe_join/扩展名白名单）
#       -> /api/file /api/stream /api/duration  -> L1 路径组
#   目录列表/树/时长
#       -> /api/files /api/tree /api/duration   -> L1 列表组
#   热键链路（control-key 广播）
#       -> POST /api/control-key /api/control   -> L1 control-key 组 + L2 interrupt_sse
#   转码（ffmpeg 命令/错误落盘/结构化错误码）
#       -> /api/stream /api/stream-error /api/stop -> L1 fake ffmpeg + L2 真实 ffmpeg
#   播放中断（流式转发/SSE 清理）
#       -> /api/stream /api/control             -> L1 SSE 上限/清理 + L2 interrupt_*
#   端口/启动（is_port_in_use/幂等启动）
#       -> 服务器启动路径                        -> L1 is_port_in_use + L2 port_in_use
#   前端（content.js/player.css/manifest）
#       -> 浏览器行为（非 HTTP 路由）            -> L3 acceptance（冻结基准）
#
# 用法：
#   bash run_tests.sh         # L0+L1+L2（秒级~分钟级，改动常规验证）
#   bash run_tests.sh --full  # L0+L1+L2+L3（含验收，进主干前必跑）
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT" || exit 1

FULL=0
for arg in "$@"; do
  case "$arg" in
    --full) FULL=1 ;;
    *) echo "[WARN] 未知参数: $arg（仅支持 --full）" ;;
  esac
done

# TRAE 注入 PYTHONHOME/PYTHONPATH 会让 python 报 "No module named 'encodings'"，一律清掉
if [ -x /opt/homebrew/bin/python3 ]; then
  PY_BIN=/opt/homebrew/bin/python3
else
  PY_BIN=python3
fi
run_py() { env -u PYTHONHOME -u PYTHONPATH "$PY_BIN" "$@"; }

PASS=0
FAIL=0
note() { echo ""; echo "===== $* ====="; }
ok()   { echo "[PASS] $*"; PASS=$((PASS + 1)); }
bad()  { echo "[FAIL] $*"; FAIL=$((FAIL + 1)); }

# ---------- L0 静态 + 哈希核对（冻结基准防漂移） ----------
note "L0 静态 + 哈希核对（scripts/check.sh --static）"
if bash scripts/check.sh --static; then
  ok "L0 静态检查（含基准三文件 sha256 冻结）"
else
  bad "L0 静态检查（判卷基准被改或语法/emoji 违规，禁止继续）"
fi

# ---------- L1 单测/集成（fake ffmpeg，随机端口） ----------
note "L1 单测/集成（tests/test_server_api.py）"
if run_py tests/test_server_api.py >/tmp/rvc-l1.log 2>&1; then
  ok "L1：$(grep -c '^test_' /tmp/rvc-l1.log 2>/dev/null || echo 29) 用例全绿"
else
  bad "L1 未通过（详见 /tmp/rvc-l1.log）"
  tail -30 /tmp/rvc-l1.log
fi

# ---------- L2 真实进程 E2E（真实 ffmpeg） ----------
note "L2 真实进程 E2E（tests/e2e_extra.py）"
if run_py tests/e2e_extra.py >/tmp/rvc-l2.log 2>&1; then
  ok "L2：$(grep -c '^test_' /tmp/rvc-l2.log 2>/dev/null || echo 8) 用例全绿（转码失败/端口占用/播放中断/正向对照/音频分流）"
else
  bad "L2 未通过（详见 /tmp/rvc-l2.log）"
  tail -30 /tmp/rvc-l2.log
fi

# ---------- L3 验收（--full 才跑，冻结基准 acceptance.py） ----------
if [ "$FULL" = 1 ]; then
  note "L3 验收（scripts/check.sh 全量，acceptance.py 冻结基准）"
  if bash scripts/check.sh; then
    ok "L3 验收通过"
  else
    bad "L3 验收未通过"
  fi
fi

# ---------- 汇总 + 受影响路由映射声明 ----------
echo ""
echo "======================================================"
echo " 分层测试汇总：PASS=${PASS} FAIL=${FAIL}（L0+L1+L2 默认，L3 --full）"
echo "======================================================"
echo ""
echo "变更 -> 受影响路由 -> 验证层（改哪类代码认哪层结论）："
echo "  鉴权/CORS      -> 全部 /api/*                     -> L1 鉴权组 + L3"
echo "  路径校验        -> /api/file /api/stream /api/duration -> L1 路径组"
echo "  目录/树/时长    -> /api/files /api/tree /api/duration  -> L1 列表组"
echo "  热键链路        -> /api/control-key /api/control       -> L1 control-key + L2 interrupt_sse"
echo "  转码/错误码     -> /api/stream /api/stream-error /api/stop -> L1 fake + L2 真实 ffmpeg"
echo "  播放中断        -> /api/stream /api/control            -> L1 SSE 清理 + L2 interrupt_*"
echo "  端口/启动       -> 服务器启动路径                      -> L1 is_port_in_use + L2 port_in_use"
echo "  前端           -> 浏览器行为（非 HTTP 路由）           -> L3 acceptance（冻结基准）"
echo ""
echo "基准哈希（只锁判卷三文件）："
echo "  acceptance.py=c1965638… test.html=4b79893e… sample.mp4=9b4a8281…"
echo ""

if [ "$FAIL" -ne 0 ]; then
  echo "[ABORT] 有分层未通过。修复后重跑：bash run_tests.sh（进主干前加 --full）"
  exit 1
fi
echo "[OK] 全部通过"
exit 0
