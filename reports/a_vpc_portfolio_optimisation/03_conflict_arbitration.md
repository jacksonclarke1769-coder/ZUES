# 03 -- A+VPC conflict/arbitration rules (Lane 2)

RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing. All rows at the pinned BASELINE sizing A@600/6 (2022+) + VPC@600/4 (1m-truth). Rules are event-stream transforms applied to the merged, ts-sorted, direction-tagged row stream BEFORE `ASR.build_events`/`ASR.day_rows` (see module docstring for the full rule-by-rule definitions and the R1 30min-bucket / strict-60min honest proxy note).

R0 naive-union baseline canary: pass=28.7 bust=17.0 exp=54.4 n=684 (expected {'pass_pct': 28.7, 'bust_pct': 17.0, 'exp_pct': 54.4, 'n': 684}, tol 0.3pp) -> PASS

E$ formula: (pass_pct/100) * e_paid_funded - 67.5, where e_paid_funded is `VR.funded_cell_report`'s E[paid] on the SAME rule-filtered rows at the established funded pair A@250/4+VPC@200/2 (`tools_salvage_vpc_reeval.part2_funded`).

Denominator-artifact flag (DEC-20260706-1108, mechanical): bust_pct improved vs R0 AND funded_per_slot_year LOWER than R0 -- flagged rows may be cutting bust mainly by shrinking the number of funded-per-year slots, not via a genuine edge change.

