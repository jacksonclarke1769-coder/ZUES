# ES Edge Expansion -- Lane A -- M1_vwap_pullback_continuation

**CFD-proxy data** (Dukascopy 24h ET ES CFD-index feed, per `01_data_validation.md`): optimistic-bias caveat applies to every number in this report; graduates need real CME futures data before certification.

RESEARCH ONLY. LIVE HOLD ACTIVE. Preregistered grid, no expansion -- see `lane_a_m1_vwap_pullback_continuation.py` module docstring for the exact grid + operationalization decisions.

## Valid trading days by year

`{2016: 257, 2017: 253, 2018: 253, 2019: 253, 2020: 255, 2021: 255, 2022: 256, 2023: 252, 2024: 252, 2025: 253, 2026: 100}`

## Coarse pass (96 cells @ stop=S2_atr2.5, exit=X3_trail5.0)

Live regions found (PF>=1.15, n>=150): **0 / 96**

### Top 15 coarse cells by PF

| cell                                                                                     |    n |   tr_wk |   wr |    pf |    expR |     totR |   maxDD_R |   n_long |   n_short |   slip_0.015R_pf |   slip_0.03R_pf | labels                                    |
|:-----------------------------------------------------------------------------------------|-----:|--------:|-----:|------:|--------:|---------:|----------:|---------:|----------:|-----------------:|----------------:|:------------------------------------------|
| W1_0945_1130|TG2_first30m|PB1_touch_vwap|E1_next_open|S2_atr2.5|X3_trail5.0              | 2507 |   4.63  | 43.3 | 1.147 |  0.0726 |  182.107 |    54.862 |     1277 |      1230 |            1.115 |           1.083 | -                                         |
| W1_0945_1130|TG2_first30m|PB3_wick_close_trend|E1_next_open|S2_atr2.5|X3_trail5.0        | 2433 |   4.494 | 42.3 | 1.043 |  0.0223 |   54.22  |    98.856 |     1241 |      1192 |            1.014 |           0.986 | WATCHLIST_ONE_REGIME                      |
| W1_0945_1130|TG2_first30m|PB1_touch_vwap|E2_break_reclaim|S2_atr2.5|X3_trail5.0          | 2072 |   3.828 | 42.3 | 1.033 |  0.0171 |   35.44  |    88.489 |     1052 |      1020 |            1.004 |           0.976 | WATCHLIST_ONE_REGIME                      |
| W1_0945_1130|TG2_first30m|PB2_reclaim|E1_next_open|S2_atr2.5|X3_trail5.0                 | 1991 |   3.677 | 42.1 | 1.017 |  0.0087 |   17.377 |    96.078 |     1008 |       983 |            0.988 |           0.961 | REJECTED_FILL_MIRAGE,WATCHLIST_ONE_REGIME |
| W1_0945_1130|TG2_first30m|PB2_reclaim|E2_break_reclaim|S2_atr2.5|X3_trail5.0             | 1827 |   3.374 | 41.8 | 1.004 |  0.0022 |    3.994 |    88.341 |      941 |       886 |            0.976 |           0.949 | REJECTED_FILL_MIRAGE,WATCHLIST_ONE_REGIME |
| W1_0945_1130|TG2_first30m|PB3_wick_close_trend|E2_break_reclaim|S2_atr2.5|X3_trail5.0    | 2169 |   4.007 | 41.8 | 0.998 | -0.0013 |   -2.745 |   102.913 |     1116 |      1053 |            0.97  |           0.942 | -                                         |
| W1_0945_1130|TG4_slope_drive|PB2_reclaim|E1_next_open|S2_atr2.5|X3_trail5.0              | 1012 |   1.87  | 40   | 0.907 | -0.0511 |  -51.759 |   103.402 |      486 |       526 |            0.882 |           0.857 | -                                         |
| W2_1000_1500|TG2_first30m|PB3_wick_close_trend|E2_break_reclaim|S2_atr2.5|X3_trail5.0    | 1996 |   3.687 | 40.2 | 0.903 | -0.0537 | -107.111 |   156.581 |     1031 |       965 |            0.877 |           0.853 | -                                         |
| W2_1000_1500|TG2_first30m|PB3_wick_close_trend|E1_next_open|S2_atr2.5|X3_trail5.0        | 2378 |   4.392 | 40.2 | 0.898 | -0.057  | -135.462 |   192.968 |     1221 |      1157 |            0.873 |           0.849 | -                                         |
| W2_1000_1500|TG4_slope_drive|PB3_wick_close_trend|E1_next_open|S2_atr2.5|X3_trail5.0     | 2126 |   3.926 | 40.4 | 0.897 | -0.0571 | -121.322 |   174.629 |     1093 |      1033 |            0.872 |           0.848 | -                                         |
| W3_1030_1500|TG3_price_vs_vwap|PB2_reclaim|E2_break_reclaim|S2_atr2.5|X3_trail5.0        | 1889 |   3.489 | 38.8 | 0.897 | -0.0595 | -112.365 |   124.669 |      918 |       971 |            0.873 |           0.849 | -                                         |
| W1_0945_1130|TG4_slope_drive|PB3_wick_close_trend|E1_next_open|S2_atr2.5|X3_trail5.0     | 1706 |   3.153 | 39.8 | 0.896 | -0.0578 |  -98.684 |   145.902 |      862 |       844 |            0.872 |           0.848 | -                                         |
| W1_0945_1130|TG4_slope_drive|PB3_wick_close_trend|E2_break_reclaim|S2_atr2.5|X3_trail5.0 | 1401 |   2.589 | 39.8 | 0.894 | -0.0585 |  -81.97  |   113.485 |      716 |       685 |            0.869 |           0.844 | -                                         |
| W2_1000_1500|TG4_slope_drive|PB3_wick_close_trend|E2_break_reclaim|S2_atr2.5|X3_trail5.0 | 1729 |   3.193 | 40.3 | 0.893 | -0.0587 | -101.529 |   134.972 |      896 |       833 |            0.868 |           0.843 | -                                         |
| W1_0945_1130|TG4_slope_drive|PB1_touch_vwap|E2_break_reclaim|S2_atr2.5|X3_trail5.0       | 1417 |   2.619 | 39.8 | 0.892 | -0.0595 |  -84.3   |   105.014 |      722 |       695 |            0.867 |           0.843 | -                                         |


