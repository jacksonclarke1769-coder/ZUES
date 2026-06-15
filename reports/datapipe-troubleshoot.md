# DATAPIPE — TradingView Feed Troubleshoot
_2026-06-15 · data-forensics · no live trading · Profile A/B/D1c untouched_

## 1. Root cause category: **A — TradingView chart frozen (Chrome background-tab throttling)**

## 2. Exact failure point
The feed is **not a file or websocket** — `tv_feed.TradingViewFeed` reads the chart's in-memory
`mainSeries().bars()` array via **Chrome DevTools Protocol** (`localhost:9222`) from the dedicated
bot-Chrome. Chrome **throttled the backgrounded TradingView tab**, freezing the chart's 1-minute
**bar-building** loop. Quotes kept ticking the tab title, but `bars()` stopped committing new candles.
The launcher `tools/launch-tv-chrome.sh` had **no anti-throttling flags**. The bot reader was healthy —
it faithfully read a frozen chart.

## 3. Evidence
- Tab title live: `NQ1! 30,603 +3.17%` (quotes flowing) — but `bars()` direct CDP read **frozen at 08:00 ET** for 21+ min.
- Bot `data_status` matched the chart exactly (last_bar 08:00, age growing) → bot reads chart, not stale-internally.
- After relaunch with anti-throttle flags: `bars()` **resumed** — 08:22 / 08:23 / 08:24 / 08:25 (age 0.5 min).

## 4. Commands run
Direct CDP `bars()` reads (`tv_feed._CDP`), `quote_get`, `pgrep auto_live`, `curl :9222/json`,
`pkill -f remote-debugging-port=9222`, `caffeinate -dimsu`, `./tools/launch-tv-chrome.sh`.

## 5. Files inspected
`tv_feed.py` (CDP reader), `tools/launch-tv-chrome.sh` (Chrome launch flags), `heimdall_monitor.py`.

## 6–10. Where the data stopped (chain trace)
| Stage | Pre-fix | Post-fix |
|---|---|---|
| 6. TradingView chart `bars()` | ❌ frozen 08:00 | ✅ advancing (08:25) |
| 7. Local feed file | n/a — no file (CDP read) | n/a |
| 8. Python runner ingest | read the frozen series (healthy reader) | ✅ reconnected (reset_count 1), ingesting |
| 9. Heartbeat / data_state | process heartbeat fresh; data_state correctly forced **RED** (wall-clock freshness) | ✅ GREEN after stability window |
| 10. Dashboard | honest **RED/not-green** (false-green already fixed) | ✅ GREEN, truthful |

## 11. Fix applied
- `tools/launch-tv-chrome.sh`: added `--disable-background-timer-throttling`,
  `--disable-backgrounding-occluded-windows`, `--disable-renderer-backgrounding`,
  `--disable-features=CalculateNativeWinOcclusion`. *(Note: this script lives outside the nq-liq-bot
  git repo, so it's a local infra edit, not committed here.)*
- Started `caffeinate -dimsu` (prevent Mac sleep).
- Relaunched the dedicated `:9222` Chrome (operator's personal Chrome untouched).

## 12. Test after fix
Chart `bars()` resumed (08:22→08:25); bot **reconnected** (the relaunch exercised the reconnect path,
reset_count=1, bars_since_reset 25 ≫ stability window); data_state **GREEN**, DATA_READY **True**.

## 13–16
- **data_state:** GREEN  ·  **DATA_READY:** True  ·  **D1c:** ACTIVE_EVAL_FILTER (legal on 1m + real-time)
- **Current allowed mode:** SEMI-AUTO GO (data now live). **Full auto still BLOCKED** (preflight FAILS on
  missing `full-auto-approved.flag`; supervised sessions still owed).

## 17. Remaining blockers before full auto
1. `full-auto-approved.flag` (final human arming — not created)
2. Supervised sessions
3. **Feed-reliability (strategic):** the browser/CDP feed just froze and needed a manual relaunch.

## ⚠️ Recommendation: `TRADINGVIEW_BROWSER_FEED = SEMI_AUTO_ONLY`
The browser feed is fine for **supervised semi-auto** — the robustness layer **fails safe** (stale →
RED → entries blocked; reconnect-tolerant; dead-man), so it never trades blind. But a CDP/browser feed
is inherently fragile for **unattended** operation (Chrome throttle/crash, tab occlusion, Mac state, TV
session expiry). The anti-throttle flags + caffeinate reduce the risk but don't eliminate it.

**For unattended FULL AUTO, replace the browser feed with a proper data source** — Tradovate API market
data (zero-basis, already scaffolded in `LiveBarFeed`) or Databento live CME 1m. Until then, treat
TradingView-CDP as supervised-grade and keep full auto gated behind the approval flag + a real-feed
upgrade (or a long clean soak proving the browser feed stable).

## Prime-directive compliance
No entries while RED (entry gate enforced) · no semi-auto sends on a stale feed · no full auto ·
`full-auto-approved.flag` not created · failure point isolated to Category A.
