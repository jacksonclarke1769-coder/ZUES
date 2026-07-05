# 3A — Attempt Cadence / Slot Model

**SIM CONDITIONAL — replay of one historical path**

- Trailing-24-month window. OVERLAP CAVEAT: every slot/cadence replays the SAME historical A-trade stream, so overlapping attempts are correlated / clustered outcomes, not independent trials — read this as one historical path, not a Monte Carlo.
- Fixed-cadence rows (1/wk, 1/5td, 2/wk) are UNCAPPED (a new attempt starts on schedule regardless of whether earlier ones finished) — peak_concurrent_slots_needed is how many slots that cadence would actually require, not an assumed N.
- maintain-N-active rows are restart-on-death (an attempt is replaced the calendar day after it terminates PASS/BUST/EXPIRE) at a FIXED slot count N=1..4, staggered 2 trading days apart at inception so slots are not exact clones.
- months_to_20cap: month index (0-based from window start) at which projected headcount (N active eval slots + funded accounts still within their ~16mo PA life) would exceed Apex's 20-account cap; None = not reached within the simulated + 16mo-pad horizon.
- marginal_funded_per_month_vs_prev_n = funded/month(N) - funded/month(N-1), the requested marginal value of each additional slot.

| config | n_slots | n_starts | funded_accounts | funded_per_month | fees_per_funded_sticker | peak_concurrent_slots_needed | months_to_20cap | marginal_funded_per_month_vs_prev_n |
|---|---|---|---|---|---|---|---|---|
| fixed cadence: 1 start/week | uncapped | 96 | 46 | 1.918 | 273.0 | 5 | None |  |
| fixed cadence: 1 per 5 trading days | uncapped | 100 | 46 | 1.918 | 285.0 | 5 | None |  |
| fixed cadence: 2/week | uncapped | 194 | 90 | 3.753 | 282.0 | 9 | None |  |
| maintain-N-active restart-on-death N=1 | 1 | 36 | 18 | 0.751 | 262.0 | 1 | None | None |
| maintain-N-active restart-on-death N=2 | 2 | 72 | 36 | 1.501 | 262.0 | 2 | 15 | 0.75 |
| maintain-N-active restart-on-death N=3 | 3 | 107 | 53 | 2.21 | 264.0 | 3 | 11 | 0.709 |
| maintain-N-active restart-on-death N=4 | 4 | 142 | 70 | 2.919 | 266.0 | 4 | 9 | 0.709 |
