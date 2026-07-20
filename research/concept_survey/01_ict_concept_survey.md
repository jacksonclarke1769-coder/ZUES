# ICT Concept Survey — 36-Cell Preregistered Arena, Gated Results

Preregistration: `backtests/zeus-ict-2026-07/concept_survey/PREREG.md` (frozen 2026-07-20, before any result was computed). Data: single-vendor Databento NQ 1m (`data/real_futures/NQ_databento_1m_5y.parquet`), window 2024-06-22 -> 2026-06-22, TRAIN=first 12mo, HOLDOUT=last 12mo. N=36 (6 concepts x 3 TFs x 2 directions), fixed a priori.

## 1. Headline
- Gate A (holdout PF>1.0 & expectancy>0): **25/36**
- Gate B (BH-FDR q=0.10 across all 36, one-sided block-bootstrap p): **19/36** (BH cutoff p = 0.0442)
- Gate A+B (both required to reach Gate C): **19/36**
- Gate C (beats 1000-run randomized-entry null, 95th pctile of total R): **19/36**

## 2. Null expectation vs observed (Gate B/C context)
- Observed cells with HOLDOUT PF>1.2: **19/36**.
- Expected cells clearing PF>1.2 under the randomized-entry null (sum, across all 36 cells, of that cell's own null-run fraction with PF>1.2 -- i.e. the false-positive yield the SAME execution template would produce from bar-selection luck alone): **0.3/36**.
- Gap (observed minus null-expected): **18.7**. This gap is large relative to the null-expected count -- the survey found a real signal, not noise; Gate C (per-cell, not aggregate) is still the decisive test for individual cells.
- Per-cell 200-run (1000-run for A+B survivors) null total-R and null-PF distributions, and the observed-vs-null-p95 outcome, are in `gate_c_result.json` for every cell, not just survivors (per PREREG §Gate B/C).

## 3. BH-FDR p-value ladder (q=0.10, N=36)

| rank | cell | p | BH threshold | passes |
|---|---|---|---|---|
| 1 | FVG_1m_long | 0.00010 | 0.00278 | YES |
| 2 | FVG_1m_short | 0.00010 | 0.00556 | YES |
| 3 | FVG_5m_long | 0.00010 | 0.00833 | YES |
| 4 | FVG_5m_short | 0.00010 | 0.01111 | YES |
| 5 | IFVG_1m_long | 0.00010 | 0.01389 | YES |
| 6 | IFVG_1m_short | 0.00010 | 0.01667 | YES |
| 7 | IFVG_5m_long | 0.00010 | 0.01944 | YES |
| 8 | IFVG_5m_short | 0.00010 | 0.02222 | YES |
| 9 | OB_1m_long | 0.00010 | 0.02500 | YES |
| 10 | OB_1m_short | 0.00010 | 0.02778 | YES |
| 11 | Breaker_1m_long | 0.00010 | 0.03056 | YES |
| 12 | Breaker_1m_short | 0.00010 | 0.03333 | YES |
| 13 | OB_5m_long | 0.00050 | 0.03611 | YES |
| 14 | IFVG_15m_short | 0.00060 | 0.03889 | YES |
| 15 | Breaker_5m_long | 0.00080 | 0.04167 | YES |
| 16 | FVG_15m_long | 0.00130 | 0.04444 | YES |
| 17 | Breaker_5m_short | 0.00540 | 0.04722 | YES |
| 18 | Breaker_15m_short | 0.04210 | 0.05000 | YES |
| 19 | MSS_15m_long | 0.04420 | 0.05278 | YES |
| 20 | IFVG_15m_long | 0.06060 | 0.05556 |  |
| 21 | FVG_15m_short | 0.10950 | 0.05833 |  |
| 22 | OB_15m_long | 0.14260 | 0.06111 |  |
| 23 | Breaker_15m_long | 0.19900 | 0.06389 |  |
| 24 | OB_5m_short | 0.26680 | 0.06667 |  |
| 25 | MSS_15m_short | 0.32970 | 0.06944 |  |
| 26 | Sweep_15m_long | 0.64910 | 0.07222 |  |
| 27 | MSS_5m_long | 0.65400 | 0.07500 |  |
| 28 | OB_15m_short | 0.69140 | 0.07778 |  |
| 29 | Sweep_5m_long | 0.75770 | 0.08056 |  |
| 30 | MSS_5m_short | 0.85650 | 0.08333 |  |
| 31 | MSS_1m_long | 0.98480 | 0.08611 |  |
| 32 | Sweep_15m_short | 0.99290 | 0.08889 |  |
| 33 | Sweep_5m_short | 0.99900 | 0.09167 |  |
| 34 | Sweep_1m_long | 1.00000 | 0.09444 |  |
| 35 | Sweep_1m_short | 1.00000 | 0.09722 |  |
| 36 | MSS_1m_short | 1.00000 | 0.10000 |  |

## 4. Per-cell table: TRAIN | HOLDOUT | LIVE-ACHIEVABLE (Gate A+B+C+D survivors get the live column)

| cell | TRAIN n/PF/exp | HOLDOUT n/PF/exp | Gate A | Gate B (p) | Gate C (beats null) | LIVE n/PF/exp (survivors) |
|---|---|---|---|---|---|---|
| FVG_1m_long | 7907/1.796/0.571 | 7953/1.897/0.643 | PASS | 0.0001 PASS | beats | 5741/1.952/0.657 |
| FVG_1m_short | 8232/1.671/0.497 | 7832/1.822/0.598 | PASS | 0.0001 PASS | beats | 5762/1.837/0.590 |
| FVG_5m_long | 1822/1.480/0.378 | 1810/1.488/0.378 | PASS | 0.0001 PASS | beats | 1810/1.488/0.378 |
| FVG_5m_short | 1738/1.348/0.274 | 1739/1.465/0.368 | PASS | 0.0001 PASS | beats | 1739/1.465/0.368 |
| FVG_15m_long | 632/1.411/0.319 | 642/1.355/0.275 | PASS | 0.0013 PASS | beats | 642/1.355/0.275 |
| FVG_15m_short | 595/1.382/0.290 | 569/1.148/0.120 | PASS | 0.1095 | - | - |
| IFVG_1m_long | 6593/1.772/0.563 | 6449/1.924/0.663 | PASS | 0.0001 PASS | beats | 4122/1.973/0.666 |
| IFVG_1m_short | 6760/1.757/0.564 | 6567/1.831/0.618 | PASS | 0.0001 PASS | beats | 4239/1.908/0.647 |
| IFVG_5m_long | 1381/1.355/0.283 | 1389/1.364/0.297 | PASS | 0.0001 PASS | beats | 1369/1.342/0.279 |
| IFVG_5m_short | 1573/1.363/0.293 | 1582/1.355/0.294 | PASS | 0.0001 PASS | beats | 1529/1.324/0.269 |
| IFVG_15m_long | 476/1.354/0.265 | 463/1.216/0.174 | PASS | 0.0606 | - | - |
| IFVG_15m_short | 566/1.264/0.214 | 537/1.513/0.404 | PASS | 0.0006 PASS | beats | 518/1.427/0.338 |
| OB_1m_long | 5264/1.241/0.153 | 5392/1.362/0.227 | PASS | 0.0001 PASS | beats | 4138/1.403/0.249 |
| OB_1m_short | 5226/1.222/0.149 | 5269/1.275/0.183 | PASS | 0.0001 PASS | beats | 4070/1.313/0.206 |
| OB_5m_long | 1353/1.099/0.064 | 1312/1.236/0.149 | PASS | 0.0005 PASS | beats | 1312/1.236/0.149 |
| OB_5m_short | 1417/1.191/0.127 | 1382/1.040/0.028 | PASS | 0.2668 | - | - |
| OB_15m_long | 543/1.309/0.186 | 542/1.105/0.068 | PASS | 0.1426 | - | - |
| OB_15m_short | 500/1.148/0.096 | 498/0.942/-0.042 | fail | 0.6914 | - | - |
| Breaker_1m_long | 3556/1.483/0.305 | 3648/1.487/0.310 | PASS | 0.0001 PASS | beats | 2643/1.503/0.312 |
| Breaker_1m_short | 3652/1.350/0.227 | 3689/1.438/0.281 | PASS | 0.0001 PASS | beats | 2685/1.470/0.292 |
| Breaker_5m_long | 925/1.175/0.122 | 910/1.245/0.165 | PASS | 0.0008 PASS | beats | 886/1.234/0.158 |
| Breaker_5m_short | 903/1.376/0.245 | 872/1.214/0.147 | PASS | 0.0054 PASS | beats | 852/1.162/0.113 |
| Breaker_15m_long | 335/1.135/0.097 | 325/1.121/0.085 | PASS | 0.1990 | - | - |
| Breaker_15m_short | 345/1.055/0.038 | 353/1.234/0.162 | PASS | 0.0421 PASS | beats | 352/1.231/0.160 |
| Sweep_1m_long | 15270/0.912/-0.050 | 15475/0.908/-0.054 | fail | 1.0000 | - | - |
| Sweep_1m_short | 15572/0.919/-0.048 | 15598/0.899/-0.062 | fail | 1.0000 | - | - |
| Sweep_5m_long | 3494/0.962/-0.021 | 3449/0.973/-0.016 | fail | 0.7577 | - | - |
| Sweep_5m_short | 3575/0.941/-0.035 | 3783/0.884/-0.073 | fail | 0.9990 | - | - |
| Sweep_15m_long | 1171/1.014/0.008 | 1149/0.972/-0.016 | fail | 0.6491 | - | - |
| Sweep_15m_short | 1208/0.870/-0.077 | 1328/0.844/-0.098 | fail | 0.9929 | - | - |
| MSS_1m_long | 10263/0.833/-0.047 | 9611/0.921/-0.023 | fail | 0.9848 | - | - |
| MSS_1m_short | 10120/0.844/-0.044 | 9950/0.847/-0.046 | fail | 1.0000 | - | - |
| MSS_5m_long | 2074/0.944/-0.015 | 2074/0.980/-0.006 | fail | 0.6540 | - | - |
| MSS_5m_short | 2045/0.938/-0.017 | 1987/0.934/-0.020 | fail | 0.8565 | - | - |
| MSS_15m_long | 711/1.115/0.029 | 747/1.182/0.047 | PASS | 0.0442 PASS | beats | 747/1.105/0.028 |
| MSS_15m_short | 734/1.052/0.014 | 678/1.041/0.012 | PASS | 0.3297 | - | - |

## 5. Quarterly walk-forward sign stability (8 quarters across the 2y window)

| cell | positive quarters / 8 | sign sequence |
|---|---|---|
| FVG_1m_long | 8/8 | ++++++++ |
| Breaker_5m_long | 7/8 | +++-++++ |
| FVG_5m_short | 8/8 | ++++++++ |
| FVG_1m_short | 8/8 | ++++++++ |
| IFVG_5m_short | 8/8 | ++++++++ |
| Breaker_1m_short | 8/8 | ++++++++ |
| FVG_5m_long | 8/8 | ++++++++ |
| IFVG_5m_long | 8/8 | ++++++++ |
| Breaker_1m_long | 8/8 | ++++++++ |
| FVG_15m_long | 8/8 | ++++++++ |
| OB_1m_long | 8/8 | ++++++++ |
| IFVG_1m_long | 8/8 | ++++++++ |
| IFVG_1m_short | 8/8 | ++++++++ |
| Breaker_15m_short | 7/8 | +++-++++ |
| IFVG_15m_short | 7/8 | +++-++++ |
| MSS_15m_long | 6/8 | ++-+++-+ |
| OB_5m_long | 8/8 | ++++++++ |
| OB_1m_short | 8/8 | ++++++++ |
| Breaker_5m_short | 8/8 | ++++++++ |

## 6. Ranked survivor shortlist

Ranked by (a) gates passed [all A+B+C here], (b) decorrelation vs other survivors/Profile A/VPC (lower mean |corr| = better), (c) live-achievable expectancy:

1. **OB_5m_long** — decorr=0.0651, live-achievable n=1312, PF=1.236, expectancy=0.149R, suppression%=0.0, edge_lives_in_suppressed=False
2. **Breaker_5m_short** — decorr=0.0651, live-achievable n=852, PF=1.162, expectancy=0.113R, suppression%=3.73, edge_lives_in_suppressed=False
3. **Breaker_5m_long** — decorr=0.0685, live-achievable n=886, PF=1.234, expectancy=0.158R, suppression%=2.76, edge_lives_in_suppressed=False
4. **IFVG_5m_long** — decorr=0.0721, live-achievable n=1369, PF=1.342, expectancy=0.279R, suppression%=2.09, edge_lives_in_suppressed=False
5. **MSS_15m_long** — decorr=0.0779, live-achievable n=747, PF=1.105, expectancy=0.028R, suppression%=0.0, edge_lives_in_suppressed=False
6. **IFVG_15m_short** — decorr=0.08, live-achievable n=518, PF=1.427, expectancy=0.338R, suppression%=6.11, edge_lives_in_suppressed=False
7. **FVG_15m_long** — decorr=0.0844, live-achievable n=642, PF=1.355, expectancy=0.275R, suppression%=0.0, edge_lives_in_suppressed=False
8. **Breaker_15m_short** — decorr=0.0893, live-achievable n=352, PF=1.231, expectancy=0.160R, suppression%=0.13, edge_lives_in_suppressed=False
9. **OB_1m_long** — decorr=0.0899, live-achievable n=4138, PF=1.403, expectancy=0.249R, suppression%=22.05, edge_lives_in_suppressed=False
10. **IFVG_5m_short** — decorr=0.0911, live-achievable n=1529, PF=1.324, expectancy=0.269R, suppression%=4.44, edge_lives_in_suppressed=False
11. **FVG_5m_long** — decorr=0.0927, live-achievable n=1810, PF=1.488, expectancy=0.378R, suppression%=0.0, edge_lives_in_suppressed=False
12. **Breaker_1m_short** — decorr=0.0992, live-achievable n=2685, PF=1.470, expectancy=0.292R, suppression%=27.46, edge_lives_in_suppressed=False
13. **FVG_5m_short** — decorr=0.105, live-achievable n=1739, PF=1.465, expectancy=0.368R, suppression%=0.0, edge_lives_in_suppressed=False
14. **Breaker_1m_long** — decorr=0.1105, live-achievable n=2643, PF=1.503, expectancy=0.312R, suppression%=27.62, edge_lives_in_suppressed=False
15. **OB_1m_short** — decorr=0.1118, live-achievable n=4070, PF=1.313, expectancy=0.206R, suppression%=21.57, edge_lives_in_suppressed=False
16. **IFVG_1m_short** — decorr=0.1442, live-achievable n=4239, PF=1.908, expectancy=0.647R, suppression%=34.43, edge_lives_in_suppressed=False
17. **IFVG_1m_long** — decorr=0.146, live-achievable n=4122, PF=1.973, expectancy=0.666R, suppression%=36.36, edge_lives_in_suppressed=False
18. **FVG_1m_long** — decorr=0.1615, live-achievable n=5741, PF=1.952, expectancy=0.657R, suppression%=28.06, edge_lives_in_suppressed=False
19. **FVG_1m_short** — decorr=0.164, live-achievable n=5762, PF=1.837, expectancy=0.590R, suppression%=26.64, edge_lives_in_suppressed=False

## 7. Correlation matrix (daily-R Pearson, holdout)

| | FVG_1m_long | Breaker_5m_long | FVG_5m_short | FVG_1m_short | IFVG_5m_short | Breaker_1m_short | FVG_5m_long | IFVG_5m_long | Breaker_1m_long | FVG_15m_long | OB_1m_long | IFVG_1m_long | IFVG_1m_short | Breaker_15m_short | IFVG_15m_short | MSS_15m_long | OB_5m_long | OB_1m_short | Breaker_5m_short | ProfileA_OTE | VPC_ProfileB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FVG_1m_long | 1.000 | 0.109 | 0.149 | 0.352 | 0.179 | 0.266 | 0.095 | 0.107 | 0.254 | 0.110 | 0.216 | 0.443 | 0.384 | -0.063 | 0.092 | 0.021 | 0.062 | 0.197 | 0.100 | -0.005 | -0.025 |
| Breaker_5m_long | 0.109 | 1.000 | 0.051 | 0.061 | 0.115 | 0.080 | -0.081 | -0.074 | 0.009 | 0.040 | 0.084 | 0.109 | 0.084 | 0.062 | 0.129 | -0.050 | 0.133 | -0.006 | 0.044 | 0.013 | 0.035 |
| FVG_5m_short | 0.149 | 0.051 | 1.000 | 0.179 | 0.196 | 0.104 | -0.071 | 0.007 | -0.046 | 0.008 | -0.028 | 0.126 | 0.203 | 0.147 | 0.188 | -0.120 | -0.031 | 0.154 | 0.183 | 0.034 | -0.074 |
| FVG_1m_short | 0.352 | 0.061 | 0.179 | 1.000 | 0.240 | 0.285 | 0.072 | 0.073 | 0.201 | -0.117 | 0.233 | 0.335 | 0.460 | 0.068 | 0.025 | -0.054 | -0.047 | 0.304 | 0.062 | 0.086 | 0.026 |
| IFVG_5m_short | 0.179 | 0.115 | 0.196 | 0.240 | 1.000 | 0.058 | 0.101 | 0.132 | -0.021 | -0.031 | 0.035 | 0.074 | 0.121 | 0.128 | 0.090 | -0.030 | -0.044 | 0.135 | -0.009 | 0.066 | 0.018 |
| Breaker_1m_short | 0.266 | 0.080 | 0.104 | 0.285 | 0.058 | 1.000 | 0.065 | -0.075 | 0.110 | 0.005 | -0.019 | 0.239 | 0.231 | 0.069 | 0.052 | -0.081 | 0.009 | 0.184 | 0.028 | 0.001 | 0.022 |
| FVG_5m_long | 0.095 | -0.081 | -0.071 | 0.072 | 0.101 | 0.065 | 1.000 | 0.186 | 0.203 | 0.155 | 0.125 | 0.226 | 0.001 | -0.006 | -0.011 | 0.197 | 0.051 | 0.073 | 0.088 | 0.002 | 0.043 |
| IFVG_5m_long | 0.107 | -0.074 | 0.007 | 0.073 | 0.132 | -0.075 | 0.186 | 1.000 | 0.149 | 0.137 | -0.010 | 0.040 | 0.060 | 0.045 | 0.022 | 0.105 | -0.071 | 0.010 | 0.016 | 0.103 | -0.018 |
| Breaker_1m_long | 0.254 | 0.009 | -0.046 | 0.201 | -0.021 | 0.110 | 0.203 | 0.149 | 1.000 | 0.124 | 0.151 | 0.260 | 0.189 | -0.065 | 0.108 | 0.034 | 0.053 | 0.108 | -0.017 | -0.046 | 0.062 |
| FVG_15m_long | 0.110 | 0.040 | 0.008 | -0.117 | -0.031 | 0.005 | 0.155 | 0.137 | 0.124 | 1.000 | -0.006 | 0.102 | 0.141 | 0.031 | 0.019 | 0.104 | 0.131 | 0.105 | -0.063 | 0.126 | 0.131 |
| OB_1m_long | 0.216 | 0.084 | -0.028 | 0.233 | 0.035 | -0.019 | 0.125 | -0.010 | 0.151 | -0.006 | 1.000 | 0.144 | 0.149 | -0.157 | 0.006 | 0.158 | 0.151 | -0.018 | 0.063 | -0.036 | 0.010 |
| IFVG_1m_long | 0.443 | 0.109 | 0.126 | 0.335 | 0.074 | 0.239 | 0.226 | 0.040 | 0.260 | 0.102 | 0.144 | 1.000 | 0.286 | -0.033 | 0.116 | 0.023 | 0.002 | 0.254 | 0.058 | -0.027 | 0.021 |
| IFVG_1m_short | 0.384 | 0.084 | 0.203 | 0.460 | 0.121 | 0.231 | 0.001 | 0.060 | 0.189 | 0.141 | 0.149 | 0.286 | 1.000 | 0.089 | 0.022 | -0.053 | 0.019 | 0.244 | 0.080 | 0.021 | -0.047 |
| Breaker_15m_short | -0.063 | 0.062 | 0.147 | 0.068 | 0.128 | 0.069 | -0.006 | 0.045 | -0.065 | 0.031 | -0.157 | -0.033 | 0.089 | 1.000 | 0.215 | -0.070 | -0.093 | 0.127 | 0.091 | 0.078 | 0.148 |
| IFVG_15m_short | 0.092 | 0.129 | 0.188 | 0.025 | 0.090 | 0.052 | -0.011 | 0.022 | 0.108 | 0.019 | 0.006 | 0.116 | 0.022 | 0.215 | 1.000 | -0.142 | 0.019 | 0.141 | 0.078 | -0.069 | -0.057 |
| MSS_15m_long | 0.021 | -0.050 | -0.120 | -0.054 | -0.030 | -0.081 | 0.197 | 0.105 | 0.034 | 0.104 | 0.158 | 0.023 | -0.053 | -0.070 | -0.142 | 1.000 | 0.153 | -0.047 | -0.030 | 0.009 | 0.079 |
| OB_5m_long | 0.062 | 0.133 | -0.031 | -0.047 | -0.044 | 0.009 | 0.051 | -0.071 | 0.053 | 0.131 | 0.151 | 0.002 | 0.019 | -0.093 | 0.019 | 0.153 | 1.000 | 0.041 | -0.084 | 0.021 | 0.090 |
| OB_1m_short | 0.197 | -0.006 | 0.154 | 0.304 | 0.135 | 0.184 | 0.073 | 0.010 | 0.108 | 0.105 | -0.018 | 0.254 | 0.244 | 0.127 | 0.141 | -0.047 | 0.041 | 1.000 | 0.003 | 0.024 | -0.061 |
| Breaker_5m_short | 0.100 | 0.044 | 0.183 | 0.062 | -0.009 | 0.028 | 0.088 | 0.016 | -0.017 | -0.063 | 0.063 | 0.058 | 0.080 | 0.091 | 0.078 | -0.030 | -0.084 | 0.003 | 1.000 | -0.081 | -0.121 |
| ProfileA_OTE | -0.005 | 0.013 | 0.034 | 0.086 | 0.066 | 0.001 | 0.002 | 0.103 | -0.046 | 0.126 | -0.036 | -0.027 | 0.021 | 0.078 | -0.069 | 0.009 | 0.021 | 0.024 | -0.081 | 1.000 | 0.126 |
| VPC_ProfileB | -0.025 | 0.035 | -0.074 | 0.026 | 0.018 | 0.022 | 0.043 | -0.018 | 0.062 | 0.131 | 0.010 | 0.021 | -0.047 | 0.148 | -0.057 | 0.079 | 0.090 | -0.061 | -0.121 | 0.126 | 1.000 |

Profile A (achievable, in-window) n=74; VPC/Profile B (in-window) n=98.

## 8. Graveyard (cause of death)

| cell | cause of death |
|---|---|
| FVG_15m_short | FDR miss (Gate B: p=0.1095 > BH cutoff 0.0442) |
| IFVG_15m_long | FDR miss (Gate B: p=0.0606 > BH cutoff 0.0442) |
| OB_5m_short | FDR miss (Gate B: p=0.2668 > BH cutoff 0.0442) |
| OB_15m_long | FDR miss (Gate B: p=0.1426 > BH cutoff 0.0442) |
| OB_15m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Breaker_15m_long | FDR miss (Gate B: p=0.1990 > BH cutoff 0.0442) |
| Sweep_1m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Sweep_1m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Sweep_5m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Sweep_5m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Sweep_15m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Sweep_15m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| MSS_1m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| MSS_1m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| MSS_5m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| MSS_5m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| MSS_15m_short | FDR miss (Gate B: p=0.3297 > BH cutoff 0.0442) |

## 9. Documented literal-reading resolutions

- **Gate B correction scope**: one-sided block-bootstrap p-values computed for ALL 36 cells
  (not just Gate-A survivors); BH-FDR (q=0.10) applied across the full N=36 ladder, per PREREG
  §4/§5/§7's repeated "across all N=36 cells." A cell needs Gate A AND Gate B to reach Gate C.
- **Gate B block length**: block length (in trades) = round(5 x that cell's own holdout
  trades-per-day), trades-per-day = cell's holdout n / 313 (unique ET calendar days with data
  in the holdout window) — "block length ~ weekly" read as 5 TRADING days of THAT cell's own
  trade cadence (PREREG's explicit wording), not 5 calendar days of raw time.
- **Gate C entry count**: "same number of entries" read as the real cell's REALIZED holdout
  trade count n (an "entry" = an executed position), not the raw pre-filter signal count.
- **Order Block "last opposing candle immediately before a displacement candle"**: read
  literally as candle i-1 exactly (no backward scan). If i-1 is not opposite-colored, no OB
  forms at that displacement bar (this is disclosed as a strict reading, not a scan-back rule).
- **IFVG inversion search horizon**: PREREG states no explicit window for "far edge closed
  through inverts"; bounded to 100 signal-TF bars, borrowing the Breaker Block's explicit
  fail-window (PREREG §6.4) for consistency and to keep detection O(n).
- **Sweep/MSS "most recent confirmed swing level"**: read as the level known as of the PRIOR
  bar (must pre-exist the bar that acts on it); the break/reclaim bar's own close is compared
  same-bar (matches the cited code's own elementwise convention).
- **MSS/BOS firing**: fires once per break (transition from not-broken to broken), not on every
  bar price remains beyond the level.
- **EOD flat / exchange day**: CME session boundary taken as 17:00 ET; a bar's trading day rolls
  forward at/after 17:00 ET; EOD-flat cutoff = 16:55 ET of the SIGNAL's (conf_ts) exchange day,
  applied to both the limit-order lifetime clock and the exit-management scan.
- **Window/split boundaries**: treated as UTC calendar timestamps (PREREG does not specify a tz
  for 2024-06-22 / 2025-06-22 / 2026-06-22).
- **Gate D**: "signal surfaces at first poll >= confirmation instant" (5m poll cadence);
  "limit entries placed AT that poll" -> the order's fill-search window is re-walked starting at
  poll_ts (not conf_ts), with the SAME absolute lifetime/EOD end anchored to conf_ts. The literal
  10-minute certified_gate staleness test is ALSO computed and reported, but is structurally
  ~0% for this survey: unlike Profile A's multi-stage internal state machine, every concept here
  has a single-instant confirmation with no extra internal lag, so the only latency source is the
  <=5-minute poll cadence itself — always under the 10-minute threshold. The substantive
  deployability effect is the poll-delay re-walk (a trade can be missed/repriced by minutes).

## 10. Anti-pattern compliance
- No train/full-window number presented as a finding above (train shown only for context alongside holdout/live-achievable).
- No per-concept tuning, no sweeps, no composites — one fixed execution template for all 36 cells.
- Single-vendor Databento data only; no other data file read by the harness.
- Survey only: no arming, no change to any existing frozen edge, no LIVE HOLD change.