### Near-miss cells (0.10<=PF<1.15, n>=150) -- NOT live regions under the mechanical gate, flagged for visibility since ES-native VPC is the priority question of this lane

| cell                                                                        |    n |   tr_wk |   wr |    pf |   expR |    totR |   maxDD_R |   n_long |   n_short |   slip_0.015R_pf |   slip_0.03R_pf | labels   |
|:----------------------------------------------------------------------------|-----:|--------:|-----:|------:|-------:|--------:|----------:|---------:|----------:|-----------------:|----------------:|:---------|
| W1_0945_1130|TG2_first30m|PB1_touch_vwap|E1_next_open|S2_atr2.5|X3_trail5.0 | 2507 |    4.63 | 43.3 | 1.147 | 0.0726 | 182.107 |    54.862 |     1277 |      1230 |            1.115 |           1.083 | -        |


- `W1_0945_1130|TG2_first30m|PB1_touch_vwap|E1_next_open|S2_atr2.5|X3_trail5.0`: per_year_pf={2016: 0.769, 2017: 0.895, 2018: 1.361, 2019: 0.785, 2020: 1.272, 2021: 1.231, 2022: 1.171, 2023: 1.174, 2024: 1.352, 2025: 1.473, 2026: 1.643}



## Full stop/exit sweep

No live regions found in the coarse pass -- full sweep skipped per task instructions.

## Kill-gate outcomes (family level, mechanical)

kill_gate_verdict
DEAD    96


## Firewall

`python3 -m pytest test_funded_config_firewall.py -q` (run from `~/trading-team/bot/zeus-es-research`) before and after this task's changes: **2 passed** both times. `git status`: 0 tracked modifications (only new untracked files under `research/es_edge_expansion/` and `reports/es_edge_expansion/`).


## Runtime

M1_vwap_pullback_continuation: ~88.5s
