# ES Edge Expansion -- Lane A -- M12_lunch_afternoon_continuation

**CFD-proxy data** (Dukascopy 24h ET ES CFD-index feed, per `01_data_validation.md`): optimistic-bias caveat applies to every number in this report; graduates need real CME futures data before certification.

RESEARCH ONLY. LIVE HOLD ACTIVE. Preregistered grid, no expansion -- see `lane_a_m12_lunch_afternoon_continuation.py` module docstring for the exact grid + operationalization decisions.

## Valid trading days by year

`{2016: 257, 2017: 253, 2018: 253, 2019: 253, 2020: 255, 2021: 255, 2022: 256, 2023: 252, 2024: 252, 2025: 253, 2026: 100}`

## Full grid (36 cells, single pass)

Cells clearing PF>=1.15 and n>=150: **0 / 36**

### Top 20 cells by PF

| cell                                                                             |    n |   tr_wk |   wr |    pf |    expR |     totR |   maxDD_R |   n_long |   n_short |   slip_0.015R_pf |   slip_0.03R_pf | labels               |
|:---------------------------------------------------------------------------------|-----:|--------:|-----:|------:|--------:|---------:|----------:|---------:|----------:|-----------------:|----------------:|:---------------------|
| WA_1200_1400|MS1_trend_2h|E1_break_morning_hl|ST_atr1.5|X3_flatten1545           |  292 |   0.544 | 34.2 | 1.033 |  0.0245 |    7.158 |    49.45  |      148 |       144 |            1.013 |           0.993 | WATCHLIST_ONE_REGIME |
| WA_1200_1400|MS1_trend_2h|E1_break_morning_hl|ST_atr1.5|X2_R2                    |  292 |   0.544 | 41.4 | 0.98  | -0.0138 |   -4.026 |    32.15  |      148 |       144 |            0.959 |           0.938 | -                    |
| WB_1300_1500|MS1_trend_2h|E2_pullback_vwap|ST_atr1.5|X3_flatten1545              |  215 |   0.401 | 34   | 0.871 | -0.0968 |  -20.816 |    31.173 |       81 |       134 |            0.853 |           0.836 | -                    |
| WB_1300_1500|MS1_trend_2h|E1_break_morning_hl|ST_atr1.5|X3_flatten1545           |  257 |   0.479 | 32.3 | 0.865 | -0.1087 |  -27.946 |    67.56  |      129 |       128 |            0.848 |           0.832 | -                    |
| WA_1200_1400|MS1_trend_2h|E1_break_morning_hl|ST_atr1.5|X1_R1.5                  |  292 |   0.544 | 45.2 | 0.86  | -0.0905 |  -26.418 |    35.529 |      148 |       144 |            0.839 |           0.818 | -                    |
| WB_1300_1500|MS1_trend_2h|E2_pullback_vwap|ST_atr1.5|X2_R2                       |  215 |   0.401 | 37.7 | 0.844 | -0.1127 |  -24.229 |    28.312 |       81 |       134 |            0.826 |           0.808 | -                    |
| WC_1400_1545|MS1_trend_2h|E2_pullback_vwap|ST_atr1.5|X3_flatten1545              |  201 |   0.375 | 38.8 | 0.839 | -0.1036 |  -20.832 |    26.175 |       80 |       121 |            0.819 |           0.799 | -                    |
| WA_1200_1400|MS2_price_vs_vwap_open|E1_break_morning_hl|ST_atr1.5|X3_flatten1545 | 1554 |   2.87  | 30.9 | 0.827 | -0.1413 | -219.605 |   227.85  |      908 |       646 |            0.811 |           0.796 | -                    |
| WB_1300_1500|MS1_trend_2h|E2_pullback_vwap|ST_atr1.5|X1_R1.5                     |  215 |   0.401 | 44.2 | 0.826 | -0.1153 |  -24.789 |    29.161 |       81 |       134 |            0.806 |           0.787 | -                    |
| WA_1200_1400|MS1_trend_2h|E2_pullback_vwap|ST_atr1.5|X3_flatten1545              |  219 |   0.408 | 30.1 | 0.812 | -0.1532 |  -33.558 |    65.302 |       75 |       144 |            0.796 |           0.781 | -                    |
| WC_1400_1545|MS1_trend_2h|E2_pullback_vwap|ST_atr1.5|X2_R2                       |  207 |   0.386 | 40.1 | 0.79  | -0.14   |  -28.987 |    29.58  |       83 |       124 |            0.771 |           0.752 | -                    |
| WB_1300_1500|MS1_trend_2h|E1_break_morning_hl|ST_atr1.5|X2_R2                    |  257 |   0.479 | 37   | 0.774 | -0.1756 |  -45.123 |    58.743 |      129 |       128 |            0.758 |           0.742 | -                    |
| WA_1200_1400|MS2_price_vs_vwap_open|E1_break_morning_hl|ST_atr1.5|X2_R2          | 1554 |   2.87  | 36.5 | 0.773 | -0.175  | -271.993 |   277.136 |      908 |       646 |            0.757 |           0.741 | -                    |
| WC_1400_1545|MS1_trend_2h|E2_pullback_vwap|ST_atr1.5|X1_R1.5                     |  207 |   0.386 | 43.5 | 0.763 | -0.1518 |  -31.432 |    31.674 |       83 |       124 |            0.743 |           0.724 | -                    |
| WA_1200_1400|MS1_trend_2h|E2_pullback_vwap|ST_atr1.5|X2_R2                       |  219 |   0.408 | 33.8 | 0.757 | -0.1894 |  -41.475 |    54.709 |       75 |       144 |            0.741 |           0.725 | -                    |
| WA_1200_1400|MS2_price_vs_vwap_open|E2_pullback_vwap|ST_atr1.5|X3_flatten1545    | 1552 |   2.866 | 28.5 | 0.753 | -0.2166 | -336.227 |   349.103 |      783 |       769 |            0.74  |           0.726 | -                    |
| WA_1200_1400|MS2_price_vs_vwap_open|E1_break_morning_hl|ST_atr1.5|X1_R1.5        | 1554 |   2.87  | 42.4 | 0.742 | -0.1813 | -281.768 |   287.674 |      908 |       646 |            0.724 |           0.707 | -                    |
| WC_1400_1545|MS1_trend_2h|E1_break_morning_hl|ST_atr1.5|X3_flatten1545           |  225 |   0.42  | 33.8 | 0.74  | -0.1867 |  -42.015 |    63.063 |      119 |       106 |            0.723 |           0.706 | -                    |
| WC_1400_1545|MS1_trend_2h|E1_break_morning_hl|ST_atr1.5|X2_R2                    |  226 |   0.421 | 35.8 | 0.73  | -0.2111 |  -47.7   |    58.639 |      119 |       107 |            0.714 |           0.699 | -                    |
| WC_1400_1545|MS1_trend_2h|E1_break_morning_hl|ST_atr1.5|X1_R1.5                  |  226 |   0.421 | 42.9 | 0.723 | -0.1939 |  -43.824 |    48.952 |      119 |       107 |            0.705 |           0.688 | -                    |


## Kill-gate outcomes (family level, mechanical)

kill_gate_verdict
DEAD    36


## Firewall

`python3 -m pytest test_funded_config_firewall.py -q` (run from `~/trading-team/bot/zeus-es-research`) before and after this task's changes: **2 passed** both times. `git status`: 0 tracked modifications (only new untracked files under `research/es_edge_expansion/` and `reports/es_edge_expansion/`).


## Runtime

M12_lunch_afternoon_continuation: ~11.5s
