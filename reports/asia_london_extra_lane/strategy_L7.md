# L7 — S5: London Trap → NY Continuation

**Status: DEAD — NEVER QUOTE. Not re-tested this sprint per no-dead-research rule.**

- **Prior test location**: `backtests/asia-london/s_rest.py` (`s5_trap_ny`, S5 baseline), this dir. Frozen/unchanged; figures below reconfirmed by re-running the existing script only.
- **Years**: 2016-01-04 → 2026-05-25 (10.4y); per-year splits 2018–2026 on file.
- **Headline numbers**: best cell (2R target) PF 0.93, N=1,310, exp_r −0.033, 3.1 trades/wk; opp-target cell PF 0.90, N=885. Per-year mixed/negative: 2018 PF 0.70, 2019 0.90, 2021 0.82, 2023 0.79, 2024 0.91 — only 2020/2022/2025 marginally positive.
- **Verdict: DEAD.** No edge and fails the one-regime gate.
