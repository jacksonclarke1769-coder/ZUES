#!/usr/bin/env bash
# CONTROLLED SUPERVISED LIVE AUTO test on the TradingView feed — operator runs this and STAYS PRESENT.
# It arms real MFFU-50K-1 orders (A3/B2, -$700 daily stop, D1c active). The runner's preflight
# still enforces every safety gate and REFUSES if anything is not green. Ctrl-C stops it.
set -uo pipefail
cd ~/trading-team/bot/nq-liq-bot

echo "================  CONTROLLED SUPERVISED LIVE AUTO TEST  ================"
echo "Account: MFFU-50K-1 · A3/B2 · -\$700 daily stop · D1c active · TradingView feed (supervised)"
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
python3 auto_live.py --account MFFU-50K-1 --tier 50K-conservative \
  --feed tradingview-1m --d1c-mode active-eval-filter --execution traderspost \
  --controlled-tv-full-live-test --live --confirm
