#!/usr/bin/env bash
# ┌──────────────────────────────────────────────────────────────────────────────────────────┐
# │  GO LIVE — Phase-3 RECERTIFIED machine (2026-07-02) on the Apex 50K eval.                 │
# │                                                                                            │
# │  Machine: Profile A ONLY · Exit#3 (0.5@+1R / 0.5@+2R) · D1c ACTIVE_EVAL_FILTER ·          │
# │           size-to-risk $1,600/trade (max A10) · B OFF · momentum OFF · $550 daily stop.    │
# │  Certified on 1m-TRUTH fills: pass 57.7% / bust 17.7% / expire 25% / median 14d            │
# │  (tools_phase3_config_sweep.py; provenance reports/apex_validation.json).                  │
# │                                                                                            │
# │  Requires the Tradovate broker panel OPEN in the :9222 TradingView (read-back).            │
# └──────────────────────────────────────────────────────────────────────────────────────────┘
set -uo pipefail
cd ~/trading-team/bot/nq-liq-bot

ACCT="APEX-50K-EVAL-1"; TIER="Apex-50K-eval"
echo "================  GO LIVE · RECERT (A-only Exit#3 + D1c)  ·  ${ACCT}  ================"
echo "  pass 57.7% / bust 17.7% on 1m-truth · size-to-risk \$1,600 · B OFF · momentum OFF"
echo "  REAL orders. Read-back REQUIRED (panel open in the :9222 Chrome). Supervise."
echo
printf 'Type exactly  GO LIVE RECERT  to arm (anything else aborts): '
read -r CONFIRM
[ "$CONFIRM" = "GO LIVE RECERT" ] || { echo "aborted — not armed."; exit 1; }
# Re-authorize the controlled-test flag for THIS session (conscious operator act — satisfies 24h TTL).
touch evidence/approvals/controlled-tv-full-live-test-approved.flag

export TRADERSPOST_LIVE_URL="$(python3 -c 'import env_loader,os;print(os.environ.get("TRADERSPOST_LIVE_URL",""))')"
export TV_REALTIME_CONFIRMED=1
export READBACK_SOURCE=tradingview
[ -n "${TRADERSPOST_LIVE_URL:-}" ] || { echo "no TRADERSPOST_LIVE_URL in .env — abort."; exit 1; }

echo "--- preflight ---"
if ! python3 full_auto_preflight.py --account "$ACCT" --feed tradingview-1m --tier "$TIER" \
        --controlled-tv-full-live-test; then
    echo "PREFLIGHT BLOCKED — not arming. (feed RED? dead-man? broker panel? fix and re-run.)"
    exit 1
fi

echo "--- arming RECERT live (Exit#3 default, no B, no momentum) ---"
pkill -f "auto_live.py" 2>/dev/null && sleep 3 || true
nohup python3 auto_live.py --account "$ACCT" --tier "$TIER" --feed tradingview-1m \
  --d1c-mode active-eval-filter --execution traderspost --controlled-tv-full-live-test \
  --live --confirm --require-d1c-active --no-profile-b \
  > logs/live-recert.log 2>&1 &
echo "  launched PID $! -> logs/live-recert.log"
sleep 18
grep -iE "ARMED, live webhooks active|exit model|EXIT3|read-back|SEEDED|FAIL CLOSED" logs/live-recert.log | tail -8
echo
echo "LIVE on the recertified machine. Watch logs/live-recert.log + the dashboard."
echo "Keep feed_watch running:  pgrep -fl feed_watch || nohup python3 feed_watch.py --heal > logs/feed-watch.log 2>&1 &"
