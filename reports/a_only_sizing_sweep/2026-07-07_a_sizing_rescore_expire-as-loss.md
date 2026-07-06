# A-only Sizing Re-Score — Expire-as-Loss (corrected objective)
**SIM-OPTIMAL — NOT real pass probability; gated on N≥30 live fills.** Re-score of the persisted 144-cell geometry sweep (`2026-07-07_a_sizing_geometry.csv`); no fresh bootstrap, no code, no DEC/config/register touched. Fable auditor, 2026-07-07. LIVE HOLD ACTIVE.

## The question, stated explicitly
Under the old framing, smaller caps were favored partly to stay LEFT of the bust wall (pass>bust discipline). Now that **expire counts as a failed eval equal to bust**, the objective is pass / not-pass, and not-pass = bust + expire. Does moving RIGHT on the grid (more size → faster R accumulation → fewer expires) raise total pass%, even at the cost of more bust — and if so, what cap minimizes (bust+expire)?

**Method identity:** pass + bust + expire = 100, so **minimizing (bust+expire) is exactly maximizing pass%.** Every input (per-cell pass/bust/expire%, bootstrap CIs) is already persisted → this is a pure re-score.

## Per-column curves (expire falls, bust rises; b+e = not-pass)
Representative columns (full 16 in the CSV; every column has the identical monotone shape):

**unfiltered_fixed15 / $1000** — cap : expire / bust / **b+e** / pass
```
cap 2:  96.6 /  0.0 / 96.6 /  3.4
cap 5:  66.3 / 12.4 / 78.7 / 21.4
cap 6:  51.7 / 20.6 / 72.2 / 27.8   <- current geometry
cap 8:  34.5 / 30.3 / 64.8 / 35.1
cap10:  24.7 / 37.1 / 61.8 / 38.2
cap12:  16.4 / 42.4 / 58.8 / 41.2
cap15:   9.9 / 46.9 / 56.8 / 43.2   <- min(b+e) = max(pass), AT GRID BOUNDARY, still falling
```
**kept_exit3 / $900** (the current live A-only surface): cap-6 b+e 82.7 → cap-15 b+e 68.0, pass 17.3 → 32.0, still falling at the boundary.

**The shape is the finding:** in ALL 16 columns, (bust+expire) is monotonically decreasing across the whole tested range — expire collapse (e.g. 52%→10%) outweighs bust rise (20%→47%) at every step. The minimum is at **cap-15 in 16/16 columns, and it is still falling at cap-15.** There is NO interior optimum inside the grid.

## Did the optimum move off cap-6?
**Point estimate (fill-blind sim): YES — to cap-15 (the grid boundary), in all 16 columns, still rising in pass%.** The corrected objective removes the bust-wall rationale that kept caps small, and expire-as-loss rewards faster R accumulation, so raw pass% climbs with size across the entire grid. This confirms the operator's hypothesis directionally: cap-6 was partly a bust-wall artifact of the old framing.

## Why the point-estimate optimum is NOT the recommendation (three honesty layers)

**1. It is a boundary optimum with no observed peak.** b+e is still falling at cap-15 in 16/16 columns → the objective, taken literally on this data, says "keep increasing size past the grid." The interior optimum would sit wherever expire floors near 0 and bust-rise finally dominates — beyond cap-15, unobserved. An objective whose optimum is "more, unbounded" is being bounded by a constraint the sweep does not model.

**2. The unmodeled constraint is FILL FRAGILITY — and it is the real binding wall.** This re-score uses persisted pass% under the current fill model, with NO fill stress. Prior stress programs (A+VPC optimisation §07, salvage A6) established that **cap-10+ configurations die at 0.015–0.019R slippage** — winners do not fill at 15-lot depth, so cap-15's 43% pass is a fill-blind illusion; under honest fills its bust climbs and its pass collapses. The old framing used the *bust wall* to keep caps small; the corrected objective removes that wall but the *fill wall* (~cap-8–10) is still there and the sim is blind to it. Removing the bust-wall guardrail did not create new headroom — it just exposed the fill wall as the real binding constraint.

**3. The move is statistically unresolvable in 15 of 16 columns.** Effective-N ≈ 22 (from the source sweep) → pass% CI half-widths ≈ 8pp. Testing each column's cap-15 optimum against its own cap-6:

| CI overlaps cap-6? | columns |
|---|---|
| **YES — indistinguishable at 95%** | **15 / 16** |
| NO — separated | 1 / 16 (kept_fixed15 / $1000 only) |

Per the operator's own stated rule ("if the new optimum's CI overlaps cap-6's, the honest recommendation is STILL don't change it"), 15/16 columns say don't change it. The lone separated column (kept_fixed15/$1000) is itself a cap-15 cell = squarely in the fill-fragility zone from layer 2 — it separates on a fill-blind number that fills would erase.

## Denominator-artifact guard (DEC-20260706-1108)
0 MIRAGE cells. Eligible-starts is geometry-invariant (kept=525, unfiltered=623, constant across all caps within a surface — sizing does not gate which days are eligible), so pass_count = pass% × constant → pass-count is monotonic in pass%. A pass%-up/count-down cell cannot exist in a pure sizing sweep. The guard is real for filter searches; structurally moot here. Confirmed numerically.

## Joint 95% frontier
Global max-pass cell = unfiltered_fixed15/$1000/cap-15, pass 43.2% (CI 35.8–50.9), bust 46.9%. The joint indistinguishable frontier (all 144 cells, CI-overlap with the top) is wide (~45 cells) — consistent with effective-N ≈ 22. The current live A-only geometry (kept_exit3/$900/cap-6, 17.3%) is NOT in the top band, but that gap is driven by the two already-decided DEC improvements (unfiltered stream, Fixed-1.5R) plus size — and the size component is the fill-fragile, statistically-unresolvable part.

## SUMMARY (one paragraph)
Under the corrected objective (expire = bust = failed eval), the (bust+expire) minimum moves OFF cap-6 to cap-15 — the grid boundary — in all 16 budget columns, and is still falling there, because expire-reduction from faster R accumulation outweighs the bust increase across the entire tested range; so in fill-blind point-estimate terms the objective favors moving right, unbounded. But that optimum is not actionable: it is a boundary with no observed interior peak, it is statistically indistinguishable from cap-6 in 15 of 16 columns at effective-N ≈ 22 (CI half-widths ~8pp), and the one column where it separates is a cap-15 cell inside the fill-fragility zone that prior stress work already showed dies at 0.015R slippage — a wall this fill-blind re-score cannot see. The honest reading is that the corrected objective correctly dissolves the *bust-wall* reason cap-6 looked optimal, but re-exposes the *fill wall* (~cap-8–10) as the true binding constraint; under the fill evidence we already have, the fill-aware optimum sits around cap-6–8, indistinguishable from cap-6 at this resolving power. **Recommendation: do not move to high cap; cap-6 remains defensible. The corrected objective mildly favors the cap-6–8 band but the surface cannot resolve cap-6 from cap-8, and cap-10+ is fill-disqualified — so the only honest way to license any rightward move is live fill evidence (N≥30) proving larger clips fill clean, not this sim.**

---
**Re-score vs fresh bootstrap:** pure RE-SCORE of persisted data — no fresh bootstrap ran (the corrected objective is an algebraic transform of already-computed pass/bust/expire% and their CIs; no honesty guards needed re-running). **Did the optimum move off cap-6:** in fill-blind sim point estimate YES (to cap-15, boundary, still rising); under honest resolution (CI overlap 15/16 + the re-imposed fill wall) effectively NO — cap-6 stays defensible and any move is unresolvable/fill-gated.
