# ES Edge Expansion Wave 3 -- Stage 2: standalone eval funnel

RESEARCH ONLY. LIVE HOLD ACTIVE. CFD-proxy caveat applies to every ES number. No verdict language below -- flags/values only, mechanical formulas per the architect spec; the auditor adjudicates.

Pipeline: `tools_account_size_research.build_events(rows,budget,cap)` / `day_rows(ev,550,1000)` / `eval_run` per eligible start (unique trading days >30d runway, EXPIRE_DAYS=30) -- literal `tools_salvage_vpc_reeval.py` pattern. `e_dollar` = pass_pct x $8000 - $131, labeled **PLACEHOLDER** per spec (mechanical formula, not a modeled dollar figure).

M8-median/M8-max cells are **BLOCKED**: `wave3_stage1_streams.py` demonstrates a 100%-failure tz-mismatch defect between `lane_d_m8_gap_fill_gap_go.build_signal_frame()` (produces a tz-naive-but-UTC-valued `entry_ts`) and `lane_c_common.simulate_exit_1m()` (requires tz-aware `entry_ts`) -- both files are outside this task's Files-allowed list; not fixed, not guessed around.

Grid: budgets [150, 200, 300, 400, 500, 600] x caps [1, 2, 3, 4, 6] = 30 cells per stream x 3 streams = 90 rows.

## Full table

