# L3 — S2: Asian Breakout Failure (reclaim within 3 candles)

**Status: DEAD — NEVER QUOTE. Not re-tested this sprint per no-dead-research rule.**

- **Prior test location**: `backtests/asia-london/s_rest.py` (`sweep_reclaim` with `max_bars=3`, S2 baseline), this dir. Frozen/unchanged; figures below reconfirmed by re-running the existing script only.
- **Years**: 2016-01-04 → 2026-05-25 (10.4y).
- **Headline numbers**: best cell (mid target) PF 0.86, N=1,325, exp_r −0.248, 3.13 trades/wk. The 3-candle reclaim constraint was non-binding (identical trade population/numbers to the unconstrained S1 04–07 window), i.e. the "failure speed" filter added nothing.
- **Verdict: DEAD.** No edge; filter is redundant with S1/L2.
