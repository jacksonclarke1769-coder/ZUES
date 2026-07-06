# ES Edge Expansion — Lane C — M10: Range-Day Mean Reversion (M7-gated)

RESEARCH ONLY. LIVE HOLD ACTIVE. CFD-proxy caveat applies to every number. Valid-day mask: 2639/2678 days used. **M7-verdict gating applied: VWAP-band-touch trigger DROPPED (structurally a vwap-fade, the family M7 killed); OR-boundary-touch and failed-breakout-reclaim kept (range-boundary reversals, not vwap-fades).** Full methodology in `lane_c_m10.py` module docstring. Prior (task brief): NQ high-WR MR = negative-skew trap across 10 instruments; the honest question here is whether CONFIRMED-range-day conditioning changes that on ES.

## Range-day classifier incidence (valid days)

| classifier | n_days | total_valid_days | pct |
|---|---|---|---|
| flat_vwap_slope_or30 | 328 | 2639 | 12.43 |
| vwap_crosses_ge3_by_1100 | 1517 | 2639 | 57.48 |
| inside_prior_day_range_at_1100 | 647 | 2639 | 24.52 |

## Branch event counts (n=27906 raw trigger events pre-classifier-cut)

| classifier | trigger | n | tr_wk | sub_floor |
|---|---|---|---|---|
| flat_vwap_slope_or30 | or_boundary_touch | 3180 | 5.867 | False |
| flat_vwap_slope_or30 | failed_breakout_reclaim | 900 | 1.661 | False |
| vwap_crosses_ge3_by_1100 | or_boundary_touch | 13591 | 25.076 | False |
| vwap_crosses_ge3_by_1100 | failed_breakout_reclaim | 4058 | 7.487 | False |
| inside_prior_day_range_at_1100 | or_boundary_touch | 5833 | 10.762 | False |
| inside_prior_day_range_at_1100 | failed_breakout_reclaim | 1762 | 3.251 | False |

## Cell grid: 48 cells run

dead=48, freeze=0, mirage=0, insufficient_n=0, **live_candidate=0**

## Live candidates (0)

None.


## Top 20 cells by PF (regardless of flag, for visibility)

| classifier | trigger | stop_type | exit_type | n | tr_wk | wr | pf | expR | totR | maxDD_R | flag |
|---|---|---|---|---|---|---|---|---|---|---|---|
| vwap_crosses_ge3_by_1100 | or_boundary_touch | 1.0xATR | time_stop_60m | 13437 | 24.792 | 0.3682 | 0.7423 | -0.1946 | -2614.508 | -2649.172 | dead |
| vwap_crosses_ge3_by_1100 | or_boundary_touch | 1.0xATR | 1R | 13437 | 24.792 | 0.5607 | 0.6952 | -0.1734 | -2330.09 | -2365.052 | dead |
| inside_prior_day_range_at_1100 | or_boundary_touch | 1.0xATR | time_stop_60m | 5773 | 10.651 | 0.3556 | 0.6826 | -0.2517 | -1453.139 | -1464.936 | dead |
| vwap_crosses_ge3_by_1100 | failed_breakout_reclaim | 1.0xATR | time_stop_60m | 4013 | 7.404 | 0.3337 | 0.6603 | -0.2815 | -1129.798 | -1134.27 | dead |
| vwap_crosses_ge3_by_1100 | or_boundary_touch | 1.0xATR | range_midpoint | 12508 | 23.077 | 0.5172 | 0.6567 | -0.198 | -2477.102 | -2529.694 | dead |
| vwap_crosses_ge3_by_1100 | or_boundary_touch | beyond_range_extreme | time_stop_60m | 13436 | 24.79 | 0.2501 | 0.6363 | -0.4732 | -6357.684 | -6362.152 | dead |
| inside_prior_day_range_at_1100 | or_boundary_touch | beyond_range_extreme | time_stop_60m | 5773 | 10.651 | 0.251 | 0.6232 | -0.4981 | -2875.321 | -2883.586 | dead |
| inside_prior_day_range_at_1100 | or_boundary_touch | 1.0xATR | 1R | 5773 | 10.651 | 0.5328 | 0.6034 | -0.2436 | -1406.373 | -1422.459 | dead |
| flat_vwap_slope_or30 | or_boundary_touch | 1.0xATR | time_stop_60m | 3149 | 5.81 | 0.3433 | 0.5739 | -0.3544 | -1115.897 | -1123.308 | dead |
| flat_vwap_slope_or30 | or_boundary_touch | 1.0xATR | 1R | 3149 | 5.81 | 0.5475 | 0.5692 | -0.2674 | -842.117 | -851.237 | dead |
| inside_prior_day_range_at_1100 | or_boundary_touch | 1.0xATR | range_midpoint | 5384 | 9.934 | 0.4998 | 0.5619 | -0.271 | -1458.938 | -1476.574 | dead |
| vwap_crosses_ge3_by_1100 | failed_breakout_reclaim | 1.0xATR | range_midpoint | 3883 | 7.164 | 0.4558 | 0.5593 | -0.3054 | -1185.703 | -1195.128 | dead |
| vwap_crosses_ge3_by_1100 | or_boundary_touch | 1.0xATR | vwap | 10092 | 18.62 | 0.4977 | 0.5552 | -0.2285 | -2306.392 | -2341.442 | dead |
| inside_prior_day_range_at_1100 | failed_breakout_reclaim | 1.0xATR | time_stop_60m | 1749 | 3.227 | 0.3053 | 0.5537 | -0.3982 | -696.39 | -697.214 | dead |
| vwap_crosses_ge3_by_1100 | failed_breakout_reclaim | beyond_range_extreme | time_stop_60m | 4013 | 7.404 | 0.1976 | 0.5455 | -0.6718 | -2695.916 | -2706.289 | dead |
| flat_vwap_slope_or30 | failed_breakout_reclaim | beyond_range_extreme | time_stop_60m | 889 | 1.64 | 0.2058 | 0.5368 | -0.6967 | -619.375 | -629.125 | dead |
| vwap_crosses_ge3_by_1100 | or_boundary_touch | beyond_range_extreme | range_midpoint | 12507 | 23.076 | 0.3673 | 0.5333 | -0.5226 | -6535.836 | -6542.284 | dead |
| flat_vwap_slope_or30 | failed_breakout_reclaim | 1.0xATR | time_stop_60m | 889 | 1.64 | 0.3105 | 0.5257 | -0.4482 | -398.431 | -401.886 | dead |
| vwap_crosses_ge3_by_1100 | failed_breakout_reclaim | 1.0xATR | 1R | 4013 | 7.404 | 0.5001 | 0.5224 | -0.3116 | -1250.377 | -1253.63 | dead |
| inside_prior_day_range_at_1100 | failed_breakout_reclaim | beyond_range_extreme | time_stop_60m | 1749 | 3.227 | 0.1921 | 0.505 | -0.7306 | -1277.822 | -1278.563 | dead |

## Full cell table

See `M10_range_day_mean_reversion.csv` for all cells.

## Runtime: 67.8s
