# ICT V2 Phase 3, WP-E — Extraction Counts Report

**Governs:** `research/ict_v2/PREREG_PHASE3.md` v1.0 + Amendment v1.1, git hash `cd652ea81093`. **Scope:** WP-E (build) only — event/feature/outcome extraction. NO statistics beyond event counts anywhere in this report (PREREG §8 ban): no means, no effects, no PF/WR/expectancy, no outcome summaries.

## 1. Frame assertion (Amendment v1.1)

- **unadjusted_bar_count:** 353952
- **rolladj_bar_count:** 353952
- **bar_counts_exactly_equal:** True
- **timestamp_index_identical:** True
- **closes_differ_as_expected:** True
- **unadjusted_range:** 2021-06-22 20:00:00-04:00 -> 2026-06-22 19:55:00-04:00
- **rolladj_range:** 2021-06-22 20:00:00-04:00 -> 2026-06-22 19:55:00-04:00

## 2. Runtime

| stage | seconds |
|---|---:|
| frame_build_s | 2.76 |
| baseline_arrays_s | 9.31 |
| engines_run_s | 18543.76 |
| derived_arrays_s | 14.82 |
| conformance_s | 9.98 |
| feature_extraction_s | 213.43 |
| parquet_write_s | 13.73 |
| total_s | 18818.22 |

## 3. Engine event inventory (raw, all event types emitted, IS+HOLDOUT combined)

- **levels**: 964,291 total events — LEVEL_CREATED=91,182, LEVEL_TESTED=781,944, LEVEL_EXPIRED=91,165
- **sweeps**: 3,689,226 total events — EXCURSION_OPEN=1,844,614, SWEEP_CONFIRMED=349,043, ACCEPTED_BREAKOUT=1,495,358, EXCURSION_TIMEOUT=211
- **structure**: 104,138 total events — STRUCTURE_INITIALIZED=1, BOS=82,645, CHOCH=10,746, MSS=8,183, MSS_WINDOW_EXPIRED=2,563
- **displacement**: 436,419 total events — DISPLACEMENT_WARMUP=5,520, DISPLACEMENT_QUALIFIED=82,467, DISPLACEMENT_COMPONENTS=348,432
- **zones**: 884,542 total events — FVG_CREATED=71,342, FVG_QUALIFIED=60,498, FVG_TESTED=209,099, FVG_INVALIDATED=46,609, IFVG_CREATED=46,609, IFVG_TESTED=127,986, IFVG_INVALIDATED=32,574, OB_CREATED=27,449, OB_TESTED=109,860, FVG_EXPIRED=24,729, IFVG_EXPIRED=14,034, OB_EXPIRED=14,085, OB_INVALIDATED=13,360, BREAKER_CREATED=13,360, BREAKER_TESTED=59,588, BREAKER_INVALIDATED=7,748, BREAKER_EXPIRED=5,612

