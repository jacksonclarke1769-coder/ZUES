# ES Edge Expansion — Lane B — M2: Opening-Drive Continuation

**CFD proxy, documented optimistic bias vs real futures; graduates need real CME data before certification.** RESEARCH ONLY. LIVE HOLD ACTIVE. No commits.

Valid days: 2639 / 2678 (98.5%). Weeks span: 541.6.

## Stage A — coarse grid (drive x strength x entry x stop, exit=1.5R, filter=none, 32 cells)

| drive | strength | entry | stop | n_events | n_no_fill | n | tr_per_wk | wr | pf | exp_r | tot_r | maxdd_r | n_long | n_short |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| first-30m | ge0.75atr_body0.6 | pullback_vwap | atr_1.5 | 18 | 5 | 13 | 0.024 | 0.846 | 3.933 | 0.362 | 4.701 | -0.567 | 7 | 6 |
| first-30m | ge0.5atr | pullback_vwap | drive_midpoint | 93 | 39 | 54 | 0.100 | 0.574 | 1.193 | 0.085 | 4.593 | -6.331 | 23 | 31 |
| first-30m | ge0.5atr | next_bar_open | atr_1.5 | 93 | 0 | 93 | 0.172 | 0.570 | 1.245 | 0.047 | 4.402 | -3.124 | 45 | 48 |
| first-30m | ge0.5atr | pullback_50pct | atr_1.5 | 93 | 78 | 15 | 0.028 | 0.733 | 2.925 | 0.277 | 4.158 | -1.396 | 14 | 1 |
| first-30m | ge0.75atr_body0.6 | next_bar_open | atr_1.5 | 18 | 0 | 18 | 0.033 | 0.667 | 2.741 | 0.221 | 3.978 | -0.641 | 10 | 8 |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | 93 | 39 | 54 | 0.100 | 0.630 | 1.370 | 0.066 | 3.579 | -1.879 | 23 | 31 |
| first-30m | ge0.75atr_body0.6 | pullback_50pct | atr_1.5 | 18 | 12 | 6 | 0.011 | 0.833 | 7.671 | 0.464 | 2.787 | -0.418 | 6 | 0 |
| first-30m | ge0.75atr_body0.6 | pullback_vwap | drive_midpoint | 18 | 5 | 13 | 0.024 | 0.615 | 1.257 | 0.113 | 1.475 | -3.507 | 7 | 6 |
| first-15m | ge0.5atr | pullback_50pct | atr_1.5 | 31 | 22 | 9 | 0.017 | 0.444 | 1.414 | 0.071 | 0.640 | -1.272 | 8 | 1 |
| first-30m | ge0.75atr_body0.6 | pullback_50pct | drive_midpoint | 18 | 12 | 0 | 0.000 | nan | nan | nan | 0.000 | 0.000 | 0 | 0 |
| first-15m | ge0.5atr | pullback_50pct | drive_midpoint | 31 | 22 | 0 | 0.000 | nan | nan | nan | 0.000 | 0.000 | 0 | 0 |
| first-30m | ge0.5atr | pullback_50pct | drive_midpoint | 93 | 78 | 0 | 0.000 | nan | nan | nan | 0.000 | 0.000 | 0 | 0 |
| first-15m | ge0.75atr_body0.6 | pullback_50pct | drive_midpoint | 8 | 6 | 0 | 0.000 | nan | nan | nan | 0.000 | 0.000 | 0 | 0 |
| first-30m | ge0.75atr_body0.6 | or_boundary_retest | atr_1.5 | 18 | 3 | 15 | 0.028 | 0.467 | 0.979 | -0.005 | -0.079 | -1.020 | 9 | 6 |
| first-15m | ge0.75atr_body0.6 | pullback_50pct | atr_1.5 | 8 | 6 | 2 | 0.004 | 0.500 | 0.463 | -0.103 | -0.206 | -0.384 | 2 | 0 |
| first-15m | ge0.5atr | pullback_vwap | atr_1.5 | 31 | 3 | 28 | 0.052 | 0.500 | 0.920 | -0.018 | -0.508 | -2.878 | 14 | 14 |
| first-15m | ge0.5atr | next_bar_open | drive_midpoint | 31 | 0 | 31 | 0.057 | 0.484 | 0.942 | -0.030 | -0.928 | -6.904 | 15 | 16 |
| first-15m | ge0.5atr | or_boundary_retest | atr_1.5 | 31 | 3 | 28 | 0.052 | 0.536 | 0.856 | -0.034 | -0.961 | -3.843 | 14 | 14 |
| first-15m | ge0.75atr_body0.6 | next_bar_open | atr_1.5 | 8 | 0 | 8 | 0.015 | 0.500 | 0.612 | -0.137 | -1.094 | -1.455 | 5 | 3 |
| first-15m | ge0.75atr_body0.6 | next_bar_open | drive_midpoint | 8 | 0 | 8 | 0.015 | 0.500 | 0.735 | -0.143 | -1.147 | -2.912 | 5 | 3 |
| first-30m | ge0.5atr | or_boundary_retest | atr_1.5 | 93 | 15 | 78 | 0.144 | 0.513 | 0.933 | -0.015 | -1.148 | -3.680 | 41 | 37 |
| first-15m | ge0.75atr_body0.6 | pullback_vwap | atr_1.5 | 8 | 1 | 7 | 0.013 | 0.571 | 0.547 | -0.170 | -1.188 | -1.101 | 4 | 3 |
| first-15m | ge0.5atr | next_bar_open | atr_1.5 | 31 | 0 | 31 | 0.057 | 0.484 | 0.840 | -0.042 | -1.288 | -4.559 | 15 | 16 |
| first-15m | ge0.75atr_body0.6 | or_boundary_retest | atr_1.5 | 8 | 0 | 8 | 0.015 | 0.500 | 0.489 | -0.182 | -1.455 | -1.514 | 5 | 3 |
| first-30m | ge0.5atr | or_boundary_retest | drive_midpoint | 93 | 15 | 78 | 0.144 | 0.423 | 0.933 | -0.032 | -2.485 | -6.599 | 41 | 37 |
| first-30m | ge0.75atr_body0.6 | or_boundary_retest | drive_midpoint | 18 | 3 | 15 | 0.028 | 0.267 | 0.533 | -0.247 | -3.704 | -5.306 | 9 | 6 |
| first-30m | ge0.75atr_body0.6 | next_bar_open | drive_midpoint | 18 | 0 | 18 | 0.033 | 0.333 | 0.568 | -0.232 | -4.180 | -5.717 | 10 | 8 |
| first-15m | ge0.75atr_body0.6 | pullback_vwap | drive_midpoint | 8 | 1 | 7 | 0.013 | 0.286 | 0.112 | -0.699 | -4.893 | -3.856 | 4 | 3 |
| first-15m | ge0.75atr_body0.6 | or_boundary_retest | drive_midpoint | 8 | 0 | 8 | 0.015 | 0.250 | 0.053 | -0.764 | -6.112 | -5.077 | 5 | 3 |
| first-15m | ge0.5atr | or_boundary_retest | drive_midpoint | 31 | 3 | 28 | 0.052 | 0.393 | 0.492 | -0.307 | -8.603 | -8.527 | 14 | 14 |
| first-30m | ge0.5atr | next_bar_open | drive_midpoint | 93 | 0 | 93 | 0.172 | 0.419 | 0.762 | -0.122 | -11.305 | -13.203 | 45 | 48 |
| first-15m | ge0.5atr | pullback_vwap | drive_midpoint | 31 | 3 | 28 | 0.052 | 0.357 | 0.377 | -0.477 | -13.346 | -13.118 | 14 | 14 |

