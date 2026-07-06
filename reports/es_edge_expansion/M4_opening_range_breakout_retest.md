# ES Edge Expansion — Lane B — M4: Opening-Range Breakout / Retest

**CFD proxy, documented optimistic bias vs real futures; graduates need real CME data before certification.** RESEARCH ONLY. LIVE HOLD ACTIVE. No commits.

Valid days: 2639 / 2678 (98.5%). Weeks span: 541.6.

## Stage A — coarse grid (OR-def x breakout x entry x stop, exit=1.5R, filter=none, 54 cells)

| or_def | breakout | entry | stop | n_events | n | tr_per_wk | wr | pf | exp_r | tot_r | maxdd_r | n_long | n_short |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30m | close_outside | retest | atr_1.5 | 2618 | 2071 | 3.824 | 0.485 | 0.964 | -0.005 | -9.666 | -38.555 | 1096 | 975 |
| 15m | two_closes_outside | retest | atr_1.5 | 2623 | 1732 | 3.198 | 0.480 | 0.956 | -0.006 | -9.789 | -28.149 | 918 | 814 |
| 5m | close_outside | retest | atr_1.5 | 2639 | 2124 | 3.922 | 0.478 | 0.959 | -0.006 | -12.751 | -24.491 | 1094 | 1030 |
| 5m | two_closes_outside | retest | atr_1.5 | 2636 | 1807 | 3.337 | 0.468 | 0.940 | -0.009 | -15.361 | -25.616 | 904 | 903 |
| 30m | body_ratio | retest | atr_1.5 | 2604 | 1849 | 3.414 | 0.478 | 0.926 | -0.010 | -17.681 | -36.938 | 967 | 882 |
| 15m | two_closes_outside | immediate | atr_1.5 | 2623 | 2609 | 4.817 | 0.486 | 0.949 | -0.007 | -18.216 | -45.554 | 1408 | 1201 |
| 15m | body_ratio | immediate | atr_1.5 | 2631 | 2617 | 4.832 | 0.488 | 0.943 | -0.008 | -20.708 | -47.612 | 1378 | 1239 |
| 15m | close_outside | immediate | atr_1.5 | 2635 | 2621 | 4.840 | 0.482 | 0.944 | -0.008 | -21.046 | -51.490 | 1372 | 1249 |
| 30m | two_closes_outside | retest | atr_1.5 | 2592 | 1730 | 3.194 | 0.469 | 0.905 | -0.012 | -21.258 | -37.202 | 939 | 791 |
| 5m | close_outside | immediate | atr_1.5 | 2639 | 2625 | 4.847 | 0.484 | 0.944 | -0.008 | -22.141 | -37.895 | 1375 | 1250 |
| 15m | close_outside | retest | atr_1.5 | 2635 | 2081 | 3.843 | 0.478 | 0.921 | -0.011 | -22.870 | -42.623 | 1067 | 1014 |
| 5m | body_ratio | immediate | atr_1.5 | 2639 | 2625 | 4.847 | 0.485 | 0.935 | -0.010 | -25.202 | -50.849 | 1365 | 1260 |
| 5m | body_ratio | retest | atr_1.5 | 2639 | 1855 | 3.425 | 0.467 | 0.902 | -0.014 | -26.191 | -40.895 | 928 | 927 |
| 15m | body_ratio | retest | atr_1.5 | 2631 | 1839 | 3.396 | 0.473 | 0.893 | -0.014 | -26.632 | -45.691 | 929 | 910 |
| 5m | two_closes_outside | immediate | atr_1.5 | 2636 | 2622 | 4.841 | 0.474 | 0.929 | -0.011 | -27.670 | -36.819 | 1371 | 1251 |
| 30m | close_outside | immediate | atr_1.5 | 2618 | 2601 | 4.803 | 0.483 | 0.921 | -0.011 | -27.899 | -54.218 | 1414 | 1187 |
| 30m | body_ratio | immediate | atr_1.5 | 2604 | 2587 | 4.777 | 0.481 | 0.898 | -0.014 | -35.326 | -53.995 | 1411 | 1176 |
| 30m | two_closes_outside | immediate | atr_1.5 | 2592 | 2576 | 4.757 | 0.480 | 0.887 | -0.015 | -39.030 | -58.774 | 1427 | 1149 |
| 15m | two_closes_outside | immediate | inside_range_0.5atr | 2623 | 2609 | 4.817 | 0.470 | 0.945 | -0.021 | -54.791 | -115.126 | 1408 | 1201 |
| 15m | two_closes_outside | retest | inside_range_0.5atr | 2623 | 1732 | 3.198 | 0.461 | 0.915 | -0.032 | -54.915 | -88.963 | 918 | 814 |
| 15m | close_outside | immediate | inside_range_0.5atr | 2635 | 2621 | 4.840 | 0.467 | 0.945 | -0.022 | -56.968 | -109.325 | 1372 | 1249 |
| 15m | body_ratio | immediate | inside_range_0.5atr | 2631 | 2617 | 4.832 | 0.472 | 0.943 | -0.022 | -57.363 | -119.383 | 1378 | 1239 |
| 15m | close_outside | retest | inside_range_0.5atr | 2635 | 2081 | 3.843 | 0.462 | 0.920 | -0.031 | -65.052 | -95.871 | 1067 | 1014 |
| 5m | two_closes_outside | retest | inside_range_0.5atr | 2636 | 1807 | 3.337 | 0.447 | 0.892 | -0.043 | -77.377 | -85.753 | 904 | 903 |
| 5m | body_ratio | immediate | inside_range_0.5atr | 2639 | 2625 | 4.847 | 0.463 | 0.924 | -0.031 | -80.590 | -98.857 | 1365 | 1260 |
| 30m | close_outside | retest | inside_range_0.5atr | 2618 | 2071 | 3.824 | 0.463 | 0.892 | -0.041 | -84.107 | -101.955 | 1096 | 975 |
| 15m | body_ratio | retest | inside_range_0.5atr | 2631 | 1839 | 3.396 | 0.456 | 0.879 | -0.046 | -84.663 | -114.442 | 929 | 910 |
| 30m | body_ratio | immediate | inside_range_0.5atr | 2604 | 2587 | 4.777 | 0.467 | 0.910 | -0.033 | -85.726 | -123.282 | 1411 | 1176 |
| 5m | close_outside | retest | inside_range_0.5atr | 2639 | 2124 | 3.922 | 0.452 | 0.902 | -0.040 | -85.911 | -88.913 | 1094 | 1030 |
| 30m | close_outside | immediate | inside_range_0.5atr | 2618 | 2601 | 4.803 | 0.466 | 0.909 | -0.035 | -89.979 | -121.333 | 1414 | 1187 |
| 5m | two_closes_outside | immediate | inside_range_0.5atr | 2636 | 2622 | 4.841 | 0.453 | 0.915 | -0.035 | -90.723 | -110.545 | 1371 | 1251 |
| 5m | close_outside | immediate | inside_range_0.5atr | 2639 | 2625 | 4.847 | 0.456 | 0.915 | -0.035 | -92.850 | -100.300 | 1375 | 1250 |
| 30m | body_ratio | retest | inside_range_0.5atr | 2604 | 1849 | 3.414 | 0.456 | 0.864 | -0.050 | -93.168 | -102.116 | 967 | 882 |
| 5m | body_ratio | retest | inside_range_0.5atr | 2639 | 1855 | 3.425 | 0.446 | 0.865 | -0.055 | -101.429 | -115.874 | 928 | 927 |
| 30m | two_closes_outside | immediate | inside_range_0.5atr | 2592 | 2576 | 4.757 | 0.465 | 0.893 | -0.040 | -101.836 | -134.501 | 1427 | 1149 |
| 30m | two_closes_outside | retest | inside_range_0.5atr | 2592 | 1730 | 3.194 | 0.447 | 0.832 | -0.063 | -108.263 | -117.539 | 939 | 791 |
| 30m | body_ratio | immediate | opposite_or_side | 2604 | 2587 | 4.777 | 0.452 | 0.887 | -0.052 | -134.451 | -167.225 | 1411 | 1176 |
| 30m | two_closes_outside | immediate | opposite_or_side | 2592 | 2576 | 4.757 | 0.452 | 0.879 | -0.054 | -139.660 | -168.658 | 1427 | 1149 |
| 30m | body_ratio | retest | opposite_or_side | 2604 | 1849 | 3.414 | 0.436 | 0.848 | -0.079 | -145.649 | -156.882 | 967 | 882 |
| 30m | close_outside | retest | opposite_or_side | 2618 | 2071 | 3.824 | 0.438 | 0.861 | -0.073 | -151.318 | -158.202 | 1096 | 975 |
| 15m | two_closes_outside | immediate | opposite_or_side | 2623 | 2609 | 4.817 | 0.441 | 0.888 | -0.059 | -154.322 | -202.811 | 1408 | 1201 |
| 30m | close_outside | immediate | opposite_or_side | 2618 | 2601 | 4.803 | 0.443 | 0.871 | -0.063 | -163.178 | -195.855 | 1414 | 1187 |
| 15m | body_ratio | immediate | opposite_or_side | 2631 | 2617 | 4.832 | 0.442 | 0.881 | -0.064 | -167.571 | -200.022 | 1378 | 1239 |
| 30m | two_closes_outside | retest | opposite_or_side | 2592 | 1730 | 3.194 | 0.421 | 0.796 | -0.107 | -185.803 | -197.320 | 939 | 791 |
| 15m | close_outside | immediate | opposite_or_side | 2635 | 2621 | 4.840 | 0.433 | 0.872 | -0.073 | -191.220 | -230.007 | 1372 | 1249 |
| 15m | two_closes_outside | retest | opposite_or_side | 2623 | 1732 | 3.198 | 0.416 | 0.797 | -0.125 | -216.438 | -233.057 | 918 | 814 |
| 15m | body_ratio | retest | opposite_or_side | 2631 | 1839 | 3.396 | 0.411 | 0.784 | -0.134 | -245.736 | -247.050 | 929 | 910 |
| 15m | close_outside | retest | opposite_or_side | 2635 | 2081 | 3.843 | 0.414 | 0.794 | -0.129 | -268.594 | -280.013 | 1067 | 1014 |
| 5m | body_ratio | immediate | opposite_or_side | 2639 | 2625 | 4.847 | 0.422 | 0.827 | -0.109 | -285.520 | -291.403 | 1365 | 1260 |
| 5m | two_closes_outside | immediate | opposite_or_side | 2636 | 2622 | 4.841 | 0.413 | 0.811 | -0.119 | -312.754 | -316.653 | 1371 | 1251 |
| 5m | two_closes_outside | retest | opposite_or_side | 2636 | 1807 | 3.337 | 0.412 | 0.751 | -0.174 | -314.704 | -322.099 | 904 | 903 |
| 5m | body_ratio | retest | opposite_or_side | 2639 | 1855 | 3.425 | 0.405 | 0.728 | -0.192 | -356.642 | -361.552 | 928 | 927 |
| 5m | close_outside | immediate | opposite_or_side | 2639 | 2625 | 4.847 | 0.405 | 0.766 | -0.157 | -412.388 | -414.784 | 1375 | 1250 |
| 5m | close_outside | retest | opposite_or_side | 2639 | 2124 | 3.922 | 0.398 | 0.705 | -0.212 | -450.529 | -450.439 | 1094 | 1030 |

