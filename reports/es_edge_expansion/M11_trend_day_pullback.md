# ES Edge Expansion -- Lane A -- M11_trend_day_pullback

**CFD-proxy data** (Dukascopy 24h ET ES CFD-index feed, per `01_data_validation.md`): optimistic-bias caveat applies to every number in this report; graduates need real CME futures data before certification.

RESEARCH ONLY. LIVE HOLD ACTIVE. Preregistered grid, no expansion -- see `lane_a_m11_trend_day_pullback.py` module docstring for the exact grid + operationalization decisions.

## Valid trading days by year

`{2016: 257, 2017: 253, 2018: 253, 2019: 253, 2020: 255, 2021: 255, 2022: 256, 2023: 252, 2024: 252, 2025: 253, 2026: 100}`

## Full grid (108 cells, single pass)

Cells clearing PF>=1.15 and n>=150: **0 / 108**

### Top 20 cells by PF

| cell                                                                              |   n |   tr_wk |   wr |    pf |    expR |    totR |   maxDD_R |   n_long |   n_short |   slip_0.015R_pf |   slip_0.03R_pf | labels                                    |
|:----------------------------------------------------------------------------------|----:|--------:|-----:|------:|--------:|--------:|----------:|---------:|----------:|-----------------:|----------------:|:------------------------------------------|
| C1_first30m_trend|T1_first_touch_1030|E2_break_pullback|ST1_swing|X1_R2           |  21 |   0.042 | 57.1 | 2.093 |  0.5148 |  10.81  |     2.372 |       11 |        10 |            2.047 |           2.002 | WATCHLIST_ONE_REGIME                      |
| C1_first30m_trend|T2_shallow_25_38|E1_next_open|ST1_swing|X2_trail3.5             |  38 |   0.074 |  5.3 | 2.085 |  1.732  |  65.815 |    52.782 |       14 |        24 |            2.066 |           2.047 | WATCHLIST_ONE_REGIME                      |
| C1_first30m_trend|T1_first_touch_1030|E2_break_pullback|ST2_atr1.5|X2_trail3.5    |  21 |   0.042 | 42.9 | 1.499 |  0.2692 |   5.653 |     6.75  |       11 |        10 |            1.464 |           1.43  | WATCHLIST_ONE_REGIME                      |
| C1_first30m_trend|T1_first_touch_1030|E2_break_pullback|ST1_swing|X2_trail3.5     |  21 |   0.042 | 33.3 | 1.471 |  0.3401 |   7.141 |     7.689 |       11 |        10 |            1.444 |           1.418 | WATCHLIST_ONE_REGIME                      |
| C1_first30m_trend|T1_first_touch_1030|E2_break_pullback|ST1_swing|X3_new_extreme  |  21 |   0.042 | 61.9 | 1.329 |  0.1503 |   3.156 |     3.729 |       11 |        10 |            1.293 |           1.257 | WATCHLIST_ONE_REGIME                      |
| C1_first30m_trend|T1_first_touch_1030|E2_break_pullback|ST2_atr1.5|X1_R2          |  21 |   0.042 | 47.6 | 1.305 |  0.1698 |   3.567 |     5.039 |       11 |        10 |            1.274 |           1.244 | WATCHLIST_ONE_REGIME                      |
| C1_first30m_trend|T1_first_touch_1030|E2_break_pullback|ST2_atr1.5|X3_new_extreme |  21 |   0.042 | 71.4 | 1.296 |  0.1005 |   2.11  |     3.748 |       11 |        10 |            1.249 |           1.203 | WATCHLIST_ONE_REGIME                      |
| C1_first30m_trend|T1_first_touch_1030|E1_next_open|ST2_atr1.5|X1_R2               |  40 |   0.078 | 45   | 1.117 |  0.0718 |   2.873 |     6.657 |       17 |        23 |            1.091 |           1.066 | WATCHLIST_ONE_REGIME                      |
| C2_vwap_slope_steep|T2_shallow_25_38|E1_next_open|ST2_atr1.5|X2_trail3.5          | 497 |   0.926 | 33.2 | 1.063 |  0.0435 |  21.624 |    28.287 |      213 |       284 |            1.041 |           1.019 | WATCHLIST_ONE_REGIME                      |
| C1_first30m_trend|T2_shallow_25_38|E1_next_open|ST2_atr1.5|X2_trail3.5            |  38 |   0.074 | 28.9 | 1.05  |  0.0357 |   1.357 |     9.635 |       14 |        24 |            1.029 |           1.008 | WATCHLIST_ONE_REGIME                      |
| C1_first30m_trend|T1_first_touch_1030|E1_next_open|ST2_atr1.5|X2_trail3.5         |  40 |   0.078 | 32.5 | 1.02  |  0.0128 |   0.514 |     8.697 |       17 |        23 |            0.997 |           0.974 | REJECTED_FILL_MIRAGE,WATCHLIST_ONE_REGIME |
| C2_vwap_slope_steep|T2_shallow_25_38|E2_break_pullback|ST2_atr1.5|X2_trail3.5     | 341 |   0.635 | 32.3 | 0.983 | -0.0116 |  -3.941 |    26.385 |      146 |       195 |            0.963 |           0.942 | -                                         |
| C1_first30m_trend|T2_shallow_25_38|E2_break_pullback|ST2_atr1.5|X2_trail3.5       |  24 |   0.047 | 25   | 0.973 | -0.0216 |  -0.518 |    11.119 |        9 |        15 |            0.954 |           0.936 | -                                         |
| C2_vwap_slope_steep|T2_shallow_25_38|E1_next_open|ST1_swing|X2_trail3.5           | 493 |   0.919 | 12.6 | 0.967 | -0.0491 | -24.201 |   153.128 |      211 |       282 |            0.958 |           0.949 | -                                         |
| C2_vwap_slope_steep|T2_shallow_25_38|E1_next_open|ST2_atr1.5|X1_R2                | 497 |   0.926 | 38   | 0.949 | -0.0348 | -17.271 |    24.825 |      213 |       284 |            0.928 |           0.908 | -                                         |
| C1_first30m_trend|T2_shallow_25_38|E2_break_pullback|ST1_swing|X2_trail3.5        |  24 |   0.047 | 20.8 | 0.934 | -0.0636 |  -1.526 |    15.078 |        9 |        15 |            0.919 |           0.905 | -                                         |
| C2_vwap_slope_steep|T1_first_touch_1030|E2_break_pullback|ST1_swing|X2_trail3.5   | 268 |   0.499 | 25.7 | 0.918 | -0.0705 | -18.883 |    49.804 |      112 |       156 |            0.902 |           0.886 | -                                         |
| C2_vwap_slope_steep|T3_medium_50_618|E2_break_pullback|ST2_atr1.5|X2_trail3.5     | 225 |   0.431 | 30.2 | 0.917 | -0.0585 | -13.165 |    24.146 |       82 |       143 |            0.897 |           0.878 | -                                         |
| C1_first30m_trend|T2_shallow_25_38|E1_next_open|ST1_swing|X3_new_extreme          |  38 |   0.074 | 23.7 | 0.916 | -0.1152 |  -4.377 |    24.3   |       14 |        24 |            0.905 |           0.895 | -                                         |
| C2_vwap_slope_steep|T2_shallow_25_38|E2_break_pullback|ST2_atr1.5|X1_R2           | 341 |   0.635 | 36.1 | 0.895 | -0.0733 | -24.99  |    35.477 |      146 |       195 |            0.875 |           0.856 | -                                         |


