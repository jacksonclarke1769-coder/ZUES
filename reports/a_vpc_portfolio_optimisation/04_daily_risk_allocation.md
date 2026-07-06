# 04 -- A+VPC daily risk allocation (Lane 2)

RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing. Naive-union (R0, no arbitration) rows only -- these are pure eval-side risk-policy knobs on top of the baseline A@600/6(2022+)+VPC@600/4(1m-truth) sizing, via `day_replay_variant` (generalizes `ASR.day_rows` with a variable shared daily stop and two optional intraday gates; canaried to reproduce `ASR.day_rows` exactly at shared_stop=550, no gates).

E$ formula: (pass_pct/100) * e_paid_funded - 67.5, where e_paid_funded = $8,622 is HELD CONSTANT across every row in this table -- computed once on the UNFILTERED rows at the established funded pair A@250/4+VPC@200/2 (these variants are eval-side risk knobs, not a strategy change a separately-governed funded account would inherit; see module docstring).

Denominator-artifact flag: bust_pct improved vs the shared_stop=550 baseline row AND funded_per_slot_year LOWER than that baseline.

| variant_group | variant | shared_stop | budget_a | cap_a | budget_v | cap_v | max_losses | no_new_after_loss | e_dollar | trades_per_week | trades_per_week_lost_to_gate | dll_touch_freq_pct | eligible_starts | pass_count | bust_count | exp_count | pass_pct | bust_pct | exp_pct | med_days_pass | worst_day_usd | funded_per_slot_year | denominator_artifact_flag | slip0.015_pass_pct | slip0.015_bust_pct | slip0.03_pass_pct | slip0.03_bust_pct | slip0.046_pass_pct | slip0.046_bust_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| shared_stop | shared_stop=400 | 400 | 600 | 6 | 600 | 4 | nan | nan | 2312 | 3.94 | 0 | 0.1 | 684 | 189 | 91 | 404 | 27.6 | 13.3 | 59.1 | 18 | -1000 | 3.98 | True | 25.9 | 14.2 | 24.7 | 16.2 | 22.7 | 17.4 |
| shared_stop | shared_stop=500 | 500 | 600 | 6 | 600 | 4 | nan | nan | 2407 | 3.94 | 0 | 0.4 | 684 | 196 | 97 | 391 | 28.7 | 14.2 | 57.2 | 19 | -1000 | 4.17 | True | 26.5 | 15.2 | 24.9 | 16.8 | 23 | 18 |
| shared_stop | shared_stop=550 | 550 | 600 | 6 | 600 | 4 | nan | nan | 2407 | 3.94 | 0 | 1.1 | 684 | 196 | 116 | 372 | 28.7 | 17 | 54.4 | 18 | -1000 | 4.22 | False | 26.5 | 17.8 | 24.9 | 17.8 | 23 | 18.6 |
| shared_stop | shared_stop=600 | 600 | 600 | 6 | 600 | 4 | nan | nan | 2424 | 3.94 | 0 | 1.7 | 684 | 198 | 140 | 346 | 28.9 | 20.5 | 50.6 | 18 | -1000 | 4.33 | False | 26.6 | 20.3 | 25.1 | 20.8 | 22.5 | 22.2 |
| shared_stop | shared_stop=700 | 700 | 600 | 6 | 600 | 4 | nan | nan | 2424 | 3.94 | 0 | 1.7 | 684 | 198 | 140 | 346 | 28.9 | 20.5 | 50.6 | 18 | -1000 | 4.33 | False | 26.5 | 22.2 | 25 | 22.7 | 22.8 | 24.4 |
| shared_stop | shared_stop=800 | 800 | 600 | 6 | 600 | 4 | nan | nan | 2424 | 3.94 | 0 | 1.7 | 684 | 198 | 140 | 346 | 28.9 | 20.5 | 50.6 | 18 | -1000 | 4.33 | False | 26.5 | 22.2 | 25 | 22.7 | 22.8 | 24.4 |
| lane_caps | A@300/6+VPC@200/4 | 550 | 300 | 6 | 200 | 4 | nan | nan | -68 | 3.05 | 0 | 0 | 576 | 0 | 0 | 576 | 0 | 0 | 100 | nan | -580 | 0 | True | 0 | 0 | 0 | 0 | 0 | 0 |
| lane_caps | A@300/6+VPC@300/4 | 550 | 300 | 6 | 300 | 4 | nan | nan | 191 | 3.62 | 0 | 0 | 644 | 19 | 0 | 625 | 3 | 0 | 97 | 23 | -748 | 0.36 | True | 2.6 | 0.2 | 2.6 | 0.5 | 2.3 | 0.6 |
| lane_caps | A@300/6+VPC@400/4 | 550 | 300 | 6 | 400 | 4 | nan | nan | 536 | 3.81 | 0 | 0.1 | 671 | 47 | 11 | 613 | 7 | 1.6 | 91.4 | 22 | -1000 | 0.88 | True | 6.3 | 1.6 | 5.5 | 1.8 | 5.5 | 2.1 |
| lane_caps | A@300/6+VPC@500/4 | 550 | 300 | 6 | 500 | 4 | nan | nan | 1002 | 3.86 | 0 | 0.3 | 678 | 84 | 19 | 575 | 12.4 | 2.8 | 84.8 | 20 | -1000 | 1.59 | True | 11.7 | 4 | 10.9 | 5.5 | 10.3 | 5.8 |
| lane_caps | A@400/6+VPC@200/4 | 550 | 400 | 6 | 200 | 4 | nan | nan | 62 | 3.09 | 0 | 0 | 584 | 9 | 1 | 574 | 1.5 | 0.2 | 98.3 | 29 | -703 | 0.19 | True | 1.4 | 0.2 | 0.7 | 0.2 | 0.3 | 0.9 |
| lane_caps | A@400/6+VPC@300/4 | 550 | 400 | 6 | 300 | 4 | nan | nan | 476 | 3.66 | 0 | 0 | 650 | 41 | 4 | 605 | 6.3 | 0.6 | 93.1 | 24 | -703 | 0.78 | True | 5.7 | 1.7 | 5.1 | 3.2 | 4.6 | 3.4 |
| lane_caps | A@400/6+VPC@400/4 | 550 | 400 | 6 | 400 | 4 | nan | nan | 829 | 3.85 | 0 | 0.1 | 675 | 70 | 26 | 579 | 10.4 | 3.9 | 85.8 | 20 | -1000 | 1.32 | True | 9.3 | 4.1 | 8.6 | 4.1 | 8.6 | 4.3 |
| lane_caps | A@400/6+VPC@500/4 | 550 | 400 | 6 | 500 | 4 | nan | nan | 1390 | 3.9 | 0 | 0.1 | 682 | 115 | 34 | 533 | 16.9 | 5 | 78.2 | 20 | -1000 | 2.22 | True | 15.7 | 5.7 | 14.8 | 6.2 | 13.6 | 7.2 |
| lane_caps | A@500/6+VPC@200/4 | 550 | 500 | 6 | 200 | 4 | nan | nan | 476 | 3.11 | 0 | 0 | 588 | 37 | 7 | 544 | 6.3 | 1.2 | 92.5 | 24 | -882 | 0.78 | True | 5.3 | 1.2 | 4.8 | 1.2 | 4.1 | 1.7 |
| lane_caps | A@500/6+VPC@300/4 | 550 | 500 | 6 | 300 | 4 | nan | nan | 984 | 3.68 | 0 | 0 | 654 | 80 | 29 | 545 | 12.2 | 4.4 | 83.3 | 22 | -882 | 1.55 | True | 10.7 | 5 | 9.9 | 5.5 | 9.3 | 6 |
| lane_caps | A@500/6+VPC@400/4 | 550 | 500 | 6 | 400 | 4 | nan | nan | 1260 | 3.87 | 0 | 0.1 | 677 | 104 | 41 | 532 | 15.4 | 6.1 | 78.6 | 20 | -1000 | 2.01 | True | 13.6 | 6.5 | 12.9 | 8.1 | 12.3 | 9.6 |
| lane_caps | A@500/6+VPC@500/4 | 550 | 500 | 6 | 500 | 4 | nan | nan | 1786 | 3.92 | 0 | 0.3 | 683 | 147 | 60 | 476 | 21.5 | 8.8 | 69.7 | 19 | -1000 | 2.93 | True | 20.1 | 10.2 | 19 | 11.7 | 17.6 | 14.5 |
| lane_caps | A@600/6+VPC@200/4 | 550 | 600 | 6 | 200 | 4 | nan | nan | 795 | 3.11 | 0 | 0.2 | 588 | 59 | 20 | 509 | 10 | 3.4 | 86.6 | 22 | -1000 | 1.26 | True | 8.5 | 3.6 | 8 | 4.3 | 7.1 | 6.1 |
| lane_caps | A@600/6+VPC@300/4 | 550 | 600 | 6 | 300 | 4 | nan | nan | 1329 | 3.68 | 0 | 0.1 | 654 | 106 | 51 | 497 | 16.2 | 7.8 | 76 | 22 | -1000 | 2.12 | True | 14.8 | 8.3 | 13.8 | 8.6 | 12.8 | 8.6 |
| lane_caps | A@600/6+VPC@400/4 | 550 | 600 | 6 | 400 | 4 | nan | nan | 1614 | 3.87 | 0 | 0.3 | 677 | 132 | 71 | 474 | 19.5 | 10.5 | 70 | 20 | -1000 | 2.63 | True | 18.6 | 10.9 | 17.3 | 11.2 | 15.4 | 12.6 |
| lane_caps | A@600/6+VPC@500/4 | 550 | 600 | 6 | 500 | 4 | nan | nan | 2131 | 3.92 | 0 | 0.6 | 683 | 174 | 89 | 420 | 25.5 | 13 | 61.5 | 19 | -1000 | 3.58 | True | 24 | 14.5 | 22.7 | 13.2 | 20.9 | 15.1 |
| max_losses | max_1_loss_stop | 550 | 600 | 6 | 600 | 4 | 1 | nan | 2226 | 3.94 | 0.44 | 0.1 | 684 | 182 | 75 | 427 | 26.6 | 11 | 62.4 | 20 | -1000 | 3.73 | True | 25.1 | 13 | 23.7 | 13.5 | 22.4 | 13.9 |
| max_losses | max_2_loss_stop | 550 | 600 | 6 | 600 | 4 | 2 | nan | 2407 | 3.94 | 0.02 | 1 | 684 | 196 | 113 | 375 | 28.7 | 16.5 | 54.8 | 18 | -1000 | 4.21 | True | 26.5 | 17 | 24.9 | 17.3 | 23 | 18.6 |
| no_new_after_loss | no_new_trade_after_-500 | 550 | 600 | 6 | 600 | 4 | nan | 500 | 2407 | 3.94 | 0.06 | 0.4 | 684 | 196 | 97 | 391 | 28.7 | 14.2 | 57.2 | 19 | -1000 | 4.17 | True | 26.5 | 15.2 | 24.9 | 16.8 | 23 | 18 |

