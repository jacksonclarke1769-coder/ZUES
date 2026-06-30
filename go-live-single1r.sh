#!/usr/bin/env bash
# ┌──────────────────────────────────────────────────────────────────────────────────────────┐
# │  GO LIVE — SINGLE_1R exit model on the Apex 50K eval.  ONE COMMAND, fully gated.           │
# │  This places REAL orders with single@1R (full qty -> +1R target, shared -1R stop) on       │
# │  Profile A AND B. It REPLACES the currently-armed EXIT3 live session.                      │
# │                                                                                            │
# │  ⚠ single@1R has NEVER traded live or paper. It is certified causally-clean + backtest-    │
# │    robust, but this skips the paper-test that EXITLOCK was designed to require. Supervise.  │
# │                                                                                            │
# │  Safer first step:  ./paper-single1r.sh   (dry-run, no real orders, no flag needed)        │
# └──────────────────────────────────────────────────────────────────────────────────────────┘
set -uo pipefail
cd ~/trading-team/bot/nq-liq-bot

ACCT="APEX-50K-EVAL-1"; TIER="Apex-50K-eval"
echo "================  GO LIVE · SINGLE_1R · ${ACCT} (${TIER})  ================"
echo "  Exit: single@1R (A full-qty +1R, B full-qty +1R, shared -1R stop) · A10/B5/mm6 · \$550 daily stop"
echo "  Replaces the live EXIT3 session. REAL orders. You supervise (no broker read-back — confirm fills by eye)."
echo
printf 'Type exactly  GO LIVE SINGLE1R  to arm (anything else aborts): '
read -r CONFIRM
[ "$CONFIRM" = "GO LIVE SINGLE1R" ] || { echo "aborted — not armed."; exit 1; }

# 1) approval flag (the live gate for SINGLE_1R) + env
mkdir -p evidence/approvals
touch evidence/approvals/single-1r-approved.flag
export TRADERSPOST_LIVE_URL="$(python3 -c 'import env_loader,os;print(os.environ.get("TRADERSPOST_LIVE_URL",""))')"
export TV_REALTIME_CONFIRMED=1
[ -n "${TRADERSPOST_LIVE_URL:-}" ] || { echo "no TRADERSPOST_LIVE_URL in .env — abort."; exit 1; }

# 2) preflight MUST pass (data GREEN + dead-man alive + trading day + all gates) — abort if not
echo "--- preflight ---"
if ! python3 full_auto_preflight.py --account "$ACCT" --feed tradingview-1m --tier "$TIER" \
        --controlled-tv-full-live-test; then
    echo "PREFLIGHT BLOCKED — not arming. (feed RED? dead-man? fix and re-run.)"
    exit 1
fi

# 3) swap the live session to SINGLE_1R
echo "--- arming SINGLE_1R live ---"
pkill -f "auto_live.py" 2>/dev/null && sleep 3 || true
nohup python3 auto_live.py --account "$ACCT" --tier "$TIER" --feed tradingview-1m \
  --d1c-mode active-eval-filter --execution traderspost --controlled-tv-full-live-test \
  --live --confirm --require-d1c-active --profile-momentum --momentum-qty 6 \
  --exit-model SINGLE_1R > logs/live-single1r.log 2>&1 &
echo "  launched PID $! -> logs/live-single1r.log"
sleep 18
grep -iE "ARMED, live webhooks active|exit model|SINGLE_1R|FAIL CLOSED" logs/live-single1r.log | tail -6
echo
echo "LIVE on SINGLE_1R. Watch logs/live-single1r.log + the dashboard. Supervise."
echo "REVERT to EXIT3:  pkill -f auto_live.py  then re-run your normal live launch (no --exit-model)."
