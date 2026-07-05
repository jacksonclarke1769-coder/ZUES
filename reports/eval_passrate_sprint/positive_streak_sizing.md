# 1E — Positive-streak sizing — SIM CONDITIONAL

Eval-sizing sprint workstream, RESEARCH ONLY. Replayed on the frozen certified Profile A stream via `tools_sprint_state_policies.py`. All numbers below are SIM CONDITIONAL (trade-level replay of a fixed historical stream; not a live guarantee).

## Baselines for comparison
- Certified baseline (10,$1200), S0 fixed: pass 47.8%, bust 15.9%, exp 36.2%
- Best 1E row overall (any policy/base): **S0_fixed @ 15,$1000 (candidate)** — pass 55.2%, bust 13.4%, exp 31.4%

## Same-base verdict (isolates the STATE POLICY effect from the sizing-base effect)

| base | flat/null best | real-policy best | delta (real - flat) |
|---|---|---|---|
| 10,$1200 (certified) | S0_fixed (47.8%) | S1_1win-unlock-15 (50.6%) | +2.8pt |
| 15,$1000 (candidate) | S0_fixed (55.2%) | S3_profit-unlock (52.9%) | -2.3pt |

**Verdict:** 1E positive-streak sizing: best real policy (S1_1win-unlock-15 @ 10,$1200 (certified)) beats its own same-base flat/null anchor by +2.8pt -- a real, if modest, deviation from the prior finding. [CAUTION: per-year pass% spread >20pt across years with n>=10 -- possibly concentrated in one year, not a robust edge]

## Outcomes-after-double-loss / after-triple-loss cohorts (all policies)

| policy | base | n hit 2-loss | pass% after 2-loss | n hit 3-loss | pass% after 3-loss |
|---|---|---|---|---|---|
| S0_fixed | 10,$1200 (certified) | 180 | 14.4 | 67 | 1.5 |
| S0_fixed | 15,$1000 (candidate) | 176 | 25.0 | 64 | 1.6 |
| S1_1win-unlock-15 | 10,$1200 (certified) | 178 | 17.4 | 66 | 1.5 |
| S1_1win-unlock-15 | 15,$1000 (candidate) | 183 | 18.6 | 68 | 4.4 |
| S2_2win-unlock-15 | 10,$1200 (certified) | 180 | 17.2 | 65 | 1.5 |
| S2_2win-unlock-15 | 15,$1000 (candidate) | 186 | 16.7 | 69 | 1.4 |
| S2b_2win-unlock-20 | 10,$1200 (certified) | 178 | 18.0 | 65 | 1.5 |
| S2b_2win-unlock-20 | 15,$1000 (candidate) | 184 | 17.9 | 69 | 1.4 |
| S3_profit-unlock | 10,$1200 (certified) | 180 | 17.8 | 68 | 2.9 |
| S3_profit-unlock | 15,$1000 (candidate) | 175 | 22.3 | 65 | 4.6 |
| S4_positive-no-double-loss | 10,$1200 (certified) | 178 | 13.5 | 67 | 1.5 |
| S4_positive-no-double-loss | 15,$1000 (candidate) | 181 | 15.5 | 66 | 1.5 |

## Per-policy funnel (both sizing bases)

