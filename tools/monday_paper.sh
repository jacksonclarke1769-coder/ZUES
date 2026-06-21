#!/usr/bin/env bash
# MONDAY PAPER SESSION — A + B + P3 + ARGUS, on the live TradingView feed. PAPER ONLY:
# no --live, no TRADERSPOST_LIVE_URL, no flag. Brings up the feed, probes it, runs the
# session (Ctrl-C to stop), then tells you to audit. The runner's own gates still refuse
# to fire on a holiday / RED feed / dead-man.
set -uo pipefail
cd ~/trading-team/bot/nq-liq-bot

echo "================  MONDAY PAPER SESSION  (A + B + P3 + ARGUS)  ================"

# ---- preflight: must be paper-only ----
if [ -f evidence/approvals/exit-model-approved.flag ]; then
  echo "ABORT: exit-model-approved.flag is PRESENT — this launcher is PAPER-ONLY. Remove it or use the live runbook."
  exit 1
fi
if [ -n "${TRADERSPOST_LIVE_URL:-}" ]; then
  echo "ABORT: TRADERSPOST_LIVE_URL is set in this shell — unset it for a paper session."
  exit 1
fi
echo "preflight: exit-model flag ABSENT ✓  ·  no live URL ✓"
python3 monday_preflight.py --account MFFU-50K-1 --tier 50K-conservative 2>&1 | tail -22 || true

# ---- feed ----
echo
echo "--- bringing up TradingView Chrome (CDP) ---"
bash tools/launch-tv-chrome.sh
echo
read -r -p "In Chrome: load CME_MINI:NQ1! @ 1m, confirm candles moving + no 'delayed' marker, then press Enter… " _

# ---- probe ----
echo "--- probing the feed (must say PROBE PASS) ---"
if ! python3 tools/probe_tradingview_bars.py --duration 120; then
  echo "ABORT: probe failed — do NOT run the session until the feed is GREEN/advancing."
  exit 1
fi

# ---- run PAPER (A + B + P3 all on by default) ----
echo
echo "--- launching PAPER session — Ctrl-C to stop. Watch the dashboard (:8777). ---"
export TV_REALTIME_CONFIRMED=1
pkill -f auto_live.py 2>/dev/null || true; sleep 1
python3 auto_live.py --account MFFU-50K-1 --tier 50K-conservative \
  --feed tradingview-1m --d1c-mode active-eval-filter

echo
echo "session ended. AUDIT it now:"
echo "  python3 tools/monday_audit.py --date today --parity"
