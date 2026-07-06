# Idea 6 — Second trade after first loss (SAME DAY) — RESEARCH ONLY / SIM CONDITIONAL

Day-scoped state (resets every calendar trading day) — distinct from the prior sprint's C3 (`tools_sprint_state_policies.DoubleLossAwarePolicy`), which acts on CROSS-DAY consecutive losses within one eval run.

## Mandatory canary (A_baseline, cap10/$1200 must reproduce 47.8/15.9/36.2/med16/n395)
- got: pass=47.8 bust=15.9 exp=36.2 med=16d n=395 -> MATCH

## Preregistered priors (printed before results)
- consecutive-loss (cross-day) policies died in the prior sprint (C0-C4, `stop_bucket_caps.md`/`cushion_aware_sizing.md`) -- this is a DIFFERENT (same-day) mechanism, not assumed to inherit that verdict.
- 'bust and expiry cost the same' -- E$/attempt (not computed here directly; pass%/bust%/exp% reported separately so this is not silently baked in).
- prior 2-loss cliff figure: P(pass|max-consec-losses>=2, CROSS-DAY)=14.4% (`tools_sprint_state_policies.PRIOR_BASELINE_COHORT`) -- quoted for context ONLY; NOT the same statistic as this file's SAME-DAY double-loss-day frequency below (do not conflate).
- question under test: does PREVENTING the 2nd same-day trade after a 1st-trade loss beat losing the trades that would have won (57%+ of 2nd trades win, per the brief)?

## Double/triple-loss-day frequency (baseline A, cap10/$1200, n=395 eval-starts, summed across ALL overlapping starts -- a single calendar day can appear in multiple starts' windows)
- trading-days-with-2+-taken-trades (summed over starts): 159
- of those, DOUBLE-loss days (1st AND 2nd taken trades both R<=0): 26 (16.4% of 2+-trade days)
- of days with 3+ taken trades, TRIPLE-loss days: 0

## Per-policy funnel + count basis (both bases)

| policy | base | n(eligible) | pass% | pass-COUNT | bust% | exp% | med days | 2+trade-days | double-loss-days | triple-loss-days |
|---|---|---|---|---|---|---|---|---|---|---|
| A_baseline | 10,$1200 | 395 | 47.8% | 189 | 15.9% | 36.2% | 16 | 159 | 26 | 0 |
| B_skip_2nd_after_1st_loss | 10,$1200 | 395 | 48.9% | 193 | 14.4% | 36.7% | 16 | 113 | 0 | 0 |
| C_2nd_after_loss_only_if_band>=2 | 10,$1200 | 395 | 48.9% | 193 | 15.2% | 35.9% | 16 | 129 | 7 | 0 |
| D_2nd_after_loss_only_if_opposite_dir | 10,$1200 | 395 | 48.1% | 190 | 14.4% | 37.5% | 16 | 118 | 0 | 0 |
| E_2nd_after_loss_only_if_same_dir | 10,$1200 | 395 | 48.6% | 192 | 15.9% | 35.4% | 16 | 154 | 26 | 0 |
| F_half_risk_2nd_after_loss | 10,$1200 | 395 | 48.6% | 192 | 15.9% | 35.4% | 16 | 159 | 26 | 0 |
| G_skip_2nd_after_loss_if_sub20pt_stop | 10,$1200 | 395 | 47.8% | 189 | 15.2% | 37.0% | 16 | 154 | 21 | 0 |
| H_stop_trading_after_any_loss_same_day | 10,$1200 | 395 | 48.9% | 193 | 14.4% | 36.7% | 16 | 113 | 0 | 0 |
| A_baseline | 15,$1000 | 395 | 55.2% | 218 | 13.4% | 31.4% | 15 | 140 | 17 | 0 |
| B_skip_2nd_after_1st_loss | 15,$1000 | 395 | 55.4% | 219 | 11.6% | 32.9% | 15 | 117 | 0 | 0 |
| C_2nd_after_loss_only_if_band>=2 | 15,$1000 | 395 | 55.4% | 219 | 12.7% | 31.9% | 15 | 124 | 7 | 0 |
| D_2nd_after_loss_only_if_opposite_dir | 15,$1000 | 395 | 55.4% | 219 | 11.6% | 32.9% | 15 | 117 | 0 | 0 |
| E_2nd_after_loss_only_if_same_dir | 15,$1000 | 395 | 55.2% | 218 | 13.4% | 31.4% | 15 | 140 | 17 | 0 |
| F_half_risk_2nd_after_loss | 15,$1000 | 395 | 55.2% | 218 | 12.9% | 31.9% | 15 | 140 | 17 | 0 |
| G_skip_2nd_after_loss_if_sub20pt_stop | 15,$1000 | 395 | 55.2% | 218 | 12.7% | 32.2% | 15 | 136 | 13 | 0 |
| H_stop_trading_after_any_loss_same_day | 15,$1000 | 395 | 55.4% | 219 | 11.6% | 32.9% | 15 | 117 | 0 | 0 |

## Per-year pass% — A (baseline) vs B (skip 2nd-after-loss), cap10/$1200

| year | A pass% (n) | B pass% (n) | delta |
|---|---|---|---|
| 2021 | 51.1% (45) | 51.1% (45) | +0.0pt |
| 2022 | 38.6% (70) | 38.6% (70) | +0.0pt |
| 2023 | 52.8% (89) | 57.3% (89) | +4.5pt |
| 2024 | 35.1% (74) | 35.1% (74) | +0.0pt |
| 2025 | 62.9% (89) | 62.9% (89) | +0.0pt |
| 2026 | 35.7% (28) | 35.7% (28) | +0.0pt |

**One-year-driven check:** B's entire pass% gain over A comes from 1 start-year out of 6 (all other years show +0.0pt) -> ONE-YEAR-DRIVEN, treat as noise on a thin sample (159 2+trade-days system-wide, 26 double-loss days).

## tr/wk lost to skip-based policies (B/G/H) vs baseline A
See `n_trades`-equivalent via the CSV's per-policy funnel rows; because trade frequency here is ~1.7-1.8/wk system-wide, days with a 2nd trade at all are the binding constraint on how much any of these policies can move the needle -- see the 2+trade-days count above before over-reading any pass% delta.

---
All numbers RESEARCH ONLY / SIM CONDITIONAL. No commits.
