# ES Edge Expansion — Lane B — M3: Failed Opening-Drive Reversal

**CFD proxy, documented optimistic bias vs real futures; graduates need real CME data before certification.** RESEARCH ONLY. LIVE HOLD ACTIVE. No commits.

Valid days: 2639 / 2678 (98.5%). Weeks span: 541.6.

## Frequency floor gate (FIRST, per task brief — floor = 0.3/wk, PRIOR: NQ Idea-7 was ~0.06/wk and died on frequency)

| failure_def | timing | n_events | events_per_week | passes_freq_floor |
|---|---|---|---|---|
| OR30_break_reclaim | le10bars | 7357 | 13.5845 | True |
| OR30_break_reclaim | before_1030 | 1072 | 1.9794 | True |
| ONH_ONL_break_reclaim | le10bars | 6528 | 12.0538 | True |
| ONH_ONL_break_reclaim | before_1030 | 1618 | 2.9876 | True |
| PMH_PML_break_reclaim | le10bars | 6976 | 12.8810 | True |
| PMH_PML_break_reclaim | before_1030 | 1735 | 3.2036 | True |

**6 definition(s) pass the floor and were backtested: OR30_break_reclaim/le10bars, OR30_break_reclaim/before_1030, ONH_ONL_break_reclaim/le10bars, ONH_ONL_break_reclaim/before_1030, PMH_PML_break_reclaim/le10bars, PMH_PML_break_reclaim/before_1030.**

## Backtest grid on passing definitions (entry x stop x exit x filter = 24 cells per passing definition)

