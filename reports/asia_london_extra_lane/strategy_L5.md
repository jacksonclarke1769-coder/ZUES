# L5 — S4: London Continuation Breakout (body ≥60%, retest)

**Status: DEAD — NEVER QUOTE. Not re-tested this sprint per no-dead-research rule.**

- **Prior test location**: `backtests/asia-london/s_rest.py` (`s4_continuation`, S4 baseline), this dir. Frozen/unchanged; figures below reconfirmed by re-running the existing script only.
- **Years**: 2016-01-04 → 2026-05-25 (10.4y); per-year splits 2018–2026 on file (`ablation.py` output).
- **Headline numbers**: best cell (body≥60%, target 2R) PF 0.96, N=1,434, exp_r −0.192, 3.39 trades/wk. Body≥70% variant worse (PF 0.91). Per-year: only 2020/2022/2024/2026 marginally positive, 2018/2019/2021/2023/2025 negative.
- **Verdict: DEAD.** No edge; also fails the one-regime gate (roughly half of years negative, including a badly negative 2019 at PF 0.56 and 2023 at PF 0.69).
