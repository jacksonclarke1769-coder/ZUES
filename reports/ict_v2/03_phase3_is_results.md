# ICT V2 Phase 3, WP-F — IS Measurement Results

**Governs:** `research/ict_v2/PREREG_PHASE3.md` v1.0 + Amendment v1.1, git hash `cd652ea81093`. **Scope:** WP-F IS run (§4-§5) on the *_is.parquet files ONLY. The frozen HOLDOUT files were NOT opened — the §6 confirmatory pass is a separate later execution. No PF/WR/expectancy; nothing outside the 17 preregistered cells.

## 1. Synthetic self-test (§8, mandatory gate before the IS run)

| check | result | required |
|---|:---:|:---:|
| planted_effect_PASSES | True | True |
| null_placebo_FAILS | True | True |
| b_confound_DIES_at_G2 | True | True |
| f2_planted_uplift_PASSES_G1 | True | True |
| f2_null_uplift_FAILS_G1 | True | True |

**Self-test verdict: PASSED.** A planted effect passes all gates, a null placebo fails G1, a B-confound placebo (real raw effect fully explained by baseline B) dies at G2, and the F2 AUC path passes on planted signal / fails on noise. The IS run below was permitted only because these all behaved correctly.

## 2. Estimators & gates (as implemented, per §4-§5)

