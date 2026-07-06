# 05 -- Timing-window grid (A+VPC portfolio optimisation, Lane 3)

RESEARCH ONLY. LIVE HOLD ACTIVE. Sizing held at the pinned baseline A@600/6 + VPC@600/4 throughout (only the timing window / A per-day dedupe is varied). VPC leg = 1m-truth stream (current, 5.0xATR trail), canary n=408 PF=1.318. A leg = `tools_sim_parity_check.load_rows()`, filtered to 2022-2026 (shared VPC window).

Baseline canary (A-current+VPC-full): pass=28.7% bust=17.0% exp=54.4% n=684 (expect {'pass_pct': 28.7, 'bust_pct': 17.0, 'exp_pct': 54.4, 'n': 684}).

Mechanical dedupe-equivalence findings: first-signal-of-day-only == max-1/day: **True**; max-2/day == current (no A day in 2022-2026 has 3+ trades): **True**.

Grid = 8 VPC windows x 4 A variants = 32 cells, plus 3 named combos (one of which IS the baseline). Slip probe = 0.015/0.03/0.046R applied to BOTH legs uniformly (`tools_salvage_stress.dmg_slip`, reused verbatim). Concentration flag: any single year's PASS count > 60% of that cell's total pass count (new, mechanical, documented in module docstring).

## Full grid + named combos