| failure_def | timing | entry | stop | exit | filt | n_events_raw | n_no_fill | n | tr_per_wk | wr | pf | exp_r | tot_r | maxdd_r | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OR30_break_reclaim | before_1030 | failed_level_retest | beyond_extreme_2tick | vwap_target | flat_vwap_slope_only | 1063 | 171 | 158 | 0.292 | 0.380 | 0.973 | -0.041 | -6.485 | -92.570 |  |
| PMH_PML_break_reclaim | le10bars | failed_level_retest | atr_1.0 | 1.5R | none | 6946 | 1305 | 1948 | 3.597 | 0.466 | 0.936 | -0.012 | -23.832 | -31.895 |  |
| ONH_ONL_break_reclaim | le10bars | next_bar_open_after_reclaim | atr_1.0 | 1.5R | none | 6495 | 106 | 1874 | 3.460 | 0.475 | 0.919 | -0.016 | -30.330 | -38.026 |  |
| ONH_ONL_break_reclaim | le10bars | failed_level_retest | atr_1.0 | 1.5R | none | 6495 | 1311 | 1736 | 3.205 | 0.479 | 0.913 | -0.017 | -28.956 | -34.916 |  |
| ONH_ONL_break_reclaim | before_1030 | next_bar_open_after_reclaim | atr_1.0 | 1.5R | none | 1606 | 0 | 1137 | 2.099 | 0.478 | 0.900 | -0.022 | -24.889 | -30.390 |  |
| PMH_PML_break_reclaim | le10bars | next_bar_open_after_reclaim | atr_1.0 | 1.5R | flat_vwap_slope_only | 6946 | 104 | 1404 | 2.592 | 0.444 | 0.895 | -0.017 | -23.989 | -31.574 |  |
| ONH_ONL_break_reclaim | before_1030 | failed_level_retest | atr_1.0 | 1.5R | none | 1606 | 317 | 948 | 1.750 | 0.488 | 0.890 | -0.024 | -22.351 | -27.053 |  |
| PMH_PML_break_reclaim | before_1030 | failed_level_retest | atr_1.0 | 1.5R | none | 1727 | 291 | 1049 | 1.937 | 0.459 | 0.888 | -0.025 | -26.726 | -32.556 |  |
| PMH_PML_break_reclaim | le10bars | next_bar_open_after_reclaim | atr_1.0 | 1.5R | none | 6946 | 104 | 2082 | 3.844 | 0.454 | 0.878 | -0.025 | -51.162 | -57.170 |  |
| PMH_PML_break_reclaim | before_1030 | next_bar_open_after_reclaim | atr_1.0 | 1.5R | flat_vwap_slope_only | 1727 | 0 | 253 | 0.467 | 0.411 | 0.874 | -0.026 | -6.466 | -12.068 |  |
| ONH_ONL_break_reclaim | le10bars | next_bar_open_after_reclaim | atr_1.0 | 1.5R | flat_vwap_slope_only | 6495 | 106 | 1152 | 2.127 | 0.477 | 0.874 | -0.019 | -22.418 | -27.438 |  |
| PMH_PML_break_reclaim | before_1030 | next_bar_open_after_reclaim | atr_1.0 | 1.5R | none | 1727 | 0 | 1244 | 2.297 | 0.450 | 0.850 | -0.034 | -42.623 | -46.477 |  |
| OR30_break_reclaim | le10bars | next_bar_open_after_reclaim | atr_1.0 | 1.5R | flat_vwap_slope_only | 7304 | 123 | 1559 | 2.879 | 0.464 | 0.839 | -0.025 | -38.841 | -42.552 |  |
| PMH_PML_break_reclaim | before_1030 | failed_level_retest | atr_1.0 | 1.5R | flat_vwap_slope_only | 1727 | 291 | 267 | 0.493 | 0.431 | 0.838 | -0.033 | -8.867 | -12.378 |  |
| PMH_PML_break_reclaim | le10bars | failed_level_retest | atr_1.0 | 1.5R | flat_vwap_slope_only | 6946 | 1305 | 1263 | 2.332 | 0.450 | 0.830 | -0.028 | -34.956 | -39.285 |  |
| OR30_break_reclaim | le10bars | failed_level_retest | atr_1.0 | 1.5R | none | 7304 | 1386 | 2016 | 3.723 | 0.460 | 0.829 | -0.033 | -65.657 | -68.035 |  |
| ONH_ONL_break_reclaim | le10bars | failed_level_retest | atr_1.0 | 1.5R | flat_vwap_slope_only | 6495 | 1311 | 1037 | 1.915 | 0.464 | 0.807 | -0.030 | -31.331 | -33.920 |  |
| OR30_break_reclaim | le10bars | next_bar_open_after_reclaim | atr_1.0 | 1.5R | none | 7304 | 123 | 2147 | 3.964 | 0.454 | 0.795 | -0.041 | -87.999 | -91.068 |  |
| OR30_break_reclaim | le10bars | failed_level_retest | atr_1.0 | 1.5R | flat_vwap_slope_only | 7304 | 1386 | 1442 | 2.663 | 0.463 | 0.795 | -0.031 | -44.862 | -47.180 |  |
| ONH_ONL_break_reclaim | before_1030 | next_bar_open_after_reclaim | atr_1.0 | 1.5R | flat_vwap_slope_only | 1606 | 0 | 234 | 0.432 | 0.470 | 0.793 | -0.040 | -9.267 | -11.193 |  |
| OR30_break_reclaim | le10bars | failed_level_retest | atr_1.0 | or_midpoint | flat_vwap_slope_only | 7304 | 1386 | 2007 | 3.706 | 0.654 | 0.732 | -0.025 | -51.174 | -52.434 |  |
| OR30_break_reclaim | le10bars | failed_level_retest | atr_1.0 | or_midpoint | none | 7304 | 1386 | 3294 | 6.082 | 0.673 | 0.725 | -0.031 | -101.729 | -104.170 |  |
| OR30_break_reclaim | before_1030 | failed_level_retest | atr_1.0 | 1.5R | none | 1063 | 171 | 789 | 1.457 | 0.440 | 0.725 | -0.065 | -51.123 | -57.873 |  |
| ONH_ONL_break_reclaim | before_1030 | failed_level_retest | atr_1.0 | 1.5R | flat_vwap_slope_only | 1606 | 317 | 212 | 0.391 | 0.448 | 0.724 | -0.055 | -11.660 | -14.804 |  |
| OR30_break_reclaim | before_1030 | next_bar_open_after_reclaim | atr_1.0 | 1.5R | none | 1063 | 0 | 938 | 1.732 | 0.450 | 0.711 | -0.068 | -63.680 | -70.214 |  |
| OR30_break_reclaim | before_1030 | failed_level_retest | beyond_extreme_2tick | vwap_target | none | 1063 | 171 | 891 | 1.645 | 0.264 | 0.692 | -0.658 | -585.981 | -689.481 |  |
| OR30_break_reclaim | before_1030 | failed_level_retest | atr_1.0 | vwap_target | flat_vwap_slope_only | 1063 | 171 | 155 | 0.286 | 0.723 | 0.665 | -0.017 | -2.690 | -3.723 |  |
| OR30_break_reclaim | before_1030 | failed_level_retest | atr_1.0 | or_midpoint | none | 1063 | 171 | 812 | 1.499 | 0.711 | 0.656 | -0.049 | -39.486 | -42.784 |  |
| OR30_break_reclaim | before_1030 | failed_level_retest | atr_1.0 | vwap_target | none | 1063 | 171 | 838 | 1.547 | 0.780 | 0.630 | -0.032 | -27.188 | -29.297 |  |
| OR30_break_reclaim | before_1030 | failed_level_retest | atr_1.0 | or_midpoint | flat_vwap_slope_only | 1063 | 171 | 152 | 0.281 | 0.750 | 0.622 | -0.038 | -5.788 | -6.801 |  |
| OR30_break_reclaim | le10bars | next_bar_open_after_reclaim | atr_1.0 | or_midpoint | none | 7304 | 123 | 4104 | 7.578 | 0.648 | 0.611 | -0.038 | -153.938 | -154.997 |  |
| OR30_break_reclaim | le10bars | next_bar_open_after_reclaim | atr_1.0 | or_midpoint | flat_vwap_slope_only | 7304 | 123 | 2413 | 4.456 | 0.625 | 0.602 | -0.033 | -78.998 | -79.726 |  |
| OR30_break_reclaim | before_1030 | failed_level_retest | beyond_extreme_2tick | or_midpoint | flat_vwap_slope_only | 1063 | 171 | 157 | 0.290 | 0.255 | 0.559 | -0.977 | -153.467 | -152.874 |  |
| OR30_break_reclaim | before_1030 | next_bar_open_after_reclaim | atr_1.0 | or_midpoint | none | 1063 | 0 | 966 | 1.784 | 0.673 | 0.556 | -0.052 | -50.068 | -51.859 |  |
| PMH_PML_break_reclaim | le10bars | failed_level_retest | atr_1.0 | or_midpoint | none | 6946 | 1305 | 3999 | 7.384 | 0.456 | 0.511 | -0.040 | -161.749 | -163.045 |  |
| PMH_PML_break_reclaim | before_1030 | failed_level_retest | atr_1.0 | or_midpoint | none | 1727 | 291 | 1372 | 2.533 | 0.491 | 0.504 | -0.034 | -46.692 | -47.203 |  |
| OR30_break_reclaim | before_1030 | next_bar_open_after_reclaim | atr_1.0 | 1.5R | flat_vwap_slope_only | 1063 | 0 | 114 | 0.210 | 0.421 | 0.504 | -0.111 | -12.669 | -12.670 |  |
| OR30_break_reclaim | before_1030 | failed_level_retest | atr_1.0 | 1.5R | flat_vwap_slope_only | 1063 | 171 | 151 | 0.279 | 0.417 | 0.499 | -0.104 | -15.768 | -17.198 |  |
| OR30_break_reclaim | le10bars | failed_level_retest | atr_1.0 | vwap_target | none | 7304 | 1386 | 4377 | 8.082 | 0.534 | 0.494 | -0.040 | -175.431 | -176.289 |  |
| OR30_break_reclaim | before_1030 | next_bar_open_after_reclaim | beyond_extreme_2tick | or_midpoint | flat_vwap_slope_only | 1063 | 0 | 121 | 0.223 | 0.339 | 0.464 | -0.512 | -61.938 | -68.346 |  |

