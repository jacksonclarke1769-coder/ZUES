# Idea 5 — Stop-width treatment — RESEARCH ONLY / SIM CONDITIONAL

Mostly PRIOR ART. Cites `reports/eval_passrate_sprint/stop_bucket_caps.md` (B0-B5 all failed to beat flat at the same base, same-base verdict -0.2pt) and `reports/eval_passrate_sprint/fill_sensitivity.md` (tight-stop uniform penalty changes cap ordering by E$/attempt — cited, not rerun).

## (a) skip sub-20pt stops entirely — CITED (already tested as B3, prior sprint)

Source: `reports/eval_passrate_sprint/stop_bucket_caps.md (B3_<20-SKIP_rest-15)` — full SKIP of stop<20pt trades, rest cap15 (vs B0_all-10 flat baseline)

| policy | base | n | pass% | bust% | exp% |
|---|---|---|---|---|---|
| B0_all-10 (baseline) | 10,$1200 | 395 | 47.8 | 15.9 | 36.2 |
| B0_all-10 (baseline) | 15,$1000 | 395 | 44.8 | 12.7 | 42.5 |
| B3_<20-SKIP_rest-15 | 10,$1200 | 395 | 51.9 | 18.2 | 29.9 |
| B3_<20-SKIP_rest-15 | 15,$1000 | 395 | 50.4 | 13.4 | 36.2 |

**Same-base verdict (cited):** 1C same-base verdict (all bucket-cap policies incl. B3): best real-policy delta over its own same-base flat/null anchor is -0.2pt @10/1200 -- AGREES with 'account-state sizing policies all dead'. B3 ALONE (skip<20) shows +4.1pt vs B0 @10/1200, but its per-year table (stop_bucket_caps.md lines 175-182) shows 2024 +12.2pt / 2025 flat / 2021 +2.2pt spread across years, not single-year-concentrated -- a real but modest effect, not a denominator artifact (n=395 fixed both variants, no start-shrinkage mechanism here).

## (b) sub-20pt requires D1c band(atr) >= 2 — NEW cell (combo with Idea 4)

Stream filter (drop a trade only if stop<20pt AND band_atr<2) — a genuine denominator-shrink mechanism, so full funnel + count-basis is required (unlike (a)'s fixed-n state policy).

| n | WR% | PF | expR | totR | pass@10/1200 | eligible/pass-COUNT @10/1200 | pass@15/1000 | eligible/pass-COUNT @15/1000 | denom artifact? | auditor? |
|---|---|---|---|---|---|---|---|---|---|
| 392 | 60.2 | 2.421 | 0.4436 | +173.9 | 45.7% | 361/165 (base 395/189) | 51.5% | 361/186 (base 395/218) | none | no |

## (c) B5 wide-stop preference — TAG-ONLY (trade-level bucket stats on the certified 435, NOT the start-pooled replay stop_bucket_caps.md uses)

| bucket | n | WR% | PF | expR | totR |
|---|---|---|---|---|---|
| b1_<20 | 59 | 40.7 | 1.177 | 0.0864 | +5.1 |
| b2_20-30 | 82 | 58.5 | 2.78 | 0.5622 | +46.1 |
| b3_30-45 | 91 | 57.1 | 2.26 | 0.4352 | +39.6 |
| b4_45-60 | 65 | 49.2 | 1.506 | 0.1976 | +12.8 |
| b5_60-80 | 68 | 67.6 | 3.369 | 0.5935 | +40.4 |
| b6_80+ | 70 | 75.7 | 4.277 | 0.5706 | +39.9 |

## Everything else: citation table

| item | verdict | source |
|---|---|---|
| B0-B5 stop-bucket caps (all variants) | all failed to beat flat at same base (-0.2pt best real-policy delta) | `reports/eval_passrate_sprint/stop_bucket_caps.md` |
| fill-sensitivity tight-stop penalty | cap ordering by E$/attempt CHANGES under uniform 0.05R tight-stop damage on stop<45pt trades | `reports/eval_passrate_sprint/fill_sensitivity.md` |

---
All numbers RESEARCH ONLY / SIM CONDITIONAL. No commits.
