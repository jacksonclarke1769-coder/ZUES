# A5 — Exit Recheck on the Honest Stream

HONEST-RECERT DRAFT — pending auditor verdict + operator approval

**PRE-REGISTERED PRIOR**: SINGLE_1R's old promotion was an F1 artifact; exit comparisons are certification-sensitive; report numbers, no recommendation.

SALVAGE PROGRAM Track A. Mechanical output only — no interpretation, no candidate selection.

## Source

Kept stream's 583 raw trades (D1c-kept, ny_am, exit3 signal set — same filter as `tools_phase3_config_sweep.a_streams_d1c()['exit3']`), re-derived with full entry/stop/target/fill-bar precision (not from a CSV round-trip). CANARY: variant 1 (EXIT3 baseline, using the imported unmodified `tools_1m_truth_recert.walk_1m` with the model's own stored target) reproduces the kept stream's n=583, PF=1.361, totR=+89.2R EXACTLY.

## Variants

1. EXIT3 baseline (50%@+1R / 50%@+2R-ish model target) — CANARY.
2. Fixed all-at-1R (no partial).
3. Fixed all-at-1.5R (no partial).
4. Fixed all-at-2R (no partial).
5. BE-after-TP1: exit3 split, but the remaining 50%'s stop moves to entry starting the bar AFTER the +1R partial fills.
6. Trail-after-1R: no partial/fixed target; once +1R touched, stop trails at (highest close since the trigger bar) minus 1R distance, evaluated per 1m bar, stop-first.

All six preserve the F1 no-same-bar guard, stop-first ordering, and A_SLIP-on-stop convention from `tools_1m_truth_recert.walk_1m` (variants 1-4 call that function unmodified; variants 5-6 are verbatim-copied-and-extended, diffed in code comments).

## Results (all n=583 fillable trades unless noted)

| variant | n | WR% | PF | expR | totR | maxDD-R |
|---|---|---|---|---|---|---|
| 1_exit3_baseline | 583 | 44.9 | 1.361 | +0.153 | +89.2 | 10.2 |
| 2_fixed_1R | 583 | 56.1 | 1.271 | +0.115 | +66.9 | 8.1 |
| 3_fixed_1.5R | 583 | 48.9 | 1.337 | +0.166 | +96.9 | 9.4 |
| 4_fixed_2R | 583 | 44.1 | 1.355 | +0.191 | +111.6 | 15.4 |
| 5_be_after_tp1 | 583 | 56.1 | 1.297 | +0.126 | +73.4 | 8.4 |
| 6_trail_after_1R | 583 | 50.9 | 1.325 | +0.141 | +82.2 | 14.0 |

## Per-year totR

| variant | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 1_exit3_baseline | +13.3 | +3.8 | +17.3 | +4.5 | +37.3 | +13.0 |
| 2_fixed_1R | +13.8 | +3.9 | +7.5 | +4.0 | +28.3 | +9.4 |
| 3_fixed_1.5R | +7.1 | +0.0 | +23.1 | +11.2 | +43.7 | +11.6 |
| 4_fixed_2R | +12.8 | +3.7 | +27.1 | +5.0 | +46.4 | +16.7 |
| 5_be_after_tp1 | +14.8 | +1.3 | +11.8 | -2.0 | +35.3 | +12.1 |
| 6_trail_after_1R | +13.1 | +5.0 | +22.2 | -1.3 | +31.2 | +12.0 |

## Eval funnel (pinned formulas from the re-cert — `tools_account_size_research.py`, imported not retyped)


**(10, $1200)**

| variant | eligible_starts | pass% | bust% | exp% | median_days_pass | mean_days_all | pass_count | funded_per_slot_year |
|---|---|---|---|---|---|---|---|---|
| 1_exit3_baseline | 525 | 31.4 | 37.3 | 31.2 | 16.0 | 20.04 | 165 | 5.7287 |
| 2_fixed_1R | 525 | 29.3 | 28.4 | 42.3 | 19.0 | 23.07 | 154 | 4.6433 |
| 3_fixed_1.5R | 525 | 40.2 | 36.6 | 23.2 | 15.0 | 18.72 | 211 | 7.8432 |
| 4_fixed_2R | 525 | 41.5 | 39.4 | 19.0 | 13.0 | 16.87 | 218 | 8.992 |
| 5_be_after_tp1 | 525 | 33.9 | 29.0 | 37.1 | 17.0 | 21.62 | 178 | 5.7271 |
| 6_trail_after_1R | 525 | 33.7 | 31.8 | 34.5 | 14.0 | 20.25 | 177 | 6.0801 |

**(4, $400)**

| variant | eligible_starts | pass% | bust% | exp% | median_days_pass | mean_days_all | pass_count | funded_per_slot_year |
|---|---|---|---|---|---|---|---|---|
| 1_exit3_baseline | 521 | 0.4 | 0.0 | 99.6 | 27.0 | 29.99 | 2 | 0.0468 |
| 2_fixed_1R | 521 | 0.0 | 0.0 | 100.0 | - | 30.0 | 0 | 0.0 |
| 3_fixed_1.5R | 521 | 1.0 | 0.0 | 99.0 | 24.0 | 29.95 | 5 | 0.117 |
| 4_fixed_2R | 521 | 3.1 | 0.8 | 96.2 | 25.0 | 29.71 | 16 | 0.3775 |
| 5_be_after_tp1 | 521 | 0.4 | 0.0 | 99.6 | 27.0 | 29.99 | 2 | 0.0468 |
| 6_trail_after_1R | 521 | 1.2 | 0.0 | 98.8 | 25.5 | 29.96 | 6 | 0.1404 |

No recommendation is made here — exit comparisons are certification-sensitive per the pre-registered prior above; the auditor decides.

