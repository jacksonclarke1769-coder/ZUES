# ICT V2 — Phase 4 Preregistration (v1.0, FROZEN)

**Author:** Fable (Trading CEO) · filed 2026-07-17, operator-ordered ("run phase 4 and build
the acceptance gate"), BEFORE any Phase-4 measurement ran.
**Inputs (fixed):** the Phase-3 certified-conditional set ONLY — F1a (level timeframe class)
and F2a′ (initial thrust depth at t0). No other feature may enter any Phase-4 gate.
**Governing chain:** PREREG_PHASE3.md (cd652ea → bc35ceddcb10) · Phase-3 verdict (dd3b685) ·
Constitution (prereg-first, no self-certification).

## 0. The translation problem (why Phase 4 has two stages)

F2a′ certifies that depth at t0 predicts WHETHER an excursion resolves as sweep vs acceptance.
The candidate strategies (sweep-family) enter AFTER confirmation — the certified question is
already resolved at their entry. Whether depth/level-class predicts the POST-confirmation
path is a NEW claim and must be measured before any gate is built. Stage 4A tests that bridge
at event level; Stage 4B translates only 4A survivors into one-shot trade gates.

## STAGE 4A — Bridge cells (event-level, existing Phase-3 parquets, nothing re-extracted)

Unit: `sweep_confirmed` events (IS file). t0 = confirmation close (as extracted).
Outcomes (as extracted): fwd(24) SIGNED IN THE REVERSAL DIRECTION (back-inside side of the
swept level), maxcont(24) in reversal direction, maxrev(24). Primary outcome: fwd24_reversal.

- **P4-B1 depth:** feature = excursion_depth_ticks × tick ÷ atr20 (ATR-normalized), IS
  terciles (boundaries computed on IS, frozen). Contrast: bottom vs top tercile.
- **P4-B2 level class:** weekly-class vs intraday-class.

Estimators/gates identical to Phase-3 §4-§5: weekly block bootstrap (2,000), effect floor
0.10 ATR (magnitudes) / 0.05 (probabilities), G2 ICT-free incrementality vs baseline B,
G3 era stability (≥3/4 IS years, no year >60%), G4 BH q=0.10 within this 2-cell family.
NO other cells. NO threshold search.

**Holdout:** `sweep_confirmed_holdout` has NEVER been opened (Phase-3 hygiene record).
Survivors of 4A-IS get ONE §6-style pass: same sign AND ≥50% IS magnitude. Run as a separate
execution after the 4A-IS report is committed.

## STAGE 4B — One-shot trade-level gates (only for 4A survivors)

For each 4A-surviving cell, ONE gate, fully determined by the event study (zero tuning):
- Depth gate (if B1 survives): block entries whose originating sweep's t0 depth falls in the
  IS tercile with the ADVERSE certified outcome; threshold = that IS tercile boundary.
- Class gate (if B2 survives): block entries whose swept level is in the adverse class.

Applied ONCE, no variants, to two fixed subjects:
1. **Fork-A surface-at-MSS certified stream (581 signals)** — decision-weight subject
   (certified, unmined). Judged at slip-8 honest fills.
2. **ZEUS ICT v0.5 stream (740 trades)** — REPORT-ONLY subject (its history is mined 3×;
   no certification claim may be made from it; reported for the operator's information).

Acceptance criterion (per subject, preregistered): the gate is ACCEPTED iff total net R does
NOT decrease AND (PF improves OR maxDD improves). Mapping from trades to their originating
sweep events must be exact (same engine identifiers), else the trade is ungateable and kept.

## Verdict rules

- 4A zero survivors → Phase-4 translation FAILS; F1a/F2a′ remain event-level knowledge;
  the acceptance-gate thesis routes to order-flow (Court D1). Recorded, closed.
- 4A survivor(s) but 4B acceptance fails on the certified subject → gate rejected; same routing.
- 4B accepted on the certified subject → the gate becomes a CERTIFIED-CANDIDATE overlay for
  the Fork-A/Profile-A family, eligible for the standard certification pipeline (paper
  shadow, live gates); it is NOT deployment.

## Bans

No PF/WR reported in 4A. No new features, sessions, or thresholds. No holdout contact
outside the single 4A pass. No gate variants. v0.5 subject: report-only, no iteration.
