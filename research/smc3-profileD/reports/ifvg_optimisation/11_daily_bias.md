# 11 -- Daily-bias research pass on frozen SMC3 entries (n=5056 baseline)

Baseline (no bias filter): n=5056, WR=34.36%, avgR=-0.0105, totR=-52.9, yrs+=2/6, ex2024=-0.0286, P(+2R)=34.3%.

Sorted by **ex-2024 avgR**.

| rule | scope_n | n | WR% | PF(R) | avgR | totR | maxDD(R) | yrs+/6 | ex2024 | exFri | exBoth | long_avgR | short_avgR | reduc% | P(+2R)% | 2xcost_avgR | slip-0.01_avgR | slip-0.02_avgR | flag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F6.shorts_only_VWAP_slope_down | 4956 | 282 | 39.0 | 1.212 | +0.1340 | +37.8 | -16.79 | 3/6 | +0.2063 | +0.1158 | +0.1982 | +nan | +0.1340 | 94.3% | 39.0% | +0.0979 | +0.1240 | +0.1140 | reduction>70% |
| F3.shorts_only_below_BOTH | 5056 | 515 | 38.1 | 1.171 | +0.1093 | +56.3 | -32.59 | 3/6 | +0.1436 | +0.0583 | +0.1000 | +nan | +0.1093 | 89.8% | 38.1% | +0.0768 | +0.0993 | +0.0893 | reduction>70% |
| F3.shorts_only_below_open | 5056 | 540 | 38.3 | 1.184 | +0.1175 | +63.4 | -26.87 | 4/6 | +0.1378 | +0.0749 | +0.1059 | +nan | +0.1175 | 89.3% | 38.3% | +0.0849 | +0.1075 | +0.0975 | reduction>70% |
| F6.shorts_only_below_VWAP | 5045 | 805 | 36.8 | 1.111 | +0.0722 | +58.1 | -34.24 | 5/6 | +0.0825 | +0.0239 | +0.0413 | +nan | +0.0722 | 84.0% | 36.6% | +0.0413 | +0.0622 | +0.0522 | reduction>70% |
| F3.shorts_only_below_prevclose | 5056 | 950 | 36.8 | 1.100 | +0.0655 | +62.2 | -47.31 | 5/6 | +0.0686 | +0.0376 | +0.0410 | +nan | +0.0655 | 81.2% | 36.8% | +0.0256 | +0.0555 | +0.0455 | reduction>70% |
| F5.rev_30mLow_sweptFailed_long | 2544 | 938 | 36.4 | 1.089 | +0.0583 | +54.7 | -19.29 | 6/6 | +0.0518 | +0.0271 | +0.0286 | +0.0583 | +nan | 63.1% | 36.4% | +0.0260 | +0.0483 | +0.0383 | ok |
| F2.after_ONL_sweep_longs_only | 3029 | 1212 | 35.9 | 1.071 | +0.0466 | +56.5 | -25.34 | 5/6 | +0.0253 | +0.0105 | +0.0002 | +0.0466 | +nan | 60.0% | 35.9% | +0.0165 | +0.0366 | +0.0266 | ok |
| F5.short_only_30m_drive_down | 2544 | 433 | 35.3 | 1.030 | +0.0200 | +8.7 | -17.95 | 3/6 | +0.0246 | +0.0011 | +0.0098 | +nan | +0.0200 | 83.0% | 35.3% | -0.0201 | +0.0100 | -0.0000 | reduction>70%,one-year-carry |
| F2.after_ONH_sweep_shorts_only | 3029 | 1309 | 35.1 | 1.025 | +0.0166 | +21.8 | -47.28 | 4/6 | +0.0193 | -0.0092 | -0.0131 | +nan | +0.0166 | 56.8% | 35.1% | -0.0210 | +0.0066 | -0.0034 | one-year-carry,Friday-only |
| F2.after_ONH_sweep_block_longs | 3029 | 2391 | 35.1 | 1.029 | +0.0196 | +46.9 | -31.97 | 3/6 | +0.0122 | -0.0109 | -0.0177 | +0.0452 | +0.0065 | 21.1% | 35.1% | -0.0148 | +0.0096 | -0.0004 | Friday-only |
| F2.after_ONL_sweep_block_shorts | 3029 | 2424 | 35.1 | 1.031 | +0.0211 | +51.1 | -56.66 | 4/6 | +0.0096 | -0.0066 | -0.0202 | +0.0369 | -0.0022 | 20.0% | 35.1% | -0.0111 | +0.0111 | +0.0011 | Friday-only |
| F6.longs_only_VWAP_slope_up | 4956 | 295 | 35.6 | 1.054 | +0.0357 | +10.5 | -30.70 | 5/6 | +0.0059 | +0.0063 | -0.0424 | +0.0357 | +nan | 94.0% | 35.6% | +0.0036 | +0.0257 | +0.0157 | reduction>70% |
| F6.block_both_ONH_ONL_swept | 3029 | 1986 | 34.8 | 1.019 | +0.0125 | +24.8 | -34.29 | 3/6 | +0.0029 | -0.0171 | -0.0287 | +0.0383 | -0.0092 | 34.4% | 34.8% | -0.0203 | +0.0025 | -0.0075 | Friday-only |
| F6.longs_only_above_VWAP | 5045 | 773 | 35.3 | 1.048 | +0.0319 | +24.6 | -51.88 | 4/6 | +0.0017 | +0.0081 | -0.0262 | +0.0319 | +nan | 84.7% | 35.3% | +0.0043 | +0.0219 | +0.0119 | reduction>70% |
| F3.longs_only_above_BOTH | 5056 | 374 | 34.8 | 1.019 | +0.0130 | +4.8 | -32.94 | 4/6 | -0.0035 | +0.0231 | +0.0043 | +0.0130 | +nan | 92.6% | 34.8% | -0.0168 | +0.0030 | -0.0070 | reduction>70%,one-year-carry |
| F6.first_sweep_dir_lock | 5056 | 3720 | 34.7 | 0.998 | -0.0011 | -4.2 | -129.82 | 4/6 | -0.0064 | -0.0239 | -0.0299 | +0.0008 | -0.0026 | 26.4% | 34.7% | -0.0442 | -0.0111 | -0.0211 | ok |
| F4.dol_direction_skip_gt3R | 5056 | 1924 | 35.3 | 1.031 | +0.0208 | +40.1 | -70.56 | 2/6 | -0.0067 | -0.0383 | -0.0585 | +0.0550 | -0.0111 | 61.9% | 35.3% | -0.0171 | +0.0108 | +0.0008 | one-year-carry,Friday-only |
| F4.dol_direction_only | 5056 | 2016 | 34.8 | 1.008 | +0.0052 | +10.5 | -71.73 | 3/6 | -0.0160 | -0.0535 | -0.0692 | +0.0454 | -0.0305 | 60.1% | 34.8% | -0.0342 | -0.0048 | -0.0148 | one-year-carry,Friday-only |
| F5.short_only_15m_drive_down | 2697 | 566 | 34.1 | 0.979 | -0.0140 | -7.9 | -39.02 | 4/6 | -0.0195 | -0.0060 | -0.0184 | +nan | -0.0140 | 79.0% | 34.1% | -0.0510 | -0.0240 | -0.0340 | reduction>70% |
| F1.after_PDH_sweep_block_longs | 5056 | 4465 | 34.3 | 0.980 | -0.0136 | -60.8 | -140.59 | 3/6 | -0.0280 | -0.0412 | -0.0514 | -0.0058 | -0.0187 | 11.7% | 34.3% | -0.0559 | -0.0236 | -0.0336 | ok |
| F1.after_PDL_sweep_block_shorts | 5056 | 4560 | 34.3 | 0.981 | -0.0130 | -59.2 | -138.19 | 2/6 | -0.0303 | -0.0388 | -0.0558 | -0.0010 | -0.0257 | 9.8% | 34.3% | -0.0542 | -0.0230 | -0.0330 | ok |
| F3.longs_only_above_prevclose | 5056 | 398 | 33.9 | 0.981 | -0.0126 | -5.0 | -28.73 | 4/6 | -0.0317 | +0.0076 | -0.0102 | -0.0126 | +nan | 92.1% | 33.9% | -0.0428 | -0.0226 | -0.0326 | reduction>70% |
| F1.after_PDL_sweep_longs_only | 5056 | 1286 | 33.9 | 0.976 | -0.0164 | -21.1 | -61.19 | 2/6 | -0.0319 | -0.0336 | -0.0428 | -0.0164 | +nan | 74.6% | 33.9% | -0.0499 | -0.0264 | -0.0364 | reduction>70% |
| F3.longs_only_above_open | 5056 | 513 | 32.9 | 0.941 | -0.0408 | -20.9 | -45.45 | 4/6 | -0.0383 | -0.0481 | -0.0407 | -0.0408 | +nan | 89.9% | 32.9% | -0.0699 | -0.0508 | -0.0608 | reduction>70% |
| F5.long_only_15m_drive_up | 2697 | 527 | 34.2 | 0.992 | -0.0054 | -2.8 | -44.24 | 2/6 | -0.0392 | -0.0489 | -0.0602 | -0.0054 | +nan | 80.5% | 34.2% | -0.0355 | -0.0154 | -0.0254 | reduction>70% |
| F5.long_only_30m_drive_up | 2544 | 467 | 33.4 | 0.958 | -0.0285 | -13.3 | -22.67 | 2/6 | -0.0431 | -0.0731 | -0.0860 | -0.0285 | +nan | 81.6% | 33.4% | -0.0592 | -0.0385 | -0.0485 | reduction>70% |
| F4.dol_direction_skip_lt0.5R | 5056 | 316 | 32.0 | 0.855 | -0.1051 | -33.2 | -50.81 | 3/6 | -0.0496 | -0.1233 | -0.1014 | +0.0396 | -0.1846 | 93.8% | 32.0% | -0.1691 | -0.1151 | -0.1251 | reduction>70% |
| F4.dol_direction_0.75to3R | 5056 | 142 | 33.1 | 0.905 | -0.0674 | -9.6 | -21.91 | 2/6 | -0.0507 | -0.0705 | -0.0858 | +0.0307 | -0.1525 | 97.2% | 33.1% | -0.1277 | -0.0774 | -0.0874 | reduction>70% |
| F1.after_PDH_sweep_shorts_only | 5056 | 1677 | 33.5 | 0.939 | -0.0423 | -70.9 | -100.15 | 3/6 | -0.0536 | -0.0795 | -0.0982 | +nan | -0.0423 | 66.8% | 33.4% | -0.0881 | -0.0523 | -0.0623 | ok |
| F6.block_gt3_VWAP_crossings | 5045 | 182 | 35.2 | 0.994 | -0.0043 | -0.8 | -14.25 | 3/6 | -0.0590 | -0.0314 | -0.0963 | +0.0424 | -0.0386 | 96.4% | 35.2% | -0.0636 | -0.0143 | -0.0243 | reduction>70% |
| F5.rev_30mHigh_sweptFailed_short | 2544 | 1027 | 33.2 | 0.933 | -0.0465 | -47.7 | -67.84 | 1/6 | -0.0604 | -0.0452 | -0.0652 | +nan | -0.0465 | 59.6% | 33.2% | -0.0891 | -0.0565 | -0.0665 | ok |

