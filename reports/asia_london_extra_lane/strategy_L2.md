# L2 — S1: Asian Range Mean-Reversion

**Status: DEAD — NEVER QUOTE. Not re-tested this sprint per no-dead-research rule.**

- **Prior test location**: `backtests/asia-london/s_rest.py` (`sweep_reclaim`, S1 baseline), this dir. Frozen/unchanged; figures below reconfirmed by re-running the existing script only (no new tuning).
- **Years**: 2016-01-04 → 2026-05-25 (10.4y sample, this dir's standard window).
- **Headline numbers**: best grid cell (00:00–05:00 UTC Asian range, mid target) PF 0.98, N=1,125, exp_r −0.158, 2.66 trades/wk. All other target/window cells in the grid PF 0.84–0.98 (all < 1.0).
- **Verdict: DEAD.** Asian-range mean-reversion has no edge on NQ across any tested window/target combination; consistent with this family's overall PF ≤1.11 base rate.
