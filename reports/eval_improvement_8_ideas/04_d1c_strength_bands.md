# Idea 4 — D1c strength bands — RESEARCH ONLY / SIM CONDITIONAL

Analysis only — the LIVE D1c gate stays zero-parameter (sign-agreement only). Every kept trade's drift already agrees in sign with its own direction (that IS the D1c gate); bands here measure HOW STRONGLY aligned, not whether. Quintile bands (0=weakest..4=strongest) computed on the certified 435-trade population, per normalization, via rank-based `qcut` — no tuned thresholds.

## Per-band stats, all 3 normalizations

### raw points

| band | n | WR% | PF | expR | totR | per-year totR |
|---|---|---|---|---|---|---|
| 0 | 87 | 48.3 | 1.756 | 0.2934 | +25.5 | {2021: 6.8, 2022: 8.9, 2023: 8.0, 2024: -1.2, 2025: 5.0, 2026: -2.0} |
| 1 | 87 | 58.6 | 2.67 | 0.5003 | +43.5 | {2021: 8.3, 2022: 6.4, 2023: 9.0, 2024: 3.8, 2025: 14.0, 2026: 2.0} |
| 2 | 87 | 66.7 | 3.109 | 0.6166 | +53.6 | {2021: 11.6, 2022: 4.9, 2023: 6.2, 2024: 8.2, 2025: 20.3, 2026: 2.3} |
| 3 | 87 | 55.2 | 1.609 | 0.228 | +19.8 | {2021: 0.7, 2022: 3.3, 2023: 8.1, 2024: 5.5, 2025: 2.6, 2026: -0.4} |
| 4 | 87 | 64.4 | 2.804 | 0.476 | +41.4 | {2021: 0.4, 2022: 4.3, 2023: 6.7, 2024: 2.4, 2025: 16.0, 2026: 11.7} |

### drift/ATR14(1m)

| band | n | WR% | PF | expR | totR | per-year totR |
|---|---|---|---|---|---|---|
| 0 | 87 | 48.3 | 1.788 | 0.3038 | +26.4 | {2021: 8.8, 2022: 8.8, 2023: 6.9, 2024: -0.1, 2025: 5.0, 2026: -3.0} |
| 1 | 87 | 56.3 | 2.448 | 0.4785 | +41.6 | {2021: 3.9, 2022: 8.6, 2023: 4.6, 2024: 6.1, 2025: 14.9, 2026: 3.4} |
| 2 | 87 | 66.7 | 2.867 | 0.5692 | +49.5 | {2021: 8.0, 2022: 2.0, 2023: 13.0, 2024: 9.1, 2025: 14.7, 2026: 2.8} |
| 3 | 87 | 65.5 | 2.569 | 0.4549 | +39.6 | {2021: 7.2, 2022: 3.5, 2023: 4.0, 2024: 6.3, 2025: 16.5, 2026: 2.2} |
| 4 | 87 | 56.3 | 2.001 | 0.3079 | +26.8 | {2021: 0.1, 2022: 4.9, 2023: 9.5, 2024: -2.6, 2025: 6.7, 2026: 8.1} |

### percentile-by-minutes-since-open

| band | n | WR% | PF | expR | totR | per-year totR |
|---|---|---|---|---|---|---|
| 0 | 87 | 49.4 | 1.719 | 0.2872 | +25.0 | {2021: 3.8, 2022: 7.4, 2023: 10.5, 2024: 0.3, 2025: 5.0, 2026: -2.0} |
| 1 | 87 | 58.6 | 2.792 | 0.496 | +43.2 | {2021: 12.8, 2022: 6.6, 2023: 4.4, 2024: 0.2, 2025: 16.1, 2026: 3.0} |
| 2 | 87 | 60.9 | 2.513 | 0.5003 | +43.5 | {2021: 8.6, 2022: 5.1, 2023: 4.0, 2024: 6.6, 2025: 17.4, 2026: 1.8} |
| 3 | 87 | 58.6 | 2.127 | 0.3773 | +32.8 | {2021: -0.2, 2022: 4.6, 2023: 14.9, 2024: 5.5, 2025: 4.0, 2026: 4.0} |
| 4 | 87 | 65.5 | 2.639 | 0.4535 | +39.5 | {2021: 2.9, 2022: 4.2, 2023: 4.2, 2024: 6.0, 2025: 15.5, 2026: 6.8} |