AMD excluded per prereg §8 ban. `opening_range`/`overnight`/`ranges`/`swings_b`/`swings_c` not registered — no §3 cell names an event type from any of them (baseline B's ATR-percentile / overnight-gap are computed independently from the bar array, see `baseline.py`).

## 4. Event UNAVAILABLE check

None. All prereg-named event types (`EXCURSION_OPEN`/`SWEEP_CONFIRMED`/`ACCEPTED_BREAKOUT`/`EXCURSION_TIMEOUT`, `DISPLACEMENT_QUALIFIED`, `MSS`, `LEVEL_TESTED`, `FVG_TESTED`) are emitted by the certified engines exactly as named — no detector was improvised.

## 5. Per-family event counts by year (IS / HOLDOUT — row counts only)

### `excursion_episodes` — IS total 1,475,787, HOLDOUT total 368,827

| year | IS | HOLDOUT |
|---:|---:|---:|
| 2021 | 203,873 | 0 |
| 2022 | 364,063 | 0 |
| 2023 | 371,016 | 0 |
| 2024 | 371,522 | 0 |
| 2025 | 165,313 | 193,894 |
| 2026 | 0 | 174,933 |

### `sweep_confirmed` — IS total 280,725, HOLDOUT total 68,318

| year | IS | HOLDOUT |
|---:|---:|---:|
| 2021 | 37,841 | 0 |
| 2022 | 68,426 | 0 |
| 2023 | 73,003 | 0 |
| 2024 | 71,093 | 0 |
| 2025 | 30,362 | 36,971 |
| 2026 | 0 | 31,347 |

### `displacement_qualified` — IS total 65,964, HOLDOUT total 16,503

| year | IS | HOLDOUT |
|---:|---:|---:|
| 2021 | 8,615 | 0 |
| 2022 | 16,442 | 0 |
| 2023 | 16,649 | 0 |
| 2024 | 16,567 | 0 |
| 2025 | 7,691 | 8,735 |
| 2026 | 0 | 7,768 |

### `mss` — IS total 6,559, HOLDOUT total 1,624

| year | IS | HOLDOUT |
|---:|---:|---:|
| 2021 | 873 | 0 |
| 2022 | 1,707 | 0 |
| 2023 | 1,644 | 0 |
| 2024 | 1,578 | 0 |
| 2025 | 757 | 868 |
| 2026 | 0 | 756 |

### `level_tested` — IS total 635,377, HOLDOUT total 146,567

| year | IS | HOLDOUT |
|---:|---:|---:|
| 2021 | 87,792 | 0 |
| 2022 | 150,213 | 0 |
| 2023 | 169,652 | 0 |
| 2024 | 161,314 | 0 |
| 2025 | 66,406 | 80,245 |
| 2026 | 0 | 66,322 |

### `fvg_tested` — IS total 168,202, HOLDOUT total 40,897

| year | IS | HOLDOUT |
|---:|---:|---:|
| 2021 | 22,556 | 0 |
| 2022 | 43,720 | 0 |
| 2023 | 41,663 | 0 |
| 2024 | 40,155 | 0 |
| 2025 | 20,108 | 21,297 |
| 2026 | 0 | 19,600 |

## 6. NO-TEST flags (PREREG §3 house rule: <50 IS events per compared group)

| cell | family | unit | IS compared-group sizes | NO-TEST | note |
|---|---|---|---|:---:|---|
| F1a | F1 SALIENCE | excursion_episodes | weekly=74,038, intraday=1,401,749 | ok |  |
| F1b | F1 SALIENCE | excursion_episodes | prior_test_count=0=160,429, prior_test_count>=1=1,315,358 | ok |  |
| F1c | F1 SALIENCE | excursion_episodes | False=1,338,722, True=137,065 | ok |  |
| F1d | F1 SALIENCE | excursion_episodes | False=1,454,716, True=21,071 | ok |  |
| F1e | F1 SALIENCE | excursion_episodes | bottom_tercile=981,470, top_tercile=471,609 | ok | n_nonnull=1453079 |
| F2 Target A | F2 ACCEPTANCE/REJECTION | excursion_episodes | SWEEP_CONFIRMED=280,725, ACCEPTED_BREAKOUT=1,194,872 | ok | excluded(timeouts+unresolved)=190 |
| F2 Target B | F2 ACCEPTANCE/REJECTION | excursion_episodes | population(sign(fwd24))=1,475,783 | ok |  |
| F3 | F3 CONFIRMATION LATENCY | sweep_confirmed | 1=194,563, 2=83,035, 3=3,127 | ok |  |
| F4a | F4 DISPLACEMENT PERSISTENCE | displacement_qualified | bottom_tercile=21,658, top_tercile=21,569 | ok | n_nonnull=64716 |
| F4b | F4 DISPLACEMENT PERSISTENCE | displacement_qualified | bottom_tercile=22,012, top_tercile=21,981 | ok | n_nonnull=65964 |
| F4c | F4 DISPLACEMENT PERSISTENCE | displacement_qualified | bottom_tercile=21,988, top_tercile=21,988 | ok | n_nonnull=65964 |
| F5a | F5 PATH CLEANLINESS | displacement_qualified | bottom_tercile=22,000, top_tercile=21,988 | ok | n_nonnull=65964 |
| F5b | F5 PATH CLEANLINESS | mss | bottom_tercile=2,187, top_tercile=2,187 | ok | n_nonnull=6559 |
| F6a | F6 REMAINING OPPORTUNITY | sweep_confirmed(ny_am) | bottom_tercile=18,053, top_tercile=18,025 | ok | n_nonnull=54101, ny_am_total=54184 |
| F6b | F6 REMAINING OPPORTUNITY | mss(ny_am) | bottom_tercile=266, top_tercile=266 | ok | n_nonnull=797, ny_am_total=798 |
| F7a | F7 FRESHNESS | level_tested | False=55,186, True=580,191 | ok |  |
| F7b | F7 FRESHNESS | fvg_tested | False=47,801, True=120,401 | ok |  |

## 7. Feature completeness (% non-null, IS+HOLDOUT combined)

### `excursion_episodes`

| feature | % non-null |
|---|---:|
| level_kind | 100.0 |
| side | 100.0 |
| level_timeframe_class | 100.0 |
| level_price | 100.0 |
| breach_price | 100.0 |
| excursion_depth_pts_t0 | 100.0 |
| excursion_depth_ticks_t0 | 100.0 |
| excursion_depth_atr_t0 | 100.0 |
| t0_close_location | 100.0 |
| body_vs_tod_t0 | 98.22 |
| volume_z_t0 | 100.0 |
| prominence_above_pts | 97.61 |
| prominence_below_pts | 99.53 |
| prominence_pts_relevant | 97.83 |
| roundness_major | 100.0 |
| roundness_minor | 100.0 |
| equality_count | 100.0 |
| equality_flag | 100.0 |
| roundness_flag | 100.0 |
| prior_test_count | 100.0 |
| tod_slot_30 | 100.0 |
| day_of_week | 100.0 |
| atr20 | 100.0 |
| atr20_percentile_60sess | 99.95 |
| sigma_tod_relative_vol_12 | 98.22 |
| ret_12bar_atr | 100.0 |
| overnight_gap_atr | 99.9 |

### `sweep_confirmed`

| feature | % non-null |
|---|---:|
| level_kind | 100.0 |
| side | 100.0 |
| direction | 100.0 |
| reclaim_speed_bars | 100.0 |
| duration_bars | 100.0 |
| excursion_depth_ticks | 100.0 |
| level_timeframe_class | 100.0 |
| prominence_above_pts | 98.15 |
| prominence_below_pts | 99.55 |
| roundness_major | 100.0 |
| roundness_minor | 100.0 |
| equality_count | 100.0 |
| session | 100.0 |
| session_range_consumed | 19.2 |
| tod_slot_30 | 100.0 |
| day_of_week | 100.0 |
| atr20 | 100.0 |
| atr20_percentile_60sess | 99.91 |
| sigma_tod_relative_vol_12 | 98.11 |
| ret_12bar_atr | 100.0 |
| overnight_gap_atr | 99.86 |

### `displacement_qualified`

| feature | % non-null |
|---|---:|
| direction | 100.0 |
| body | 100.0 |
| mean20_body | 100.0 |
| ratio | 100.0 |
| body_vs_tod_magnitude | 98.49 |
| close_location | 100.0 |
| volume_z | 100.0 |
| efficiency_12 | 100.0 |
| tod_slot_30 | 100.0 |
| day_of_week | 100.0 |
| atr20 | 100.0 |
| atr20_percentile_60sess | 99.93 |
| sigma_tod_relative_vol_12 | 98.49 |
| ret_12bar_atr | 100.0 |
| overnight_gap_atr | 99.88 |

### `mss`

| feature | % non-null |
|---|---:|
| direction | 100.0 |
| choch_bars_elapsed | 100.0 |
| efficiency_12 | 100.0 |
| session | 100.0 |
| session_range_consumed | 12.12 |
| tod_slot_30 | 100.0 |
| day_of_week | 100.0 |
| atr20 | 100.0 |
| atr20_percentile_60sess | 99.93 |
| sigma_tod_relative_vol_12 | 98.42 |
| ret_12bar_atr | 100.0 |
| overnight_gap_atr | 99.88 |

### `level_tested`

| feature | % non-null |
|---|---:|
| level_kind | 100.0 |
| test_count | 100.0 |
| test_number_ge2 | 100.0 |
| age_seconds | 100.0 |
| direction | 99.33 |
| tod_slot_30 | 100.0 |
| day_of_week | 100.0 |
| atr20 | 100.0 |
| atr20_percentile_60sess | 99.92 |
| sigma_tod_relative_vol_12 | 98.01 |
| ret_12bar_atr | 100.0 |
| overnight_gap_atr | 99.86 |

### `fvg_tested`

| feature | % non-null |
|---|---:|
| fvg_direction | 100.0 |
| test_count | 100.0 |
| test_number_ge2 | 100.0 |
| direction | 100.0 |
| tod_slot_30 | 100.0 |
| day_of_week | 100.0 |
| atr20 | 99.99 |
| atr20_percentile_60sess | 99.93 |
| sigma_tod_relative_vol_12 | 98.43 |
| ret_12bar_atr | 99.99 |
| overnight_gap_atr | 99.87 |

## 8. Knowability assertion

`assert_knowable()` (structural check: every cross-referenced event feeding a feature at t0 must have `confirmed_at <= t0`) was invoked and passed on **15,991,659** individual event lookups (prior LEVEL_TESTED counts for F1b's `prior_test_count`, plus a same-bar-or-later assertion on every terminal-event linkage in `excursion_episodes`), **0** violations. The extraction run would have raised `AssertionError` and halted before writing any parquet on the first violation — this report existing at all IS the pass evidence (fail-closed design, `research/ict_v2/phase3/extract.py::assert_knowable`).

**Fast-path conformance (vectorization fidelity):** `run_conformance_checks()` ran at the START of the extraction (before any parquet write) and proved the fast vectorized path equals the slow per-event reference EXACTLY on a deterministic >=200-event sample per family: outcome_value_comparisons=13,500, efficiency_value_comparisons=500, prior_test_count_comparisons=250 comparisons, 0 mismatches (the run would have aborted on the first mismatch). The vectorized outcomes / efficiency / prior_test_count are therefore bit-for-bit identical to the audited slow path.

## 9. Integrity: unsplit rows (t0 outside both IS and HOLDOUT ranges)

- `excursion_episodes`: 0
- `sweep_confirmed`: 0
- `displacement_qualified`: 0
- `mss`: 0
- `level_tested`: 0
- `fvg_tested`: 0

## 10. Output files

`research/ict_v2/phase3/data/{unit}_is.parquet` and `{unit}_holdout.parquet` for unit in `{excursion_episodes, sweep_confirmed, displacement_qualified, mss, level_tested, fvg_tested}`. IS and HOLDOUT written to SEPARATE files; this extraction run never re-reads the holdout files after writing them (PREREG §6/§8).
