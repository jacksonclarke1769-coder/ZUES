# INC-20260707 — Re-cert on the Databento-native live-achievable subset — RESULT
**Sim re-certification (measurement only). No strategy change, no arming, no hold lift, no VPC wiring. LIVE HOLD ACTIVE.** Full-history Databento emission replay (708 signals, 2021-06→2026-06, 3.1h) → 506 achievable / 202 suppressed (28.5%), all suppressed "stale-at-surface" (0 poll-recoverable, 0 clustering — the irreducible pattern replicates across all 5 years, vendor-robust). Pipeline canary PASSED (kept load_rows reproduces certified PF 1.3606 / +89.23R / n=583 exactly).

## THE HEADLINE — the freshness gate suppresses ~92% of the edge
Clean partition of the certified D1c-kept stream (n=583, +89.23R):
| set | n | PF | totR (1m-truth) |
|---|---|---|---|
| KEPT full (certified) | 583 | 1.361 | +89.23 |
| **KEPT achievable — what live actually trades** | 394 | **1.037** | **+7.37** |
| KEPT suppressed — what live CANNOT reach | 189 | **2.64** | **+81.86** |
Unfiltered mirrors it: full 705/PF 1.237/+74.7R → achievable 502/**PF 1.004**/**+1.01R**. **The fat winners (PF 2.64) surface >10min late and never emit; the live engine keeps only the near-breakeven remainder.**

## THREE-COLUMN COMPARISON (the operator's board)
| metric | OLD BOARD (INVALIDATED) | NEW HONEST (Databento achievable) | DELTA |
|---|---|---|---|
| Profile A unfiltered PF | 1.237 | **1.004** | −0.233 (→ breakeven) |
| Profile A D1c-kept PF | 1.361 | **1.037** | −0.324 (→ ~breakeven) |
| A unfiltered totR | +74.7R | **+1.01R** | −73.7R (92% of edge gone) |
| A-only cap-6/$900 eval pass | (A+VPC 37.4% portfolio) | **3.4% pass / 8.9% bust / 87.6% expire** | — |
| A-only E[$]/attempt | (portfolio ~$2,861) | **−$60 (LOW-CONFIDENCE)** | NEGATIVE |
| trades/week (achievable) | ~2.24 | 1.94 unfiltered / 1.53 kept | thinner |

Per-year achievable D1c-kept PF: 2021 1.31 · 2022 0.97 · 2023 1.03 · 2024 0.85 · 2025 1.24 · 2026 0.96 — **not a single-window artifact; near-breakeven every year.**

## VERDICT — does the achievable A-only clear the bar? NO.
The honest live-achievable Profile A edge is **near-breakeven (PF ~1.0-1.04)**, and A-only at the arm-able cap-6/$900 config **loses money (−$60/attempt, 3.4% pass, 87.6% expire)**. The certified PF 1.237/1.361 was carried almost entirely (92%) by trades the live engine — with its now-correct freshness gate — **cannot emit**. The A+VPC re-lock candidate (37.4% pass) was computed on the full set live cannot trade; **it is invalid as-stated and must be re-reviewed** on the achievable basis.

## THE REAL LEVER (this is an EMISSION-PATH problem, not necessarily a dead edge)
The edge is not gone — it is UNREACHABLE via the current live emission path. The 189/202 suppressed winners are dropped by an intrinsic ~35min engine surface-lag (model01.run(realtime=True)'s sequential no-overlap scan surfaces a completed setup into tr.tail(3) long after its fill). If that surface-lag can be fixed — i.e. the engine surfaces a fillable setup at/near FILL time instead of after the scan reaches it — live would capture the winners and the edge returns toward 1.36. **That engine-emission fix (frozen-strategy-adjacent, needs its own scoped task + proof of live-fillability) is the real lever between "near-breakeven live" and "viable."** The poll-cadence resolution was already eliminated (0 recoverable); this is the deeper mechanism.

## CAVEATS (ride with every number above)
1. **Still sim.** Faithful engine-replay model of live emission, NOT a live measurement. The N≥30 live-fill parity read still gates everything — AND it is now the decisive test of whether the surface-lag suppression is exactly this severe live.
2. **Vendor basis open.** Databento-certified; live fills = Tradovate. The 241pt Dukascopy/Databento gap proves vendor identity moves price materially — an unresolved arming precondition.
3. **A-only; VPC unwired.** The arm-able system is A-only (near-breakeven per above). A+VPC figures were always aspirational pending the cancel-replace lane + N≥30 — and are now doubly so, since VPC would face the same emission-path question.
4. Fee/funded values LOW-CONFIDENCE/PLACEHOLDER (Apex-terms canary) — not laundered.
