# ES Edge Expansion -- Lane D -- M14: Time-Conditional Momentum Stat Scan

**CFD proxy, documented optimistic bias vs real futures; graduates need real CME data before certification.** RESEARCH ONLY. LIVE HOLD ACTIVE. No commits.

Preregistered design, mirrors `H_statistical_baseline_search.py` (the "H-scan pattern"). No expansion of scope after first run.

**Panel**: 13299 (date,stamp) rows -- IS(2016-2022)=8939, OOS(2023-2026)=4360. Stamps: 0945, 1000, 1030, 1100, 1300 ET.

**Cells tested**: 2562 total (369 single-feature cells + 2193 pair cells, from 10 preregistered pairs).

## Structural data-availability exclusions (causal, not omissions)

- `vwap_slope_6bar`: NaN at 09:45 and 10:00 (needs 6 prior bars); scanned from 10:30 onward only -- matches `H_statistical_baseline_search.py`'s own finding.
- `or30_state`: undefined before the OR30 window itself closes at 10:00 (using it at 09:45 would look ahead into that day's still-open opening range); scanned from 10:00 onward only.

## Nominee table

| feature | stamp | label | bin | is_hit | is_n | oos_hit | oos_n | monotone | direction | n_trades | pf | per_year |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gap_dir | 0945 | L2_next60m_dir | -1.0 | 0.55 | 800 | 0.559 | 379 | True | up | 1179 | 1.057 | 114.3 |
| gap_dir | 1100 | L1_next30m_dir | -1.0 | 0.551 | 798 | 0.549 | 377 | True | up | 1179 | 1.057 | 114.3 |
| gap_dir | 1100 | L2_next60m_dir | 1.0 | 0.558 | 985 | 0.53 | 494 | True | up | 1483 | 0.956 | 143.4 |
| gap_dir | 1100 | L3_race_1R | 1.0 | 0.447 | 396 | 0.428 | 215 | True | down | 1483 | 0.83 | 143.4 |
| gap_dir | 1300 | L3_race_1R | 1.0 | 0.397 | 224 | 0.454 | 141 | True | down | 1471 | 0.83 | 142.4 |
| or30_state | 1100 | L1_next30m_dir | both | 0.577 | 227 | 0.561 | 148 | True | up | 376 | 0.996 | 36.4 |
| or30_state | 1300 | L2_next60m_dir | broke_up | 0.553 | 646 | 0.556 | 302 | True | up | 982 | 9.059 | 95.3 |
| or30_state | 1300 | L3_race_1R | broke_up | 0.397 | 141 | 0.421 | 76 | True | down | 982 | 0.084 | 95.3 |
| last_15m_ret_atr__x__vwap_dist_atr | 1000 | L2_next60m_dir | Q5,Q5 | 0.568 | 273 | 0.585 | 135 | None | up | 408 | 2.697 | 39.5 |
| last_15m_ret_atr__x__vwap_dist_atr | 1100 | L2_next60m_dir | Q5,Q5 | 0.571 | 184 | 0.578 | 64 | None | up | 248 | 3.303 | 24.1 |
| last_15m_ret_atr__x__open_to_now_ret_atr | 1000 | L2_next60m_dir | Q5,Q5 | 0.575 | 200 | 0.567 | 90 | None | up | 290 | 4.952 | 28.2 |
| vwap_dist_atr__x__vwap_slope_6bar | 1100 | L2_next60m_dir | Q2,Q2 | 0.589 | 158 | 0.545 | 55 | None | up | 215 | 0.41 | 20.9 |
| vwap_dist_atr__x__vwap_slope_6bar | 1300 | L1_next30m_dir | Q3,Q3 | 0.45 | 169 | 0.412 | 34 | None | down | 214 | 0.812 | 20.7 |
| vwap_dist_atr__x__vwap_slope_6bar | 1300 | L2_next60m_dir | Q5,Q5 | 0.575 | 219 | 0.541 | 170 | None | up | 393 | 6.573 | 38.1 |
| vwap_dist_atr__x__gap_dir | 0945 | L2_next60m_dir | Q2,-1.0 | 0.6 | 150 | 0.595 | 79 | None | up | 229 | 0.649 | 22.2 |
| vwap_dist_atr__x__gap_dir | 0945 | L2_next60m_dir | Q3,1.0 | 0.617 | 214 | 0.574 | 94 | None | up | 308 | 1.164 | 29.8 |
| vwap_dist_atr__x__gap_dir | 1000 | L1_next30m_dir | Q2,-1.0 | 0.597 | 154 | 0.655 | 58 | None | up | 212 | 0.875 | 20.6 |
| vwap_dist_atr__x__gap_dir | 1000 | L1_next30m_dir | Q5,1.0 | 0.564 | 188 | 0.66 | 94 | None | up | 282 | 2.987 | 27.3 |
| vwap_dist_atr__x__gap_dir | 1000 | L2_next60m_dir | Q2,-1.0 | 0.565 | 154 | 0.69 | 58 | None | up | 212 | 0.875 | 20.6 |
| vwap_dist_atr__x__gap_dir | 1000 | L2_next60m_dir | Q5,1.0 | 0.622 | 188 | 0.585 | 94 | None | up | 282 | 2.987 | 27.3 |
| vwap_dist_atr__x__gap_dir | 1030 | L1_next30m_dir | Q1,-1.0 | 0.418 | 170 | 0.448 | 87 | None | down | 257 | 4.152 | 24.9 |
| vwap_dist_atr__x__gap_dir | 1030 | L1_next30m_dir | Q2,-1.0 | 0.554 | 166 | 0.568 | 74 | None | up | 240 | 0.876 | 23.3 |
| vwap_dist_atr__x__gap_dir | 1030 | L1_next30m_dir | Q3,1.0 | 0.562 | 226 | 0.553 | 85 | None | up | 311 | 0.964 | 30.1 |
| vwap_dist_atr__x__gap_dir | 1030 | L1_next30m_dir | Q4,-1.0 | 0.581 | 167 | 0.695 | 59 | None | up | 226 | 2.893 | 22.3 |
| vwap_dist_atr__x__gap_dir | 1030 | L2_next60m_dir | Q2,-1.0 | 0.59 | 166 | 0.548 | 73 | None | up | 240 | 0.876 | 23.3 |
| vwap_dist_atr__x__gap_dir | 1030 | L2_next60m_dir | Q4,-1.0 | 0.593 | 167 | 0.712 | 59 | None | up | 226 | 2.893 | 22.3 |
| vwap_dist_atr__x__gap_dir | 1100 | L2_next60m_dir | Q4,1.0 | 0.557 | 201 | 0.615 | 104 | None | up | 305 | 3.316 | 29.7 |
| vwap_dist_atr__x__gap_dir | 1100 | L2_next60m_dir | Q5,1.0 | 0.581 | 186 | 0.547 | 95 | None | up | 281 | 4.753 | 27.4 |
| vwap_dist_atr__x__gap_dir | 1300 | L1_next30m_dir | Q2,1.0 | 0.56 | 193 | 0.571 | 77 | None | up | 280 | 0.277 | 27.5 |
| vwap_dist_atr__x__gap_dir | 1300 | L2_next60m_dir | Q1,1.0 | 0.557 | 174 | 0.552 | 125 | None | up | 300 | 0.096 | 29.4 |
| vwap_dist_atr__x__gap_dir | 1300 | L2_next60m_dir | Q5,1.0 | 0.581 | 191 | 0.549 | 91 | None | up | 284 | 5.895 | 27.6 |
| vwap_dist_atr__x__open_to_now_ret_atr | 0945 | L2_next60m_dir | Q2,Q2 | 0.553 | 161 | 0.536 | 84 | None | up | 245 | 0.675 | 23.7 |
| vwap_dist_atr__x__open_to_now_ret_atr | 0945 | L2_next60m_dir | Q5,Q5 | 0.579 | 240 | 0.585 | 94 | None | up | 334 | 4.097 | 32.6 |
| vwap_dist_atr__x__open_to_now_ret_atr | 0945 | L3_race_1R | Q1,Q1 | 0.436 | 179 | 0.442 | 86 | None | down | 364 | 3.362 | 35.4 |
| vwap_dist_atr__x__open_to_now_ret_atr | 1000 | L1_next30m_dir | Q2,Q2 | 0.564 | 156 | 0.54 | 63 | None | up | 219 | 0.453 | 21.3 |
| vwap_dist_atr__x__open_to_now_ret_atr | 1000 | L1_next30m_dir | Q5,Q5 | 0.569 | 246 | 0.583 | 108 | None | up | 354 | 5.537 | 34.5 |
| vwap_dist_atr__x__open_to_now_ret_atr | 1000 | L2_next60m_dir | Q5,Q5 | 0.577 | 246 | 0.574 | 108 | None | up | 354 | 5.537 | 34.5 |
| vwap_dist_atr__x__open_to_now_ret_atr | 1030 | L1_next30m_dir | Q3,Q3 | 0.6 | 140 | 0.533 | 60 | None | up | 200 | 0.879 | 19.4 |
| vwap_dist_atr__x__open_to_now_ret_atr | 1030 | L1_next30m_dir | Q4,Q4 | 0.55 | 140 | 0.6 | 70 | None | up | 210 | 2.139 | 21.0 |
| vwap_dist_atr__x__open_to_now_ret_atr | 1100 | L1_next30m_dir | Q2,Q2 | 0.601 | 148 | 0.539 | 76 | None | up | 224 | 0.387 | 21.7 |
| vwap_dist_atr__x__open_to_now_ret_atr | 1100 | L1_next30m_dir | Q4,Q4 | 0.572 | 152 | 0.642 | 81 | None | up | 233 | 5.873 | 22.7 |
| vwap_dist_atr__x__open_to_now_ret_atr | 1100 | L2_next60m_dir | Q2,Q2 | 0.588 | 148 | 0.553 | 76 | None | up | 224 | 0.387 | 21.7 |
| vwap_dist_atr__x__open_to_now_ret_atr | 1100 | L2_next60m_dir | Q4,Q4 | 0.559 | 152 | 0.617 | 81 | None | up | 233 | 5.873 | 22.7 |
| gap_dir__x__or30_state | 1030 | L2_next60m_dir | 1.0,broke_up | 0.557 | 409 | 0.541 | 196 | None | up | 606 | 3.247 | 58.8 |
| gap_dir__x__or30_state | 1030 | L3_race_1R | 1.0,broke_dn | 0.423 | 189 | 0.451 | 102 | None | down | 553 | 2.689 | 53.6 |
| gap_dir__x__or30_state | 1100 | L3_race_1R | 1.0,broke_dn | 0.44 | 184 | 0.43 | 93 | None | down | 573 | 3.656 | 55.5 |
| gap_dir__x__or30_state | 1100 | L3_race_1R | 1.0,broke_up | 0.446 | 139 | 0.365 | 74 | None | down | 614 | 0.183 | 59.6 |
| gap_dir__x__or30_state | 1300 | L2_next60m_dir | -1.0,both | 0.555 | 256 | 0.573 | 110 | None | up | 374 | 0.95 | 36.2 |
| gap_dir__x__or30_state | 1300 | L2_next60m_dir | 1.0,broke_up | 0.599 | 354 | 0.55 | 149 | None | up | 524 | 11.323 | 50.9 |
| gap_dir__x__last_15m_ret_atr | 1000 | L2_next60m_dir | -1.0,Q4 | 0.557 | 158 | 0.55 | 80 | None | up | 238 | 1.486 | 23.2 |
| gap_dir__x__last_15m_ret_atr | 1000 | L2_next60m_dir | 1.0,Q5 | 0.579 | 178 | 0.571 | 98 | None | up | 276 | 2.699 | 26.7 |
| gap_dir__x__last_15m_ret_atr | 1030 | L1_next30m_dir | -1.0,Q2 | 0.571 | 168 | 0.539 | 76 | None | up | 244 | 0.994 | 23.7 |
| gap_dir__x__last_15m_ret_atr | 1030 | L1_next30m_dir | -1.0,Q3 | 0.559 | 136 | 0.531 | 64 | None | up | 200 | 1.018 | 19.4 |
| gap_dir__x__last_15m_ret_atr | 1030 | L2_next60m_dir | 1.0,Q4 | 0.589 | 207 | 0.531 | 96 | None | up | 304 | 1.57 | 29.6 |
| gap_dir__x__last_15m_ret_atr | 1100 | L1_next30m_dir | -1.0,Q2 | 0.594 | 160 | 0.571 | 70 | None | up | 231 | 0.967 | 22.5 |
| gap_dir__x__last_15m_ret_atr | 1100 | L1_next30m_dir | -1.0,Q5 | 0.621 | 182 | 0.547 | 75 | None | up | 259 | 1.698 | 25.2 |
| gap_dir__x__last_15m_ret_atr | 1100 | L1_next30m_dir | 1.0,Q3 | 0.559 | 211 | 0.552 | 116 | None | up | 327 | 1.418 | 31.7 |
| gap_dir__x__last_15m_ret_atr | 1100 | L2_next60m_dir | 1.0,Q3 | 0.597 | 211 | 0.534 | 116 | None | up | 327 | 1.418 | 31.7 |
| gap_dir__x__last_15m_ret_atr | 1100 | L2_next60m_dir | 1.0,Q5 | 0.555 | 173 | 0.595 | 79 | None | up | 253 | 1.075 | 24.6 |
| gap_dir__x__last_15m_ret_atr | 1300 | L1_next30m_dir | -1.0,Q1 | 0.574 | 183 | 0.535 | 99 | None | up | 290 | 0.765 | 28.2 |
| gap_dir__x__last_15m_ret_atr | 1300 | L2_next60m_dir | 1.0,Q4 | 0.574 | 209 | 0.588 | 119 | None | up | 335 | 1.333 | 32.6 |
| open_to_now_ret_atr__x__or30_state | 1000 | L1_next30m_dir | Q2,neither | 0.564 | 358 | 0.552 | 145 | None | up | 503 | 0.526 | 48.9 |
| open_to_now_ret_atr__x__or30_state | 1000 | L1_next30m_dir | Q5,neither | 0.55 | 358 | 0.563 | 167 | None | up | 525 | 5.094 | 50.9 |
| open_to_now_ret_atr__x__or30_state | 1000 | L2_next60m_dir | Q5,neither | 0.573 | 358 | 0.563 | 167 | None | up | 525 | 5.094 | 50.9 |
| open_to_now_ret_atr__x__or30_state | 1030 | L2_next60m_dir | Q5,broke_up | 0.559 | 331 | 0.558 | 181 | None | up | 512 | 11.227 | 49.7 |
| open_to_now_ret_atr__x__or30_state | 1100 | L2_next60m_dir | Q2,broke_dn | 0.577 | 227 | 0.615 | 109 | None | up | 337 | 0.36 | 32.7 |
| open_to_now_ret_atr__x__or30_state | 1300 | L2_next60m_dir | Q5,broke_up | 0.562 | 299 | 0.544 | 147 | None | up | 452 | 58.745 | 43.9 |
| last_30m_ret_atr__x__vwap_slope_6bar | 1100 | L1_next30m_dir | Q5,Q5 | 0.57 | 128 | 0.567 | 104 | None | up | 232 | 5.183 | 22.5 |
| last_30m_ret_atr__x__vwap_slope_6bar | 1100 | L2_next60m_dir | Q5,Q5 | 0.555 | 128 | 0.548 | 104 | None | up | 232 | 5.183 | 22.5 |

## False-positive expectation (multiple-comparisons honesty)

Sum of per-cell binomial-null probabilities (normal approximation, p=0.5, independent IS/OOS draws) of clearing (|IS-50%|>=5pp AND same-sign OOS>=3pp) using each cell's ACTUAL is_n/oos_n -- ignores the pooled-n>=200 and monotone-across-bins gates (upper bound), identical method to `H_statistical_baseline_search.py`:

- single-feature cells: expected false positives ~ 11.82 (out of 369 cells)
- pair cells: expected false positives ~ 391.49 (out of 2193 cells)
- **this scan's total expected false positives (upper bound): ~403.31 out of 2562 cells tested**
- **this scan's actual nominees found: 69**

**PRIOR** (NQ H-scan, `H_statistical_baseline_search.md`): 21 nominees vs an upper-bound null expectation of ~794.4 out of 6055 cells tested -- DECISIVE NULL, the standing reference for what a preregistered scan at this repo's typical multiple-comparisons scale produces absent a real edge.

## Verdict

**NOISE-GRADE / DECISIVE NULL** -- observed nominee count (69) is at or below the binomial-null upper-bound expectation (~403.3) at this cell count, consistent with the NQ H-scan prior (21 vs ~794.4). No robust interpretable statistical edge found in this lane.

## Runtime

11.6s wall clock.