## Denominator-artifact flags: 21/25 rows
| variant_group | variant | pass_pct | bust_pct | funded_per_slot_year |
| --- | --- | --- | --- | --- |
| shared_stop | shared_stop=400 | 27.6 | 13.3 | 3.98 |
| shared_stop | shared_stop=500 | 28.7 | 14.2 | 4.17 |
| lane_caps | A@300/6+VPC@200/4 | 0 | 0 | 0 |
| lane_caps | A@300/6+VPC@300/4 | 3 | 0 | 0.36 |
| lane_caps | A@300/6+VPC@400/4 | 7 | 1.6 | 0.88 |
| lane_caps | A@300/6+VPC@500/4 | 12.4 | 2.8 | 1.59 |
| lane_caps | A@400/6+VPC@200/4 | 1.5 | 0.2 | 0.19 |
| lane_caps | A@400/6+VPC@300/4 | 6.3 | 0.6 | 0.78 |
| lane_caps | A@400/6+VPC@400/4 | 10.4 | 3.9 | 1.32 |
| lane_caps | A@400/6+VPC@500/4 | 16.9 | 5 | 2.22 |
| lane_caps | A@500/6+VPC@200/4 | 6.3 | 1.2 | 0.78 |
| lane_caps | A@500/6+VPC@300/4 | 12.2 | 4.4 | 1.55 |
| lane_caps | A@500/6+VPC@400/4 | 15.4 | 6.1 | 2.01 |
| lane_caps | A@500/6+VPC@500/4 | 21.5 | 8.8 | 2.93 |
| lane_caps | A@600/6+VPC@200/4 | 10 | 3.4 | 1.26 |
| lane_caps | A@600/6+VPC@300/4 | 16.2 | 7.8 | 2.12 |
| lane_caps | A@600/6+VPC@400/4 | 19.5 | 10.5 | 2.63 |
| lane_caps | A@600/6+VPC@500/4 | 25.5 | 13 | 3.58 |
| max_losses | max_1_loss_stop | 26.6 | 11 | 3.73 |
| max_losses | max_2_loss_stop | 28.7 | 16.5 | 4.21 |
| no_new_after_loss | no_new_trade_after_-500 | 28.7 | 14.2 | 4.17 |

## Which policy keeps pass while cutting the bust tail (mechanical, no winner-picking): rows where bust_pct < baseline bust_pct AND pass_pct >= baseline pass_pct AND denominator_artifact_flag is False:
(none)


Runtime this section: 2.5s
Firewall (before/after, must be unchanged):
  config_eval_locked.py: UNCHANGED
  config_funded_locked.py: UNCHANGED
  config_defaults.py: UNCHANGED
  auto_safety.py: UNCHANGED