| a_variant | window | named_combo | n_a | n_v | trades_wk_a | trades_wk_v | eligible_starts | pass_count | bust_count | exp_count | pass_pct | bust_pct | exp_pct | med_days_pass | worst_day_usd | funded_per_slot_year | pf_dollar | e_dollar_placeholder | joint_loss_days | joint_loss_pct | one_year_concentration_flag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A-current (all trades) | 10:00-15:00 (full) | False | 513 | 408 | 2.208 | 1.767 | 684 | 196 | 116 | 372 | 28.7 | 17 | 54.4 | 18 | -1000 | 4.22 | 1.377 | 2165 | 65 | 9.3 | False |
| A-first-signal-of-day-only | 10:00-15:00 (full) | False | 475 | 408 | 2.045 | 1.767 | 684 | 198 | 108 | 378 | 28.9 | 15.8 | 55.3 | 19 | -1000 | 4.23 | 1.403 | 2181 | 63 | 9 | False |
| A-max-1/day | 10:00-15:00 (full) | False | 475 | 408 | 2.045 | 1.767 | 684 | 198 | 108 | 378 | 28.9 | 15.8 | 55.3 | 19 | -1000 | 4.23 | 1.403 | 2181 | 63 | 9 | False |
| A-max-2/day | 10:00-15:00 (full) | False | 513 | 408 | 2.208 | 1.767 | 684 | 196 | 116 | 372 | 28.7 | 17 | 54.4 | 18 | -1000 | 4.22 | 1.377 | 2165 | 65 | 9.3 | False |
| A-current (all trades) | 10:00-14:00 | False | 513 | 400 | 2.208 | 1.733 | 680 | 197 | 109 | 374 | 29 | 16 | 55 | 19 | -1000 | 4.25 | 1.391 | 2189 | 64 | 9.2 | False |
| A-first-signal-of-day-only | 10:00-14:00 | False | 475 | 400 | 2.045 | 1.733 | 680 | 199 | 108 | 373 | 29.3 | 15.9 | 54.9 | 19 | -1000 | 4.27 | 1.418 | 2213 | 62 | 8.9 | False |
| A-max-1/day | 10:00-14:00 | False | 475 | 400 | 2.045 | 1.733 | 680 | 199 | 108 | 373 | 29.3 | 15.9 | 54.9 | 19 | -1000 | 4.27 | 1.418 | 2213 | 62 | 8.9 | False |
| A-max-2/day | 10:00-14:00 | False | 513 | 400 | 2.208 | 1.733 | 680 | 197 | 109 | 374 | 29 | 16 | 55 | 19 | -1000 | 4.25 | 1.391 | 2189 | 64 | 9.2 | False |
| A-current (all trades) | 10:00-13:00 | False | 513 | 390 | 2.208 | 1.689 | 674 | 191 | 109 | 374 | 28.3 | 16.2 | 55.5 | 18 | -1000 | 4.16 | 1.393 | 2133 | 64 | 9.3 | False |
| A-first-signal-of-day-only | 10:00-13:00 | False | 475 | 390 | 2.045 | 1.689 | 674 | 194 | 108 | 372 | 28.8 | 16 | 55.2 | 19 | -1000 | 4.2 | 1.421 | 2173 | 62 | 9 | False |
| A-max-1/day | 10:00-13:00 | False | 475 | 390 | 2.045 | 1.689 | 674 | 194 | 108 | 372 | 28.8 | 16 | 55.2 | 19 | -1000 | 4.2 | 1.421 | 2173 | 62 | 9 | False |
| A-max-2/day | 10:00-13:00 | False | 513 | 390 | 2.208 | 1.689 | 674 | 191 | 109 | 374 | 28.3 | 16.2 | 55.5 | 18 | -1000 | 4.16 | 1.393 | 2133 | 64 | 9.3 | False |
| A-current (all trades) | 10:30-15:00 | False | 513 | 151 | 2.208 | 0.662 | 543 | 80 | 47 | 416 | 14.7 | 8.7 | 76.6 | 20 | -1000 | 1.95 | 1.36 | 1045 | 23 | 4.1 | False |
| A-first-signal-of-day-only | 10:30-15:00 | False | 475 | 151 | 2.045 | 0.662 | 543 | 83 | 43 | 417 | 15.3 | 7.9 | 76.8 | 21 | -1000 | 2.02 | 1.395 | 1093 | 21 | 3.8 | False |
| A-max-1/day | 10:30-15:00 | False | 475 | 151 | 2.045 | 0.662 | 543 | 83 | 43 | 417 | 15.3 | 7.9 | 76.8 | 21 | -1000 | 2.02 | 1.395 | 1093 | 21 | 3.8 | False |
| A-max-2/day | 10:30-15:00 | False | 513 | 151 | 2.208 | 0.662 | 543 | 80 | 47 | 416 | 14.7 | 8.7 | 76.6 | 20 | -1000 | 1.95 | 1.36 | 1045 | 23 | 4.1 | False |
| A-current (all trades) | 10:30-14:00 | False | 513 | 143 | 2.208 | 0.627 | 538 | 80 | 45 | 413 | 14.9 | 8.4 | 76.8 | 19 | -1000 | 1.97 | 1.378 | 1061 | 22 | 4 | False |
| A-first-signal-of-day-only | 10:30-14:00 | False | 475 | 143 | 2.045 | 0.627 | 538 | 83 | 41 | 414 | 15.4 | 7.6 | 77 | 21 | -1000 | 2.04 | 1.416 | 1101 | 20 | 3.6 | False |
| A-max-1/day | 10:30-14:00 | False | 475 | 143 | 2.045 | 0.627 | 538 | 83 | 41 | 414 | 15.4 | 7.6 | 77 | 21 | -1000 | 2.04 | 1.416 | 1101 | 20 | 3.6 | False |
| A-max-2/day | 10:30-14:00 | False | 513 | 143 | 2.208 | 0.627 | 538 | 80 | 45 | 413 | 14.9 | 8.4 | 76.8 | 19 | -1000 | 1.97 | 1.378 | 1061 | 22 | 4 | False |
| A-current (all trades) | 11:00-15:00 | False | 513 | 69 | 2.208 | 0.305 | 501 | 69 | 36 | 396 | 13.8 | 7.2 | 79 | 20 | -1000 | 1.8 | 1.409 | 973 | 10 | 1.9 | False |
| A-first-signal-of-day-only | 11:00-15:00 | False | 475 | 69 | 2.045 | 0.305 | 501 | 73 | 32 | 396 | 14.6 | 6.4 | 79 | 21 | -1000 | 1.9 | 1.454 | 1037 | 9 | 1.8 | False |
| A-max-1/day | 11:00-15:00 | False | 475 | 69 | 2.045 | 0.305 | 501 | 73 | 32 | 396 | 14.6 | 6.4 | 79 | 21 | -1000 | 1.9 | 1.454 | 1037 | 9 | 1.8 | False |
| A-max-2/day | 11:00-15:00 | False | 513 | 69 | 2.208 | 0.305 | 501 | 69 | 36 | 396 | 13.8 | 7.2 | 79 | 20 | -1000 | 1.8 | 1.409 | 973 | 10 | 1.9 | False |
| A-current (all trades) | 11:00-14:00 | False | 513 | 61 | 2.208 | 0.27 | 496 | 67 | 36 | 393 | 13.5 | 7.3 | 79.2 | 19 | -1000 | 1.77 | 1.432 | 949 | 9 | 1.8 | False |
| A-first-signal-of-day-only | 11:00-14:00 | False | 475 | 61 | 2.045 | 0.27 | 496 | 69 | 32 | 395 | 13.9 | 6.5 | 79.6 | 20 | -1000 | 1.82 | 1.48 | 981 | 8 | 1.6 | False |
| A-max-1/day | 11:00-14:00 | False | 475 | 61 | 2.045 | 0.27 | 496 | 69 | 32 | 395 | 13.9 | 6.5 | 79.6 | 20 | -1000 | 1.82 | 1.48 | 981 | 8 | 1.6 | False |
| A-max-2/day | 11:00-14:00 | False | 513 | 61 | 2.208 | 0.27 | 496 | 67 | 36 | 393 | 13.5 | 7.3 | 79.2 | 19 | -1000 | 1.77 | 1.432 | 949 | 9 | 1.8 | False |
| A-current (all trades) | 12:00-15:00 | False | 513 | 25 | 2.208 | 0.114 | 478 | 49 | 23 | 406 | 10.3 | 4.8 | 84.9 | 24 | -1000 | 1.29 | 1.372 | 693 | 2 | 0.4 | False |
| A-first-signal-of-day-only | 12:00-15:00 | False | 475 | 25 | 2.045 | 0.114 | 478 | 48 | 19 | 411 | 10 | 4 | 86 | 24 | -1000 | 1.26 | 1.418 | 669 | 2 | 0.4 | False |
| A-max-1/day | 12:00-15:00 | False | 475 | 25 | 2.045 | 0.114 | 478 | 48 | 19 | 411 | 10 | 4 | 86 | 24 | -1000 | 1.26 | 1.418 | 669 | 2 | 0.4 | False |
| A-max-2/day | 12:00-15:00 | False | 513 | 25 | 2.208 | 0.114 | 478 | 49 | 23 | 406 | 10.3 | 4.8 | 84.9 | 24 | -1000 | 1.29 | 1.372 | 693 | 2 | 0.4 | False |
| A-current+VPC-full (=baseline) | (named combo) | True | 513 | 408 | 2.208 | 1.767 | 684 | 196 | 116 | 372 | 28.7 | 17 | 54.4 | 18 | -1000 | 4.22 | 1.377 | 2165 | 65 | 9.3 | False |
| A-current+VPC-after-11:00 | (named combo) | True | 513 | 69 | 2.208 | 0.305 | 501 | 69 | 36 | 396 | 13.8 | 7.2 | 79 | 20 | -1000 | 1.8 | 1.409 | 973 | 10 | 1.9 | False |
| A-1/day+VPC-full | (named combo) | True | 475 | 408 | 2.045 | 1.767 | 684 | 198 | 108 | 378 | 28.9 | 15.8 | 55.3 | 19 | -1000 | 4.23 | 1.403 | 2181 | 63 | 9 | False |

