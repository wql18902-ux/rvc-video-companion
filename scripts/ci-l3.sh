#!/bin/bash
# CI L3 前端行为验收执行器 —— headless Playwright 全量验收，回退闸门的执行端
#
# 职责：在 CI（无显示器）上执行 L3 验收并留下可审计证据。判卷基准
#       （acceptance.py/test.html/sample.mp4）与 scripts/check.sh 行为均不触碰，
#       只负责「以正确环境调用 + 证据收集 + 失败即非零退出」。
#
# 环境坑（CLAUDE.md 2026-08-02 实测）：
#   HTTP_PROXY 注入会让 acceptance.py 里对 127.0.0.1 的探活/请求误走代理
#   → 误判 server 未运行 → 验收假失败。CI 一律清空代理 env 再跑。
#
# 证据（由 CI 上传为 artifact，仓库外可审计）：
#   /tmp/rvc-l3.log            check.sh 全量完整日志（静态 + 8765 拉起 + acceptance 每步 PASS/FAIL）
#   /tmp/rvc-l3.summary        L3 汇总：日期 / commit / 通过数 / exit code
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

echo "===== CI L3 前端行为验收（headless）开始 $(date '+%F %T') ====="
echo "commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

# 清代理 + 清 PYTHONHOME/PYTHONPATH（check.sh 内部已清后者，这里双保险）
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy \
  bash scripts/check.sh > /tmp/rvc-l3.log 2>&1
rc=$?

# 汇总证据：通过/失败步数从 acceptance 输出统计
echo ""
echo "===== L3 验收汇总 ====="
grep -E '^\[(PASS|FAIL|OK|ABORT|INFO)\]|^===== ' /tmp/rvc-l3.log | tail -50 || true
echo ""
PASS_N="$(grep -c '^PASS ' /tmp/rvc-l3.log 2>/dev/null || true)"
FAIL_N="$(grep -c '^FAIL ' /tmp/rvc-l3.log 2>/dev/null || true)"
printf 'date=%s\ncommit=%s\nacceptance_pass=%s\nacceptance_fail=%s\nexit=%s\n' \
  "$(date '+%F %T')" "$(git rev-parse --short HEAD 2>/dev/null || echo unknown)" \
  "$PASS_N" "$FAIL_N" "$rc" > /tmp/rvc-l3.summary

if [ "$rc" -ne 0 ]; then
  echo "exit=$rc（完整日志：/tmp/rvc-l3.log）"
  echo ""
  echo "----- L3 失败日志尾部（完整证据见 artifact rvc-ci-evidence/rvc-l3.log）-----"
  tail -60 /tmp/rvc-l3.log
fi
exit "$rc"
