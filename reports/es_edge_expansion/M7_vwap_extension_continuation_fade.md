# ES Edge Expansion — Lane C — M7: VWAP Extension Continuation/Fade Guardrail

RESEARCH ONLY. LIVE HOLD ACTIVE. CFD-proxy caveat applies to every number (see `01_data_validation.md`). Valid-day mask applied (density>=95% OR half-day profile): 2639/2678 days used. Full methodology in `lane_c_m7.py` module docstring.

## THE M7 BEHAVIOUR VERDICT (read this first)

**ES MATCHES NQ — extensions win the race in every bucket, every year with data. Retire ES VWAP-fade permanently; continuation-only grid.**

NQ prior (task brief): extensions CONTINUE 11/11 years, all buckets — killed every NQ VWAP-fade family. Per-bucket pooled race (60m horizon), ES 2016-2026:

| bucket | n | revert_share_60m | extend_share_60m | extend_wins_pooled | years_extend_wins | years_total |
|---|---|---|---|---|---|---|
| 1.0-1.5 | 26981 | 0.3487 | 0.5472 | True | 11 | 11 |
| 1.5-2.0 | 21633 | 0.2521 | 0.5663 | True | 11 | 11 |
| 2.0-2.5 | 17263 | 0.1806 | 0.5791 | True | 11 | 11 |
| >2.5 | 62516 | 0.0681 | 0.5866 | True | 11 | 11 |

## PART 1 — full race table (30m + 60m, all bucket x tod cells)

Race event count (bucket-bar qualifying events, valid days only): 128393

### 60m horizon

