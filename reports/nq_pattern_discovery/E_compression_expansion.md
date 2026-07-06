# NQ Pattern Discovery — Discovery Lane E: Compression / Expansion

RESEARCH ONLY — distributions/conditional stats only, no strategy construction, no backtest. Reads `store/features_daily.parquet` + `store/features_intraday.parquet` (foundation-lane, read-only). Full methodology in `E_compression_expansion.py`'s module docstring (all 6 compression definitions + all 5 outcome sub-analyses).

PRIORS (from task brief): B5 strategy cells 9/9 dead; W6 absorption dead; Profile B (ORB) honest PF ~1.07 = the incumbent. This lane maps whether ANY raw compression signal exists worth graduating despite the strategy-level graveyard — it does not construct or test a strategy.

## Summary: 95/113 cells consistency-flagged

Consistency flag = pooled n (compressed/flagged group) >= 200 AND same-sign difference-from-baseline in >= 8 of the 11 calendar years 2016-2026.

## Compression-flag base rates (fraction of days flagged, 2016-2026)

```
c_on: 0.2984
c_pm: 0.2965
c_atr5open: 0.2961
c_or30: 0.2901
c_priorrange: 0.2928
c_insideday: 0.1075
```

- First-OR30-breakout classified days: 2664 (outcome1 distribution: {'fail_and_reverse': 2080, 'continue': 367, 'no_resolution': 172, 'no_breakout': 45})
- Second-breakout-after-failure attempts: 1971 (outcome2 distribution: {'fail_and_reverse': 1564, 'continue': 209, 'no_resolution': 198})

## 10 strongest consistency-flagged cells

| workstream | analysis | metric | n | value | n_years_match | n_years_total | consistent | flag | n_false | false_value | diff | c_on | c_pm | c_atr5open | c_or30 | c_priorrange | c_insideday | n_flags_true | same_dir_as_first |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E | E_e_drift_alignment | same_sign | 2390 | 0.777 | 11 | 11 | True | nan | nan | nan | nan | nan | nan | nan | nan | nan | False | nan | nan |
| E | E_b_or30_breakout_outcome | outcome1=fail_and_reverse | 2377 | 0.7863 | 11 | 11 | True | nan | nan | nan | nan | nan | nan | nan | nan | nan | False | nan | nan |
| E | E_b_or30_breakout_outcome | outcome1=no_resolution | 2377 | 0.0602 | 11 | 11 | True | nan | nan | nan | nan | nan | nan | nan | nan | nan | False | nan | nan |
| E | E_b_or30_breakout_outcome | outcome1=continue | 2377 | 0.1371 | 11 | 11 | True | nan | nan | nan | nan | nan | nan | nan | nan | nan | False | nan | nan |
| E | E_b_or30_breakout_outcome | outcome1=no_breakout | 2377 | 0.0164 | 11 | 11 | True | nan | nan | nan | nan | nan | nan | nan | nan | nan | False | nan | nan |
| E | E_e_drift_alignment | same_sign | 1901 | 0.7796 | 11 | 11 | True | nan | nan | nan | nan | nan | nan | nan | False | nan | nan | nan | nan |
| E | E_e_drift_alignment | same_sign | 1894 | 0.7703 | 11 | 11 | True | nan | nan | nan | nan | nan | nan | nan | nan | False | nan | nan | nan |
| E | E_b_or30_breakout_outcome | outcome1=fail_and_reverse | 1887 | 0.779 | 11 | 11 | True | nan | nan | nan | nan | nan | nan | nan | False | nan | nan | nan | nan |
| E | E_b_or30_breakout_outcome | outcome1=no_resolution | 1887 | 0.0541 | 11 | 11 | True | nan | nan | nan | nan | nan | nan | nan | False | nan | nan | nan | nan |
| E | E_b_or30_breakout_outcome | outcome1=continue | 1887 | 0.1468 | 11 | 11 | True | nan | nan | nan | nan | nan | nan | nan | False | nan | nan | nan | nan |

## 5 most decisive nulls (largest n, NOT consistency-flagged)

| workstream | analysis | metric | n | value | n_years_match | n_years_total | consistent | flag | n_false | false_value | diff | c_on | c_pm | c_atr5open | c_or30 | c_priorrange | c_insideday | n_flags_true | same_dir_as_first |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E | E_a_full_session_expansion | directionality | 799 | 0.4926 | 7 | 11 | False | c_on | 1879.0 | 0.4789 | 0.0136 | nan | nan | nan | nan | nan | nan | nan | nan |
| E | E_a_full_session_expansion | directionality | 794 | 0.4777 | 6 | 11 | False | c_pm | 1884.0 | 0.4853 | -0.0076 | nan | nan | nan | nan | nan | nan | nan | nan |
| E | E_a_full_session_expansion | directionality | 793 | 0.4809 | 5 | 11 | False | c_atr5open | 1885.0 | 0.4839 | -0.0029 | nan | nan | nan | nan | nan | nan | nan | nan |
| E | E_a_full_session_expansion | directionality | 784 | 0.4719 | 7 | 11 | False | c_priorrange | 1894.0 | 0.4876 | -0.0157 | nan | nan | nan | nan | nan | nan | nan | nan |
| E | E_d_1000_1130_expansion | directionality_1000_1130 | 777 | 0.4299 | 7 | 11 | False | c_or30 | 1887.0 | 0.4422 | -0.0124 | nan | nan | nan | nan | nan | nan | nan | nan |

## Full cell table

See `E_compression_expansion.csv` for all cells (workstream/analysis/metric/n/value/n_years_match/consistent + true-vs-false group means where applicable).