| rule | desc | n_events | pf_dollar | trades_per_week | worst_week_usd | e_paid_funded | e_dollar | eligible_starts | pass_count | bust_count | exp_count | pass_pct | bust_pct | exp_pct | med_days_pass | worst_day_usd | funded_per_slot_year | n_days | dl_freq_pct | tl_freq_pct | joint_loss_days | slip0.015_pass_pct | slip0.015_bust_pct | slip0.03_pass_pct | slip0.03_bust_pct | slip0.046_pass_pct | slip0.046_bust_pct | denominator_artifact_flag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R0 | naive union (baseline) | 921 | 1.377 | 3.96 | -2041 | 8622 | 2407 | 684 | 196 | 116 | 372 | 28.7 | 17 | 54.4 | 18 | -1000 | 4.22 | 699 | 9.2 | 52.6 | 64 | 26.5 | 17.8 | 24.9 | 17.8 | 23 | 18.6 | False |
| R1a | one-position-at-a-time (30min bucket proxy) | 915 | 1.375 | 3.93 | -2041 | 8571 | 2392 | 684 | 196 | 109 | 379 | 28.7 | 15.9 | 55.4 | 19 | -1000 | 4.19 | 699 | 9.2 | 52.8 | 64 | 26.3 | 16.8 | 24.4 | 17.8 | 22.5 | 18.7 | True |
| R1b | one-position-at-a-time (strict 60min/trade) | 892 | 1.415 | 3.84 | -2041 | 8470 | 2380 | 684 | 198 | 102 | 384 | 28.9 | 14.9 | 56.1 | 19 | -1000 | 4.22 | 699 | 8.9 | 52.9 | 62 | 27.2 | 15.5 | 25.7 | 16.4 | 24.3 | 17.1 | False |
| R2 | priority-A (drop VPC within 60min of an A event) | 921 | 1.377 | 3.96 | -2041 | 8622 | 2407 | 684 | 196 | 116 | 372 | 28.7 | 17 | 54.4 | 18 | -1000 | 4.22 | 699 | 9.2 | 52.6 | 64 | 26.5 | 17.8 | 24.9 | 17.8 | 23 | 18.6 | False |
| R3 | priority-VPC (drop A within 60min of a VPC event) | 921 | 1.377 | 3.96 | -2041 | 8622 | 2407 | 684 | 196 | 116 | 372 | 28.7 | 17 | 54.4 | 18 | -1000 | 4.22 | 699 | 9.2 | 52.6 | 64 | 26.5 | 17.8 | 24.9 | 17.8 | 23 | 18.6 | False |
| R4 | no same-direction duplicate within 60min | 900 | 1.403 | 3.87 | -2041 | 8614 | 2405 | 684 | 196 | 110 | 378 | 28.7 | 16.1 | 55.3 | 19 | -1000 | 4.18 | 699 | 9 | 52.5 | 63 | 26.9 | 16.7 | 25.4 | 17.7 | 24 | 18.3 | True |
| R5 | no opposite-direction conflict within 60min | 911 | 1.397 | 3.92 | -2041 | 8700 | 2447 | 684 | 198 | 108 | 378 | 28.9 | 15.8 | 55.3 | 18 | -1000 | 4.26 | 699 | 9 | 53.1 | 63 | 26.5 | 16.7 | 24.6 | 16.5 | 23 | 17.4 | False |
| R6 | max-one-loser-then-stop (day) | 804 | 1.524 | 3.46 | -1927 | 8953 | 2314 | 684 | 182 | 75 | 427 | 26.6 | 11 | 62.4 | 20 | -1000 | 3.73 | 699 | 0 | 56.2 | 0 | 25.1 | 13 | 23.7 | 13.5 | 22.4 | 13.9 | True |
| R7 | VPC only before A's first event / A-flat days | 741 | 1.365 | 3.19 | -1927 | 7198 | 1099 | 684 | 111 | 88 | 485 | 16.2 | 12.9 | 70.9 | 22 | -1000 | 2.15 | 699 | 0 | 53.6 | 0 | 15.4 | 13 | 14.5 | 13 | 13.3 | 13.7 | True |
| R8 | time-separated (A<=11:30, VPC>=11:30 ET) | 904 | 1.362 | 3.89 | -2041 | 9084 | 2385 | 675 | 182 | 114 | 379 | 27 | 16.9 | 56.1 | 18 | -1000 | 3.93 | 689 | 9.1 | 53.1 | 63 | 24.6 | 17.8 | 22.8 | 18.5 | 21.3 | 18.2 | True |
| R9 | VPC only strictly after an A win same day | 608 | 1.588 | 2.62 | -1627 | 9303 | 2286 | 463 | 117 | 19 | 327 | 25.3 | 4.1 | 70.6 | 21 | -1000 | 3.39 | 475 | 0.4 | 55.4 | 2 | 23.5 | 5.2 | 22.2 | 7.1 | 20.3 | 7.6 | True |
| R10 | VPC only on A-flat days (calendar widener) | 741 | 1.365 | 3.19 | -1927 | 7198 | 1099 | 684 | 111 | 88 | 485 | 16.2 | 12.9 | 70.9 | 22 | -1000 | 2.15 | 699 | 0 | 53.6 | 0 | 15.4 | 13 | 14.5 | 13 | 13.3 | 13.7 | True |

## Denominator-artifact flags: 7/12 rows
| rule | desc | pass_pct | bust_pct | funded_per_slot_year |
| --- | --- | --- | --- | --- |
| R1a | one-position-at-a-time (30min bucket proxy) | 28.7 | 15.9 | 4.19 |
| R4 | no same-direction duplicate within 60min | 28.7 | 16.1 | 4.18 |
| R6 | max-one-loser-then-stop (day) | 26.6 | 11 | 3.73 |
| R7 | VPC only before A's first event / A-flat days | 16.2 | 12.9 | 2.15 |
| R8 | time-separated (A<=11:30, VPC>=11:30 ET) | 27 | 16.9 | 3.93 |
| R9 | VPC only strictly after an A win same day | 25.3 | 4.1 | 3.39 |
| R10 | VPC only on A-flat days (calendar widener) | 16.2 | 12.9 | 2.15 |


Runtime this section: 2.0s
Firewall (before/after, must be unchanged):
  config_eval_locked.py: UNCHANGED
  config_funded_locked.py: UNCHANGED
  config_defaults.py: UNCHANGED
  auto_safety.py: UNCHANGED