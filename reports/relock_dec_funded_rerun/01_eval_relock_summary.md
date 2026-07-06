# 01 -- Eval Re-Lock Summary (RE-LOCK DEC + Funded Re-Run)

RESEARCH ONLY. LIVE HOLD ACTIVE. Reproduced via the pinned funnel (`tools_opt_finalist_stress.funnel` / `tools_salvage_vpc_reeval.ASR`), unmodified.

OVERLAP CAVEAT (verbatim): monthly rolling starts OVERLAP -> effective independent samples ~4-5, bust% has wide CI

| row | A(budget/cap) | VPC(budget/cap) | pass% | bust% | exp% | not-pass% | n | f/slot/yr | attempts/pass | fee/pass ($131) | fee/pass ($30 promo) | flip_R | Δpass | Δbust | Δexp | Δflip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 600/6 | 600/4 | 28.7 | 17.0 | 54.4 | 71.4 | 684 | 4.22 | 3.484 | 456.0 | 105.0 | 0.0554 | 0.0 | 0.0 | 0.0 | 0.0 |
| balanced | 900/6 | 600/3 | 37.4 | 18.0 | 44.6 | 62.6 | 684 | 5.89 | 2.674 | 350.0 | 80.0 | 0.068 | 8.7 | 1.0 | -9.8 | 0.0126 |
| watch | 900/6 | 700/3 | 39.3 | 19.6 | 41.1 | 60.7 | 684 | 6.37 | 2.545 | 333.0 | 76.0 | 0.0758 | 10.6 | 2.6 | -13.3 | 0.0204 |

`flip_point_R` reused verbatim from the already-certified `reports/a_vpc_portfolio_optimisation/07_top_cell_stress.csv` (F01/F08/F02 rows), NOT recomputed here (avoids duplicating the full slip-ladder engine for 3 rows already on file at the exact pinned (budget,cap) tuples).

No winner-picking.
