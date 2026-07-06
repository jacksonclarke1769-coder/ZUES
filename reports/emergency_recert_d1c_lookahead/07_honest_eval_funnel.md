# 07 — Honest Eval Funnel Comparison

HONEST-RECERT DRAFT — pending auditor verdict + operator approval

INC-20260706-1141. Numbers only, no conclusions -- the auditor writes the interpretation.

Row 1 is the pre-fix, lookahead-invalidated cap-10/$1,200 row, copied verbatim for reference (not recomputed -- built on the pre-fix `run_d1c_real.attach_drift` kept-set, see `04_invalidated_numbers.md`). Row 2 is the honest re-cert of the same (cap=10, budget=$1,200) config from `05_honest_machine_certification.md` / `06_honest_sizing_matrix.csv`. Rows 3-7 are the top-5 cells from `06_honest_sizing_matrix.csv` ranked by `funded_per_slot_year` desc (DEC-20260706-1108 count-basis metric), plus the lowest-`bust_pct` cell among cells with `pass_pct>=25`.

`attempts_per_funded` = eligible_starts / pass_count. `fee_drag_at_131`/`fee_drag_at_30` = attempts_per_funded x $131 (sticker) / x $30 (promo) -- expected up-front eval-entry dollars spent per one funded pass, ignoring monthly re-eval fees.

| label | budget | cap | pass_pct | bust_pct | exp_pct | median_days_pass | mean_days_all | pass_count | eligible_starts | funded_per_slot_year | E_proxy | mean_risk_usd | mean_contracts | dl_freq | tl_freq | trades_per_eval | attempts_per_funded | fee_drag_at_131 | fee_drag_at_30 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| INVALIDATED-LOOKAHEAD (pre-fix) | 1200 | 10 | 47.8 | 15.9 | 36.2 | 16 | n/a (copied verbatim, not recomputed) | n/a | 395 | n/a (copied verbatim, not recomputed) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| honest-A10/$1200 | 1200 | 10 | 31.4 | 37.1 | 31.4 | 16.0 | 20.09 | 165 | 525 | 5.7146 | 3011.9 | 102.85 | 8.926 | 75.8 | 32.8 | 6.92 | 3.182 | 416.8 | 95.5 |
| honest-top1-by-funded_per_slot_year | 1100 | 20 | 37.1 | 50.7 | 12.2 | 14.0 | 15.29 | 195 | 525 | 8.8752 | 3583.3 | 102.85 | 12.947 | 67.4 | 14.9 | 5.16 | 2.692 | 352.7 | 80.8 |
| honest-top2-by-funded_per_slot_year | 1200 | 20 | 33.9 | 55.2 | 10.9 | 12.0 | 14.31 | 178 | 525 | 8.6513 | 3259.5 | 102.85 | 13.666 | 65.1 | 11.8 | 4.82 | 2.949 | 386.3 | 88.5 |
| honest-top3-by-funded_per_slot_year | 1100 | 15 | 35.8 | 44.2 | 20.0 | 14.0 | 16.99 | 188 | 525 | 7.6964 | 3450.0 | 102.85 | 11.322 | 69.1 | 22.9 | 5.79 | 2.793 | 365.9 | 83.8 |
| honest-top4-by-funded_per_slot_year | 1200 | 15 | 34.3 | 48.2 | 17.5 | 13.0 | 16.28 | 180 | 525 | 7.6904 | 3297.6 | 102.85 | 11.765 | 68.4 | 19.4 | 5.53 | 2.917 | 382.1 | 87.5 |
| honest-top5-by-funded_per_slot_year | 1000 | 20 | 34.9 | 48.2 | 17.0 | 15.0 | 17.12 | 183 | 525 | 7.435 | 3354.7 | 102.85 | 12.154 | 69.5 | 21.9 | 5.76 | 2.869 | 375.8 | 86.1 |
| honest-lowest-bust(pass_pct>=25) | 1100 | 8 | 25.0 | 26.1 | 49.0 | 16.0 | 23.23 | 131 | 525 | 3.9232 | 2364.2 | 102.85 | 7.367 | 79.6 | 41.7 | 7.94 | 4.008 | 525.0 | 120.2 |

## Double-loss cliff (honest A10/$1,200 config)

P(pass | attempt experienced >=2 consecutive losing trades before terminal outcome), honest (cap=10, budget=$1,200) config: cohort size = 398 of 525 eligible starts, cohort PASS count = 60, conditional pass% = 15.1. (Unconditional pass% for this config = 31.4, n=525, pass_count=165.)

## Trades/week sensitivity (note, not a column)

Per `honest_d1c_stream_summary.json`: honest-stream (kept=True) rate = 2.236/wk (583 trades / 260.7 weeks); unfiltered-705 rate = 2.704/wk. The task brief cited "2.24/wk vs old 1.68/wk" -- 2.24 matches the honest rate to rounding, but I could not independently reproduce "1.68/wk" from any artifact in `reports/emergency_recert_d1c_lookahead/` (the closest computed figure, unfiltered-705, is 2.704/wk, not 1.68). Flagging rather than silently reconciling -- numbers only, no fix attempted.

## Precision note (adjudicated)

The canonical honest cap-10/$1,200 row is 31.4/37.3/31.2 (regenerated pipeline value; matches the auditor's original emergency read exactly and is now the `CANARY_EXPECT` in `tools_sim_parity_check.py`). The `honest-A10/$1200` row in the table above (37.1/31.4) is CSV-derived and differs on one boundary start -- a 1-ULP float round-trip through the CSV flips a single knife-edge eligible start between BUST and EXPIRE, not an engine disagreement. Difference is immaterial: +-0.2pp, 1/525 starts.