| bucket | tod | outcome | n | share | n_years_match | n_years_total | consistent |
|---|---|---|---|---|---|---|---|
| 1.0-1.5 | mid_1100_1330 | extend | 11365 | 0.5739 | 11 | 11 | True |
| 1.0-1.5 | mid_1100_1330 | neither | 11365 | 0.0788 | 11 | 11 | True |
| 1.0-1.5 | mid_1100_1330 | revert | 11365 | 0.3423 | 11 | 11 | True |
| 1.0-1.5 | mid_1100_1330 | tie | 11365 | 0.0051 | 11 | 11 | True |
| 1.0-1.5 | post_1330 | extend | 8240 | 0.5642 | 11 | 11 | True |
| 1.0-1.5 | post_1330 | neither | 8240 | 0.1163 | 11 | 11 | True |
| 1.0-1.5 | post_1330 | revert | 8240 | 0.3107 | 11 | 11 | True |
| 1.0-1.5 | post_1330 | tie | 8240 | 0.0089 | 11 | 11 | True |
| 1.0-1.5 | pre_1100 | extend | 7376 | 0.487 | 11 | 11 | True |
| 1.0-1.5 | pre_1100 | neither | 7376 | 0.1093 | 11 | 11 | True |
| 1.0-1.5 | pre_1100 | revert | 7376 | 0.4012 | 11 | 11 | True |
| 1.0-1.5 | pre_1100 | tie | 7376 | 0.0026 | 11 | 11 | True |
| 1.5-2.0 | mid_1100_1330 | extend | 9692 | 0.5938 | 11 | 11 | True |
| 1.5-2.0 | mid_1100_1330 | neither | 9692 | 0.1601 | 11 | 11 | True |
| 1.5-2.0 | mid_1100_1330 | revert | 9692 | 0.2438 | 8 | 11 | True |
| 1.5-2.0 | mid_1100_1330 | tie | 9692 | 0.0023 | 11 | 11 | True |
| 1.5-2.0 | post_1330 | extend | 7745 | 0.5872 | 11 | 11 | True |
| 1.5-2.0 | post_1330 | neither | 7745 | 0.1751 | 11 | 11 | True |
| 1.5-2.0 | post_1330 | revert | 7745 | 0.2338 | 8 | 11 | True |
| 1.5-2.0 | post_1330 | tie | 7745 | 0.0039 | 11 | 11 | True |
| 1.5-2.0 | pre_1100 | extend | 4196 | 0.4643 | 11 | 11 | True |
| 1.5-2.0 | pre_1100 | neither | 4196 | 0.2293 | 6 | 11 | False |
| 1.5-2.0 | pre_1100 | revert | 4196 | 0.3051 | 11 | 11 | True |
| 1.5-2.0 | pre_1100 | tie | 4196 | 0.0014 | 11 | 11 | True |
| 2.0-2.5 | mid_1100_1330 | extend | 8116 | 0.6012 | 11 | 11 | True |
| 2.0-2.5 | mid_1100_1330 | neither | 8116 | 0.2266 | 8 | 11 | True |
| 2.0-2.5 | mid_1100_1330 | revert | 8116 | 0.1707 | 11 | 11 | True |
| 2.0-2.5 | mid_1100_1330 | tie | 8116 | 0.0016 | 11 | 11 | True |
| 2.0-2.5 | post_1330 | extend | 7056 | 0.5999 | 11 | 11 | True |
| 2.0-2.5 | post_1330 | neither | 7056 | 0.2177 | 9 | 11 | True |
| 2.0-2.5 | post_1330 | revert | 7056 | 0.181 | 11 | 11 | True |
| 2.0-2.5 | post_1330 | tie | 7056 | 0.0014 | 11 | 11 | True |
| 2.0-2.5 | pre_1100 | extend | 2091 | 0.4232 | 11 | 11 | True |
| 2.0-2.5 | pre_1100 | neither | 2091 | 0.3587 | 9 | 11 | True |
| 2.0-2.5 | pre_1100 | revert | 2091 | 0.2181 | 7 | 11 | False |
| 2.0-2.5 | pre_1100 | tie | 2091 | 0.0 | 11 | 11 | True |
| >2.5 | mid_1100_1330 | extend | 24493 | 0.5851 | 11 | 11 | True |
| >2.5 | mid_1100_1330 | neither | 24493 | 0.3421 | 11 | 11 | True |
| >2.5 | mid_1100_1330 | revert | 24493 | 0.0717 | 11 | 11 | True |
| >2.5 | mid_1100_1330 | tie | 24493 | 0.0011 | 11 | 11 | True |
| >2.5 | post_1330 | extend | 36513 | 0.5941 | 11 | 11 | True |
| >2.5 | post_1330 | neither | 36513 | 0.3417 | 11 | 11 | True |
| >2.5 | post_1330 | revert | 36513 | 0.0635 | 11 | 11 | True |
| >2.5 | post_1330 | tie | 36513 | 0.0007 | 11 | 11 | True |
| >2.5 | pre_1100 | extend | 1510 | 0.4318 | 11 | 11 | True |
| >2.5 | pre_1100 | neither | 1510 | 0.4477 | 11 | 11 | True |
| >2.5 | pre_1100 | revert | 1510 | 0.1205 | 11 | 11 | True |
| >2.5 | pre_1100 | tie | 1510 | 0.0 | 11 | 11 | True |

### 30m horizon

