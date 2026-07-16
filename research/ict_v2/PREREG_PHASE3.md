# ICT V2 — Phase 3 Preregistration (v1.0, FROZEN)

**Author:** Fable (Trading CEO) · filed 2026-07-14, BEFORE any Phase-3 measurement code ran.
**Governs:** the decision-layer measurement programme (Charter Phase 3). Amendments require a new version + vault DEC; results obtained outside this prereg are void.
**Canon:** `01 Projects/ICT V2/ICT V2 — Missing Decision Layer.md` · Implementation Standard · Constitution (prereg-first).

## 0. What Phase 3 is and is not

Phase 3 measures whether **decision-layer features** — the things V1 never tested — carry conditional structure over the certified event streams. It is **event-level descriptive science (ATLAS-style)**: outcomes are forward path measures in ATR units and event-terminal states. **No strategy P&L, no PF/WR/expectancy, no entries/exits/stops.** Strategy translation is Phase 4/5, and only for features that survive here.

**Known priors this must not rediscover** (cited, not re-run): ATLAS-0008 (sweep+reclaim 1m reversal dead as a trade); SMC3 bucket-flat WR across its causal features; ATLAS meta-law (direction ≈ null at event granularity); "no filter raises total R" ×7. Phase 3 differs by: complete denominators (ACCEPTED_BREAKOUT/TIMEOUT recorded, not discarded), richer never-tested features (salience components, reclaim latency, cleanliness, remaining-opportunity, freshness), event-level outcomes rather than fixed-2R trade outcomes, and a mandatory ICT-free incrementality control.

## 1. Data & eras (FROZEN)

- Instrument/frame: certified NQ 5m frame (the WP-D dataset, 2021-06-22 → 2026-06-22, 353,952 bars), events from the semantically-certified V2 engine stack (`research/ict_v2/`, cert `reports/ict_v2/02`).
- **IS (development era): 2021-06-22 → 2025-06-21.**
- **HOLDOUT (frozen): 2025-06-22 → 2026-06-22.** Touched exactly ONCE, by the confirmatory pass (§6), only for cells that survive all IS gates. Any other read of holdout events voids the cell.
- Sessions: primary label from SessionEngine; unless a cell says otherwise, events from all sessions with session as a control.

## 2. Units, decision times, features (knowability rule)

Every feature is computed from data with `confirmed_at ≤ t0` for that event's declared decision time t0. The extraction layer must assert this structurally (events consumed via `history_through(t0)`).

**Baseline feature set B (the ICT-free control, fixed):** time-of-day slot (30-min bucket), day-of-week, ATR20 percentile (vs trailing 60 sessions), σ_TOD-relative realized vol of last 12 bars, signed 12-bar return in ATR units, overnight gap in ATR units. Nothing else enters B.

**Outcomes (per event, direction-adjusted where the event has a direction):**
- `fwd(h)` = signed close-to-close return from t0 to t0+h bars, ÷ ATR20(t0). Horizons h ∈ {12, 24, 48} (1h/2h/4h). Primary h = 24.
- `maxcont(h)` / `maxrev(h)` = max favorable / adverse excursion over (t0, t0+h], ÷ ATR20(t0).
- `rev24` = 1 if fwd(24) < 0 (against event direction).
- Excursion episodes additionally carry their FSM terminal state (SWEEP_CONFIRMED / ACCEPTED_BREAKOUT / EXCURSION_TIMEOUT).

## 3. Preregistered cells (complete list — nothing else may be reported)

**F1 SALIENCE** — unit: level-excursion episodes (EXCURSION_OPEN, t0 = close of first bar beyond). One cell per component, testing outcome heterogeneity of |fwd(24)| and P(terminal = SWEEP_CONFIRMED):
F1a timeframe class (weekly vs intraday level) · F1b prior test_count (0 vs ≥1) · F1c equality flag · F1d roundness flag · F1e prominence tercile (top vs bottom). *(5 cells)*

**F2 ACCEPTANCE/REJECTION PREDICTION** — unit: excursion episodes at t0 (first-beyond bar close). Target A: terminal SWEEP_CONFIRMED vs ACCEPTED_BREAKOUT (timeouts excluded, count reported). Target B: sign(fwd(24)). Ex-ante features: excursion depth (ticks and ATR units), t0 bar close-location, body_vs_tod at t0, volume_z at t0, salience component snapshot, + B. Metric: blocked-CV AUC uplift over B alone (gate G2). *(2 cells)*

**F3 CONFIRMATION LATENCY** — unit: SWEEP_CONFIRMED (t0 = confirmation close). Feature: reclaim_speed_bars (1 / 2 / 3). Outcome: fwd(24) in the reversal direction; monotonic tercile/ordinal contrast fast-vs-slow. *(1 cell)*

**F4 DISPLACEMENT PERSISTENCE** — unit: DISPLACEMENT_QUALIFIED (t0 = qualifying bar close). Features (one cell each): body_vs_tod magnitude tercile · close_location tercile · volume_z tercile. Outcome: fwd(24) in displacement direction (continuation) and maxrev(24). *(3 cells)*

