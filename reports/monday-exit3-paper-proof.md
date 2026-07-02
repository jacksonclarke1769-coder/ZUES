> ⛔ **OBSOLETE (pre-2026-07-02 machine).** This document describes a configuration/certification
> that was INVALIDATED by the 2026-07-02 audit (5m fill-bar look-ahead) and superseded by
> **ZEUS Production Machine v2026.07.02** — see `AGENTS.md` §"THE SELECTED MACHINE" and
> `reports/apex_validation.json`. Kept for historical reference only.

# MONDAY EXIT3 PAPER PROOF — STAGED (session not yet run)
_prepared 2026-06-21 (Sunday 02:35 ET) · paper only · live BLOCKED_

## STATUS: SESSION PENDING — MARKET CLOSED
The live-feed NY-AM paper session **could not run**: it is **Sunday, the NQ cash session is closed,
and the TradingView CDP feed (:9222) is down**. There is no live data to run the engine on. The next
valid window is **Monday 2026-06-22, 09:30–11:30 ET**. Everything below is staged and verified ready;
items 1–22 are filled by the auditor *after* the Monday session.

## Pre-checks (done now — all ✓)
| Check | Result |
|---|---|
| `exit-model-approved.flag` | **ABSENT** ✓ (live blocked) |
| `full-auto-approved.flag` | **ABSENT** ✓ |
| `EXIT_MODEL` | `EXIT3_FIXED_PARTIAL` ✓ |
| ARGUS logger + auditor | present ✓ |
| EXITFORGE / EXITLOCK / ARGUS tests | 45 passed ✓ |
| CDP :9222 feed | DOWN (expected — market closed) |
| Tools built this pass | `tools/launch-tv-chrome.sh`, `tools/probe_tradingview_bars.py` (were missing) |

## Monday runbook (exact, in order)
```bash
cd ~/trading-team/bot/nq-liq-bot

# 0. ~09:00 ET — stop stragglers, keep Mac awake
pkill -f auto_live.py || true
caffeinate -dimsu > out/caffeinate.log 2>&1 & echo $! > out/caffeinate.pid

# 1. launch dedicated TradingView Chrome (CDP + anti-throttle)
bash tools/launch-tv-chrome.sh
#    then in Chrome: load CME_MINI:NQ1! (or MNQ1!) @ 1m, confirm candles moving, no 'delayed' marker

# 2. probe the feed BEFORE the session — must say PROBE PASS
python3 tools/probe_tradingview_bars.py --duration 180

# 3. ~09:25 ET — start PAPER session (NO --live, NO URL, NO flag)
export TV_REALTIME_CONFIRMED=1
python3 auto_live.py --account MFFU-50K-1 --tier 50K-conservative \
  --feed tradingview-1m --d1c-mode active-eval-filter

# 4. monitor (second terminal) — dashboard is :8777 (NOT :3000)
#    watch out/heimdall/heartbeat.json + logs/live_engine_decisions/$(TZ=America/New_York date +%F).jsonl

# 5. ~11:30–14:30 ET — stop after the window
pkill -f auto_live.py || true

# 6. AUDIT
python3 tools/audit_live_engine_session.py --date today --session ny-am
python3 tools/check_exit3_parity.py
```

## Acceptance criteria
- **No trade:** auditor returns `SESSION CLEAN — NO SETUP` (ARGUS no_signal rows cover the window).
- **Trade:** auditor returns `SESSION CLEAN — TRADE TAKEN`; the decision row shows
  `exit_model=EXIT3_FIXED_PARTIAL`, `tp1_qty=1`, `tp2_qty=2`, shared stop; the calendar books two-leg
  P&L (~$1,167-scale win), realised — **no synthetic full-qty +2R, no hypothetical-as-realised**.
- **Bad:** `INCONCLUSIVE — LOGGING GAP` / `FAIL — POSSIBLE MISSED TRADE` / `BLOCKED BY DATA` → live stays blocked, investigate.

## Results (to be completed after Monday session)
1. session date — _pending_ · 2. start/end — _pending_ · 3. feed source — tradingview-1m ·
4. feed health — _pending_ · 5. DATA_READY timeline — _pending_ · 6. D1c — ACTIVE_EVAL_FILTER (expected) ·
7. ARES — armed (expected) · 8. exit model — EXIT3_FIXED_PARTIAL · 9–14 ARGUS counts — _pending_ ·
15. trade? — _pending_ · 16. TP1/TP2 P&L — _pending_ · 17. no-setup proof — _pending_ ·
18. RED/YELLOW — _pending_ · 19. missed-trade verdict — _pending_ · 20. parity — _pending_ ·
21. final verdict — _pending_ · 22. flag — **remains ABSENT (operator-only).**

## Honest gap
`tools/launch-tv-chrome.sh` and `tools/probe_tradingview_bars.py` were **missing** and are now built,
but **could not be exercised against a live feed** (market closed) — only graceful-failure verified.
Their first real run is Monday's step 1–2.
