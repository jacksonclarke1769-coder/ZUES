# ICT V2 — Phase 1: Implementation Review (consolidated)

**Date:** 2026-07-13 · **Author:** Fable (Trading CEO), from 3 parallel read-only audits
**Programme:** ICT Reopening (V2) — operator directive 2026-07-13. Charter: vault `01 Projects/ICT V2/ICT V2 — Programme Charter.md`.
**Scope:** every existing ICT implementation (live path + research harnesses) + the complete V1 verdict ledger.

---

## Headline findings

### F1 — V1 verdicts are causally honest. The graveyard stands on merit.

The audits looked hard for the failure classes named in the ICT V2 Implementation Standard (symmetric pivots traded at pivot time, FVG stamped on the middle candle, post-hoc dealing-range anchors, favourable same-bar ordering). **None were found inflating or deflating any recorded verdict:**

- Pivots are consumed only at the confirmation bar (`i+right`) in every harness (framework `last_known_swings`, SMC3 `_pivot`, ATLAS fractals).
- FVG is stamped at the 3rd candle everywhere; no middle-candle stamping exists in the codebase.
- Fills are adverse-first (stop-before-target) when one bar spans both; SMC3 exits start the bar after entry.
- The one genuine dealing-range/OTE exposure (is the OTE limit final at MSS time?) was explicitly stress-tested by fork_a and cleared **581/581** from MSS-truncated data.
- Per-trade lookahead assertions exist and pass at scale (SMC3 5,056/5,056; occ 20,965 trades).

**Consequence:** the directive's implicit hope that honest reimplementation alone might flip V1 kills into survivors is NOT supported. The V1 negatives are real negatives. V2's live levers are therefore (a) the never-tested decision layer, (b) order-flow data (Court docket D1), (c) execution-model honesty in the other direction (see F2) — not geometry re-coding.

### F2 — Where V1 falls short of the V2 Standard (real gaps, both directions)

| Gap | Where | Direction of bias |
|---|---|---|
| **Touch = fill** on resting limits (FVG-50 / OTE) | `model01:230-243` | Optimistic (fewer real fills) — the Profile A fill-mirage class |
| **Slip parity: live 2 ticks vs certified 8** | `fork_a/05`; live `PROFILE_A` config omits `slip_ticks` | Live limit rests 1.5pt shallower than certified — parity bug, pin slip=8 |
| No queue / partial-fill / liquidity model | all harnesses | Unknown; report sensitivity instead |
| **No 4-timestamp event model, no prefix-invariance test suite** | everywhere | Untested invariant (D1c tz bug was exactly this class: research attach path re-localized UTC→NY, +4-5h lookahead; the canary didn't cover post-hoc joins) |
| Sweep semantics vary silently (same-bar reclaim vs 1–3 bar; wick trigger + close reclaim) | SMC3 vs primitives | Different strategies under one name — V2 Standard violation |
| Sessions by wall-clock strings, killzones hardcoded | model01, config | The D1c incident class; needs IANA+CME calendar engine |
| No level registry with salience/test-count/freshness; fixed tier lists only | `model01:39-96` | The entire decision layer is absent |
| SMT visual/logged-only; no formal residual model; no macro-event state; no AMD FSM; no OR engine; no overnight-inventory object | — | Never built |

### F3 — What has never been tested (the genuinely new surface)

All of Phase 3's decision layer is greenfield: **level salience scoring, acceptance-vs-rejection classification, confirmation-latency decay, displacement persistence, path cleanliness, remaining-opportunity, freshness decay, and the acceptance gate itself.** V1 tested pattern geometry exhaustively and selection policy never.

### F4 — Meta-laws that bind Phase 4 (from the V1 ledger)

1. **Sweep-core has no NQ edge; confirmation flavor irrelevant** — BOS, FVG, IFVG-inversion all converge on pinned ~33% WR (SMC3, 6-pass).
2. **ATLAS meta-law:** direction ≈ null at event granularity once ToD/geometry/multiplicity controlled; structure lives in VOL. Sweep+reclaim reversal at 1m explicitly dead (ATLAS-0008), 6th independent confirmation.
3. **No filter raises total R** (replicated 7×) — levers are exit and sizing.
4. **Denominator-artifact rule** — judge filters on funded/slot-yr COUNT, not pass %.
5. **Overlap kill-bar** — ≥80-85% trade-day overlap with Profile A ⇒ "A in disguise" (killed M2, sweep→FVG-50).
6. **Causality-not-math rule** — every major V1 error was a causality bug, never arithmetic.

### V1 verdict ledger (summary — full ledger in vault `01 Projects/ICT V2/`)

CERTIFIED/live-lineage: Profile A core (on hold, fill-fragile; surface-at-MSS rescue causally clean, needs N≥30 live fills). WATCHLIST: sweep→OTE reversal (measurement-certified, fails cost/fill stress), momentum (portfolio ctx). KILLED/REJECTED/MIRAGE: EMIT-001 fill mirage, sweep→FVG-50 (A in disguise), SMC3/Profile-D, IFVG probe, Profile C (PD/FVG, 1,024 cells), Wyckoff (4,000 cells), turtle soup, Silver Bullet, opening-drive, OCC HTF-align, HTF-skip (ticket Z), Asia/London transplants (all), Asia VWAP orphan. Non-ICT context: VPC certified-measurement (the one deployable lane).

### Discrepancy noted

Agent citations disagree on `reports/prelive_audit/` (one audit found it absent in the bot repo; the ledger cites `reports/prelive_audit/04_fill_verification.md`). Locate and reconcile the canonical prelive-audit path in Phase 2 housekeeping; the findings themselves are cross-confirmed via `emergency_recert_d1c_lookahead/` and `fork_a/`.

---

## Phase 1 verdict → Phase 2 direction

1. **Reuse, don't rewrite, the frozen detection core** (`ict-nq-framework/engine/primitives.py`, `model01`) — it is causally clean and battle-audited. Wrap it in the V2 event model (4 timestamps, lifecycles, registry) rather than re-implementing geometry.
2. **Build the missing infrastructure first:** CausalEvent model + prefix-invariance test harness + level registry (salience/test-count/freshness) + session/calendar engine + sweep FSM with ACCEPTED_BREAKOUT as a recorded outcome (V1 discarded continuations — the acceptance/rejection classifier needs both classes).
3. **Priority re-order within the directive:** Phase 3 (decision layer) is the scientific payload; Phase 2 exists to serve it. Geometry-only re-tests of graveyard families are prohibited as rediscovery — a graveyard family re-enters testing ONLY behind a new decision-layer gate or new data.
4. **Fix the two live parity items regardless of programme outcome:** pin `slip_ticks=8` in live `PROFILE_A` (fork_a/05) and adopt prefix-invariance tests into the standing suite.
5. **Data gating flagged in every registry row:** OFI/depth/formal-SMT cells wait on Court docket D1 (Databento MBP-10/MBO + ES sync). Price-only proxies proceed now, labelled as the weak form.