- Contrast cells (F1, F3-F7): Δ = mean/proportion(group A) − (group B); 95% CI + two-sided p via the weekly block bootstrap (resample calendar weeks, 2,000 draws, vectorized via per-week sums). Floors: probabilities |Δ|≥0.05, magnitudes |Δ|≥0.10 ATR.
- F2 (prediction): standardized logistic regression (IRLS, numpy-only — sklearn is not installed), blocked 5-fold CV by calendar week, metric = out-of-fold AUC uplift of (B+ICT) over (B alone); CI/p via the weekly block bootstrap of the AUC uplift (exact c⊤Uc quadratic form over the cross-week Mann-Whitney matrix).
- G1: CI excludes 0 AND floor met (F2: uplift ≥0.02 & CI excl 0). G2: B-residualized contrast retains ≥50% of raw size, same sign (F2: uplift over B IS the metric → holds by construction). G3: sign consistent in ≥3 of 4 IS-years AND no year >60% of the aggregate (n·Δ share). G4: Benjamini-Hochberg q=0.10 within family.
- Two-outcome cells: each declared outcome is a separate statistic; the CELL survives iff ≥1 outcome passes G1∧G2∧G3∧G4; BH is applied within each family over ALL its (cell,outcome) statistics (conservative FDR reading; the prereg's cell/outcome granularity is imprecise — flagged for Fable).

## 3. Per-cell / per-outcome results (contrast families F1, F3–F7)

| cell | family | unit | outcome | groups (A vs B) | Δ | 95% CI | floor✓ | G1 | G2 ret | G2 | per-yr Δ signs | G3 | p | q(BH) | G4 | verdict |
|---|---|---|---|---|---:|---|:---:|:---:|---:|:---:|---|:---:|---:|---:|:---:|:---:|
| F1a | F1 | excursion_episodes | abs_fwd24 | weekly vs intraday | -0.235 | [-0.285, -0.183] | ✓ | True | 0.25 | False | −−−− | True | 0.0000 | 0.0000 | True | dies |
| F1a | F1 | excursion_episodes | P(SWEEP_CONFIRMED) | weekly vs intraday | -0.149 | [-0.157, -0.140] | ✓ | True | 1.02 | True | −−−− | True | 0.0000 | 0.0000 | True | SURVIVES |
| F1b | F1 | excursion_episodes | abs_fwd24 | prior_test>=1 vs prior_test=0 | -0.020 | [-0.056, 0.011] | ✗ | False | 2.18 | True | −+−− | False | 0.2400 | 0.3000 | False | dies |
| F1b | F1 | excursion_episodes | P(SWEEP_CONFIRMED) | prior_test>=1 vs prior_test=0 | -0.003 | [-0.010, 0.003] | ✗ | False | 0.95 | True | −+−− | True | 0.3150 | 0.3500 | False | dies |
| F1c | F1 | excursion_episodes | abs_fwd24 | equality vs no_equality | 0.288 | [0.235, 0.339] | ✓ | True | 0.15 | False | ++++ | True | 0.0000 | 0.0000 | True | dies |
| F1c | F1 | excursion_episodes | P(SWEEP_CONFIRMED) | equality vs no_equality | 0.029 | [0.023, 0.036] | ✗ | False | 0.84 | True | ++++ | True | 0.0000 | 0.0000 | True | dies |
| F1d | F1 | excursion_episodes | abs_fwd24 | round vs not_round | -0.304 | [-0.433, -0.169] | ✓ | True | 0.13 | False | −−−− | True | 0.0000 | 0.0000 | True | dies |
| F1d | F1 | excursion_episodes | P(SWEEP_CONFIRMED) | round vs not_round | 0.001 | [-0.015, 0.019] | ✗ | False | 4.19 | True | +−−+ | False | 0.8860 | 0.8860 | False | dies |
| F1e | F1 | excursion_episodes | abs_fwd24 | prominence_top_tercile vs prominence_bottom_tercile | -0.044 | [-0.101, 0.012] | ✗ | False | -0.37 | False | −−−+ | False | 0.1290 | 0.2150 | False | dies |
| F1e | F1 | excursion_episodes | P(SWEEP_CONFIRMED) | prominence_top_tercile vs prominence_bottom_tercile | -0.005 | [-0.011, 0.002] | ✗ | False | 0.68 | True | +−−− | False | 0.1580 | 0.2257 | False | dies |
| F3 | F3 | sweep_confirmed | fwd24_reversal | speed=1(fast) vs speed=3(slow) | 0.103 | [-0.079, 0.302] | ✓ | False | 0.93 | True | +++− | False | 0.2950 | 0.2950 | False | dies |
| F4a | F4 | displacement_qualified | fwd24_continuation | body_vs_tod_magnitude_top vs body_vs_tod_magnitude_bottom | -0.042 | [-0.133, 0.045] | ✗ | False | 0.24 | False | −−++ | False | 0.3090 | 0.3708 | False | dies |
| F4a | F4 | displacement_qualified | maxrev24 | body_vs_tod_magnitude_top vs body_vs_tod_magnitude_bottom | -0.666 | [-0.741, -0.592] | ✓ | True | 0.09 | False | −−−− | True | 0.0000 | 0.0000 | True | dies |
| F4b | F4 | displacement_qualified | fwd24_continuation | close_location_top vs close_location_bottom | -0.015 | [-0.220, 0.174] | ✗ | False | 1.14 | True | −−+− | False | 0.8650 | 0.8650 | False | dies |
| F4b | F4 | displacement_qualified | maxrev24 | close_location_top vs close_location_bottom | 0.117 | [0.014, 0.228] | ✓ | True | 1.07 | True | ++++ | True | 0.0270 | 0.0540 | True | SURVIVES |
| F4c | F4 | displacement_qualified | fwd24_continuation | volume_z_top vs volume_z_bottom | 0.058 | [-0.037, 0.158] | ✗ | False | 1.00 | True | −−++ | False | 0.2210 | 0.3315 | False | dies |
| F4c | F4 | displacement_qualified | maxrev24 | volume_z_top vs volume_z_bottom | 0.960 | [0.891, 1.031] | ✓ | True | 0.18 | False | ++++ | True | 0.0000 | 0.0000 | True | dies |
| F5a | F5 | displacement_qualified | fwd24_event_dir | efficiency_top vs efficiency_bottom | 0.003 | [-0.101, 0.104] | ✗ | False | 0.59 | True | −−++ | False | 0.9380 | 0.9380 | False | dies |
| F5b | F5 | mss | fwd24_event_dir | efficiency_top vs efficiency_bottom | -0.078 | [-0.370, 0.234] | ✗ | False | 0.81 | True | +−−+ | False | 0.6220 | 0.9380 | False | dies |
| F6a | F6 | sweep_confirmed(ny_am) | abs_fwd24 | range_consumed_top vs range_consumed_bottom | -1.602 | [-1.913, -1.315] | ✓ | True | -0.02 | False | −−−− | True | 0.0000 | 0.0000 | True | dies |
| F6a | F6 | sweep_confirmed(ny_am) | maxcont24 | range_consumed_top vs range_consumed_bottom | -1.528 | [-1.762, -1.305] | ✓ | True | 0.00 | False | −−−− | True | 0.0000 | 0.0000 | True | dies |
| F6b | F6 | mss(ny_am) | abs_fwd24 | range_consumed_top vs range_consumed_bottom | -1.491 | [-1.951, -1.052] | ✓ | True | -0.03 | False | −−−− | True | 0.0000 | 0.0000 | True | dies |
| F6b | F6 | mss(ny_am) | maxcont24 | range_consumed_top vs range_consumed_bottom | -1.359 | [-1.871, -0.882] | ✓ | True | 0.07 | False | −−−− | True | 0.0000 | 0.0000 | True | dies |
| F7a | F7 | level_tested | P(bounce) | 1st_test vs 2nd+_test | 0.008 | [0.001, 0.014] | ✗ | False | 0.85 | True | −+++ | True | 0.0230 | 0.0307 | True | dies |
| F7a | F7 | level_tested | abs_fwd12 | 1st_test vs 2nd+_test | 0.086 | [0.059, 0.113] | ✗ | False | 0.78 | True | ++++ | True | 0.0000 | 0.0000 | True | dies |
| F7b | F7 | fvg_tested | P(bounce) | 1st_test vs 2nd+_test | -0.002 | [-0.007, 0.003] | ✗ | False | 0.67 | True | −−++ | False | 0.3600 | 0.3600 | False | dies |
| F7b | F7 | fvg_tested | abs_fwd12 | 1st_test vs 2nd+_test | 0.043 | [0.017, 0.068] | ✗ | False | 0.65 | True | ++++ | True | 0.0010 | 0.0020 | True | dies |

## 4. F2 prediction cells (AUC uplift of B+ICT over baseline B)

| cell | target | n | n_pos | AUC(B) | AUC(B+ICT) | uplift | 95% CI | G1(≥.02) | G2 | per-yr uplift signs | G3 | p | q(BH) | G4 | verdict |
|---|---|---:|---:|---:|---:|---:|---|:---:|:---:|---|:---:|---:|---:|:---:|:---:|
| F2a | SWEEP_CONFIRMED vs ACCEPTED_BREAKOUT | 1,475,597 | 280,725 | 0.572 | 0.956 | 0.383 | [0.379, 0.388] | True | True | ++++ | True | 0.0000 | 0.0000 | True | SURVIVES |
| F2b | sign(fwd24) | 1,475,783 | 768,833 | 0.506 | 0.505 | -0.000 | [-0.001, 0.001] | False | True | +−−+ | False | 0.8630 | 0.8630 | False | dies |

**Adjudication flag on F2a (mechanism caveat, not a new statistic — for Fable's §6/§7 decision):** F2a's large AUC uplift (0.572→0.956) is heavily driven by the preregistered `t0 close-location` feature, which is *mechanically* aligned with the target for the large sub-population of episodes whose terminal is decided on the first-beyond bar itself (`reclaim_speed_bars=1`: SWEEP_CONFIRMED `confirmed_at == t0`). For those episodes the t0 close being back inside the level *is* essentially the SWEEP_CONFIRMED vs ACCEPTED_BREAKOUT label observed contemporaneously — knowable-at-t0 (no lookahead), but a near-tautology rather than genuine ex-ante *prediction*. The prereg names `t0 bar close-location` as an F2 feature and does not exclude same-bar-resolved episodes, so this is reported faithfully as SURVIVES; whether F2a should proceed to the §6 holdout as a real acceptance-predictor, or be re-scoped to exclude `reclaim_speed_bars=1` (a prereg change requiring a new version), is an adjudication decision, not WP-F's to make. F2b (directional sign) shows ~0 uplift, consistent with the cited ATLAS meta-law (direction ≈ null).

## 5. Per-cell verdict summary (one line per preregistered cell)

| cell | family | survives? | driving outcome (if any) | G1 | G2 | G3 | G4 |
|---|---|:---:|---|:---:|:---:|:---:|:---:|
| F1a | F1 | **SURVIVES** | P(SWEEP_CONFIRMED) | True | True | True | True |
| F1b | F1 | dies | P(SWEEP_CONFIRMED) | False | True | True | False |
| F1c | F1 | dies | abs_fwd24 | True | False | True | True |
| F1d | F1 | dies | abs_fwd24 | True | False | True | True |
| F1e | F1 | dies | P(SWEEP_CONFIRMED) | False | True | False | False |
| F2a | F2 | **SURVIVES** | SWEEP_CONFIRMED vs ACCEPTED_BREAKOUT | True | True | True | True |
| F2b | F2 | dies | sign(fwd24) | False | True | False | False |
| F3 | F3 | dies | fwd24_reversal | False | True | False | False |
| F4a | F4 | dies | maxrev24 | True | False | True | True |
| F4b | F4 | **SURVIVES** | maxrev24 | True | True | True | True |
| F4c | F4 | dies | maxrev24 | True | False | True | True |
| F5a | F5 | dies | fwd24_event_dir | False | True | False | False |
| F5b | F5 | dies | fwd24_event_dir | False | True | False | False |
| F6a | F6 | dies | abs_fwd24 | True | False | True | True |
| F6b | F6 | dies | abs_fwd24 | True | False | True | True |
| F7a | F7 | dies | P(bounce) | False | True | True | True |
| F7b | F7 | dies | abs_fwd12 | False | True | True | True |

**IS survivors (pass G1∧G2∧G3∧G4): 3** — ['F1a', 'F2a', 'F4b'].

Per §7 verdict rules, the survivor set determines routing; only cells that pass all IS gates are eligible for the single §6 holdout pass (a later, separate execution). This report makes NO holdout contact.

## 6. Runtime

| stage | seconds |
|---|---:|
| selftest_s | 7.45 |
| load_is_s | 1.48 |
| F1_s | 21.62 |
| F3_s | 0.92 |
| F4_s | 0.36 |
| F5_s | 0.21 |
| F6_s | 0.15 |
| F7_s | 5.34 |
| F2_s | 290.6 |
| total_s | 328.14 |