| policy | base | n | pass% | bust% | exp% | med/mean days | worst day | E[$/attempt] | n_trades | WR% | PF(R) | expR | clipped% | risk-used$ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S0_fixed | 10,$1200 (certified) | 395 | 47.8 | 15.9 | 36.2 | 16/16.0 | -1000 | 5959.1 | 2426 | 58.5 | 2.276 | 0.4156 | 66.1 | 775.2 |
| S0_fixed | 15,$1000 (candidate) | 395 | 55.2 | 13.4 | 31.4 | 15/16.6 | -1000 | 6893.6 | 2388 | 58.9 | 2.353 | 0.431 | 36.2 | 817.8 |
| S1_1win-unlock-15 | 10,$1200 (certified) | 395 | 50.6 | 18.0 | 31.4 | 15/15.4 | -1000 | 6313.6 | 2315 | 58.5 | 2.307 | 0.4218 | 55.8 | 846.3 |
| S1_1win-unlock-15 | 15,$1000 (candidate) | 395 | 47.6 | 13.7 | 38.7 | 15/16.7 | -1000 | 5926.9 | 2505 | 58.5 | 2.315 | 0.4236 | 46.0 | 752.1 |
| S2_2win-unlock-15 | 10,$1200 (certified) | 395 | 48.9 | 16.2 | 34.9 | 15/15.8 | -1000 | 6088.0 | 2399 | 58.7 | 2.324 | 0.4245 | 61.6 | 804.8 |
| S2_2win-unlock-15 | 15,$1000 (candidate) | 395 | 45.6 | 12.9 | 41.5 | 16/16.9 | -1000 | 5669.1 | 2566 | 58.7 | 2.329 | 0.4256 | 52.0 | 721.9 |
| S2b_2win-unlock-20 | 10,$1200 (certified) | 395 | 49.1 | 16.2 | 34.7 | 14/15.4 | -1000 | 6120.2 | 2372 | 58.7 | 2.328 | 0.4244 | 59.0 | 820.1 |
| S2b_2win-unlock-20 | 15,$1000 (candidate) | 395 | 45.8 | 13.2 | 41.0 | 15/16.6 | -1000 | 5701.3 | 2541 | 58.7 | 2.328 | 0.4247 | 49.7 | 732.0 |
| S3_profit-unlock | 10,$1200 (certified) | 395 | 50.4 | 18.7 | 30.9 | 14/15.2 | -1000 | 6281.3 | 2316 | 58.4 | 2.29 | 0.4174 | 52.5 | 865.4 |
| S3_profit-unlock | 15,$1000 (candidate) | 395 | 52.9 | 12.9 | 34.2 | 15/16.2 | -1000 | 6603.6 | 2403 | 58.8 | 2.34 | 0.4287 | 38.2 | 798.3 |
| S4_positive-no-double-loss | 10,$1200 (certified) | 395 | 49.1 | 18.2 | 32.7 | 15/14.9 | -1000 | 6120.2 | 2329 | 58.3 | 2.28 | 0.4159 | 57.0 | 840.0 |
| S4_positive-no-double-loss | 15,$1000 (candidate) | 395 | 48.9 | 12.4 | 38.7 | 15/16.6 | -1000 | 6088.0 | 2491 | 58.8 | 2.344 | 0.4295 | 47.3 | 749.6 |

## Per-year pass% (2021-2026)

| policy | base | 2021 (n) | 2022 (n) | 2023 (n) | 2024 (n) | 2025 (n) | 2026 (n) |
|---|---|---|---|---|---|---|---|
| S0_fixed | 10,$1200 (certified) | 51.1% (45) | 38.6% (70) | 52.8% (89) | 35.1% (74) | 62.9% (89) | 35.7% (28) |
| S0_fixed | 15,$1000 (candidate) | 57.8% (45) | 48.6% (70) | 66.3% (89) | 36.5% (74) | 66.3% (89) | 46.4% (28) |
| S1_1win-unlock-15 | 10,$1200 (certified) | 55.6% (45) | 42.9% (70) | 62.9% (89) | 39.2% (74) | 59.6% (89) | 25.0% (28) |
| S1_1win-unlock-15 | 15,$1000 (candidate) | 46.7% (45) | 40.0% (70) | 55.1% (89) | 32.4% (74) | 60.7% (89) | 42.9% (28) |
| S2_2win-unlock-15 | 10,$1200 (certified) | 55.6% (45) | 41.4% (70) | 57.3% (89) | 36.5% (74) | 57.3% (89) | 35.7% (28) |
| S2_2win-unlock-15 | 15,$1000 (candidate) | 44.4% (45) | 41.4% (70) | 51.7% (89) | 29.7% (74) | 57.3% (89) | 42.9% (28) |
| S2b_2win-unlock-20 | 10,$1200 (certified) | 53.3% (45) | 42.9% (70) | 57.3% (89) | 36.5% (74) | 58.4% (89) | 35.7% (28) |
| S2b_2win-unlock-20 | 15,$1000 (candidate) | 46.7% (45) | 41.4% (70) | 52.8% (89) | 28.4% (74) | 57.3% (89) | 42.9% (28) |
| S3_profit-unlock | 10,$1200 (certified) | 53.3% (45) | 42.9% (70) | 57.3% (89) | 40.5% (74) | 64.0% (89) | 25.0% (28) |
| S3_profit-unlock | 15,$1000 (candidate) | 57.8% (45) | 44.3% (70) | 59.6% (89) | 37.8% (74) | 64.0% (89) | 50.0% (28) |
| S4_positive-no-double-loss | 10,$1200 (certified) | 55.6% (45) | 40.0% (70) | 53.9% (89) | 39.2% (74) | 62.9% (89) | 28.6% (28) |
| S4_positive-no-double-loss | 15,$1000 (candidate) | 51.1% (45) | 40.0% (70) | 52.8% (89) | 36.5% (74) | 61.8% (89) | 46.4% (28) |
