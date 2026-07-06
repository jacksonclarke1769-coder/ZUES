# C -- A+VPC combined portfolio test (Part 2 centerpiece + Part 3 per-year)

RESEARCH ONLY. LIVE HOLD ACTIVE. Independent per-strategy sizing: A and VPC events are each built via tools_account_size_research.build_events with their OWN (budget, cap), then merged onto one shared day calendar and fed the same day_rows($550 stop, $1,000 DLL) / eval_run (EVAL side) or the generalized combined_daily_series (FUNDED side, apex_funded_40 constants, imported not retyped).

**PART 3 WINDOW NOTE**: the VPC stream starts 2022-01-01 (no earlier real Databento VPC trades exist by construction of the recert). All combined analysis below -- including the A-alone comparison rows -- is therefore restricted to the shared 2022-2026 window (A rows filtered to ts >= 2022-01-01, dropping the 2021-06-25 -> 2021-12-31 portion of the certified 583-row honest-A stream) so the comparison is apples-to-apples. This is NOT the full-history A-alone number reported elsewhere (that one uses all 583 rows from 2021-06-25).

Same-day unit-level reference stats (2022-2026 window, 1-contract unclamped, cap/budget-invariant to first order, computed once and repeated on every EVAL combo row): n_days=701, same_day_corr=0.164, dl_freq_pct=9.3 (both streams net-negative same day), tl_freq_pct=53.9 (combined day net-negative). dl_freq/tl_freq have no prior-art precedent in this repo; definitions are stated here explicitly (double-loss-day % and combined-loss-day %, respectively) -- not hidden assumptions.

## EVAL side -- A-alone / VPC-alone / every A x VPC combo