## Per-year pass% (2022-2026)

| a_variant | window | named_combo | py2022_n | py2022_pass_pct | py2023_n | py2023_pass_pct | py2024_n | py2024_pass_pct | py2025_n | py2025_pass_pct | py2026_n | py2026_pass_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A-current (all trades) | 10:00-15:00 (full) | False | 151 | 22.5 | 160 | 20.6 | 152 | 21.7 | 160 | 43.1 | 61 | 44.3 |
| A-first-signal-of-day-only | 10:00-15:00 (full) | False | 151 | 23.2 | 160 | 23.1 | 152 | 16.4 | 160 | 46.2 | 61 | 44.3 |
| A-max-1/day | 10:00-15:00 (full) | False | 151 | 23.2 | 160 | 23.1 | 152 | 16.4 | 160 | 46.2 | 61 | 44.3 |
| A-max-2/day | 10:00-15:00 (full) | False | 151 | 22.5 | 160 | 20.6 | 152 | 21.7 | 160 | 43.1 | 61 | 44.3 |
| A-current (all trades) | 10:00-14:00 | False | 150 | 24 | 159 | 20.8 | 152 | 23.7 | 158 | 41.1 | 61 | 44.3 |
| A-first-signal-of-day-only | 10:00-14:00 | False | 150 | 24.7 | 159 | 23.3 | 152 | 19.1 | 158 | 43.7 | 61 | 44.3 |
| A-max-1/day | 10:00-14:00 | False | 150 | 24.7 | 159 | 23.3 | 152 | 19.1 | 158 | 43.7 | 61 | 44.3 |
| A-max-2/day | 10:00-14:00 | False | 150 | 24 | 159 | 20.8 | 152 | 23.7 | 158 | 41.1 | 61 | 44.3 |
| A-current (all trades) | 10:00-13:00 | False | 149 | 23.5 | 158 | 19 | 151 | 23.8 | 155 | 40.6 | 61 | 44.3 |
| A-first-signal-of-day-only | 10:00-13:00 | False | 149 | 22.8 | 158 | 21.5 | 151 | 19.2 | 155 | 45.2 | 61 | 44.3 |
| A-max-1/day | 10:00-13:00 | False | 149 | 22.8 | 158 | 21.5 | 151 | 19.2 | 155 | 45.2 | 61 | 44.3 |
| A-max-2/day | 10:00-13:00 | False | 149 | 23.5 | 158 | 19 | 151 | 23.8 | 155 | 40.6 | 61 | 44.3 |
| A-current (all trades) | 10:30-15:00 | False | 122 | 12.3 | 121 | 1.7 | 122 | 10.7 | 130 | 27.7 | 48 | 29.2 |
| A-first-signal-of-day-only | 10:30-15:00 | False | 122 | 11.5 | 121 | 3.3 | 122 | 7.4 | 130 | 32.3 | 48 | 29.2 |
| A-max-1/day | 10:30-15:00 | False | 122 | 11.5 | 121 | 3.3 | 122 | 7.4 | 130 | 32.3 | 48 | 29.2 |
| A-max-2/day | 10:30-15:00 | False | 122 | 12.3 | 121 | 1.7 | 122 | 10.7 | 130 | 27.7 | 48 | 29.2 |
| A-current (all trades) | 10:30-14:00 | False | 121 | 12.4 | 120 | 1.7 | 121 | 13.2 | 128 | 25.8 | 48 | 29.2 |
| A-first-signal-of-day-only | 10:30-14:00 | False | 121 | 11.6 | 120 | 2.5 | 121 | 9.9 | 128 | 31.2 | 48 | 29.2 |
| A-max-1/day | 10:30-14:00 | False | 121 | 11.6 | 120 | 2.5 | 121 | 9.9 | 128 | 31.2 | 48 | 29.2 |
| A-max-2/day | 10:30-14:00 | False | 121 | 12.4 | 120 | 1.7 | 121 | 13.2 | 128 | 25.8 | 48 | 29.2 |
| A-current (all trades) | 11:00-15:00 | False | 110 | 12.7 | 116 | 0 | 111 | 5.4 | 121 | 28.1 | 43 | 34.9 |
| A-first-signal-of-day-only | 11:00-15:00 | False | 110 | 12.7 | 116 | 2.6 | 111 | 5.4 | 121 | 29.8 | 43 | 32.6 |
| A-max-1/day | 11:00-15:00 | False | 110 | 12.7 | 116 | 2.6 | 111 | 5.4 | 121 | 29.8 | 43 | 32.6 |
| A-max-2/day | 11:00-15:00 | False | 110 | 12.7 | 116 | 0 | 111 | 5.4 | 121 | 28.1 | 43 | 34.9 |
| A-current (all trades) | 11:00-14:00 | False | 109 | 12.8 | 115 | 0 | 110 | 6.4 | 119 | 26.1 | 43 | 34.9 |
| A-first-signal-of-day-only | 11:00-14:00 | False | 109 | 12.8 | 115 | 0.9 | 110 | 6.4 | 119 | 27.7 | 43 | 32.6 |
| A-max-1/day | 11:00-14:00 | False | 109 | 12.8 | 115 | 0.9 | 110 | 6.4 | 119 | 27.7 | 43 | 32.6 |
| A-max-2/day | 11:00-14:00 | False | 109 | 12.8 | 115 | 0 | 110 | 6.4 | 119 | 26.1 | 43 | 34.9 |
| A-current (all trades) | 12:00-15:00 | False | 106 | 2.8 | 113 | 4.4 | 104 | 5.8 | 117 | 17.9 | 38 | 36.8 |
| A-first-signal-of-day-only | 12:00-15:00 | False | 106 | 0 | 113 | 7.1 | 104 | 5.8 | 117 | 19.7 | 38 | 28.9 |
| A-max-1/day | 12:00-15:00 | False | 106 | 0 | 113 | 7.1 | 104 | 5.8 | 117 | 19.7 | 38 | 28.9 |
| A-max-2/day | 12:00-15:00 | False | 106 | 2.8 | 113 | 4.4 | 104 | 5.8 | 117 | 17.9 | 38 | 36.8 |
| A-current+VPC-full (=baseline) | (named combo) | True | 151 | 22.5 | 160 | 20.6 | 152 | 21.7 | 160 | 43.1 | 61 | 44.3 |
| A-current+VPC-after-11:00 | (named combo) | True | 110 | 12.7 | 116 | 0 | 111 | 5.4 | 121 | 28.1 | 43 | 34.9 |
| A-1/day+VPC-full | (named combo) | True | 151 | 23.2 | 160 | 23.1 | 152 | 16.4 | 160 | 46.2 | 61 | 44.3 |

