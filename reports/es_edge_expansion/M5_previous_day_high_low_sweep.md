# ES Edge Expansion — Lane C — M5: Previous-Day-High/Low (+ Prior Close) Sweep

RESEARCH ONLY. LIVE HOLD ACTIVE. CFD-proxy caveat applies to every number. Valid-day mask: 2639/2678 days used. Full methodology in `lane_c_m5.py` module docstring. Priors (task brief): NQ B3 sweep family = 112/112 dead (best PF 1.001); NQ turtle-soup 0.84-0.91 — ES fresh territory, expectations low; no ES incumbent to collide with (overlap discipline N/A).

## Branch event counts (n=27581 raw events)

Frequency-floor gate (0.3 tr/wk) applied BEFORE the fine grid — sub-floor branches are listed here but not expanded into entry x stop x exit x filter cells.

| level | side | event_type | n | tr_wk | sub_floor |
|---|---|---|---|---|---|
| pdh | upper | break_and_retest | 1387 | 2.559 | False |
| pdh | upper | first_touch_rejection | 1066 | 1.967 | False |
| pdh | upper | sweep_and_close_back_inside | 3265 | 6.024 | False |
| pdl | lower | break_and_retest | 1070 | 1.974 | False |
| pdl | lower | first_touch_rejection | 929 | 1.714 | False |
| pdl | lower | sweep_and_close_back_inside | 3277 | 6.046 | False |
| prior_close | lower | break_and_retest | 1845 | 3.404 | False |
| prior_close | lower | first_touch_rejection | 1438 | 2.653 | False |
| prior_close | lower | sweep_and_close_back_inside | 5137 | 9.478 | False |
| prior_close | upper | break_and_retest | 1886 | 3.48 | False |
| prior_close | upper | first_touch_rejection | 1390 | 2.565 | False |
| prior_close | upper | sweep_and_close_back_inside | 4891 | 9.024 | False |

## Cell grid: 576 cells run

dead=490, sub_floor=58, freeze=0, mirage=0, insufficient_n=28, **live_candidate=0**

## Live candidates (0)

None.


## Top 20 cells by PF (regardless of flag, for visibility)

| level | side | event_type | entry_type | stop_type | exit_type | filter | n | tr_wk | wr | pf | expR | totR | maxDD_R | n_no_retest_skip | flag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| prior_close | upper | first_touch_rejection | next_bar_open | 1.0xATR | vwap | vwap_slope_agreement | 3 | 0.006 | 1.0 | inf | 0.4144 | 1.243 | 0.0 | 0 | insufficient_n |
| pdh | upper | first_touch_rejection | next_bar_open | 1.0xATR | vwap | vwap_slope_agreement | 6 | 0.011 | 1.0 | inf | 0.5875 | 3.525 | 0.0 | 0 | insufficient_n |
| prior_close | upper | first_touch_rejection | retest_limit | 1.0xATR | vwap | vwap_slope_agreement | 3 | 0.006 | 1.0 | inf | 0.6508 | 1.952 | 0.0 | 80 | insufficient_n |
| pdh | upper | first_touch_rejection | retest_limit | 1.0xATR | vwap | vwap_slope_agreement | 5 | 0.009 | 1.0 | inf | 0.8293 | 4.146 | 0.0 | 39 | insufficient_n |
| pdh | upper | first_touch_rejection | retest_limit | beyond_extreme_2tk | vwap | vwap_slope_agreement | 5 | 0.009 | 0.8 | 5.6942 | 1.9323 | 9.662 | 0.0 | 39 | sub_floor |
| pdh | upper | first_touch_rejection | next_bar_open | beyond_extreme_2tk | vwap | vwap_slope_agreement | 6 | 0.011 | 0.8333 | 3.9607 | 0.8848 | 5.309 | 0.0 | 0 | sub_floor |
| prior_close | upper | first_touch_rejection | retest_limit | beyond_extreme_2tk | vwap | vwap_slope_agreement | 3 | 0.006 | 0.6667 | 2.2403 | 0.5347 | 1.604 | -1.293 | 80 | sub_floor |
| prior_close | upper | first_touch_rejection | next_bar_open | beyond_extreme_2tk | vwap | vwap_slope_agreement | 3 | 0.006 | 0.6667 | 1.0165 | 0.0068 | 0.02 | -1.241 | 0 | sub_floor |
| pdl | lower | sweep_and_close_back_inside | retest_limit | 1.0xATR | 1.5R | ny_am_only | 1089 | 2.009 | 0.4444 | 0.8943 | -0.0688 | -74.893 | -74.899 | 224 | dead |
| pdl | lower | sweep_and_close_back_inside | retest_limit | beyond_extreme_2tk | 2R | ny_am_only | 1089 | 2.009 | 0.438 | 0.8832 | -0.0901 | -98.066 | -141.234 | 224 | dead |
| pdh | upper | first_touch_rejection | retest_limit | 1.0xATR | 2R | vwap_slope_agreement | 185 | 0.341 | 0.4162 | 0.8777 | -0.0937 | -17.34 | -37.072 | 39 | dead |
| prior_close | upper | sweep_and_close_back_inside | retest_limit | beyond_extreme_2tk | 1.5R | ny_am_only | 1975 | 3.644 | 0.5423 | 0.8748 | -0.0802 | -158.391 | -277.298 | 306 | dead |
| prior_close | upper | sweep_and_close_back_inside | retest_limit | beyond_extreme_2tk | 2R | ny_am_only | 1975 | 3.644 | 0.4471 | 0.8736 | -0.0977 | -192.989 | -296.999 | 306 | dead |
| pdl | lower | sweep_and_close_back_inside | retest_limit | 1.0xATR | prior_day_mid | ny_am_only | 1089 | 2.009 | 0.3269 | 0.8725 | -0.0993 | -108.116 | -140.881 | 224 | dead |
| pdl | lower | sweep_and_close_back_inside | retest_limit | beyond_extreme_2tk | 1.5R | ny_am_only | 1089 | 2.009 | 0.5225 | 0.8571 | -0.0934 | -101.669 | -131.452 | 224 | dead |
| pdl | lower | sweep_and_close_back_inside | retest_limit | beyond_extreme_2tk | 2R | none | 2684 | 4.952 | 0.44 | 0.8442 | -0.1205 | -323.415 | -326.64 | 593 | dead |
| pdl | lower | sweep_and_close_back_inside | retest_limit | 1.0xATR | 2R | ny_am_only | 1089 | 2.009 | 0.3554 | 0.8381 | -0.1212 | -131.971 | -130.714 | 224 | dead |
| prior_close | lower | first_touch_rejection | retest_limit | 1.0xATR | vwap | vwap_slope_agreement | 13 | 0.024 | 0.4615 | 0.8355 | -0.099 | -1.287 | -4.409 | 81 | sub_floor |
| pdl | lower | sweep_and_close_back_inside | retest_limit | beyond_extreme_2tk | 1.5R | none | 2684 | 4.952 | 0.5261 | 0.8253 | -0.1135 | -304.598 | -310.907 | 593 | dead |
| pdh | upper | first_touch_rejection | retest_limit | beyond_extreme_2tk | 2R | vwap_slope_agreement | 185 | 0.341 | 0.427 | 0.8248 | -0.1346 | -24.897 | -30.528 | 39 | dead |

## Full cell table

See `M5_previous_day_high_low_sweep.csv` for all cells.

## Runtime: 135.1s