| section | label | pf_dollar | trades_per_week | same_day_corr | dl_freq_pct | tl_freq_pct | eligible_starts | pass_count | bust_count | exp_count | pass_pct | bust_pct | exp_pct | med_days_pass | worst_day_usd | funded_per_slot_year | py2022_n | py2022_pass_pct | py2023_n | py2023_pass_pct | py2024_n | py2024_pass_pct | py2025_n | py2025_pass_pct | py2026_n | py2026_pass_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EVAL | A@400/4 ALONE | 1.386 | 2.19 | 0.164 | 9.3 | 53.9 | 459 | 2 | 0 | 457 | 0.4 | 0 | 99.6 | 27 | -661 | 0.05 | 104 | 0 | 110 | 0 | 102 | 0 | 109 | 1.8 | 34 | 0 |
| EVAL | A@600/6 ALONE | 1.388 | 2.21 | 0.164 | 9.3 | 53.9 | 463 | 42 | 16 | 405 | 9.1 | 3.5 | 87.5 | 23 | -1000 | 1.14 | 104 | 2.9 | 110 | 0.9 | 102 | 6.9 | 110 | 18.2 | 37 | 29.7 |
| EVAL | A@1200/10 ALONE | 1.442 | 2.21 | 0.164 | 9.3 | 53.9 | 463 | 151 | 162 | 150 | 32.6 | 35 | 32.4 | 16 | -1000 | 5.92 | 104 | 17.3 | 110 | 23.6 | 102 | 28.4 | 110 | 56.4 | 37 | 43.2 |
| EVAL | VPC@300/3 ALONE | 1.396 | 1.48 | 0.164 | 9.3 | 53.9 | 331 | 1 | 0 | 330 | 0.3 | 0 | 99.7 | 30 | -522 | 0.04 | 76 | 0 | 86 | 0 | 83 | 0 | 65 | 1.5 | 21 | 0 |
| EVAL | VPC@400/4 ALONE | 1.342 | 1.68 | 0.164 | 9.3 | 53.9 | 373 | 17 | 0 | 356 | 4.6 | 0 | 95.4 | 21 | -1000 | 0.56 | 85 | 0 | 87 | 0 | 90 | 7.8 | 79 | 12.7 | 32 | 0 |
| EVAL | VPC@600/4 ALONE | 1.331 | 1.75 | 0.164 | 9.3 | 53.9 | 388 | 42 | 11 | 335 | 10.8 | 2.8 | 86.3 | 16 | -1000 | 1.39 | 86 | 4.7 | 87 | 4.6 | 93 | 14 | 83 | 16.9 | 39 | 17.9 |
| EVAL | A@400/4 + VPC@300/3 | 1.39 | 3.66 | 0.164 | 9.3 | 53.9 | 650 | 28 | 0 | 622 | 4.3 | 0 | 95.7 | 23 | -737 | 0.53 | 147 | 0.7 | 159 | 1.3 | 148 | 1.4 | 147 | 13.6 | 49 | 6.1 |
| EVAL | A@400/4 + VPC@400/4 | 1.367 | 3.85 | 0.164 | 9.3 | 53.9 | 675 | 60 | 9 | 606 | 8.9 | 1.3 | 89.8 | 21 | -1000 | 1.12 | 150 | 0.7 | 160 | 3.8 | 152 | 8.6 | 157 | 19.7 | 56 | 16.1 |
| EVAL | A@400/4 + VPC@600/4 | 1.355 | 3.93 | 0.164 | 9.3 | 53.9 | 683 | 120 | 38 | 525 | 17.6 | 5.6 | 76.9 | 20 | -1000 | 2.33 | 151 | 15.9 | 160 | 12.5 | 152 | 15.1 | 159 | 21.4 | 61 | 31.1 |
| EVAL | A@600/6 + VPC@300/3 | 1.39 | 3.68 | 0.164 | 9.3 | 53.9 | 654 | 109 | 52 | 493 | 16.7 | 8 | 75.4 | 22 | -1000 | 2.19 | 147 | 6.1 | 159 | 10.1 | 148 | 8.8 | 148 | 35.8 | 52 | 34.6 |
| EVAL | A@600/6 + VPC@400/4 | 1.373 | 3.87 | 0.164 | 9.3 | 53.9 | 677 | 131 | 70 | 476 | 19.4 | 10.3 | 70.3 | 20 | -1000 | 2.61 | 150 | 8.7 | 160 | 11.9 | 152 | 13.2 | 158 | 36.1 | 57 | 38.6 |
| EVAL | A@600/6 + VPC@600/4 | 1.362 | 3.95 | 0.164 | 9.3 | 53.9 | 684 | 190 | 106 | 388 | 27.8 | 15.5 | 56.7 | 18 | -1000 | 4.04 | 151 | 17.9 | 160 | 18.8 | 152 | 22.4 | 160 | 44.4 | 61 | 45.9 |
| EVAL | A@1200/10 + VPC@300/3 | 1.435 | 3.68 | 0.164 | 9.3 | 53.9 | 654 | 255 | 222 | 177 | 39 | 33.9 | 27.1 | 15 | -1000 | 7.19 | 147 | 29.3 | 159 | 30.8 | 148 | 31.1 | 148 | 61.5 | 52 | 50 |
| EVAL | A@1200/10 + VPC@400/4 | 1.421 | 3.87 | 0.164 | 9.3 | 53.9 | 677 | 281 | 234 | 162 | 41.5 | 34.6 | 23.9 | 15 | -1000 | 7.88 | 150 | 30.7 | 160 | 33.1 | 152 | 32.2 | 158 | 65.8 | 57 | 50.9 |
| EVAL | A@1200/10 + VPC@600/4 | 1.408 | 3.95 | 0.164 | 9.3 | 53.9 | 684 | 305 | 235 | 144 | 44.6 | 34.4 | 21.1 | 14 | -1000 | 8.99 | 151 | 39.1 | 160 | 30.6 | 152 | 36.2 | 160 | 68.8 | 61 | 52.5 |

## FUNDED side -- A(250,4) x VPC{OFF,(200,2),(300,2)} (tools_recert_funded pattern, generalized)

CAVEAT (verbatim style from tools_recert_funded/apex_funded_40): monthly rolling starts overlap -> effective independent samples are far fewer than n_starts; every percentage below is MODEL-OBSERVED over a small number of effectively-independent overlapping-start samples on the 2022-2026-restricted A subset, not an i.i.d. probability. Wide confidence intervals apply throughout.

| label | n_starts | e_paid | med_paid | med_months | bust_pct | closed_max_pct | data_end_pct | safety_net_pct | med_days_to_safety_net | worst_day | section |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A@250/4 ALONE (VPC OFF) | 42 | 7292 | 7346 | 31.1 | 0 | 69 | 31 | 100 | 298 | -446 | FUNDED |
| A@250/4 + VPC@200/2 | 42 | 8567 | 8758 | 28.2 | 0 | 73.8 | 26.2 | 100 | 225.5 | -579 | FUNDED |
| A@250/4 + VPC@300/2 | 42 | 10510 | 12335 | 25.3 | 16.7 | 69 | 14.3 | 100 | 142 | -579 | FUNDED |

## PF freeze check: no cell exceeded PF>1.8.