## Family-4 combined row: direction-of-nearest-DOL eligibility + target-the-DOL exit

Eligible n=2016 (direction-of-DOL match, DOL defined). Fixed-2R on this SAME eligible subset: n=2016, avgR=+0.0052, PF=1.008, ex2024=-0.0160, P(+2R)=34.8%.

Target-the-DOL exit (sequential single-position replay, matches dol10_battery `dol_nearest_any` methodology): n=2013, avgR=-0.0414, PF=0.781, ex2024=-0.0452.

Reference (previously tested, `10_dol_exit_audit`/`10_dol_exit_summary`): `dol_htf_pocket_only` avgR +0.0842, PF 1.103, n=3773 (different universe -- ALL frozen entries, no direction-of-DOL eligibility filter, single-source htf-pocket target, not nearest-of-pool).

_Method: allow-only / block-only causal filters applied ISOLATED to the frozen n=5056 SMC3 ledger (default Config, fixed-2R exits unchanged except the one flagged row above). Sweep-state, first-drive and VWAP features are built from strictly-prior bars only (see docstring in day_bias_filters.py for the exact causal conventions). stress columns = direct R-space haircut (2x commission-equivalent / -0.01R / -0.02R slip), consistent with this repo's other stress scripts. artifact_count=0 throughout (causality is asserted in dol10_levels.py / enforced by construction in the cumulative-before-today scan, which only ever looks at STRICTLY PRIOR same-day bars)._
