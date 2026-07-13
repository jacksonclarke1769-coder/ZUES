# B2 — Adversarial Verification of the Overnight-Compressed ORB Edge

**TOP-LINE VERDICT: INCONCLUSIVE-THIN → CORRELATED-REDUNDANT. NOT a deployable new uncorrelated edge.**
It is *not* a fill/lookahead fraud (unlike Profile A or ES-ORB) — it reproduces to the digit and is
causally clean. It dies on two other grounds: (a) the profitable part is the **momentum trend-flow we
already own** (0.60 conditional daily-P&L corr, 85% same-direction where they co-fire), and (b) the OOS
is **statistically indistinguishable from breakeven** and carried by a single quarter. The 0.8 gate is
IS-optimized. Do not size it; it does not solve the pass-rate problem (which needs UNCORRELATED flow).

---

## Front 1 — Independent reproduction: PASS (exact)
Re-ran `gauntlet.py` on the real Databento parquet. Every number matches the claim exactly:
IS PF **1.556 (n199)** / OOS **1.188 (n90)** / full **1.393** / WR **.481**; cost ×1/×2/×3 =
1.393/1.368/1.344; +1-bar canary 1.393→1.339. Control reproduces: ungated OOS **1.068**, expanded
OOS **0.896**, compressed OOS **1.188**. No reporting artifact. The claim's arithmetic is honest.

## Front 2 — DECISIVE: new edge, or a slice of momentum/VPC we own?
Built momentum daily P&L via `H.m_events` on the **same Databento data**, unit size, plus VPC daily
(`nq_vwap_pullback`). Correlated against the 324-day ORB stream:

| pair | full-union 0-filled r | r where BOTH trade | same-direction |
|---|---|---|---|
| ORB vs **Momentum** | **0.121** (n728) | **0.596** (n111) | **85%** same side |
| ORB vs **VPC** | 0.136 (n617) | 0.660 (n108) | — |

Read honestly: momentum is *flat* on 66% of ORB-fire days, so the portfolio-level corr is low (0.12) —
ORB does supply some flow momentum doesn't. **But mechanistically it is the same trend-continuation
phenomenon**: on the 1/3 of days they co-fire, they win/lose together (r≈0.6) and take the **same
direction 85%** of the time. It is a differently-gated cousin of momentum, exactly as Family A's own
note admitted — not an orthogonal edge. The "diversifying" 2/3 is precisely the low-trend residual that
Front 4 shows is not a proven edge.

## Front 3 — Post-hoc gate / threshold sensitivity: FAIL (IS-fit)
OOS PF is **non-monotonic** in the threshold and does **not** peak at 0.8 (peaks at `<1.0`: OOS 1.434).
Disjoint bands expose the mining:

| ON-range band | full PF | OOS PF |
|---|---|---|
| [0.0, 0.6) | 1.137 | 1.527 |
| **[0.6, 0.8)** | **1.561** | **1.034** ← drives the headline IS PF, DEAD OOS |
| [0.8, 1.0) | 1.216 | **1.841** ← best OOS band, EXCLUDED by the <0.8 gate |
| [1.0, 1.2) | 1.051 | 0.837 |
| [1.2, ∞) | 1.146 | 0.896 |

The headline IS 1.556 rests on the [0.6,0.8) band whose OOS is a dead 1.034; the genuinely OOS-strong
regime sits *outside* the chosen gate. The only robust effect is "avoid EXPANDED (>1.0)" — the specific
0.8 "compression" cutoff is an in-sample fit, not a smooth regime law.

## Front 4 — Thin-OOS / significance: FAIL (not distinguishable from 1.0)
Bootstrap of OOS trade P&L (10k resamples, n=90): PF **5%=0.78 / 50%=1.18 / 95%=1.78**;
**P(PF ≤ 1.0) = 25.0%**. A 1-in-4 chance the OOS "edge" is ≤ breakeven — CI comfortably includes 1.0.
Worse, it is **single-quarter-carried**: 2025Q1 = **586 of 772** OOS points (**76%**). Excluding
2025Q1, OOS PF collapses to **1.054** (n=73). 2025Q4 loses (0.90), 2025Q2 breakeven (1.01). This is
one good quarter, not an established out-of-sample edge.

## Front 5 — Fill realism + lookahead: CLEAN
Code review + reproduction confirm: gate uses only pre-09:30 bars, `on_rng_med20 = rolling(20).median().shift(1)`
(causal); OR levels use only 09:30–10:00 (`g.index < end`); entries only 10:00–10:30 (no post-10:00
leakage); entry is a **stop order**, fill = `max(level, bar-open)` (adverse, not a stale resting limit);
exits adverse-first, entry-bar allows only the stop to hit. +1-bar canary reproduces (1.393→1.339,
graceful). No fill or lookahead artifact — this is a genuine, causally-clean simulation.

---

## Why it lives or dies — single biggest reason
It **dies as a diversifier**: the OOS is a one-quarter mirage (76% from 2025Q1; ex-that PF 1.054;
bootstrap P(PF≤1)=25%), and the money it *does* make is the momentum trend-flow already deployed
(0.60 conditional corr, 85% same direction). It clears the fill/lookahead bar that killed the last two
edges, so it is not fraud — but it supplies neither statistically-established edge nor uncorrelated flow.
Research-grade curiosity, not deployable. Would need genuine forward data (not the 2025Q1-laden OOS) and
a gate re-derived as "not-expanded" rather than the IS-fit 0.8 before any capital.

Artifacts: `research/edge_discovery/verify_corr.py`, `verify_gate_boot.py`.
