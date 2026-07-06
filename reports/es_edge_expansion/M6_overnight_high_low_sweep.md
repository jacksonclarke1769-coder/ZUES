# ES Edge Expansion — Lane C — M6: Overnight/Premarket High/Low Sweep

RESEARCH ONLY. LIVE HOLD ACTIVE. CFD-proxy caveat applies to every number. Valid-day mask: 2639/2678 days used. Same event/entry/stop/exit machinery as M5 (`lane_c_m5.py`, imported); full methodology + the window-axis modeling choice in `lane_c_m6.py`'s module docstring.

## Branch event counts (n=34415 raw events)

| level | side | event_type | n | tr_wk | sub_floor |
|---|---|---|---|---|---|
| on_hi | upper | break_and_retest | 1947 | 3.592 | False |
| on_hi | upper | first_touch_rejection | 1523 | 2.81 | False |
| on_hi | upper | sweep_and_close_back_inside | 4742 | 8.749 | False |
| on_lo | lower | break_and_retest | 1785 | 3.293 | False |
| on_lo | lower | first_touch_rejection | 1393 | 2.57 | False |
| on_lo | lower | sweep_and_close_back_inside | 4843 | 8.935 | False |
| pm_hi | upper | break_and_retest | 2291 | 4.227 | False |
| pm_hi | upper | first_touch_rejection | 1674 | 3.089 | False |
| pm_hi | upper | sweep_and_close_back_inside | 5151 | 9.504 | False |
| pm_lo | lower | break_and_retest | 2044 | 3.771 | False |
| pm_lo | lower | first_touch_rejection | 1574 | 2.904 | False |
| pm_lo | lower | sweep_and_close_back_inside | 5448 | 10.052 | False |

## Cell grid: 1152 cells run

dead=786, sub_floor=366, freeze=0, mirage=0, insufficient_n=0, **live_candidate=0**

## Live candidates (0)

None.


## Top 20 cells by PF (regardless of flag, for visibility)