## 3-point slip probe (0.015 / 0.03 / 0.046 R, both legs)

| a_variant | window | named_combo | slip0.015_pass_pct | slip0.015_bust_pct | slip0.03_pass_pct | slip0.03_bust_pct | slip0.046_pass_pct | slip0.046_bust_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A-current (all trades) | 10:00-15:00 (full) | False | 26.5 | 17.8 | 24.9 | 17.8 | 23 | 18.6 |
| A-first-signal-of-day-only | 10:00-15:00 (full) | False | 27.2 | 16.4 | 25.7 | 16.4 | 24.3 | 17 |
| A-max-1/day | 10:00-15:00 (full) | False | 27.2 | 16.4 | 25.7 | 16.4 | 24.3 | 17 |
| A-max-2/day | 10:00-15:00 (full) | False | 26.5 | 17.8 | 24.9 | 17.8 | 23 | 18.6 |
| A-current (all trades) | 10:00-14:00 | False | 26.5 | 16.9 | 24.9 | 17.9 | 22.9 | 18.7 |
| A-first-signal-of-day-only | 10:00-14:00 | False | 27.2 | 16.5 | 26 | 16.5 | 24.6 | 17.1 |
| A-max-1/day | 10:00-14:00 | False | 27.2 | 16.5 | 26 | 16.5 | 24.6 | 17.1 |
| A-max-2/day | 10:00-14:00 | False | 26.5 | 16.9 | 24.9 | 17.9 | 22.9 | 18.7 |
| A-current (all trades) | 10:00-13:00 | False | 25.5 | 17.2 | 24.2 | 18.1 | 22.7 | 18.8 |
| A-first-signal-of-day-only | 10:00-13:00 | False | 26.6 | 16.6 | 25.4 | 16.6 | 24.2 | 17.1 |
| A-max-1/day | 10:00-13:00 | False | 26.6 | 16.6 | 25.4 | 16.6 | 24.2 | 17.1 |
| A-max-2/day | 10:00-13:00 | False | 25.5 | 17.2 | 24.2 | 18.1 | 22.7 | 18.8 |
| A-current (all trades) | 10:30-15:00 | False | 13.8 | 8.8 | 12.5 | 10.5 | 12.2 | 12.2 |
| A-first-signal-of-day-only | 10:30-15:00 | False | 14.5 | 8.3 | 12.9 | 9.9 | 12.7 | 10.3 |
| A-max-1/day | 10:30-15:00 | False | 14.5 | 8.3 | 12.9 | 9.9 | 12.7 | 10.3 |
| A-max-2/day | 10:30-15:00 | False | 13.8 | 8.8 | 12.5 | 10.5 | 12.2 | 12.2 |
| A-current (all trades) | 10:30-14:00 | False | 13.9 | 8.6 | 12.6 | 10.2 | 12.3 | 10.6 |
| A-first-signal-of-day-only | 10:30-14:00 | False | 14.9 | 8 | 13.2 | 9.7 | 13 | 10 |
| A-max-1/day | 10:30-14:00 | False | 14.9 | 8 | 13.2 | 9.7 | 13 | 10 |
| A-max-2/day | 10:30-14:00 | False | 13.9 | 8.6 | 12.6 | 10.2 | 12.3 | 10.6 |
| A-current (all trades) | 11:00-15:00 | False | 13.2 | 7.6 | 12.8 | 8.2 | 12.4 | 8.2 |
| A-first-signal-of-day-only | 11:00-15:00 | False | 14 | 7.2 | 13 | 8.2 | 12.8 | 8.2 |
| A-max-1/day | 11:00-15:00 | False | 14 | 7.2 | 13 | 8.2 | 12.8 | 8.2 |
| A-max-2/day | 11:00-15:00 | False | 13.2 | 7.6 | 12.8 | 8.2 | 12.4 | 8.2 |
| A-current (all trades) | 11:00-14:00 | False | 12.9 | 7.3 | 12.7 | 7.9 | 12.3 | 7.9 |
| A-first-signal-of-day-only | 11:00-14:00 | False | 13.7 | 6.9 | 13.1 | 7.9 | 12.9 | 7.9 |
| A-max-1/day | 11:00-14:00 | False | 13.7 | 6.9 | 13.1 | 7.9 | 12.9 | 7.9 |
| A-max-2/day | 11:00-14:00 | False | 12.9 | 7.3 | 12.7 | 7.9 | 12.3 | 7.9 |
| A-current (all trades) | 12:00-15:00 | False | 9.6 | 5.2 | 9 | 6.7 | 8.4 | 6.9 |
| A-first-signal-of-day-only | 12:00-15:00 | False | 9.6 | 4 | 8.4 | 5 | 7.7 | 6.3 |
| A-max-1/day | 12:00-15:00 | False | 9.6 | 4 | 8.4 | 5 | 7.7 | 6.3 |
| A-max-2/day | 12:00-15:00 | False | 9.6 | 5.2 | 9 | 6.7 | 8.4 | 6.9 |
| A-current+VPC-full (=baseline) | (named combo) | True | 26.5 | 17.8 | 24.9 | 17.8 | 23 | 18.6 |
| A-current+VPC-after-11:00 | (named combo) | True | 13.2 | 7.6 | 12.8 | 8.2 | 12.4 | 8.2 |
| A-1/day+VPC-full | (named combo) | True | 27.2 | 16.4 | 25.7 | 16.4 | 24.3 | 17 |

## One-year-concentration flags: 0/35 cells

(none)

## Auditor-stress flags: grid cells where pass_pct exceeds the baseline by >2pp at equal-or-better bust (0/32 grid cells, named combos excluded from this specific check since 2 of the 3 duplicate grid cells)

(none)

## Firewall before/after

- `config_eval_locked.py`: UNCHANGED
- `config_funded_locked.py`: UNCHANGED
- `config_defaults.py`: UNCHANGED
- `auto_safety.py`: UNCHANGED

## PF freeze check: no cell exceeded PF>1.8.

Runtime (lane 3 only): 3.3s

No recommendation. No commits.
