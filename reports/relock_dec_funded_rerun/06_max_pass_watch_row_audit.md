# 06 — Max-Pass Watch-Row Mini-Audit (RE-LOCK cycle)

RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing. No recommendation language, no commits — mechanical verdict legs only, per task spec.

WATCH    = WATCH A900/6+VPC700/3  (pinned: {'pass_pct': 39.3, 'bust_pct': 19.6, 'exp_pct': 41.1})
BALANCED = BALANCED A900/6+VPC600/3  (pinned: {'pass_pct': 37.4, 'bust_pct': 18.0, 'exp_pct': 44.6})

## Canary — reproduce both pinned rows exactly (tolerance 0.3pp)

- WATCH:    got pass=39.3 bust=19.6 exp=41.1 n=684 vs {'pass_pct': 39.3, 'bust_pct': 19.6, 'exp_pct': 41.1}
- BALANCED: got pass=37.4 bust=18.0 exp=44.6 n=684 vs {'pass_pct': 37.4, 'bust_pct': 18.0, 'exp_pct': 44.6}
- CANARY GATE: **PASS**

## (1) Per-year pass/bust/expire + E$ (side-by-side)

| row | year | n | pass_count | bust_count | exp_count | pass% | bust% | exp% | E$ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WATCH | 2022 | 151 | 48 | 32 | 71 | 31.8 | 21.2 | 47.0 | 364219.0 |
| WATCH | 2023 | 160 | 29 | 18 | 113 | 18.1 | 11.2 | 70.6 | 211040.0 |
| WATCH | 2024 | 152 | 49 | 39 | 64 | 32.2 | 25.7 | 42.1 | 372088.0 |
| WATCH | 2025 | 160 | 110 | 22 | 28 | 68.8 | 13.8 | 17.5 | 859040.0 |
| WATCH | 2026 | 61 | 33 | 23 | 5 | 54.1 | 37.7 | 8.2 | 256009.0 |
| BALANCED | 2022 | 151 | 42 | 31 | 78 | 27.8 | 20.5 | 51.7 | 316219.0 |
| BALANCED | 2023 | 160 | 30 | 14 | 116 | 18.8 | 8.8 | 72.5 | 219040.0 |
| BALANCED | 2024 | 152 | 46 | 32 | 74 | 30.3 | 21.1 | 48.7 | 348088.0 |
| BALANCED | 2025 | 160 | 105 | 22 | 33 | 65.6 | 13.8 | 20.6 | 819040.0 |
| BALANCED | 2026 | 61 | 33 | 24 | 4 | 54.1 | 39.3 | 6.6 | 256009.0 |

## (2) EXCLUDING-2025 aggregate

- WATCH ex-2025:    {'n': 524, 'pass_count': 159, 'bust_count': 112, 'exp_count': 253, 'pass_pct': 30.3, 'bust_pct': 21.4, 'exp_pct': 48.3}
- BALANCED ex-2025: {'n': 524, 'pass_count': 151, 'bust_count': 101, 'exp_count': 272, 'pass_pct': 28.8, 'bust_pct': 19.3, 'exp_pct': 51.9}
- watch advantage over balanced (ex-2025, pass pp): **1.5**

## (3) Worst-start-month analysis (3 worst months per row, by pass%)

| row | month | n | pass% |
| --- | --- | --- | --- |
| WATCH | 2024-01 | 16 | 0.0 |
| WATCH | 2023-05 | 15 | 0.0 |
| WATCH | 2023-08 | 15 | 0.0 |
| BALANCED | 2024-01 | 16 | 0.0 |
| BALANCED | 2023-05 | 15 | 0.0 |
| BALANCED | 2023-08 | 15 | 0.0 |

Does the watch row's advantage survive in those months (watch pass% vs balanced pass% in the SAME month, for every month appearing in either row's worst-3)?

| month | watch_pass% | balanced_pass% | watch_minus_balanced |
| --- | --- | --- | --- |
| 2023-05 | 0.0 | 0.0 | 0.0 |
| 2023-08 | 0.0 | 0.0 | 0.0 |
| 2024-01 | 0.0 | 0.0 | 0.0 |

## (4) Stress side-by-side — slippage {0.02, 0.046, 0.068, 0.076}R

| row | slip(R) | pass% | bust% | margin(pass-bust) |
| --- | --- | --- | --- | --- |
| WATCH | 0.02 | 36.8 | 20.2 | 16.599999999999998 |
| WATCH | 0.046 | 32.5 | 22.1 | 10.399999999999999 |
| WATCH | 0.068 | 30.0 | 28.5 | 1.5 |
| WATCH | 0.076 | 28.8 | 28.7 | 0.10000000000000142 |
| BALANCED | 0.02 | 34.6 | 19.6 | 15.0 |
| BALANCED | 0.046 | 30.6 | 21.9 | 8.700000000000003 |
| BALANCED | 0.068 | 27.2 | 27.6 | -0.40000000000000213 |
| BALANCED | 0.076 | 26.0 | 28.1 | -2.1000000000000014 |

## (5) Paired bootstrap (1000x, seed=42) — pass% 90% CI + watch-minus-balanced difference

- common start-dates paired: 684 (watch eligible_starts=684, balanced eligible_starts=684)
- WATCH pass% 90% CI:    [36.4, 42.1]  (median 39.3)
- BALANCED pass% 90% CI: [34.5, 40.4]  (median 37.4)
- DIFFERENCE (watch - balanced) 90% CI: [0.88, 2.92]  (median 1.9)
- P(watch pass% > balanced pass%) per resample: **0.999**

## (6) VPC-budget delta mechanics (700 vs 600, cap=3 both) — what changes mechanically

- VPC trades kept at budget<=600: n=404; at budget<=700: n=405 (kept-set membership; q<1 dropped)

| band (q@600 -> q@700) | risk_usd range | n trades | stop_pts range | agg raw R | agg $ delta from sizing alone (first-order) |
| --- | --- | --- | --- | --- | --- |
| q 2->3 | (200.0, 233.33] | 61 | 100.98-115.98 | 18.228 | 4037.14 |
| q 1->2 | (300.0, 350.0] | 33 | 150.22-173.66 | 8.705 | 2770.21 |
| q 0->1 (added) | (600.0, 700.0] | 1 | 334.11-334.11 | 1.838 | 1228.5 |

(first-order $ delta = sum((q@700 - q@600) * R * risk_usd) over the affected trades; does not re-walk day-level $550 stop / $1,000 DLL clamps — flagged, not hidden.)

## VERDICT (mechanical, auditor adjudicates)

- leg1 (ex-2025 pass advantage >= +1.5pp): **True** (delta=1.5pp)
- leg2 (P(watch>balanced) >= 0.80): **True** (value=0.999)
- leg3 (no single year >50% of E$ advantage): **True** (worst year=2022 share=0.429 of total positive advantage $112000.0)
- leg4 (stress margin >= balanced at every tested point): **True**

## VERDICT: **PROMOTABLE**

## Firewall before/after

- `config_eval_locked.py`: UNCHANGED
- `config_funded_locked.py`: UNCHANGED
- `config_defaults.py`: UNCHANGED
- `auto_safety.py`: UNCHANGED

Runtime: 20.1s