## Stage B — fine sweep on 3 live region(s)

| drive | strength | entry | stop | exit | filt | n_events | n | tr_per_wk | wr | pf | exp_r | tot_r | maxdd_r | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | drive_extension_1.0x | vwap_slope_agreement | 93 | 54 | 0.100 | 0.648 | 1.441 | 0.074 | 3.997 | -1.516 |  |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | drive_extension_1.0x | none | 93 | 54 | 0.100 | 0.648 | 1.441 | 0.074 | 3.997 | -1.516 |  |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | 2R | vwap_slope_agreement | 93 | 54 | 0.100 | 0.630 | 1.421 | 0.076 | 4.079 | -1.879 |  |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | 2R | none | 93 | 54 | 0.100 | 0.630 | 1.421 | 0.076 | 4.079 | -1.879 |  |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | 1.5R | vwap_slope_agreement | 93 | 54 | 0.100 | 0.630 | 1.370 | 0.066 | 3.579 | -1.879 |  |
| first-30m | ge0.5atr | next_bar_open | atr_1.5 | drive_extension_1.0x | none | 93 | 93 | 0.172 | 0.602 | 1.321 | 0.057 | 5.297 | -2.038 |  |
| first-30m | ge0.5atr | next_bar_open | atr_1.5 | drive_extension_1.0x | vwap_slope_agreement | 93 | 93 | 0.172 | 0.602 | 1.321 | 0.057 | 5.297 | -2.038 |  |
| first-30m | ge0.5atr | pullback_vwap | drive_midpoint | 1.5R | exclude_gap_fill | 93 | 34 | 0.063 | 0.559 | 1.250 | 0.100 | 3.407 | -3.745 |  |
| first-30m | ge0.5atr | next_bar_open | atr_1.5 | 1.5R | vwap_slope_agreement | 93 | 93 | 0.172 | 0.570 | 1.245 | 0.047 | 4.402 | -3.124 |  |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | trail_3.5xATR | vwap_slope_agreement | 93 | 54 | 0.100 | 0.537 | 1.220 | 0.030 | 1.631 | -1.562 |  |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | trail_3.5xATR | none | 93 | 54 | 0.100 | 0.537 | 1.220 | 0.030 | 1.631 | -1.562 |  |
| first-30m | ge0.5atr | pullback_vwap | drive_midpoint | 1.5R | vwap_slope_agreement | 93 | 54 | 0.100 | 0.574 | 1.193 | 0.085 | 4.593 | -6.331 |  |
| first-30m | ge0.5atr | pullback_vwap | drive_midpoint | 2R | exclude_gap_fill | 93 | 34 | 0.063 | 0.500 | 1.182 | 0.085 | 2.907 | -4.898 |  |
| first-30m | ge0.5atr | next_bar_open | atr_1.5 | 2R | vwap_slope_agreement | 93 | 93 | 0.172 | 0.570 | 1.180 | 0.035 | 3.246 | -3.124 |  |
| first-30m | ge0.5atr | next_bar_open | atr_1.5 | 2R | none | 93 | 93 | 0.172 | 0.570 | 1.180 | 0.035 | 3.246 | -3.124 |  |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | 2R | exclude_gap_fill | 93 | 34 | 0.063 | 0.559 | 1.133 | 0.027 | 0.911 | -1.852 |  |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | trail_3.5xATR | exclude_gap_fill | 93 | 34 | 0.063 | 0.529 | 1.073 | 0.010 | 0.349 | -1.457 |  |
| first-30m | ge0.5atr | pullback_vwap | drive_midpoint | 2R | none | 93 | 54 | 0.100 | 0.519 | 1.071 | 0.036 | 1.956 | -10.031 |  |
| first-30m | ge0.5atr | pullback_vwap | drive_midpoint | 2R | vwap_slope_agreement | 93 | 54 | 0.100 | 0.519 | 1.071 | 0.036 | 1.956 | -10.031 |  |
| first-30m | ge0.5atr | next_bar_open | atr_1.5 | trail_3.5xATR | none | 93 | 93 | 0.172 | 0.441 | 1.060 | 0.009 | 0.833 | -3.484 |  |
| first-30m | ge0.5atr | next_bar_open | atr_1.5 | trail_3.5xATR | vwap_slope_agreement | 93 | 93 | 0.172 | 0.441 | 1.060 | 0.009 | 0.833 | -3.484 |  |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | 1.5R | exclude_gap_fill | 93 | 34 | 0.063 | 0.559 | 1.060 | 0.012 | 0.411 | -1.852 |  |
| first-30m | ge0.5atr | next_bar_open | atr_1.5 | drive_extension_1.0x | exclude_gap_fill | 93 | 64 | 0.118 | 0.547 | 0.978 | -0.005 | -0.290 | -2.393 |  |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | drive_extension_1.0x | exclude_gap_fill | 93 | 34 | 0.063 | 0.559 | 0.923 | -0.016 | -0.531 | -2.105 |  |
| first-30m | ge0.5atr | next_bar_open | atr_1.5 | trail_3.5xATR | exclude_gap_fill | 93 | 64 | 0.118 | 0.391 | 0.876 | -0.018 | -1.156 | -2.935 |  |
| first-30m | ge0.5atr | next_bar_open | atr_1.5 | 1.5R | exclude_gap_fill | 93 | 64 | 0.118 | 0.500 | 0.822 | -0.040 | -2.592 | -3.531 |  |
| first-30m | ge0.5atr | next_bar_open | atr_1.5 | 2R | exclude_gap_fill | 93 | 64 | 0.118 | 0.500 | 0.787 | -0.048 | -3.100 | -3.613 |  |
| first-30m | ge0.5atr | pullback_vwap | drive_midpoint | drive_extension_1.0x | vwap_slope_agreement | 93 | 54 | 0.100 | 0.407 | 0.627 | -0.244 | -13.173 | -21.746 |  |
| first-30m | ge0.5atr | pullback_vwap | drive_midpoint | drive_extension_1.0x | none | 93 | 54 | 0.100 | 0.407 | 0.627 | -0.244 | -13.173 | -21.746 |  |
| first-30m | ge0.5atr | pullback_vwap | drive_midpoint | trail_3.5xATR | vwap_slope_agreement | 93 | 54 | 0.100 | 0.370 | 0.512 | -0.294 | -15.849 | -23.202 |  |

