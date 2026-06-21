#!/usr/bin/env bash
# MONDAY PROOF — launch a dedicated TradingView Chrome with CDP on :9222 and anti-throttle
# flags (so a backgrounded tab never freezes the feed — the 2026-06-15 root cause). Operator
# then loads CME_MINI:NQ1! (or MNQ1!) at 1m. No trading happens here — this only opens Chrome.
set -uo pipefail

PORT="${CDP_PORT:-9222}"
if curl -s -o /dev/null "http://127.0.0.1:${PORT}/json/version" 2>/dev/null; then
  echo "CDP already live on :${PORT} — reusing existing Chrome."
  exit 0
fi

echo "launching TradingView Chrome (CDP :${PORT}, anti-throttle)…"
open -na "Google Chrome" --args \
  --remote-debugging-port="${PORT}" \
  --disable-background-timer-throttling \
  --disable-backgrounding-occluded-windows \
  --disable-renderer-backgrounding \
  --disable-features=CalculateNativeWinOcclusion

echo "Now, in the Chrome window that opened:"
echo "  1. open tradingview.com chart"
echo "  2. symbol CME_MINI:NQ1!  (or MNQ1!)"
echo "  3. timeframe 1m"
echo "  4. confirm: candles moving, NO 'delayed data' marker"
echo
echo "verify CDP: curl -s http://127.0.0.1:${PORT}/json/version"
