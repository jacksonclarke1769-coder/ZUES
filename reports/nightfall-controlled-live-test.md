# NIGHTFALL-LIVE — Controlled Full-Live Test on TradingView Feed
_2026-06-16 · CONTROLLED_FULL_LIVE_TEST (NOT production full auto) · A/B/D1c/sizing untouched_

## Status: **ARMED & READY — awaiting operator launch**
The harness is built, gated, and verified. The live run is the **operator's supervised action**
(needs the local TradersPost URL + the test flag + your presence). I did not send orders or create
the live-arming flag.

## What's built this session
- **Controlled test mode** (`auto_live --controlled-tv-live-test`): a supervised, single-session live
  path on the TradingView browser feed. It swaps `full-auto-approved.flag` → one-time
  `controlled-tv-live-test-approved.flag` and permits the browser feed, but keeps **every** other
  gate. Verified the flag does **not** open production (browser still hard-blocked there).
- **TradingView throttle fix** (`tools/launch-tv-chrome.sh`, local): added `IntensiveWakeUpThrottling`
  + Memory-Saver disables — the 5-min background throttle that caused the prior freeze. Feed held
  GREEN this session after the fix.
- 289 tests pass (+3 controlled-test gating); 1 pre-existing vulcan red.

## Pre-launch state (verified live)
data_state **GREEN** · DATA_READY **True** · dashboard **green** · dead-man **OK** · guardian **armed**
· D1c **ACTIVE_EVAL_FILTER** (1m + real-time, legal) · ARES **armed** (MFFU-50K-1, A3/B2, −$700) ·
TradersPost **proven** (PROVEN + bracket-verified + traderspost-approved flags).

**Controlled-test preflight currently BLOCKED on exactly 2 operator actions:**
1. `controlled-tv-live-test-approved.flag` missing (your approval)
2. `TRADERSPOST_LIVE_URL` not set (you set it in your terminal)

## ⚠️ Honest scope limits
- **Profile A only.** Profile B is NOT in the live engine (FENRIR B2) — B cannot fire live tonight.
  The missed-trade audit must treat this as A-only.
- **Browser feed is SEMI_AUTO_ONLY for production.** Tonight is a *supervised test*, not approval.
  Production full auto stays blocked until a proper feed (Tradovate-md/Databento) is soak-passed.
- It can still freeze; if it does → data RED → entries blocked + self-healer recovers. Fails safe.

## Operator procedure (you run these — stay present the whole session)
```bash
cd ~/trading-team/bot/nq-liq-bot
# 1. approve tonight's controlled test (your decision):
touch evidence/approvals/controlled-tv-live-test-approved.flag
# 2. set env in THIS terminal (URL stays local; do not echo it):
export TV_REALTIME_CONFIRMED=1
read -s TRADERSPOST_LIVE_URL; export TRADERSPOST_LIVE_URL
# 3. launch the controlled live test (A3/B2, D1c active, −$700 daily stop):
python3 auto_live.py --account MFFU-50K-1 --tier 50K-conservative \
  --feed tradingview-1m --d1c-mode active-eval-filter --execution traderspost \
  --controlled-tv-live-test --live --confirm
```
If any gate is not satisfied it **refuses** (fail-closed). It will print a SUPERVISED-TEST banner.

## Watch (a freeze/RED must block entries)
`tail -f logs/feed-watch.log` and the dashboard. Any RED → entries auto-block; if a position is open,
the kill/EOD guardian + manual flatten apply.

## End of session
```bash
TRADERSPOST_LIVE_URL=<set> python3 bridge_test.py --account MFFU-50K-1 --flatten   # confirm flat + no orphans
# stop the runner; then re-lock:
rm -f evidence/approvals/controlled-tv-live-test-approved.flag
```

## Post-session audit (fill after the run) — `reports/nightfall-live-missed-trade-audit.md`
1. Live data covered every 1m bar? 2. 5m aggregation built every engine bar? 3. Feed gaps?
4. Dup/out-of-order bars? 5. Profile A qualifying setups? 6. (B: N/A — not live) 7. D1c blocks?
8. Trade missed due to freeze? 9. Trade missed due to entry gate? 10. Trades sent? 11. TradersPost
received? 12. Stop/target attached? 13. Flatten clean?

## Verdict (so far): **CONTROLLED LIVE TEST — READY** (not yet run)
Becomes **PASS** only if, during the supervised run: data stays live, no trade missed, every decision
logged, any live order is bracketed, a freeze blocks entries, EOD/kill stays armed, and the flatten is
clean. Otherwise SEMI-AUTO / MANUAL.
