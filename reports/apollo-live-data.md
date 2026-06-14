# APOLLO — Live Data for Full Auto
_2026-06-14 (Sun, market closed; NQ reopens Sun 18:00 ET)_

## Verdict: **DATA_NOT_READY**

Full auto requires a **real-time 1-minute CME** feed (so D1c runs at its validated fidelity). That does not exist tonight, and cannot be proven with the market closed.

## Why 1m matters here
- **Profile A/B are 5-minute strategies** (`load_spine("NQ","5m")`) — they must stay on 5m. Feeding 1m bars to the engine would change the frozen strategy (forbidden).
- **D1c is validated on 1m** (`drift_gate.py`: `sign(last_1m_close − 0930_open)`). On a 5m feed it runs at reduced fidelity → must be SHADOW.
- Therefore "1m for full auto" = a **dual stream**: 5m drives the engine, native 1m drives D1c. That needs a **1m→5m aggregator + native-1m D1c stream** — *not built/validated*. Until it exists, `--feed tradingview-1m` is **refused** by the runner (it would feed 1m to the 5m engine).

## Options evaluated
### Option A — TradingView 1m (preferred for speed)
- Mechanism exists (CDP read path), but requires: **real-time CME entitlement on the TradingView account** (UNVERIFIED), a 1m chart, and the 1m→5m aggregator (unbuilt).
- Real-time entitlement **cannot be auto-detected** and **cannot be verified with the market closed**.
- Status: **blocked** — entitlement unconfirmed + aggregator unbuilt.

### Option B — Databento 1m CME
- Proper live CME 1m. Requires an **account + API key (none configured)** and a feed adapter (unbuilt).
- Best long-term; not achievable tonight.

## What IS ready (5m path)
- TradingView **5m** real CME via Chrome CDP, deep warmup from Dukascopy 45d basis-aligned to the CME frame: **verified 8,409 bars / 43-day span / warmup_ok=True / basis +27.96**.
- `DATA_READY` gate (`tv_feed.data_status`) returns **false** now: real-time entitlement unverified + bars stale (market closed). Correct, fail-closed.

## Go-live condition status (data)
| # | Condition | Status |
|---|---|---|
| 1 | Real-time | ❌ entitlement UNVERIFIED (set `TV_REALTIME_CONFIRMED=1` after confirming) |
| 2 | 1-minute feed | ❌ only 5m available (1m engine path refused; aggregator unbuilt) |
| 3 | Warmup ≥2 wks | ✅ 43-day span |
| 4 | Not stale | ❌ stale now (market closed) — re-check during session |

## Fastest safe path
- **Tonight:** none for full auto. 5m feed only → **D1c SHADOW**.
- **Tomorrow (market open):** confirm TradingView real-time CME, run on **`tradingview-5m` + D1c SHADOW**. D1c-active full-auto needs the 1m dual-stream (Option A aggregator or Option B Databento) — a follow-on build.

**DATA_NOT_READY.**