## Best cells overall (n>=30)

| drive | strength | entry | stop | exit | filt | n | tr_per_wk | wr | pf | exp_r | tot_r | maxdd_r |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | drive_extension_1.0x | none | 54 | 0.100 | 0.648 | 1.441 | 0.074 | 3.997 | -1.516 |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | drive_extension_1.0x | vwap_slope_agreement | 54 | 0.100 | 0.648 | 1.441 | 0.074 | 3.997 | -1.516 |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | 2R | none | 54 | 0.100 | 0.630 | 1.421 | 0.076 | 4.079 | -1.879 |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | 2R | vwap_slope_agreement | 54 | 0.100 | 0.630 | 1.421 | 0.076 | 4.079 | -1.879 |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | 1.5R | vwap_slope_agreement | 54 | 0.100 | 0.630 | 1.370 | 0.066 | 3.579 | -1.879 |
| first-30m | ge0.5atr | next_bar_open | atr_1.5 | drive_extension_1.0x | none | 93 | 0.172 | 0.602 | 1.321 | 0.057 | 5.297 | -2.038 |
| first-30m | ge0.5atr | next_bar_open | atr_1.5 | drive_extension_1.0x | vwap_slope_agreement | 93 | 0.172 | 0.602 | 1.321 | 0.057 | 5.297 | -2.038 |
| first-30m | ge0.5atr | pullback_vwap | drive_midpoint | 1.5R | exclude_gap_fill | 34 | 0.063 | 0.559 | 1.250 | 0.100 | 3.407 | -3.745 |
| first-30m | ge0.5atr | next_bar_open | atr_1.5 | 1.5R | vwap_slope_agreement | 93 | 0.172 | 0.570 | 1.245 | 0.047 | 4.402 | -3.124 |
| first-30m | ge0.5atr | pullback_vwap | atr_1.5 | trail_3.5xATR | none | 54 | 0.100 | 0.537 | 1.220 | 0.030 | 1.631 | -1.562 |

