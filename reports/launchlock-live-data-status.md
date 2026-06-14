# LAUNCHLOCK — Live Data Status Audit
_Generated 2026-06-14 (Sun, market closed; NQ reopens Sun 18:00 ET)_

## Verdict: **DATA NOT READY** (for full automation)
Adequate for **supervised observation only**. Not proven for unattended trading tomorrow night.

---

## Does ZEUS currently receive live NQ bars?
**Partially — 5-minute bars, in PAPER, via TradingView over Chrome CDP. NOT 1-minute. Not production-proven.**

### Source inventory (all checked)
| Source | State | Notes |
|---|---|---|
| **TradingView (Chrome CDP)** | **ACTIVE (paper)** | `tv_feed.py` reads `CME_MINI:NQ1!` 5m off a logged-in Chrome chart on `localhost:9222`. Running now via `auto_live --feed tradingview`. |
| Tradovate API | **BLOCKED** | `config.TRADOVATE` has real user/pass but `cid`/`sec`/`account_spec` = `YOUR_*` placeholders, `env=demo` → API auth impossible. `LiveBarFeed` (`--feed tradovate`) cannot connect. |
| TradersPost | **N/A for data** | Execution-only. Does not provide bars (correctly noted in brief). |
| Databento | **NOT BUILT** | No account, no adapter. |
| Dukascopy (local proxy) | available | `--feed dukascopy`, credential-free CFD proxy, **has basis**, 40-day warmup. Was running earlier; stopped in favor of TradingView. |
| Replay feed | available | `ReplayFeed` / `replay_*.py` — historical only. **Not live.** |
| `paper_live.py` | engine host | Runs SimBot on whichever feed; default ReplayFeed. Data-only, never sends orders. |
| `dom_collector.py` | **UNTESTED** | Tradovate MD websocket; "untested until key arrives." Not a bar feed. |

---

## Quality of the active feed (TradingView CDP)

| Question | Answer |
|---|---|
| Real-time or delayed? | **UNVERIFIED — must confirm.** TradingView CME data is real-time **only if the logged-in TradingView account holds CME real-time entitlement**; otherwise 10–15 min delayed. **A delayed feed is unusable for live trading.** Operator must confirm entitlement before any live use. |
| CME NQ/MNQ? | **Yes** — `CME_MINI:NQ1!` (real front-month NQ, zero basis vs Tradovate). Note: chart is **NQ**; execution symbol is **MNQ** (micro). Acceptable (same price), confirmed in bridge `TP_SYMBOL` mapping. |
| 1-minute bars? | **NO — feed is 5-minute.** Profile A/B are built/validated on **5m** (`load_spine("NQ","5m")`) ✓. But **D1c is validated on 1m** and is being fed 5m (staleness widened 120s→360s to compensate) → **fidelity gap**, see below. |
| Exact bar format the bot expects? | **Yes** — `tv_feed` emits `(ts_ET, o, h, l, c)` bar-open timestamps, drops the forming bar, only yields closed bars. 11 unit tests pass; live smoke pulled 299 real bars. |
| Can D1c use it? | **Degraded.** D1c wants completed **1m** closes; it is getting **5m**. The drift sign on a 5m close ≠ the validated 1m signal. **Recommend D1c → SHADOW on live data until a 1m feed exists** (runtime flag, no code change). |
| Can Profile A/B use it? | **A: timeframe correct (5m), but warmup too shallow** (see below). **B: not wired into the live engine at all** (FENRIR B2). |
| Reliable enough to trade tomorrow? | **NO.** Three blockers: (1) warmup depth, (2) real-time entitlement unverified, (3) CDP-feed robustness. |

### Blocker 1 — Warmup depth (CORRECTNESS)
The engine's binding lookback is **previous-week levels (PWH/PWL)** in `htf.py` (`shift(1)` on completed weekly bars). The live chart cached only **~299 bars (~1 day)**. With that, PWH/PWL and even PDH/PDL are **wrong or missing → invalid signals**.
- **Minimum for correct signals:** ~2 weeks of 5m bars (~2,800 on a 24h chart).
- **Recommended:** ~6 weeks (~8,000 bars).
- **Fix:** scroll the TradingView chart back ~45 days to force history load, re-pull, confirm a clean prior-week level before relying on signals.

### Blocker 2 — Real-time entitlement (UNVERIFIED)
Must confirm the TradingView account streams **real-time** CME (not delayed). Untrustworthy until confirmed.

### Blocker 3 — Feed robustness (OBSERVED RISK)
One `[tvfeed] poll error: Connection reset by peer` already logged (auto-reconnected). The feed depends on Chrome staying open + logged in + chart on NQ 5m. No production soak; never run through a full live session. Single point of failure (Chrome/CDP).

---

## Bottom line
Real CME 5m bars **can** flow into Python (proven in paper today), but for **trading tomorrow** the feed is **NOT READY**: shallow warmup → wrong levels, real-time entitlement unconfirmed, D1c on wrong timeframe, and no live-session soak. **DATA NOT READY.**