## Best cells (n>=20)

| failure_def | timing | entry | stop | exit | filt | n_events_raw | n_no_fill | n | tr_per_wk | wr | pf | exp_r | tot_r | maxdd_r | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OR30_break_reclaim | before_1030 | failed_level_retest | beyond_extreme_2tick | vwap_target | flat_vwap_slope_only | 1063 | 171 | 158 | 0.292 | 0.380 | 0.973 | -0.041 | -6.485 | -92.570 |  |
| PMH_PML_break_reclaim | le10bars | failed_level_retest | atr_1.0 | 1.5R | none | 6946 | 1305 | 1948 | 3.597 | 0.466 | 0.936 | -0.012 | -23.832 | -31.895 |  |
| ONH_ONL_break_reclaim | le10bars | next_bar_open_after_reclaim | atr_1.0 | 1.5R | none | 6495 | 106 | 1874 | 3.460 | 0.475 | 0.919 | -0.016 | -30.330 | -38.026 |  |
| ONH_ONL_break_reclaim | le10bars | failed_level_retest | atr_1.0 | 1.5R | none | 6495 | 1311 | 1736 | 3.205 | 0.479 | 0.913 | -0.017 | -28.956 | -34.916 |  |
| ONH_ONL_break_reclaim | before_1030 | next_bar_open_after_reclaim | atr_1.0 | 1.5R | none | 1606 | 0 | 1137 | 2.099 | 0.478 | 0.900 | -0.022 | -24.889 | -30.390 |  |
| PMH_PML_break_reclaim | le10bars | next_bar_open_after_reclaim | atr_1.0 | 1.5R | flat_vwap_slope_only | 6946 | 104 | 1404 | 2.592 | 0.444 | 0.895 | -0.017 | -23.989 | -31.574 |  |
| ONH_ONL_break_reclaim | before_1030 | failed_level_retest | atr_1.0 | 1.5R | none | 1606 | 317 | 948 | 1.750 | 0.488 | 0.890 | -0.024 | -22.351 | -27.053 |  |
| PMH_PML_break_reclaim | before_1030 | failed_level_retest | atr_1.0 | 1.5R | none | 1727 | 291 | 1049 | 1.937 | 0.459 | 0.888 | -0.025 | -26.726 | -32.556 |  |
| PMH_PML_break_reclaim | le10bars | next_bar_open_after_reclaim | atr_1.0 | 1.5R | none | 6946 | 104 | 2082 | 3.844 | 0.454 | 0.878 | -0.025 | -51.162 | -57.170 |  |
| PMH_PML_break_reclaim | before_1030 | next_bar_open_after_reclaim | atr_1.0 | 1.5R | flat_vwap_slope_only | 1727 | 0 | 253 | 0.467 | 0.411 | 0.874 | -0.026 | -6.466 | -12.068 |  |

## Kill / freeze outcomes

- Family best PF: 0.973
- Family kill rule (PF<1.15): **KILLED**
- No cells exceeded the PF>1.8 freeze-flag threshold.

## Slip probes on the single best cell (OR30_break_reclaim/before_1030/failed_level_retest/beyond_extreme_2tick/vwap_target/flat_vwap_slope_only)

- +0.015R adverse slip: PF=0.964, expR=-0.056, totR=-8.9
- +0.03R adverse slip: PF=0.954, expR=-0.071, totR=-11.2

## Runtime
- Total M3: 359.1s
