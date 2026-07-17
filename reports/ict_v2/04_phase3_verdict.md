# ICT V2 Phase 3 — WP-F §6 Holdout Verdict

**Governs:** `research/ict_v2/PREREG_PHASE3.md` v1.0 + Amendment v1.1, git hash `cd652ea81093`. **IS report:** committed `fb798d7` (`reports/ict_v2/03_phase3_is_results.md`), adjudicated by Fable. **Scope:** the single §6 holdout confirmation pass — a separate execution touching the frozen holdout files EXACTLY ONCE, only for the two Fable-certified IS survivors (F1a, F4b), reading only each cell's preregistered columns. F2a was NOT taken to holdout (Fable ruling — see §3). No PF/WR/expectancy.

## 1. Holdout confirmation (§6 rule: same sign AND |holdout Δ| ≥ 0.5·|IS Δ|)

| cell | unit | outcome | groups (A vs B) | IS Δ | HOLDOUT Δ | 95% CI (holdout) | same sign | |Δ| ratio | ≥0.5 | VERDICT |
|---|---|---|---|---:|---:|---|:---:|---:|:---:|:---:|
| F1a | excursion_episodes | P(SWEEP_CONFIRMED) | weekly vs intraday | -0.149 | -0.142 | [-0.155, -0.127] | True | 0.95 | ✓ | **CERTIFIED-CONDITIONAL** |
| F4b | displacement_qualified | maxrev24 | close_location_top vs close_location_bottom | 0.117 | 0.006 | [-0.208, 0.201] | True | 0.05 | ✗ | **REFUTED** |

Supplementary (not the §6 gate): holdout bootstrap p and B-residualized retention — F1a: p=0.0000, CI-excl-0=True, G2-retention(holdout)=1.07, n_A=19,728, n_B=349,099; F4b: p=0.9820, CI-excl-0=False, G2-retention(holdout)=6.88, n_A=5,500, n_B=5,499.

## 2. Final Phase-3 verdict per cell

- **F1a** (salience: weekly vs intraday level → P(SWEEP_CONFIRMED)): **CERTIFIED-CONDITIONAL**.
- **F4b** (displacement close-location tercile → maxrev(24)): **REFUTED**.

## 3. §7 routing summary

- **F2a** — IS-SURVIVOR, **HOLDOUT DEFERRED, re-scope required.** Fable ruling: F2a passes the prereg's letter but fails its spirit. For the `reclaim_speed_bars=1` majority (~69% of confirmed sweeps) the terminal resolves ON the t0 (first-beyond) bar, so the preregistered `t0 close-location` feature is quasi-contemporaneous with the label — AUC 0.956 mostly *reads* the outcome rather than *predicting* it. This is a design defect in the cell's own definition (t0 = first-beyond close while terminals can resolve same-bar), NOT look-ahead and NOT an extraction error. It did NOT touch holdout. Disposition: re-scope via a prereg amendment (either restrict the unit to episodes UNRESOLVED at t0, or restrict features to strictly-pre-t0 bars); the amendment is OPERATOR-GATED and the re-scoped cell is not implemented here.
  - **Residual scientific content carried to the amendment:** whether acceptance/rejection of a level excursion is predictable *before* it resolves is exactly the book's Chapter-20 question, and it remains **OPEN**. The tautological version (F2a as written) answers nothing about it; the re-scoped cell would.
- **F6a, F6b** (remaining-opportunity: ny_am session-range-consumed → |fwd24| / maxcont24): route to **ATLAS as market-state, NOT ICT.** Both showed large raw contrasts (|Δ|≈1.3–1.6 ATR) but the effect is fully explained by baseline set B (G2 retention ≈ 0) — i.e. it is generic volatility/opportunity structure, not a decision-layer (ICT) signal. Per §7 this is filed to ATLAS; the ICT label is redundant here.
- **F2b** (sign(fwd24) prediction): AUC uplift ≈ 0 — a **reconfirmation of the ATLAS meta-law (direction ≈ null at event granularity)**, cited in the prereg as a known prior. Filed as such.
- **12 dead cells** (no conditional structure on IS; not taken further): F1b, F1c, F1d, F1e, F2b, F3, F4a, F4c, F5a, F5b, F7a, F7b — each failed >=1 IS gate (floor/G1, or G2 market-state, or G3 era-instability, or BH/G4). Recorded for the causal ledger. (F2b is among these 12 and additionally carries the direction≈null note above.)

