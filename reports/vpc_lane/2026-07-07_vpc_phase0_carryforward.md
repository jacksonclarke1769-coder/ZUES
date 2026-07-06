# VPC Phase-0 → Live-Phase Carry-Forward Risk Register
**PHASE-0-SIM-ONLY.** These blockers are NOT Phase-0 code — they are live-boundary risks that Phase 0 (canonical `vpc_trail()` + parity canary) deliberately does not resolve. They are recorded here so they **cannot be silently dropped** when the live phase is eventually scoped. Each must survive into the live-phase scope with its required resolution attached. Fable auditor, 2026-07-07. LIVE HOLD ACTIVE.

Phase 0 proves the trail refactor is behavior-preserving (sim reproduces the frozen VPC stop series bit-for-bit). It does **not** prove live will match sim, and it does **not** build any of the four items below. Do not read a green Phase-0 gate as live-readiness.

---

## BLOCKER 1 — Watchdog / trail-churn reconciliation
**The risk:** VPC's live exit is a *moving* stop implemented by cancel-replace. Each trail update makes a stop-leg vanish and reappear — normal for VPC, an ORPHAN for the watchdog's current single-lane logic. A naive orphan check false-positives on every trail update and either spam-flattens VPC or, worse, gets **disabled by a human to stop the spam — removing fail-closed authority on the exact lane doing cancel-replace.**

**Required resolution (GATING, not optional):** the watchdog's orphan/parity logic must be extended to recognize VPC's expected cancel-replace churn as legitimate (whitelist the in-flight trail-replace window) WHILE still catching a genuinely naked or mis-sized position. This must be resolved **IN THE SAME PHASE as the live trail manager, not after** — the two are one unit. Acceptance: a paper-shadow replay shows ZERO orphan false-positives across the full observation-mode session count, proven, before arm. The watchdog must never be the thing an operator turns off to make VPC quiet.

## BLOCKER 2 — Cancel-replace timeout / in-flight bound
**The risk:** "replace-then-cancel, never naked" is an *ordering* rule; it has no *time* bound. Naked-position risk materializes not via ordering but via **latency during fast moves** — if the replace hangs or the confirm is slow while the market runs, the intended new stop is not yet working and the old one may already be through market.

**Required resolution:** spec a **maximum in-flight window** for any trail replace, and a **hard-flatten-and-stand-down** behavior when it is exceeded (if the new stop is not confirmed working within the bound, flatten the position immediately and halt the lane — a realized exit is safe; an unbounded naked window is not). The bound is a live-phase design parameter with its own test; a trail update that cannot complete inside it converts to an exit, never to a wait.

## BLOCKER 3 — Live-shaped parity arm (from Phase-0 canary ARM B)
**The risk:** the Phase-0 parity canary (ARM A) proves the refactored `vpc_trail()` reproduces historical replay bit-for-bit — it proves the refactor is clean. It does **NOT** prove that the same `vpc_trail()`, fed live-shaped bar-close input (real broker bar-arrival semantics, streaming one bar at a time), produces the identical stop series. **The real sim/live divergence risk lives at exactly that boundary**, and a canary that can only test historical replay cannot see it.

**Required resolution (REQUIRED-BEFORE-ARM):** build ARM B of the parity canary — feed the same `VpcTrail` stepper one bar at a time from a live-shaped feed mock and assert the resulting stop_path is identical to ARM A's historical replay. Currently STUBBED (`pytest.skip("REQUIRED-BEFORE-ARM")`). The lane may not arm until ARM B is built and green.

---

## SEQUENCING GATE (hard precondition on the live-wiring phase)
**The live-wiring phase is GATED ON Profile A clearing N≥30 live fills.**

**Rationale (record permanently):** Profile A is the simple case — static stops, static targets, no order-modify path, fire-and-forget bracket. A's live fills are the calibration that confirms sim/live parity *in this stack on the easy case* before VPC's cancel-replace trail machinery is trusted. **Building VPC live before A's fills means you could not distinguish a fill-model error from a trail-manager bug** — a divergence in VPC live-vs-sim would be unattributable between "the stack's fills differ from sim" (which A would have already revealed) and "the trail manager is wrong." A de-risks the fill model on the trivial case first; only then does VPC's hard case get wired.

**Consequence:** Phase 0 (canonical `vpc_trail()` refactor + parity canary, sim-only) proceeds now. The live-wiring phase does **not scope** until A's N≥30 live-fill evidence exists. This gate sits upstream of Blockers 1–3; none of them are built until it clears.

---

## Standing status
- Phase 0 (this build): canonical `vpc_trail()` + bit-identical ARM-A parity canary — sim-only, no live path touched.
- Live phase: NOT SCOPED, NOT ESTIMATED. Gated on A's N≥30 fills, then Blockers 1–3 resolved (Blockers 1 & the trail manager in one phase), then paper-shadow clean, then re-certification + DEC, then operator arming approval.
- The hold does not lift on any partial completion.