## Policies — filter/funnel/count-basis (both bases) + one-year-driven check

| policy | n | WR% | PF | expR | totR | pass@10/1200 | eligible/pass-COUNT @10/1200 | pass@15/1000 | eligible/pass-COUNT @15/1000 | denom artifact? | one-year check | auditor? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| drop_band0[raw points] | 348 | 61.2 | 2.48 | 0.4552 | +158.4 | 40.6% | 325/132 (base 395/189) | 44.6% | 325/145 (base 395/218) | none | top single-year share of positive totR delta = 63% -> spread, OK | no |
| allow_only_band2-3[raw points] | 174 | 60.9 | 2.266 | 0.4223 | +73.5 | 20.8% | 168/35 (base 395/189) | 23.2% | 168/39 (base 395/218) | none | no positive totR delta vs baseline (n/a) | no |
| drop_band4[raw points]_exhaustion-check | 348 | 57.2 | 2.209 | 0.4096 | +142.5 | 36.4% | 321/117 (base 395/189) | 48.9% | 321/157 (base 395/218) | none | no positive totR delta vs baseline (n/a) | no |
| drop_band0[drift/ATR14(1m)] | 348 | 61.2 | 2.468 | 0.4526 | +157.5 | 42.8% | 325/139 (base 395/189) | 46.8% | 325/152 (base 395/218) | none | top single-year share of positive totR delta = 97% -> ONE-YEAR-DRIVEN, REJECT | no |
| allow_only_band2-3[drift/ATR14(1m)] | 174 | 66.1 | 2.721 | 0.512 | +89.1 | 25.9% | 166/43 (base 395/189) | 28.9% | 166/48 (base 395/218) | none | no positive totR delta vs baseline (n/a) | no |
| drop_band4[drift/ATR14(1m)]_exhaustion-check | 348 | 59.2 | 2.378 | 0.4516 | +157.2 | 40.7% | 317/129 (base 395/189) | 47.3% | 317/150 (base 395/218) | none | top single-year share of positive totR delta = 100% -> ONE-YEAR-DRIVEN, REJECT | no |
| drop_band0[percentile-by-minutes-since-open] | 348 | 60.9 | 2.499 | 0.4568 | +159.0 | 41.6% | 322/134 (base 395/189) | 45.7% | 322/147 (base 395/218) | none | top single-year share of positive totR delta = 100% -> ONE-YEAR-DRIVEN, REJECT | no |
| allow_only_band2-3[percentile-by-minutes-since-open] | 174 | 59.8 | 2.319 | 0.4388 | +76.3 | 20.7% | 169/35 (base 395/189) | 23.7% | 169/40 (base 395/218) | none | no positive totR delta vs baseline (n/a) | no |
| drop_band4[percentile-by-minutes-since-open]_exhaustion-check | 348 | 56.9 | 2.238 | 0.4152 | +144.5 | 40.0% | 325/130 (base 395/189) | 48.6% | 325/158 (base 395/218) | none | no positive totR delta vs baseline (n/a) | no |

## Per-year robustness flags (vs baseline)
- **drop_band0[raw points]**: none
- **allow_only_band2-3[raw points]**: none
- **drop_band4[raw points]_exhaustion-check**: none
- **drop_band0[drift/ATR14(1m)]**: none
- **allow_only_band2-3[drift/ATR14(1m)]**: none
- **drop_band4[drift/ATR14(1m)]_exhaustion-check**: none
- **drop_band0[percentile-by-minutes-since-open]**: none
- **allow_only_band2-3[percentile-by-minutes-since-open]**: none
- **drop_band4[percentile-by-minutes-since-open]_exhaustion-check**: none

---
All numbers RESEARCH ONLY / SIM CONDITIONAL. No commits.
