# 09 — Day-sequence / repeat-entry filter battery (SMC3 NY-AM, causal drop-only replay)

Baseline (unlimited/no filter): n=1624, sorted by **ex-2024 avgR** (the gate that killed the raw baseline).

| rule | n | days | tr/day | WR% | PF(R) | avgR | totR | maxDD(R) | yrs+/6 | ex2024_avgR | exFri_avgR | exBoth_avgR | reduc% | R_removed | R_kept | bleed_days_improved | gooddays_survive | flag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B.standalone_sig#3 | 145 | 145 | 1.00 | 36.6 | 1.113 | +0.074 | +10.7 | -15.2 | 3/6 | +0.096 | +0.043 | +0.079 | 91.1% | +57.0 | +10.7 | yes | no | REJECTED_DENOMINATOR_TRICK (reduction>70%) |
| B.standalone_sig#4+ | 26 | 23 | 1.13 | 42.3 | 1.418 | +0.247 | +6.4 | -4.1 | 3/6 | +0.081 | +0.263 | +0.100 | 98.4% | +61.3 | +6.4 | yes | no | REJECTED_DENOMINATOR_TRICK (reduction>70%,n<50) |
| F.dir_lock_first_sweep | 1438 | 961 | 1.50 | 36.0 | 1.086 | +0.056 | +80.6 | -51.0 | 5/6 | +0.016 | +0.049 | +0.008 | 11.5% | -12.9 | +80.6 | yes | no | ok |
| F.no_opp_within_60min_entry | 1555 | 961 | 1.62 | 36.1 | 1.094 | +0.062 | +95.7 | -41.8 | 5/6 | +0.011 | +0.052 | +0.006 | 4.2% | -28.0 | +95.7 | yes | no | ok |
| F.no_opp_after_loss | 1548 | 961 | 1.61 | 36.0 | 1.090 | +0.059 | +91.1 | -48.5 | 5/6 | +0.008 | +0.049 | +0.003 | 4.7% | -23.4 | +91.1 | yes | yes | ok |
| E.stop_day+1R | 1398 | 961 | 1.45 | 35.2 | 1.050 | +0.033 | +46.4 | -48.5 | 4/6 | -0.000 | +0.009 | -0.023 | 13.9% | +21.3 | +46.4 | no | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| E.stop_day+1.5R | 1398 | 961 | 1.45 | 35.2 | 1.050 | +0.033 | +46.4 | -48.5 | 4/6 | -0.000 | +0.009 | -0.023 | 13.9% | +21.3 | +46.4 | no | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| F.no_opp_within_30min_entry | 1606 | 961 | 1.67 | 35.7 | 1.076 | +0.050 | +79.9 | -42.2 | 4/6 | -0.001 | +0.034 | -0.014 | 1.1% | -12.2 | +79.9 | no | yes | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| G.cooldown_exit_30min | 1289 | 961 | 1.34 | 35.7 | 1.072 | +0.047 | +61.1 | -55.9 | 4/6 | -0.001 | +0.024 | -0.015 | 20.6% | +6.6 | +61.1 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| G.cooldown_exit_60min | 1167 | 961 | 1.21 | 35.7 | 1.074 | +0.049 | +56.8 | -44.3 | 3/6 | -0.003 | +0.032 | -0.009 | 28.1% | +10.9 | +56.8 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| G.cooldown_exit_45min | 1218 | 961 | 1.27 | 35.6 | 1.065 | +0.043 | +52.6 | -50.7 | 4/6 | -0.004 | +0.014 | -0.021 | 25.0% | +15.1 | +52.6 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| E.stop_after_2_wins | 1602 | 961 | 1.67 | 35.5 | 1.063 | +0.041 | +66.2 | -43.2 | 2/6 | -0.004 | +0.023 | -0.023 | 1.4% | +1.5 | +66.2 | no | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| E.stop_day+2R | 1604 | 961 | 1.67 | 35.5 | 1.063 | +0.042 | +67.2 | -43.2 | 2/6 | -0.004 | +0.025 | -0.023 | 1.2% | +0.5 | +67.2 | no | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| G.cooldown_entry_60min | 1262 | 961 | 1.31 | 35.8 | 1.077 | +0.051 | +64.2 | -51.9 | 4/6 | -0.006 | +0.040 | -0.007 | 22.3% | +3.5 | +64.2 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| A.max_trades_4 | 1621 | 961 | 1.69 | 35.5 | 1.063 | +0.042 | +67.8 | -45.2 | 2/6 | -0.007 | +0.025 | -0.021 | 0.2% | -0.1 | +67.8 | no | yes | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| D.first_wins_allow_1_more | 1130 | 961 | 1.18 | 36.0 | 1.089 | +0.058 | +66.0 | -45.8 | 2/6 | -0.007 | +0.049 | -0.007 | 30.4% | +1.7 | +66.0 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| A.max_trades_unlimited(baseline) | 1624 | 961 | 1.69 | 35.5 | 1.063 | +0.042 | +67.7 | -45.2 | 2/6 | -0.008 | +0.026 | -0.022 | 0.0% | +0.0 | +67.7 | no | yes | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| A.max_trades_3 | 1598 | 961 | 1.66 | 35.4 | 1.058 | +0.038 | +61.3 | -45.3 | 4/6 | -0.009 | +0.022 | -0.023 | 1.6% | +6.4 | +61.3 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| B.signal_1-3 | 1598 | 961 | 1.66 | 35.4 | 1.058 | +0.038 | +61.3 | -45.3 | 4/6 | -0.009 | +0.022 | -0.023 | 1.6% | +6.4 | +61.3 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| G.cooldown_entry_10min | 1602 | 961 | 1.67 | 35.5 | 1.062 | +0.041 | +66.0 | -48.8 | 3/6 | -0.010 | +0.025 | -0.025 | 1.4% | +1.7 | +66.0 | yes | yes | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| C.stop_after_1_loss | 1146 | 961 | 1.19 | 36.0 | 1.090 | +0.059 | +67.7 | -46.9 | 2/6 | -0.012 | +0.050 | -0.007 | 29.4% | +0.0 | +67.7 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| B.standalone_sig#1 | 961 | 961 | 1.00 | 35.4 | 1.059 | +0.039 | +37.4 | -47.6 | 4/6 | -0.013 | +0.024 | -0.013 | 40.8% | +30.3 | +37.4 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| B.signal_1_only | 961 | 961 | 1.00 | 35.4 | 1.059 | +0.039 | +37.4 | -47.6 | 4/6 | -0.013 | +0.024 | -0.013 | 40.8% | +30.3 | +37.4 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| A.max_trades_1 | 961 | 961 | 1.00 | 35.4 | 1.059 | +0.039 | +37.4 | -47.6 | 4/6 | -0.013 | +0.024 | -0.013 | 40.8% | +30.3 | +37.4 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| E.stop_after_1_win | 1354 | 961 | 1.41 | 34.8 | 1.031 | +0.021 | +28.2 | -60.4 | 4/6 | -0.015 | -0.005 | -0.040 | 16.6% | +39.5 | +28.2 | no | no | REJECTED_DENOMINATOR_TRICK (profit from one year,Friday-only) |
| D.first_wins_allow_2_more | 1176 | 961 | 1.22 | 35.8 | 1.079 | +0.052 | +61.0 | -48.3 | 2/6 | -0.017 | +0.047 | -0.009 | 27.6% | +6.7 | +61.0 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| G.cooldown_exit_20min | 1350 | 961 | 1.40 | 35.3 | 1.052 | +0.035 | +46.8 | -61.1 | 4/6 | -0.017 | +0.011 | -0.036 | 16.9% | +20.9 | +46.8 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| C.stop_after_2_losses | 1537 | 961 | 1.60 | 35.3 | 1.054 | +0.036 | +54.8 | -52.3 | 2/6 | -0.018 | +0.026 | -0.024 | 5.4% | +12.9 | +54.8 | yes | yes | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| C.stop_daycum<=-1 | 1183 | 961 | 1.23 | 35.8 | 1.077 | +0.051 | +59.8 | -47.4 | 2/6 | -0.019 | +0.046 | -0.010 | 27.2% | +7.9 | +59.8 | yes | yes | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| D.first_loses_before_10_stop | 1255 | 961 | 1.31 | 35.6 | 1.070 | +0.046 | +57.9 | -47.3 | 2/6 | -0.019 | +0.042 | -0.010 | 22.7% | +9.8 | +57.9 | yes | yes | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| B.signal_1-2 | 1453 | 961 | 1.51 | 35.2 | 1.053 | +0.035 | +50.6 | -58.0 | 2/6 | -0.020 | +0.020 | -0.034 | 10.5% | +17.1 | +50.6 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| A.max_trades_2 | 1453 | 961 | 1.51 | 35.2 | 1.053 | +0.035 | +50.6 | -58.0 | 2/6 | -0.020 | +0.020 | -0.034 | 10.5% | +17.1 | +50.6 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| D.stop_day_if_first_loses | 1184 | 961 | 1.23 | 35.7 | 1.076 | +0.050 | +58.7 | -47.4 | 2/6 | -0.020 | +0.045 | -0.012 | 27.1% | +9.0 | +58.7 | yes | yes | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| D.stop_if_first_two_lose | 1548 | 961 | 1.61 | 35.3 | 1.054 | +0.036 | +55.5 | -51.4 | 2/6 | -0.021 | +0.026 | -0.027 | 4.7% | +12.2 | +55.5 | yes | yes | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| C.stop_daycum<=-2 | 1548 | 961 | 1.61 | 35.3 | 1.054 | +0.036 | +55.5 | -51.4 | 2/6 | -0.021 | +0.026 | -0.027 | 4.7% | +12.2 | +55.5 | yes | yes | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| C.stop_daycum<=-1.5 | 1548 | 961 | 1.61 | 35.3 | 1.054 | +0.036 | +55.5 | -51.4 | 2/6 | -0.021 | +0.026 | -0.027 | 4.7% | +12.2 | +55.5 | yes | yes | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| G.cooldown_exit_5min | 1482 | 961 | 1.54 | 35.0 | 1.039 | +0.026 | +38.0 | -48.0 | 3/6 | -0.021 | +0.003 | -0.041 | 8.7% | +29.7 | +38.0 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| G.cooldown_exit_10min | 1432 | 961 | 1.49 | 34.9 | 1.037 | +0.025 | +35.2 | -58.1 | 3/6 | -0.024 | +0.006 | -0.036 | 11.8% | +32.5 | +35.2 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| G.cooldown_entry_20min | 1538 | 961 | 1.60 | 34.9 | 1.037 | +0.025 | +38.0 | -53.3 | 2/6 | -0.029 | +0.010 | -0.040 | 5.3% | +29.7 | +38.0 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| B.standalone_sig#2 | 492 | 492 | 1.00 | 35.0 | 1.040 | +0.027 | +13.2 | -19.2 | 3/6 | -0.031 | +0.011 | -0.075 | 69.7% | +54.5 | +13.2 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |
| G.cooldown_entry_30min | 1463 | 961 | 1.52 | 34.7 | 1.025 | +0.017 | +24.3 | -60.8 | 2/6 | -0.037 | +0.002 | -0.048 | 9.9% | +43.4 | +24.3 | yes | no | REJECTED_DENOMINATOR_TRICK (profit from one year) |

_Method: sequential per-ET-day replay; a rule's skip decision at each trade uses only the outcomes of trades ALREADY TAKEN that day (skipped trades are not 'prior' for later decisions). Drop-only: cannot recover R from windows the original single-position engine was blocked from trading. bleed_days_improved = do the historical worst-10 days (by day R) sum to a less-negative R under this filter? gooddays_survive = do the historical best-10 days retain at least their full R (i.e. none of their trades were skipped)?_