| level | side | event_type | window | entry_type | stop_type | exit_type | filter | n | tr_wk | wr | pf | expR | totR | maxDD_R | n_no_retest_skip | flag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on_lo | lower | first_touch_rejection | 0930_1030 | retest_limit | 1.0xATR | prior_day_mid | vwap_slope_agreement | 32 | 0.059 | 0.5625 | 1.9603 | 0.3921 | 12.548 | -2.827 | 7 | sub_floor |
| on_lo | lower | first_touch_rejection | 0930_1030 | retest_limit | 1.0xATR | vwap | vwap_slope_agreement | 10 | 0.018 | 0.6 | 1.2895 | 0.1582 | 1.582 | -1.749 | 7 | sub_floor |
| pm_lo | lower | sweep_and_close_back_inside | 0930_1030 | retest_limit | 1.0xATR | vwap | vwap_slope_agreement | 71 | 0.131 | 0.6197 | 1.2083 | 0.0482 | 3.421 | -2.799 | 27 | sub_floor |
| pm_hi | upper | first_touch_rejection | 0930_1030 | next_bar_open | 1.0xATR | 2R | vwap_slope_agreement | 41 | 0.076 | 0.4634 | 1.1907 | 0.127 | 5.209 | -6.093 | 0 | sub_floor |
| on_lo | lower | first_touch_rejection | 0930_1030 | next_bar_open | 1.0xATR | vwap | vwap_slope_agreement | 10 | 0.018 | 0.7 | 1.1664 | 0.0708 | 0.708 | -2.17 | 0 | sub_floor |
| pm_lo | lower | sweep_and_close_back_inside | 0930_1030 | retest_limit | beyond_extreme_2tk | vwap | vwap_slope_agreement | 71 | 0.131 | 0.4507 | 1.1606 | 0.1026 | 7.285 | -24.379 | 27 | sub_floor |
| pm_lo | lower | first_touch_rejection | 0930_1030 | retest_limit | 1.0xATR | vwap | vwap_slope_agreement | 16 | 0.03 | 0.5625 | 1.1182 | 0.0619 | 0.99 | -3.03 | 4 | sub_floor |
| on_hi | upper | break_and_retest | 0930_1030 | next_bar_open | beyond_extreme_2tk | prior_day_mid | vwap_slope_agreement | 30 | 0.055 | 0.3 | 1.0755 | 0.0716 | 2.148 | -8.16 | 0 | sub_floor |
| on_hi | upper | break_and_retest | 0930_1030 | next_bar_open | 1.0xATR | prior_day_mid | vwap_slope_agreement | 30 | 0.055 | 0.4333 | 1.0604 | 0.0381 | 1.144 | -8.634 | 0 | sub_floor |
| pm_hi | upper | sweep_and_close_back_inside | 1000_1130 | retest_limit | 1.0xATR | prior_day_mid | vwap_slope_agreement | 217 | 0.4 | 0.3456 | 1.0381 | 0.0308 | 6.677 | -44.548 | 61 | dead |
| pm_hi | upper | sweep_and_close_back_inside | 1000_1130 | retest_limit | beyond_extreme_2tk | prior_day_mid | vwap_slope_agreement | 217 | 0.4 | 0.2074 | 1.0333 | 0.0391 | 8.495 | -53.407 | 61 | dead |
| on_hi | upper | break_and_retest | 0930_1030 | retest_limit | 1.0xATR | prior_day_mid | vwap_slope_agreement | 29 | 0.054 | 0.3793 | 1.0038 | 0.0025 | 0.073 | -7.422 | 19 | sub_floor |
| on_hi | upper | first_touch_rejection | 0930_1030 | retest_limit | 1.0xATR | vwap | vwap_slope_agreement | 9 | 0.017 | 0.5556 | 1.0035 | 0.0018 | 0.017 | -2.902 | 21 | sub_floor |
| on_hi | upper | first_touch_rejection | 0930_1030 | next_bar_open | 1.0xATR | vwap | vwap_slope_agreement | 9 | 0.017 | 0.6667 | 0.9862 | -0.006 | -0.054 | -1.765 | 0 | sub_floor |
| on_lo | lower | first_touch_rejection | 0930_1030 | retest_limit | 1.0xATR | 2R | vwap_slope_agreement | 60 | 0.111 | 0.4167 | 0.9801 | -0.015 | -0.902 | -15.143 | 7 | sub_floor |
| on_hi | upper | first_touch_rejection | full_rth | retest_limit | 1.0xATR | vwap | vwap_slope_agreement | 11 | 0.02 | 0.5455 | 0.9796 | -0.0113 | -0.124 | -2.902 | 59 | sub_floor |
| on_hi | upper | first_touch_rejection | 1000_1130 | retest_limit | 1.0xATR | vwap | vwap_slope_agreement | 11 | 0.02 | 0.5455 | 0.9796 | -0.0113 | -0.124 | -2.902 | 36 | sub_floor |
| on_hi | upper | sweep_and_close_back_inside | 0930_1030 | retest_limit | beyond_extreme_2tk | 2R | vwap_slope_agreement | 197 | 0.363 | 0.4822 | 0.9748 | -0.0187 | -3.682 | -50.009 | 45 | dead |
| on_lo | lower | sweep_and_close_back_inside | 0930_1030 | retest_limit | 1.0xATR | prior_day_mid | vwap_slope_agreement | 96 | 0.177 | 0.3958 | 0.954 | -0.0301 | -2.886 | -17.238 | 37 | sub_floor |
| on_hi | upper | break_and_retest | 1000_1130 | retest_limit | 1.0xATR | prior_day_mid | vwap_slope_agreement | 91 | 0.168 | 0.4396 | 0.9526 | -0.0293 | -2.667 | -12.383 | 57 | sub_floor |

## Full cell table

See `M6_overnight_high_low_sweep.csv` for all cells.

## Runtime: 214.2s
