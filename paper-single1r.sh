#!/usr/bin/env bash
# PAPER-TEST single@1R — live data, REAL signals, DRY-RUN webhooks (NO orders). No flag needed.
# This is the recommended first step: run single@1R in paper alongside the validated model, collect
# real side-by-side fills, THEN go live (./go-live-single1r.sh) only if it holds up. Ctrl-C to stop.
set -uo pipefail
cd ~/trading-team/bot/nq-liq-bot
ACCT="APEX-50K-EVAL-1"; TIER="Apex-50K-eval"
echo "PAPER · SINGLE_1R · ${ACCT} — live data, dry-run webhooks, NO orders. Supervise + compare to EXIT3."
nohup python3 auto_live.py --account "$ACCT" --tier "$TIER" --feed tradingview-1m \
  --d1c-mode active-eval-filter --execution traderspost --controlled-tv-full-live-test \
  --confirm --require-d1c-active --profile-momentum --momentum-qty 6 \
  --exit-model SINGLE_1R > logs/paper-single1r.log 2>&1 &
echo "  launched PID $! -> logs/paper-single1r.log  (paper: --live omitted -> dry-run, no real orders)"
sleep 16
grep -iE "PAPER|SINGLE_1R|exit model|ARMED|FAIL CLOSED" logs/paper-single1r.log | tail -6
