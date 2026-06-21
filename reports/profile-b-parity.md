# Profile B — Parity Harness (streaming == backtest)
_2026-06-21 · `tools/check_profile_b_parity.py` · the biggest gap before B can go live_

## Result: **0 MISMATCHES** ✓
The streaming `ProfileBEngine` (the live engine) emits the **identical** signal to the validated
batch backtest (`b_entries`/`b_exits`) on **all 3,173 complete-data days** of the full 12-year history:
same day, same side, same entry level, same stop, same target. This is the Profile-A-equivalent
"0 signal mismatches" proof, now done for B.

```
batch signals: 3,173 · streaming signals: 3,173 · MISMATCHES: 0
(only-batch 0, only-stream 0, side 0, price 0)
```

## What the harness found (and how it was fixed to parity)
| Issue | Cause | Fix |
|---|---|---|
| 767 → stop/target off | streaming took ATR at the first post-OR bar (09:45) | take ATR at the **last OR bar** (09:40), matching the batch |
| 767 extra signals | streaming compared to batch *fills*; the batch drops breaks with no retest-fill within 6 bars | compare at the **break / limit-placement** level — the engine's job is to place the limit; the fill is the downstream order layer |
| OR-bar guard | batch requires `len(orng) >= 2` | engine now requires ≥2 opening-range bars |
| 9 residual (all **Dec 30**) | data-gap days: < 20 RTH bars in the historical feed (`len(r) >= 20` batch guard) | a **data-quality** filter, not strategy logic — the batch excludes them retrospectively; **LIVE the data-readiness GREEN gate excludes them prospectively**. Harness applies the same filter to both. |

## Why the 9 data-gap days are not a real difference
They are year-end days with < 20 RTH 5m bars in the framework feed (incomplete data). A live session
runs only when the feed is GREEN/DATA_READY, so the engine never trades on a sparse feed live. Both the
backtest (`len(r)>=20`) and the live system (data gate) exclude them — the harness mirrors that.

## Locked in the suite
`test_profile_b_parity.py` runs the full-history parity as a subprocess and asserts **0 mismatches**
(~13s). Full suite **398 green**.

## What this unblocks (and what still remains)
- ✅ **Profile B's signal engine is now proven equal to its validated backtest** — the #1 gap is closed.
- Still before B live money: (a) **B paper-P&L tracking** on the calendar, (b) at least one clean
  **paper session**, (c) funded **broker-truth cushion** for P3. Live stays blocked behind the flag.