## Stage B — fine sweep on 0 live region(s) (exit x filter, capped top-10-by-totR of Stage-A n>=30 & PF>=1.0 candidates)

(no Stage-A cell passed n>=30 & PF>=1.0 — no live regions to sweep)

## Best cells overall (Stage A ∪ Stage B, n>=30)

(none)

## ES-ORB incumbent comparison (PIN)

Incumbent class pinned to: OR30 / close-outside / immediate next-bar-open / opposite-OR-side stop / 1.5R exit / no filter (classic ORB cell). Prior register claim: **PF 1.22** (pre-1m-truth, NOT re-run — cited only).

- Honest (this lane, 1m-truth, adverse-first, valid-day mask, MES costs): n=2601, tr/wk=4.80, WR=44.3%, **PF=0.871**, expR=-0.063, totR=-163.2, maxDD-R=-195.9

- Honest vs claimed: 0.871 vs 1.22 claimed (DOES NOT CONFIRM the prior at the family-kill bar of 1.15).

## Kill / freeze outcomes

- Family best PF across all cells run: 0.871
- Family kill rule (PF<1.15): **KILLED**
- No cells exceeded the PF>1.8 freeze-flag threshold.

## Runtime
- Stage A: 318.3s
- Stage B: 0.0s
- Total M4: 318.3s
