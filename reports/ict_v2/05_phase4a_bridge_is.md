# ICT V2 Phase 4 — Stage 4A Bridge Cells (IS)

**Governs:** `research/ict_v2/PREREG_PHASE4.md` v1.0, git hash `ff1d59980743` (chain: PREREG_PHASE3 cd652ea→bc35ceddcb10, Phase-3 verdict dd3b685). **Scope:** Stage 4A IS bridge test on the existing `sweep_confirmed_is.parquet` (nothing re-extracted). Two cells only. `sweep_confirmed_holdout` NOT opened. No PF/WR reported (§Bans). No new features/sessions/thresholds.

## 0. The bridge question & reversal-sign mapping

Phase-3 F2a′ certified that t0 depth predicts WHETHER an excursion resolves sweep-vs-acceptance — resolved before a sweep strategy enters. Stage 4A tests the NEW claim: does depth / level-class predict the POST-confirmation PATH of a confirmed sweep? **Reversal-sign mapping** (verified 1:1 in-data): side=`buy` (buy-side liquidity above a high-type level, closed back inside) → reversal = **down** → `fwd24_reversal = −Δclose/ATR20`; side=`sell` (sell-side liquidity below a low-type level) → reversal = **up** → `fwd24_reversal = +Δclose/ATR20`. This is exactly WP-E's `direction` column (buy→down, sell→up); the extracted `fwd_24`/`maxcont_24`/`maxrev_24` are already reversal-signed, so no re-derivation was needed. Primary outcome = `fwd24_reversal`; `maxcont24_reversal` / `maxrev24` reported as secondary context.

## 1. Self-test (planted passes / null fails)

- Planted mag contrast survives all gates: **True** (Δ=0.299).
- Null placebo fails G1: **True** (Δ=-0.006).
- Self-test verdict: **PASSED** (IS run permitted only on PASS).

## 2. Results (contrast Δ = mean(A) − mean(B); weekly block bootstrap 2,000; floor 0.10 ATR)

| cell | outcome | groups (A vs B) | Δ | 95% CI | floor✓ | G1 | G2 ret | G2 | per-yr signs | G3 | p | q(BH) | G4 | verdict |
|---|---|---|---:|---|:---:|:---:|---:|:---:|---|:---:|---:|---:|:---:|:---:|
| P4-B1 | fwd24_reversal (PRIMARY) | depth_bottom_tercile vs depth_top_tercile | -0.056 | [-0.115, 0.001] | ✗ | False | 1.13 | True | −+−− | True | 0.0570 | 0.1140 | False | dies |
| P4-B1 | maxcont24_reversal | depth_bottom_tercile vs depth_top_tercile | -0.430 | [-0.477, -0.385] | ✓ | True | 0.26 | False | −−−− | True | 0.0000 | — | — | (secondary) |
| P4-B1 | maxrev24 | depth_bottom_tercile vs depth_top_tercile | -0.339 | [-0.379, -0.297] | ✓ | True | 0.07 | False | −−−− | True | 0.0000 | — | — | (secondary) |
| P4-B2 | fwd24_reversal (PRIMARY) | weekly vs intraday | -0.076 | [-0.347, 0.202] | ✗ | False | 1.14 | True | −−−+ | False | 0.6020 | 0.6020 | False | dies |
| P4-B2 | maxcont24_reversal | weekly vs intraday | -0.306 | [-0.505, -0.092] | ✓ | True | -0.13 | False | −−−− | True | 0.0040 | — | — | (secondary) |
| P4-B2 | maxrev24 | weekly vs intraday | -0.338 | [-0.520, -0.146] | ✓ | True | -0.08 | False | −−−− | True | 0.0010 | — | — | (secondary) |

BH q=0.10 is applied within the 2-cell family over the two cells' PRIMARY-outcome (`fwd24_reversal`) p-values; the secondary outcomes are descriptive and do not enter the FDR set or decide survival.

## 3. Verdict (per cell, on the primary outcome)

- **P4-B1** (depth bottom-vs-top tercile): **dies** — G1 fails (|Δ|=0.056 vs 0.10 floor / CI -0.115,0.001).
- **P4-B2** (weekly-vs-intraday class): **dies** — G1 fails (|Δ|=0.076 vs 0.10 floor / CI -0.347,0.202).

**Stage 4A-IS survivors: NONE.**

Per §Verdict rules, **zero 4A survivors → the Phase-4 translation FAILS**: F1a/F2a′ remain event-level knowledge (depth predicts sweep-vs-acceptance AT resolution) but do NOT predict the post-confirmation reversal path, so no acceptance-gate is licensed; the thesis routes to order-flow (Court D1). No holdout contact; no Stage 4B.

*Runtime: 5.73 s. sweep_confirmed_is only; holdout sealed.*
