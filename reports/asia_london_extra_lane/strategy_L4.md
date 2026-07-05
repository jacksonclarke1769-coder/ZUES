# L4 — S3: London Sweep of Asian High/Low

**Status: DEAD — NEVER QUOTE. Not re-tested this sprint per no-dead-research rule.**

- **Prior test location**: `backtests/asia-london/s3_london_sweep.py` (canonical baseline of this dir); trades archived at `s3_canonical_trades.csv`. Frozen/unchanged; figures below reconfirmed by re-running the existing script only.
- **Years**: 2016-01-04 → 2026-05-25 (10.4y); per-year splits 2018–2026 on file.
- **Headline numbers**: canonical config (A00-05/L07-11, mid target) PF 0.99, N=1,761. Best-of-16-cell window/range grid: A00-04/L08-12, PF 1.11, N=1,632 — the single strongest cell in the entire family, still below the 1.15 bar. Per-year: negative in 2018/2019/2022–2024/2026, only marginally positive 2020/2021/2025.
- **Verdict: DEAD** (this sprint's rejection bar: best-of-grid PF 1.11 < 1.15 → REJECTED). This is the family's headline "PF ≤1.11" baseline referenced in the sprint brief.