## Kill / freeze outcomes

- Family best PF across all cells run: 1.441
- Family kill rule (PF<1.15): **ALIVE**
- Prior context: NQ KRONOS breakout-continuation was dead at PF 0.97 (different instrument/definition); ES M2's best cell here is ABOVE that reference point.
- No cells exceeded the PF>1.8 freeze-flag threshold.

**FREQUENCY CAUTION (editorial addendum, not a mechanical kill — M2 has no task-brief frequency
floor unlike M3):** the best cell trades at ~0.10-0.17/wk (n=54-93 over the ~10.4-year, 541.6-
week window) — roughly one trade every 6-10 weeks. This is thin enough that the PF/expR point
estimates carry wide uncertainty despite technically clearing the PF>=1.15 alive bar; the
`ge0.5atr` strength def (drive >=0.5x daily ATR in 30 minutes) is itself a rare event on ES.
Treat M2 as WATCHLIST-ALIVE, not a robust standalone edge, pending either a longer window or a
looser strength threshold in any follow-up pass.

## Slip probes on the single best cell (first-30m/ge0.5atr/pullback_vwap/atr_1.5/drive_extension_1.0x/none)

- +0.015R adverse slip: PF=1.341, expR=0.059, totR=3.2
- +0.03R adverse slip: PF=1.246, expR=0.044, totR=2.4

## Runtime
- Stage A: 16.2s
- Stage B: 16.2s
- Total M2: 32.4s
