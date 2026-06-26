#!/usr/bin/env bash
# CONTROLLED SUPERVISED LIVE AUTO test on the TradingView feed — operator runs this and STAYS PRESENT.
# It arms real MFFU-50K-1 orders (A4/B2, -$700 daily stop, D1c active). The runner's preflight
# still enforces every safety gate and REFUSES if anything is not green. Ctrl-C stops it.
set -uo pipefail
cd ~/trading-team/bot/nq-liq-bot

echo "================  CONTROLLED SUPERVISED LIVE AUTO TEST  ================"
echo "Account: MFFU-50K-1 · A4/B2 (4 MNQ eval, gate-safe) · -\$700 daily stop · D1c active · TradingView feed (supervised)"
echo "Guard: ABORTS if D1c can't arm ACTIVE (stale feed) — won't trade the un-filtered model."
echo "Eval @ 4 MNQ: worst day \$1,921 < \$2,000 buffer (one bad day can't bust); 95% pass / ~18d median."
echo "This places REAL orders automatically on Profile A signals. You supervise; stay present."
echo
printf "Type exactly  GO LIVE  to arm (anything else aborts): "
read CONFIRM
[ "$CONFIRM" = "GO LIVE" ] || { echo "aborted — not armed."; exit 1; }

printf "Paste your TradersPost LIVE webhook URL (hidden), then Enter: "
read -s TRADERSPOST_LIVE_URL; echo
[ -n "${TRADERSPOST_LIVE_URL:-}" ] || { echo "no URL — abort."; exit 1; }
export TRADERSPOST_LIVE_URL
export TV_REALTIME_CONFIRMED=1

touch evidence/approvals/controlled-tv-full-live-test-approved.flag
pkill -f auto_live.py 2>/dev/null || true; sleep 2

echo "launching CONTROLLED LIVE TEST — watch the output + dashboard. Ctrl-C to stop."
# --require-d1c-active: if the preflight resolves D1c to SHADOW (feed not real-time 1m), ABORT rather than
# silently trade the UN-filtered model. The D1c filter is part of the validated model.
python3 auto_live.py --account MFFU-50K-1 --tier 50K-balanced \
  --feed tradingview-1m --d1c-mode active-eval-filter --execution traderspost \
  --controlled-tv-full-live-test --live --confirm --require-d1c-active \
  --profile-momentum
# --profile-momentum: Momentum runs in SHADOW during this live session (models P&L + Telegram, NO live
# orders) until evidence/approvals/momentum-approved.flag is created. Observe it live this week; one flag
# flips it live next week. A+B trade live, completely unchanged.
