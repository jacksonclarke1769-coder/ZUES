# KILL-20260709 — SMC3 / Profile-D Research Record (line CLOSED)

**Verdict: KILL, 6 independent passes converge.** Research-only; never armed; LIVE HOLD stayed ACTIVE throughout.
**Record:** `research/smc3-profileD/` (faithful engine + all scripts + reports/ifvg_optimisation/).

Strategy: 60m confirmed-pivot liquidity sweep+reclaim → 5m BOS/FVG confirm → 1m trigger → 2R (user Pine, mirrored no-lookahead, 0 artifacts across every pass).

The six verdicts:
1. **Baseline** — n5056, WR 34.4%, avgR −0.010; net +$79k is a fixed-contract sizing mirage (measure in R).
2. **Param/context (26 cells, 10 features)** — WR pinned 32-38% everywhere; NY-AM "edge" = pure 2024 carry (ex-2024 −0.008); Friday = calendar coincidence.
3. **IFVG close-through probe** — no speed gradient (≤4 ≈ ≥5 ≈ dead core); BOS/FVG/IFVG-inversion all identical → confirmation flavor irrelevant.
4. **Day-sequence (34 rules)** — repeat-entry hypothesis REFUTED (no signal-order decay; 2-trade days best bucket); direction-lock chop diagnostic later failed full-book replication (retracted).
5. **DOL exit audit (34 exit models, strict target provenance)** — **touch-ladder proves entry edgeless at EVERY horizon** (P(+0.5/1/1.5/2/3R) = 66.9/50.4/41.0/34.3/25.3% ≈ breakeven at each rung, flat all 6 yrs). One nuance: dol_htf_pocket_only +0.084R/PF 1.103, robust to stress but <1.20 gate, maxDD 125R, prop-hostile.
6. **Daily-bias (32 rules)** — no rule lifts P(+2R) off the 34.3% rung; all improvements = shorts-only trend-alignment composition; best clean finding (30m-low-swept-failed→long, 6/6 yrs) tops at PF 1.089.

Sessions: best NY-AM 09:30-12 (+0.037 raw) / worst London (−0.042) & pre-market 08:00-09:30 (−0.117) — but NO session survives ex-2024.

**Surviving reusable insights:** (1) "target the opposite HTF pocket" beats fixed-R on sweep setups → test as exit variant on sweep→OTE; (2) 30m-failed-sweep long-bias as a candidate feature for future real-entry models.
**Benchmark context:** never beat live-achievable Profile A (PF 1.037/+7.4R).