| stream | budget | cap | eligible | pass_count | bust_count | expire_count | not_pass | pass_pct | bust_pct | expire_pct | not_pass_pct | attempts_per_pass | med_days | trades_per_eval | f_slot | e_dollar | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M1 | 150 | 1 | 2200 | 0 | 0 | 2200 | 2200 | 0 | 0 | 100 | 100 | nan | nan | 19.3 | 0 | -131 |  |
| M1 | 150 | 2 | 2200 | 0 | 0 | 2200 | 2200 | 0 | 0 | 100 | 100 | nan | nan | 19.3 | 0 | -131 |  |
| M1 | 150 | 3 | 2200 | 0 | 0 | 2200 | 2200 | 0 | 0 | 100 | 100 | nan | nan | 19.3 | 0 | -131 |  |
| M1 | 150 | 4 | 2200 | 0 | 0 | 2200 | 2200 | 0 | 0 | 100 | 100 | nan | nan | 19.3 | 0 | -131 |  |
| M1 | 150 | 6 | 2200 | 0 | 0 | 2200 | 2200 | 0 | 0 | 100 | 100 | nan | nan | 19.3 | 0 | -131 |  |
| M1 | 200 | 1 | 2379 | 0 | 0 | 2379 | 2379 | 0 | 0 | 100 | 100 | nan | nan | 20.09 | 0 | -131 |  |
| M1 | 200 | 2 | 2379 | 0 | 0 | 2379 | 2379 | 0 | 0 | 100 | 100 | nan | nan | 20.09 | 0 | -131 |  |
| M1 | 200 | 3 | 2379 | 0 | 0 | 2379 | 2379 | 0 | 0 | 100 | 100 | nan | nan | 20.09 | 0 | -131 |  |
| M1 | 200 | 4 | 2379 | 0 | 0 | 2379 | 2379 | 0 | 0 | 100 | 100 | nan | nan | 20.09 | 0 | -131 |  |
| M1 | 200 | 6 | 2379 | 2 | 1 | 2376 | 2377 | 0.1 | 0 | 99.9 | 99.9 | 1189.5 | 26 | 20.09 | 0.01 | -124.27 |  |
| M1 | 300 | 1 | 2462 | 0 | 0 | 2462 | 2462 | 0 | 0 | 100 | 100 | nan | nan | 20.63 | 0 | -131 |  |
| M1 | 300 | 2 | 2462 | 33 | 8 | 2421 | 2429 | 1.3 | 0.3 | 98.3 | 98.7 | 74.61 | 24 | 20.57 | 0.16 | -23.77 |  |
| M1 | 300 | 3 | 2462 | 88 | 13 | 2361 | 2374 | 3.6 | 0.5 | 95.9 | 96.4 | 27.98 | 23 | 20.44 | 0.44 | 154.95 |  |
| M1 | 300 | 4 | 2462 | 115 | 23 | 2324 | 2347 | 4.7 | 0.9 | 94.4 | 95.3 | 21.41 | 22 | 20.37 | 0.58 | 242.68 |  |
| M1 | 300 | 6 | 2462 | 143 | 78 | 2241 | 2319 | 5.8 | 3.2 | 91 | 94.2 | 17.22 | 23 | 20.25 | 0.72 | 333.66 |  |
| M1 | 400 | 1 | 2475 | 0 | 0 | 2475 | 2475 | 0 | 0 | 100 | 100 | nan | nan | 20.72 | 0 | -131 |  |
| M1 | 400 | 2 | 2475 | 88 | 48 | 2339 | 2387 | 3.6 | 1.9 | 94.5 | 96.4 | 28.12 | 22 | 20.45 | 0.44 | 153.44 |  |
| M1 | 400 | 3 | 2475 | 185 | 102 | 2188 | 2290 | 7.5 | 4.1 | 88.4 | 92.5 | 13.38 | 21 | 20.03 | 0.94 | 466.98 |  |
| M1 | 400 | 4 | 2475 | 264 | 142 | 2069 | 2211 | 10.7 | 5.7 | 83.6 | 89.3 | 9.38 | 21 | 19.74 | 1.37 | 722.33 |  |
| M1 | 400 | 6 | 2475 | 382 | 257 | 1836 | 2093 | 15.4 | 10.4 | 74.2 | 84.6 | 6.48 | 21 | 19.18 | 2.03 | 1103.75 |  |
| M1 | 500 | 1 | 2481 | 5 | 11 | 2465 | 2476 | 0.2 | 0.4 | 99.4 | 99.8 | 496.2 | 29 | 20.74 | 0.02 | -114.88 |  |
| M1 | 500 | 2 | 2481 | 104 | 93 | 2284 | 2377 | 4.2 | 3.7 | 92.1 | 95.8 | 23.86 | 21 | 20.3 | 0.52 | 204.35 |  |
| M1 | 500 | 3 | 2481 | 213 | 173 | 2095 | 2268 | 8.6 | 7 | 84.4 | 91.4 | 11.65 | 20 | 19.72 | 1.1 | 555.82 |  |
| M1 | 500 | 4 | 2481 | 355 | 237 | 1889 | 2126 | 14.3 | 9.6 | 76.1 | 85.7 | 6.99 | 20 | 19.14 | 1.9 | 1013.7 |  |
| M1 | 500 | 6 | 2481 | 550 | 446 | 1485 | 1931 | 22.2 | 18 | 59.9 | 77.8 | 4.51 | 18 | 17.81 | 3.17 | 1642.48 |  |
| M1 | 600 | 1 | 2484 | 23 | 8 | 2453 | 2461 | 0.9 | 0.3 | 98.8 | 99.1 | 108 | 15 | 20.7 | 0.11 | -56.93 |  |
| M1 | 600 | 2 | 2484 | 110 | 95 | 2279 | 2374 | 4.4 | 3.8 | 91.7 | 95.6 | 22.58 | 21 | 20.25 | 0.55 | 223.27 |  |
| M1 | 600 | 3 | 2484 | 231 | 170 | 2083 | 2253 | 9.3 | 6.8 | 83.9 | 90.7 | 10.75 | 17 | 19.53 | 1.21 | 612.96 |  |
| M1 | 600 | 4 | 2484 | 397 | 281 | 1806 | 2087 | 16 | 11.3 | 72.7 | 84 | 6.26 | 19 | 18.69 | 2.17 | 1147.58 |  |
| M1 | 600 | 6 | 2484 | 657 | 495 | 1332 | 1827 | 26.4 | 19.9 | 53.6 | 73.6 | 3.78 | 17 | 16.93 | 3.99 | 1984.94 |  |
| M8_median | 150 | 1 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 150 | 2 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 150 | 3 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 150 | 4 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 150 | 6 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 200 | 1 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 200 | 2 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 200 | 3 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 200 | 4 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 200 | 6 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 300 | 1 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 300 | 2 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 300 | 3 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 300 | 4 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 300 | 6 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 400 | 1 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 400 | 2 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 400 | 3 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 400 | 4 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 400 | 6 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 500 | 1 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 500 | 2 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 500 | 3 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 500 | 4 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 500 | 6 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 600 | 1 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 600 | 2 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 600 | 3 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 600 | 4 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_median | 600 | 6 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.3806 (not this funnel) |
| M8_max | 150 | 1 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 150 | 2 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 150 | 3 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 150 | 4 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 150 | 6 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 200 | 1 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 200 | 2 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 200 | 3 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 200 | 4 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 200 | 6 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 300 | 1 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 300 | 2 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 300 | 3 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 300 | 4 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 300 | 6 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 400 | 1 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 400 | 2 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 400 | 3 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 400 | 4 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 400 | 6 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 500 | 1 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 500 | 2 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 500 | 3 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 500 | 4 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 500 | 6 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 600 | 1 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 600 | 2 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 600 | 3 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 600 | 4 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |
| M8_max | 600 | 6 | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | BLOCKED -- see wave3_stage1_streams.py docstring (M8 tz-mismatch defect); csv-recorded standalone n=184 PF=1.7909 (not this funnel) |


## Runtime

6.1s wall clock.
