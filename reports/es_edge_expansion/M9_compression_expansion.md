# ES Edge Expansion — Lane B — M9: Compression -> Expansion

**CFD proxy, documented optimistic bias vs real futures; graduates need real CME data before certification.** RESEARCH ONLY. LIVE HOLD ACTIVE. No commits.

Valid days: 2639 / 2678 (98.5%) — Wave-1 adjudicated mask (density>=95% OR half-day profile).

## Compression-behaviour stat (reported FIRST, per task brief)

range_ratio = mean(RTH_range / atr14_daily_prior | compression day) / mean(RTH_range / atr14_daily_prior | all valid days). <0.85 = contraction persists (matches NQ's 11/11-year finding).

| compression_def | n_days | pct_of_days | mean_rth_range_atr_compression | mean_rth_range_atr_baseline | range_ratio | contracts_lt_0_85 |
|---|---|---|---|---|---|---|
| overnight_range_pctile<30 | 817 | 30.9587 | 0.8186 | 0.9113 | 0.8983 | False |
| atr14_contraction_pctile<30 | 959 | 36.3395 | 0.9592 | 0.9113 | 1.0525 | False |
| prior_day_range_pctile<30 | 782 | 29.6324 | 0.8134 | 0.9113 | 0.8926 | False |

### Per-year consistency (years with n>=5 compression days)
- **overnight_range_pctile<30**: 3/11 years contract (<0.85); pooled ratio=0.8983 (n=817 days, 1.51 events/wk)
  - per-year ratios: 2016:0.951, 2017:0.893, 2018:0.784, 2019:0.939, 2020:0.917, 2021:0.790, 2022:0.987, 2023:0.979, 2024:0.857, 2025:0.891, 2026:0.832
- **atr14_contraction_pctile<30**: 0/11 years contract (<0.85); pooled ratio=1.0525 (n=959 days, 1.77 events/wk)
  - per-year ratios: 2016:1.080, 2017:1.131, 2018:0.911, 2019:1.046, 2020:1.013, 2021:1.186, 2022:1.038, 2023:1.096, 2024:1.141, 2025:0.978, 2026:0.982
- **prior_day_range_pctile<30**: 3/11 years contract (<0.85); pooled ratio=0.8926 (n=782 days, 1.44 events/wk)
  - per-year ratios: 2016:0.883, 2017:0.889, 2018:0.822, 2019:0.887, 2020:0.803, 2021:0.860, 2022:1.011, 2023:0.997, 2024:0.964, 2025:0.795, 2026:1.050

## VERDICT: MIXED/NO-CONTRACTION — proceeding to strategy grid (task brief: only skip cells if range-ratio<0.85; here at least one def is >=0.85)

## Strategy grid (108 cells: 3 compression-def x 3 breakout x 2 entry x 2 stop x 3 exit)

| compression_def | breakout | entry | stop | exit | n_events | n | tr_per_wk | wr | pf | exp_r | tot_r | maxdd_r | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| overnight_range_pctile<30 | second_break | retest | atr_1.0 | 1.5R | 467 | 381 | 0.704 | 0.478 | 1.120 | 0.020 | 7.535 | -9.212 |  |
| overnight_range_pctile<30 | first_break_continuation | immediate | atr_1.0 | 1.5R | 817 | 817 | 1.509 | 0.496 | 1.093 | 0.016 | 13.393 | -9.445 |  |
| atr14_contraction_pctile<30 | second_break | retest | atr_1.0 | 1.5R | 505 | 406 | 0.750 | 0.478 | 1.061 | 0.011 | 4.594 | -8.387 |  |
| overnight_range_pctile<30 | second_break | immediate | atr_1.0 | 1.5R | 467 | 466 | 0.860 | 0.483 | 1.052 | 0.009 | 4.180 | -9.747 |  |
| overnight_range_pctile<30 | break_retest | retest | atr_1.0 | 1.5R | 656 | 656 | 1.211 | 0.482 | 1.044 | 0.008 | 5.124 | -7.338 | WATCHLIST_ONE_REGIME |
| overnight_range_pctile<30 | first_break_continuation | retest | atr_1.0 | 1.5R | 817 | 656 | 1.211 | 0.482 | 1.044 | 0.008 | 5.124 | -7.338 | WATCHLIST_ONE_REGIME |
| atr14_contraction_pctile<30 | first_break_continuation | immediate | atr_1.0 | 1.5R | 958 | 958 | 1.769 | 0.472 | 0.977 | -0.005 | -4.978 | -28.180 |  |
| overnight_range_pctile<30 | first_break_continuation | immediate | atr_1.0 | trail_3.5xATR | 817 | 817 | 1.509 | 0.411 | 0.964 | -0.005 | -4.056 | -12.776 |  |
| prior_day_range_pctile<30 | second_break | retest | atr_1.0 | 1.5R | 418 | 337 | 0.622 | 0.519 | 0.955 | -0.007 | -2.507 | -9.647 |  |
| atr14_contraction_pctile<30 | break_retest | retest | atr_1.0 | 1.5R | 751 | 751 | 1.387 | 0.467 | 0.951 | -0.010 | -7.879 | -24.692 |  |
| atr14_contraction_pctile<30 | first_break_continuation | retest | atr_1.0 | 1.5R | 958 | 751 | 1.387 | 0.467 | 0.951 | -0.010 | -7.879 | -24.692 |  |
| atr14_contraction_pctile<30 | second_break | immediate | atr_1.0 | 1.5R | 505 | 503 | 0.929 | 0.475 | 0.948 | -0.010 | -5.143 | -14.978 |  |
| overnight_range_pctile<30 | first_break_continuation | immediate | opposite_compression_side | trail_3.5xATR | 817 | 817 | 1.509 | 0.389 | 0.946 | -0.027 | -22.363 | -51.452 |  |
| atr14_contraction_pctile<30 | first_break_continuation | immediate | opposite_compression_side | trail_3.5xATR | 958 | 958 | 1.769 | 0.379 | 0.943 | -0.028 | -27.274 | -74.852 |  |
| atr14_contraction_pctile<30 | first_break_continuation | immediate | atr_1.0 | trail_3.5xATR | 958 | 958 | 1.769 | 0.409 | 0.937 | -0.010 | -9.885 | -23.106 |  |
| prior_day_range_pctile<30 | first_break_continuation | immediate | atr_1.0 | trail_3.5xATR | 780 | 780 | 1.440 | 0.423 | 0.920 | -0.011 | -8.470 | -21.311 |  |
| prior_day_range_pctile<30 | first_break_continuation | immediate | opposite_compression_side | trail_3.5xATR | 780 | 780 | 1.440 | 0.397 | 0.913 | -0.043 | -33.382 | -86.315 |  |
| prior_day_range_pctile<30 | first_break_continuation | immediate | atr_1.0 | 1.5R | 780 | 780 | 1.440 | 0.494 | 0.911 | -0.017 | -13.307 | -26.066 |  |
| prior_day_range_pctile<30 | second_break | immediate | atr_1.0 | 1.5R | 418 | 417 | 0.770 | 0.506 | 0.901 | -0.017 | -7.073 | -14.614 |  |
| prior_day_range_pctile<30 | first_break_continuation | immediate | opposite_compression_side | 1.5R | 780 | 780 | 1.440 | 0.449 | 0.893 | -0.060 | -47.070 | -97.972 |  |
| atr14_contraction_pctile<30 | second_break | immediate | opposite_compression_side | trail_3.5xATR | 505 | 503 | 0.929 | 0.366 | 0.884 | -0.056 | -28.227 | -50.959 |  |
| prior_day_range_pctile<30 | break_retest | retest | opposite_compression_side | trail_3.5xATR | 609 | 609 | 1.125 | 0.369 | 0.884 | -0.067 | -40.906 | -96.011 |  |
| prior_day_range_pctile<30 | first_break_continuation | retest | opposite_compression_side | trail_3.5xATR | 780 | 609 | 1.125 | 0.369 | 0.884 | -0.067 | -40.906 | -96.011 |  |
| prior_day_range_pctile<30 | second_break | retest | atr_1.0 | trail_3.5xATR | 418 | 337 | 0.622 | 0.427 | 0.883 | -0.014 | -4.557 | -7.917 |  |
| overnight_range_pctile<30 | break_retest | retest | opposite_compression_side | trail_3.5xATR | 656 | 656 | 1.211 | 0.349 | 0.881 | -0.069 | -45.491 | -61.963 |  |
| overnight_range_pctile<30 | first_break_continuation | retest | opposite_compression_side | trail_3.5xATR | 817 | 656 | 1.211 | 0.349 | 0.881 | -0.069 | -45.491 | -61.963 |  |
| atr14_contraction_pctile<30 | break_retest | retest | opposite_compression_side | trail_3.5xATR | 751 | 751 | 1.387 | 0.352 | 0.880 | -0.071 | -52.982 | -85.172 |  |
| atr14_contraction_pctile<30 | first_break_continuation | retest | opposite_compression_side | trail_3.5xATR | 958 | 751 | 1.387 | 0.352 | 0.880 | -0.071 | -52.982 | -85.172 |  |
| overnight_range_pctile<30 | break_retest | retest | atr_1.0 | trail_3.5xATR | 656 | 656 | 1.211 | 0.389 | 0.879 | -0.016 | -10.753 | -11.435 |  |
| overnight_range_pctile<30 | first_break_continuation | retest | atr_1.0 | trail_3.5xATR | 817 | 656 | 1.211 | 0.389 | 0.879 | -0.016 | -10.753 | -11.435 |  |
| prior_day_range_pctile<30 | second_break | retest | opposite_compression_side | trail_3.5xATR | 418 | 337 | 0.622 | 0.386 | 0.872 | -0.067 | -22.630 | -36.622 |  |
| prior_day_range_pctile<30 | first_break_continuation | retest | atr_1.0 | trail_3.5xATR | 780 | 609 | 1.125 | 0.415 | 0.871 | -0.017 | -10.480 | -19.757 |  |
| prior_day_range_pctile<30 | break_retest | retest | atr_1.0 | trail_3.5xATR | 609 | 609 | 1.125 | 0.415 | 0.871 | -0.017 | -10.480 | -19.757 |  |
| atr14_contraction_pctile<30 | second_break | retest | opposite_compression_side | trail_3.5xATR | 505 | 406 | 0.750 | 0.340 | 0.868 | -0.072 | -29.155 | -39.637 |  |
| prior_day_range_pctile<30 | second_break | immediate | opposite_compression_side | trail_3.5xATR | 418 | 417 | 0.770 | 0.384 | 0.862 | -0.067 | -27.752 | -46.499 |  |
| overnight_range_pctile<30 | second_break | immediate | atr_1.0 | trail_3.5xATR | 467 | 466 | 0.860 | 0.384 | 0.859 | -0.019 | -8.693 | -10.464 |  |
| atr14_contraction_pctile<30 | first_break_continuation | retest | atr_1.0 | trail_3.5xATR | 958 | 751 | 1.387 | 0.405 | 0.858 | -0.023 | -17.256 | -22.798 |  |
| atr14_contraction_pctile<30 | break_retest | retest | atr_1.0 | trail_3.5xATR | 751 | 751 | 1.387 | 0.405 | 0.858 | -0.023 | -17.256 | -22.798 |  |
| prior_day_range_pctile<30 | break_retest | retest | atr_1.0 | 1.5R | 609 | 609 | 1.125 | 0.499 | 0.856 | -0.028 | -16.788 | -25.941 |  |
| prior_day_range_pctile<30 | first_break_continuation | retest | atr_1.0 | 1.5R | 780 | 609 | 1.125 | 0.499 | 0.856 | -0.028 | -16.788 | -25.941 |  |

## Best cells (n>=30)

| compression_def | breakout | entry | stop | exit | n_events | n | tr_per_wk | wr | pf | exp_r | tot_r | maxdd_r | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| overnight_range_pctile<30 | second_break | retest | atr_1.0 | 1.5R | 467 | 381 | 0.704 | 0.478 | 1.120 | 0.020 | 7.535 | -9.212 |  |
| overnight_range_pctile<30 | first_break_continuation | immediate | atr_1.0 | 1.5R | 817 | 817 | 1.509 | 0.496 | 1.093 | 0.016 | 13.393 | -9.445 |  |
| atr14_contraction_pctile<30 | second_break | retest | atr_1.0 | 1.5R | 505 | 406 | 0.750 | 0.478 | 1.061 | 0.011 | 4.594 | -8.387 |  |
| overnight_range_pctile<30 | second_break | immediate | atr_1.0 | 1.5R | 467 | 466 | 0.860 | 0.483 | 1.052 | 0.009 | 4.180 | -9.747 |  |
| overnight_range_pctile<30 | first_break_continuation | retest | atr_1.0 | 1.5R | 817 | 656 | 1.211 | 0.482 | 1.044 | 0.008 | 5.124 | -7.338 | WATCHLIST_ONE_REGIME |
| overnight_range_pctile<30 | break_retest | retest | atr_1.0 | 1.5R | 656 | 656 | 1.211 | 0.482 | 1.044 | 0.008 | 5.124 | -7.338 | WATCHLIST_ONE_REGIME |
| atr14_contraction_pctile<30 | first_break_continuation | immediate | atr_1.0 | 1.5R | 958 | 958 | 1.769 | 0.472 | 0.977 | -0.005 | -4.978 | -28.180 |  |
| overnight_range_pctile<30 | first_break_continuation | immediate | atr_1.0 | trail_3.5xATR | 817 | 817 | 1.509 | 0.411 | 0.964 | -0.005 | -4.056 | -12.776 |  |
| prior_day_range_pctile<30 | second_break | retest | atr_1.0 | 1.5R | 418 | 337 | 0.622 | 0.519 | 0.955 | -0.007 | -2.507 | -9.647 |  |
| atr14_contraction_pctile<30 | first_break_continuation | retest | atr_1.0 | 1.5R | 958 | 751 | 1.387 | 0.467 | 0.951 | -0.010 | -7.879 | -24.692 |  |

## Kill / freeze outcomes

- Family best PF: 1.120
- Family kill rule (PF<1.15): **KILLED**
- No cells exceeded the PF>1.8 freeze-flag threshold.

## Slip probes on the single best cell (overnight_range_pctile<30/second_break/retest/atr_1.0/1.5R)

- +0.015R adverse slip: PF=1.028, expR=0.005, totR=1.8
- +0.03R adverse slip: PF=0.943, expR=-0.010, totR=-3.9

## Runtime
- M9 total: 221.6s