## Kill-gate outcomes (family level, mechanical)

kill_gate_verdict
DEAD                                            101
SURVIVOR                                          5
FREEZE+FLAG (PF>1.8, verify before trusting)      2


### FREEZE+FLAG cells (PF>1.8, verify before trusting)

| cell                                                                    |   n |   tr_wk |   wr |    pf |   expR |   totR |   maxDD_R |   n_long |   n_short |   slip_0.015R_pf |   slip_0.03R_pf | labels               |
|:------------------------------------------------------------------------|----:|--------:|-----:|------:|-------:|-------:|----------:|---------:|----------:|-----------------:|----------------:|:---------------------|
| C1_first30m_trend|T1_first_touch_1030|E2_break_pullback|ST1_swing|X1_R2 |  21 |   0.042 | 57.1 | 2.093 | 0.5148 | 10.81  |     2.372 |       11 |        10 |            2.047 |           2.002 | WATCHLIST_ONE_REGIME |
| C1_first30m_trend|T2_shallow_25_38|E1_next_open|ST1_swing|X2_trail3.5   |  38 |   0.074 |  5.3 | 2.085 | 1.732  | 65.815 |    52.782 |       14 |        24 |            2.066 |           2.047 | WATCHLIST_ONE_REGIME |



## Firewall

`python3 -m pytest test_funded_config_firewall.py -q` (run from `~/trading-team/bot/zeus-es-research`) before and after this task's changes: **2 passed** both times. `git status`: 0 tracked modifications (only new untracked files under `research/es_edge_expansion/` and `reports/es_edge_expansion/`).


## Runtime

M11_trend_day_pullback: ~8.3s