**F5 PATH CLEANLINESS** — unit: (a) DISPLACEMENT_QUALIFIED, (b) MSS events. Feature: efficiency = |net move| / Σ|bar moves| over the trailing 12 bars ending at t0, terciles. Outcome: fwd(24) in event direction. *(2 cells)*

**F6 REMAINING OPPORTUNITY** — unit: (a) SWEEP_CONFIRMED, (b) MSS, both restricted to ny_am. Feature: session-range-consumed = (session H−L so far at t0) ÷ (median full-session range, trailing 20 sessions), terciles. Outcome: |fwd(24)| and maxcont(24). *(2 cells)*

**F7 FRESHNESS** — unit: (a) LEVEL_TESTED, (b) FVG TESTED (first eligible test events; t0 = test bar close). Feature: test_number (1st vs 2nd+). Outcome: P(bounce) = P(sign(fwd(12)) is away from level/zone) and |fwd(12)|. *(2 cells)*

**Total: 17 cells.** Cells with <50 IS events per compared group = **NO-TEST** (recorded, not interpreted; house rule).

## 4. Estimators (fixed)

- Contrast cells (F1, F3-F7): difference in mean outcome (or proportion) between preregistered groups; 95% CI by **weekly block bootstrap** (resample calendar weeks, 2,000 draws). Effect floor: |Δ| ≥ 0.05 for probabilities, ≥ 0.10 ATR for magnitudes.
- Prediction cells (F2): logistic regression, features standardized; **blocked 5-fold CV by calendar week**; metric = mean AUC. A gradient-boosting sensitivity run is permitted but is not the gate.
- Multiplicity: **Benjamini-Hochberg at q = 0.10 within each family** over that family's preregistered cells; families are separate.

## 5. Gates (kill thresholds — a cell must pass ALL to survive IS)

- **G1 effect:** 95% CI excludes 0 AND meets the effect floor (F2: AUC(B+feature) − AUC(B) ≥ 0.02, CI excluding 0).
- **G2 ICT-free incrementality (Arm-4, every cell):** the contrast/AUC must remain ≥50% of its size after regression-adjusting for baseline set B (contrast cells: B-residualized outcome; F2: uplift over B is the metric itself). If B alone reproduces the effect → cell dies as "market-state, not ICT" (recorded as such — that finding routes to ATLAS, not to Phase 4).
- **G3 era stability:** effect sign consistent in ≥3 of the 4 IS years AND no single year contributes >60% of the aggregate effect.
- **G4 FDR:** survives BH within family (q=0.10).

## 6. Holdout confirmation (single pass)

Cells passing G1-G4 on IS are measured ONCE on the frozen holdout: survive iff same sign AND ≥50% of IS effect magnitude (F2: holdout AUC uplift ≥ 0.01). The holdout pass is run by a separate execution from the IS analysis, after the IS report is committed. Failures are final.

## 7. Verdict rules (preregistered interpretations)

- **0 survivors:** decision layer carries no conditional structure on price-only NQ data → Phase 4 tests only the declared raw sequences (expected dead per priors) → programme routes toward Outcome-1 closure; order-flow re-run remains open under Court D1.
- **Survivors exist but all G2-die (B explains them):** finding = market-state structure, filed to ATLAS; ICT labels redundant; same routing as 0 survivors for the ICT branch.
- **≥1 survivor passes G2 + holdout:** feature is **CERTIFIED-CONDITIONAL** and becomes a Phase-4 building block (acceptance-gate candidate). Only then does the Alpha-Asset-#2 hypothesis (Setup Acceptance Score) get built — as a Phase-4/5 prereg of its own.

## 8. Execution plan & bans

- **WP-E (build, Sonnet):** event/feature/outcome extraction over the certified engine streams → per-family parquet datasets + counts report. NO statistics beyond event counts. Knowability asserted via `history_through`. Holdout rows written to separate files and NOT READ by any analysis until §6.
- **WP-F (build+run, Sonnet):** measurement harness implementing §4-§5 exactly; synthetic self-test (planted effect + null placebo must pass/fail correctly); then the IS run; report to `reports/ict_v2/03_phase3_is_results.md` citing this prereg's git hash. Fable adjudicates gates; then §6 holdout pass; final report `reports/ict_v2/04_phase3_verdict.md`.
- Bans: no PF/WR/expectancy; no parameter search over thresholds/horizons beyond the preregistered lists; no unlisted cells; no holdout contact outside §6; AMD events excluded (uncertified on real data).

---
## AMENDMENT v1.1 (2026-07-17, BEFORE any Phase-3 measurement ran)

**Change (data-quality only, no cell/gate/threshold change):** §1's frame is replaced by the
roll-adjusted series `data/real_futures/NQ_databento_1m_5y_rolladj.parquet` (16 quarterly roll
gaps back-adjusted; discovery + validation: vault BT-20260716-1659). Rationale: the original
splice contains 16 artificial ~80-320pt bars at expiry-week midnights that forge
displacement/excursion events with extreme ATR-multiple outcomes — a known data artifact, not
market structure. The certified engines are frame-agnostic (semantic certification, WP-D).
Same resample recipe, same date range, same IS/holdout boundaries. Authorized by operator
session directive 2026-07-17 (Phase-3 execution order); no outcome data were consulted.