## 4. Programme verdict (§7)

**1 feature(s) CERTIFIED-CONDITIONAL** (passed all IS gates AND the §6 holdout): F1a. Per §7, a certified-conditional feature becomes a Phase-4 building block (acceptance-gate / Alpha-Asset-#2 candidate), to be built only under its own Phase-4/5 prereg. Phase 3 is CLOSED for the measured cells, pending the operator's F2a re-scope amendment decision.

*Holdout pass runtime: 12.85 s. Holdout files opened exactly once, for F1a and F4b only.*


---

## v1.2 — F2a′ §6 holdout (Amendment v1.2, git hash `bc35ceddcb10`)

Final Phase-3 measurement. F2a′ (F2a re-scoped to episodes whose FSM terminal resolves STRICTLY AFTER t0) passed all IS gates (uplift 0.347; leak audit accepted by Fable) and was taken to the one-shot §6 holdout. Confirmatory design: B and B+ICT logistic models FIT on the IS post-t0 population (committed IS run `fb798d7`), evaluated EXACTLY ONCE on the frozen holdout post-t0 population. §6 F2 rule: holdout AUC uplift ≥ 0.01 AND same sign as IS. DISCLOSURE: `excursion_episodes_holdout` was previously opened once for F1a's columns (incl. the terminal column); no F2a′ FEATURE column had been read from holdout before this pass.

| quantity | IS (train) | HOLDOUT (eval) |
|---|---:|---:|
| kept post-t0 episodes | 1,281,034 | 320,809 |
| excluded same-bar resolutions | 194,563 | 47,995 |
| SWEEP_CONFIRMED | 86,162 | 20,323 |
| ACCEPTED_BREAKOUT | 1,194,872 | 300,486 |

| metric | value |
|---|---:|
| IS AUC uplift (committed) | 0.347 |
| holdout AUC(B-only) | 0.5734 |
| holdout AUC(B+ICT) | 0.9134 |
| **holdout AUC uplift** | **0.3400** |
| holdout uplift 95% CI (weekly block bootstrap, supplementary) | [0.3273, 0.3521] |
| §6 bar (≥0.01, same sign) | MET |

### F2a′ FINAL VERDICT: **CERTIFIED-CONDITIONAL**

The out-of-sample holdout AUC uplift (0.3400) clears the §6 bar (≥0.01, same positive sign as the IS uplift), confirming genuine ex-ante conditional structure in acceptance-vs-rejection once the same-bar tautological episodes are excluded. Per §7, **F2a′ is CERTIFIED-CONDITIONAL** and joins F1a as a Phase-4 building block (acceptance-gate / Alpha-Asset-#2 candidate), to be built only under its own Phase-4/5 prereg — including the deferred level-kind attribution check, which is Phase-4 work, not a §6 gate. This is the honest answer to the book's Chapter-20 question for this event stream: whether a level excursion is accepted or rejected is partly predictable BEFORE it resolves — carried chiefly by the initial thrust depth at t0, not by the discredited same-bar close-location tautology.

**Phase-3 certified-conditional set is now: F1a, F2a′.** F2a's original (unrestricted) cell remains superseded by F2a′ per Amendment v1.2. Amendment v1.2 paper trail closed (prereg hash `bc35ceddcb10`, IS base `fb798d7`). This was the final measurement of Phase 3.

*F2a′ holdout runtime: 36.72 s. Holdout opened once, F2a′ columns only.*
