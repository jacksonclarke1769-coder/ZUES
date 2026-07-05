# Wave 2 — Fill-Damage Sensitivity on the Surviving Sizing Cells

**SIM CONDITIONAL — pending live fill evidence**

Generated 2026-07-05. New tool: `tools_sprint_fill_sensitivity.py`. Modifies nothing existing.

Cells under test: (10,1200) reference; (15,1000) candidate; (20,1100), (25,1100), (30,1100) — the raw-E$/attempt maxima per cap from `cap_risk_matrix.csv`. E$/attempt = pass% x 12,728 - 131.

## Canary

(10,1200) no-damage: got pass=47.8 bust=15.9 exp=36.2 (n=395) vs expected pass=47.8 bust=15.9 exp=36.2 (n=395) -> **PASS**

Size-scaled-k cap-10 invariance check (E$[cap10,b1200] must be identical across every k, since q<=10 always): **OK**

## Headline table 1 — break-even damage level vs (10,1200), per overlay type (interpolated)

Break-even = damage level at which the cell's E$/attempt advantage over (10,1200) under the SAME damage level vanishes. `frac_f` break-even is reported as the f value (descending from 1.0); the cell survives partial fills down to that f.

| cap | budget | uniform s* | size k* | frac f* | touch-neutral t*% | touch-adverse t*% | survives realistic damage? |
|---|---|---|---|---|---|---|---|
| 15 | 1000 | >0.1 | >0.02 | 0.25 | >30 | 16.40979 | SURVIVES |
| 20 | 1100 | >0.1 | 0.01625 | 0.25 | >30 | >30 | COLLAPSES |
| 25 | 1100 | >0.1 | 0.01604 | >0.25 | >30 | >30 | COLLAPSES |
| 30 | 1100 | >0.1 | 0.0125 | >0.25 | >30 | >30 | COLLAPSES |

'Realistic damage' bar used for the survive/collapse call: uniform s<=0.05, size k<=0.02, frac f>=0.5, touch-adverse t<=10%. A cell must clear its E$ advantage over (10,1200) at EVERY one of these to be called SURVIVES.

## Headline table 2 — cap-15 (15,1000) confirmations

**(1) Does (15,1000) still beat (10,1200) under size-scaled k<=0.02?** **YES**

| k | E$[15,1000] | E$[10,1200] | 15 beats 10 |
|---|---|---|---|
| 0.0 | 6,894 | 5,959 | True |
| 0.0025 | 6,797 | 5,959 | True |
| 0.005 | 6,732 | 5,959 | True |
| 0.0075 | 6,700 | 5,959 | True |
| 0.01 | 6,668 | 5,959 | True |
| 0.015 | 6,604 | 5,959 | True |
| 0.02 | 6,281 | 5,959 | True |

**(2) Does (15,1000) still beat (10,1200) under asymmetric-partial f>=0.5?** **YES**

| f | E$[15,1000] | E$[10,1200] | 15 beats 10 |
|---|---|---|---|
| 1.0 | 6,894 | 5,959 | True |
| 0.75 | 3,639 | 3,252 | True |
| 0.5 | 1,061 | 1,029 | True |

**(3) NEW — does (15,1000) still beat (10,1200) under ADVERSE touch-without-fill up to t=20%?** **NO**

| t% (target) | t% (actual drop) | E$[15,1000] | E$[10,1200] | 15 beats 10 |
|---|---|---|---|---|
| 0 | 0.0 | 6,894 | 5,959 | True |
| 10 | 10.11 | 4,288 | 4,218 | True |
| 20 | 20.0 | 2,407 | 2,446 | False |

## Headline table 3 — tight-stop penalty (uniform 0.05R on stop<45pt trades only)

Penalized cohort: 232 / 435 trades had stop distance < 45.0pt.

| rank | cap,budget (no damage) | E$ (no damage) | | cap,budget (tight-stop) | E$ (tight-stop) |
|---|---|---|---|---|---|
| 1 | 30,1100 | 7,860 | | 30,1100 | 6,990 |
| 2 | 25,1100 | 7,796 | | 25,1100 | 6,894 |
| 3 | 20,1100 | 7,506 | | 15,1000 | 6,668 |
| 4 | 15,1000 | 6,894 | | 20,1100 | 6,571 |
| 5 | 10,1200 | 5,959 | | 10,1200 | 5,862 |

**Cap ordering by E$/attempt changes under the tight-stop penalty: YES**

## Machine-viability flags (ABSOLUTE E$/attempt <= 0 at plausible damage)

This is a machine-viability line, NOT a cap-choice line — it flags where the whole attempt goes value-negative regardless of which cap wins the comparison.

- **(10,1200)**: frac f=0.25 -> E$=-131
- **(15,1000)**: frac f=0.25 -> E$=-131
- **(20,1100)**: frac f=0.25 -> E$=-131
- **(25,1100)**: frac f=0.25 -> E$=-67
- **(30,1100)**: frac f=0.25 -> E$=-67

## Which raw-E$-max cells survive realistic damage vs collapse

- (15,1000): **SURVIVES** vs (10,1200) under the realistic-damage bar above.
- (20,1100): **COLLAPSES** vs (10,1200) under the realistic-damage bar above.
- (25,1100): **COLLAPSES** vs (10,1200) under the realistic-damage bar above.
- (30,1100): **COLLAPSES** vs (10,1200) under the realistic-damage bar above.

Runtime: 18.5s.

