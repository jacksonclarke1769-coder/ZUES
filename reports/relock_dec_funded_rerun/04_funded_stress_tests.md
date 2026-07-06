# 04 -- Funded Stress Tests (RE-LOCK DEC + Funded Re-Run)

RESEARCH ONLY. LIVE HOLD ACTIVE. Top-5 cells by E[paid] among bust<=15% (from 03_funded_rerun_matrix), plus the best VPC-inclusive cell (A@250/4+VPC@300/2) if not already in that set.

OVERLAP CAVEAT (verbatim): monthly rolling starts OVERLAP -> effective independent samples ~4-5, bust% has wide CI

## Winners-fill adjudication (quoted verbatim, `reports/a_vpc_portfolio_optimisation/07_top_cell_stress.md`) -- NOT used as a funded-side REJECT criterion:
> the winners-75% clause is UNSATISFIABLE by construction for any honest thin edge (PF 1.35 x 0.75 ~= 1.01 breakeven -- only PF>=1.8 machines pass it, which our too-good gate would freeze). It rejected the baseline and discriminates nothing. RULING: winners-fill sensitivity is a MACHINE-LEVEL operating condition governed by the existing live fill-telemetry kill line (15% adverse touch-without-fill ~= 85% winner-capture floor), NOT a config selector. Config-level reject bar = dies-at-0.015R OR flip<0.025R OR dies-at-2x-costs -- under which all 45 survive.

REJECT column: bust% > 25.0 at 0.02R slip OR E[paid] < $3,000 at 0.02R slip.

| label | base E[paid] | base bust% | base SN% | slip0.01 E[paid] | slip0.01 bust% | slip0.02 E[paid] | slip0.02 bust% | slip0.03 E[paid] | slip0.03 bust% | slip0.05 E[paid] | slip0.05 bust% | slip0.075 E[paid] | slip0.075 bust% | slip0.1 E[paid] | slip0.1 bust% | cost2x E[paid] | cost2x bust% | cost3x E[paid] | cost3x bust% | REJECT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A@250/4+VPC@300/2 | $10,291 | 14.3 | 100.0 | $10,041 | 14.3 | $9,873 | 14.3 | $7,759 | 31.0 | $5,841 | 45.2 | $2,945 | 64.3 | $1,075 | 85.7 | $9,908 | 14.3 | $7,086 | 35.7 | False |
| A@300/4+VPC@150/1 | $8,974 | 2.4 | 100.0 | $8,662 | 2.4 | $7,505 | 9.5 | $6,693 | 31.0 | $4,054 | 50.0 | $2,561 | 61.9 | $1,993 | 64.3 | $6,569 | 31.0 | $3,994 | 50.0 | False |
| A@200/3+VPC@300/2 | $8,729 | 7.1 | 100.0 | $9,314 | 0.0 | $6,274 | 28.6 | $5,147 | 33.3 | $3,266 | 47.6 | $1,896 | 57.1 | $1,260 | 64.3 | $6,748 | 21.4 | $4,383 | 33.3 | True |
| A@250/4+VPC@200/2 | $8,622 | 2.4 | 100.0 | $8,644 | 2.4 | $8,556 | 2.4 | $6,654 | 16.7 | $5,530 | 23.8 | $2,389 | 54.8 | $1,713 | 54.8 | $8,185 | 4.8 | $5,745 | 21.4 | False |
| A@300/4+VPC@100/1 | $8,525 | 2.4 | 100.0 | $7,589 | 9.5 | $6,120 | 26.2 | $5,141 | 38.1 | $3,118 | 57.1 | $2,360 | 59.5 | $1,946 | 59.5 | $5,604 | 33.3 | $2,686 | 59.5 | True |

Winners-fill (90/85/75%) and entry-realism (A +1/+2tk, VPC +0.5/+1pt) points are in the CSV (all columns) for completeness; per the adjudication above, winners-fill is informational only, not a reject criterion here.

No winner-picking.