| bucket | tod | outcome | n | share | n_years_match | n_years_total | consistent |
|---|---|---|---|---|---|---|---|
| 1.0-1.5 | mid_1100_1330 | extend | 11365 | 0.4911 | 11 | 11 | True |
| 1.0-1.5 | mid_1100_1330 | neither | 11365 | 0.2623 | 6 | 11 | False |
| 1.0-1.5 | mid_1100_1330 | revert | 11365 | 0.2433 | 9 | 11 | True |
| 1.0-1.5 | mid_1100_1330 | tie | 11365 | 0.0033 | 11 | 11 | True |
| 1.0-1.5 | post_1330 | extend | 8240 | 0.5166 | 11 | 11 | True |
| 1.0-1.5 | post_1330 | neither | 8240 | 0.2175 | 7 | 11 | False |
| 1.0-1.5 | post_1330 | revert | 8240 | 0.258 | 8 | 11 | True |
| 1.0-1.5 | post_1330 | tie | 8240 | 0.0079 | 11 | 11 | True |
| 1.0-1.5 | pre_1100 | extend | 7376 | 0.402 | 11 | 11 | True |
| 1.0-1.5 | pre_1100 | neither | 7376 | 0.3084 | 11 | 11 | True |
| 1.0-1.5 | pre_1100 | revert | 7376 | 0.287 | 9 | 11 | True |
| 1.0-1.5 | pre_1100 | tie | 7376 | 0.0026 | 11 | 11 | True |
| 1.5-2.0 | mid_1100_1330 | extend | 9692 | 0.4889 | 11 | 11 | True |
| 1.5-2.0 | mid_1100_1330 | neither | 9692 | 0.3768 | 11 | 11 | True |
| 1.5-2.0 | mid_1100_1330 | revert | 9692 | 0.1328 | 11 | 11 | True |
| 1.5-2.0 | mid_1100_1330 | tie | 9692 | 0.0015 | 11 | 11 | True |
| 1.5-2.0 | post_1330 | extend | 7745 | 0.5201 | 11 | 11 | True |
| 1.5-2.0 | post_1330 | neither | 7745 | 0.3081 | 11 | 11 | True |
| 1.5-2.0 | post_1330 | revert | 7745 | 0.169 | 11 | 11 | True |
| 1.5-2.0 | post_1330 | tie | 7745 | 0.0028 | 11 | 11 | True |
| 1.5-2.0 | pre_1100 | extend | 4196 | 0.3704 | 11 | 11 | True |
| 1.5-2.0 | pre_1100 | neither | 4196 | 0.4673 | 11 | 11 | True |
| 1.5-2.0 | pre_1100 | revert | 4196 | 0.1613 | 11 | 11 | True |
| 1.5-2.0 | pre_1100 | tie | 4196 | 0.001 | 11 | 11 | True |
| 2.0-2.5 | mid_1100_1330 | extend | 8116 | 0.4932 | 11 | 11 | True |
| 2.0-2.5 | mid_1100_1330 | neither | 8116 | 0.432 | 11 | 11 | True |
| 2.0-2.5 | mid_1100_1330 | revert | 8116 | 0.0742 | 11 | 11 | True |
| 2.0-2.5 | mid_1100_1330 | tie | 8116 | 0.0006 | 11 | 11 | True |
| 2.0-2.5 | post_1330 | extend | 7056 | 0.5225 | 11 | 11 | True |
| 2.0-2.5 | post_1330 | neither | 7056 | 0.3696 | 11 | 11 | True |
| 2.0-2.5 | post_1330 | revert | 7056 | 0.107 | 11 | 11 | True |
| 2.0-2.5 | post_1330 | tie | 7056 | 0.0009 | 11 | 11 | True |
| 2.0-2.5 | pre_1100 | extend | 2091 | 0.3372 | 10 | 11 | True |
| 2.0-2.5 | pre_1100 | neither | 2091 | 0.583 | 11 | 11 | True |
| 2.0-2.5 | pre_1100 | revert | 2091 | 0.0799 | 11 | 11 | True |
| 2.0-2.5 | pre_1100 | tie | 2091 | 0.0 | 11 | 11 | True |
| >2.5 | mid_1100_1330 | extend | 24493 | 0.4763 | 11 | 11 | True |
| >2.5 | mid_1100_1330 | neither | 24493 | 0.5017 | 11 | 11 | True |
| >2.5 | mid_1100_1330 | revert | 24493 | 0.0218 | 11 | 11 | True |
| >2.5 | mid_1100_1330 | tie | 24493 | 0.0003 | 11 | 11 | True |
| >2.5 | post_1330 | extend | 36513 | 0.5129 | 11 | 11 | True |
| >2.5 | post_1330 | neither | 36513 | 0.4606 | 11 | 11 | True |
| >2.5 | post_1330 | revert | 36513 | 0.0259 | 11 | 11 | True |
| >2.5 | post_1330 | tie | 36513 | 0.0006 | 11 | 11 | True |
| >2.5 | pre_1100 | extend | 1510 | 0.3589 | 11 | 11 | True |
| >2.5 | pre_1100 | neither | 1510 | 0.6093 | 11 | 11 | True |
| >2.5 | pre_1100 | revert | 1510 | 0.0318 | 11 | 11 | True |
| >2.5 | pre_1100 | tie | 1510 | 0.0 | 11 | 11 | True |

