# ES Edge Expansion Wave 3 -- Stage 3: portfolio integration

RESEARCH ONLY. LIVE HOLD ACTIVE. CFD-proxy caveat on the ES leg. No verdict language -- flags/values only, mechanical formulas per the architect spec; the auditor adjudicates. No commits.

Benchmark canary: A(900,6)+VPC(600,3) -> got {'pass_pct': 37.4, 'bust_pct': 18.0, 'exp_pct': 44.6, 'n': 684} vs pinned {'pass_pct': 37.4, 'bust_pct': 18.0, 'exp_pct': 44.6, 'n': 684} -> **PASS**.

ES-M8-median / ES-M8-max rows (6 of 10) are **BLOCKED**: `wave3_stage1_streams.py` demonstrates a 100%-failure tz-mismatch defect in existing, forbidden-to-touch files (`lane_d_m8_gap_fill_gap_go.py` / `lane_c_common.py`) -- not fixed, not guessed around.

## 10-row portfolio table

| row | es_budget | es_cap | eligible | pass_count | bust_count | expire_count | not_pass | pass_pct | bust_pct | expire_pct | worst_day | attempts_per_pass | f_slot | e_dollar | trades_wk_total | trades_wk_A | trades_wk_VPC | trades_wk_ES | same_day_joint_loss_days | same_day_common_days | same_week_joint_loss_weeks | same_week_common_weeks | n_days_ES_alone | ES_alone_WR | ES_alone_PF | worst_portfolio_day | FLAG_PASS_NOT_IMPROVED | FLAG_BUST_EXCEEDS_PASS_GAIN | FLAG_CLUSTERING | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BENCHMARK A900/6+VPC600/3 | nan | nan | 684 | 256 | 123 | 305 | 428 | 37.4 | 18 | 44.6 | -1000 | 2.67 | 5.89 | 2863.15 | 3.94 | 2.21 | 1.75 | nan | 64 | 173 | 44 | 197 | nan | nan | nan | -1000 | True | False | False |  |
| BENCHMARK + ES-M1@300/2 | 300 | 2 | 2521 | 501 | 190 | 1830 | 2020 | 19.9 | 7.5 | 72.6 | -1000 | 5.03 | 2.76 | 1458.85 | 6.24 | 2.21 | 1.75 | 4.59 | 45 | 161 | 24 | 193 | 1853 | 43.1 | 1.117 | -1000 | True | True | False |  |
| BENCHMARK + ES-M1@400/3 | 400 | 3 | 2530 | 630 | 263 | 1637 | 1900 | 24.9 | 10.4 | 64.7 | -1000 | 4.02 | 3.61 | 1861.09 | 6.26 | 2.21 | 1.75 | 4.61 | 45 | 161 | 25 | 194 | 1853 | 43.1 | 1.117 | -1000 | True | True | False |  |
| BENCHMARK + ES-M1@600/4 | 600 | 4 | 2535 | 727 | 410 | 1398 | 1808 | 28.7 | 16.2 | 55.1 | -1000 | 3.49 | 4.47 | 2163.28 | 6.28 | 2.21 | 1.75 | 4.63 | 45 | 161 | 25 | 194 | 1853 | 43.1 | 1.117 | -1000 | True | True | False |  |
| BENCHMARK + ES-M8-median@300/2 | 300 | 2 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | None | None | None | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this portfolio funnel) |
| BENCHMARK + ES-M8-median@400/3 | 400 | 3 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | None | None | None | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this portfolio funnel) |
| BENCHMARK + ES-M8-median@600/4 | 600 | 4 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | None | None | None | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this portfolio funnel) |
| BENCHMARK + ES-M8-max@300/2 | 300 | 2 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | None | None | None | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this portfolio funnel) |
| BENCHMARK + ES-M8-max@400/3 | 400 | 3 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | None | None | None | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this portfolio funnel) |
| BENCHMARK + ES-M8-max@600/4 | 600 | 4 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | None | None | None | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this portfolio funnel) |

## Runtime

22.3s wall clock.