## PART 2 — strategy grid

Qualifying bar-events (pre-entry-logic, any bucket/tod, valid days): 128393 (236.89/wk)

Fade grid run: False (per the verdict above).

Columns: n/tr_wk/wr/pf/expR/totR/maxDD_R are pooled 2016-2026 R-multiple metrics (1m-truth adverse-first exits, cost=1.0pt RT). `flag`: dead (PF<1.15), freeze (PF>1.8), mirage (edge concentrated in <3 years), sub_floor (<0.3 tr/wk), N/A_geometrically_invalid (VWAP-target exit on a continuation trade), live_candidate (passes all screens).

| grid_direction | entry_type | stop_mult | exit_type | n | tr_wk | wr | pf | expR | totR | maxDD_R | flag | n_no_pullback_skip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| continuation | next_bar_open | 1.0 | vwap_target | 0 | 0.0 | nan | nan | nan | 0.0 | 0.0 | N/A_geometrically_invalid | nan |
| continuation | next_bar_open | 1.5 | vwap_target | 0 | 0.0 | nan | nan | nan | 0.0 | 0.0 | N/A_geometrically_invalid | nan |
| continuation | pullback_after_extension | 1.0 | vwap_target | 0 | 0.0 | nan | nan | nan | 0.0 | 0.0 | N/A_geometrically_invalid | nan |
| continuation | pullback_after_extension | 1.5 | vwap_target | 0 | 0.0 | nan | nan | nan | 0.0 | 0.0 | N/A_geometrically_invalid | nan |
| continuation | next_bar_open | 1.0 | 1.5R | 126392 | 233.196 | 0.3987 | 0.527 | -0.3921 | -49562.299 | -49561.099 | dead | 0.0 |
| continuation | next_bar_open | 1.0 | trail | 126392 | 233.196 | 0.2689 | 0.4335 | -0.3743 | -47305.38 | -47304.37 | dead | 0.0 |
| continuation | next_bar_open | 1.5 | 1.5R | 126392 | 233.196 | 0.4096 | 0.6572 | -0.2453 | -31006.861 | -31126.909 | dead | 0.0 |
| continuation | next_bar_open | 1.5 | trail | 126392 | 233.196 | 0.3031 | 0.5726 | -0.2347 | -29668.348 | -29766.01 | dead | 0.0 |
| continuation | pullback_after_extension | 1.0 | 1.5R | 118743 | 219.083 | 0.4023 | 0.5416 | -0.3751 | -44540.351 | -44541.927 | dead | 9650.0 |
| continuation | pullback_after_extension | 1.0 | trail | 118743 | 219.083 | 0.2711 | 0.4434 | -0.3624 | -43032.113 | -43031.423 | dead | 9650.0 |
| continuation | pullback_after_extension | 1.5 | 1.5R | 118743 | 219.083 | 0.4107 | 0.6656 | -0.2373 | -28172.202 | -28366.73 | dead | 9650.0 |
| continuation | pullback_after_extension | 1.5 | trail | 118743 | 219.083 | 0.3053 | 0.5855 | -0.2251 | -26731.186 | -26898.963 | dead | 9650.0 |

## Live candidates: 0

None — every M7 strategy cell is dead/freeze/mirage/sub-floor/N-A.


## Runtime: 130.4s
