# Profile D (IFVG/SMC) Optimisation — 00 Current State

_Research-only. LIVE HOLD ACTIVE. No arming, no funded-config change, no certification claim._

## Benchmark to beat (the bar)
**Live-achievable Profile A: PF 1.037 · +7.4R · 394 trades.** (Full Profile A PF 2.64/+81.9R is the SUSPICIOUS suppressed subset, invalid until its causal fork resolves — NOT the benchmark.) A promoted Profile D candidate must be **causal, robust, and > live-achievable Profile A** on risk-normalised terms.

## What actually exists right now (honest)
This is the **first** Profile-D optimisation cycle. **No prior IFVG parameter grid has been run** — the "current results" are the faithful SMC3 baseline just built, plus a session cut. The engine is `smc3/smc3_engine.py` (no-lookahead asserted, per-trade check 5056/5056, 0 artifacts).

### Candidate 1 — SMC3 all-session (baseline default)
n 5056 · WR 34.4% · PF($) 1.036 · **totR −52.9 · avgR −0.010** · net +$79,410 · maxDD $61,825 · IS PF 1.065 / OOS PF 0.991 · OOS avgR −0.011 · 2 of 6 yrs losing.
→ **KILL as-is.** PF ≤ 1.10, negative OOS R, net-$ positive is a fixed-1-contract sizing artifact (R is negative). This is a coin-flip.

### Candidate 2 — SMC3 NY-AM only (09:30–12:00 ET)  ← current best lead
n 1624 · WR 35.5% · PF($) 1.119 · **totR +67.7 · avgR +0.042** · net +$117,520 · avgWin/avgLoss $1,919/$942 · median hold 24m.
IS avgR **+0.042** / OOS avgR **+0.041** (remarkably stable). Per-year R: 2021 −0.8 · 2022 −1.0 · 2023 **−27.7** · 2024 **+77.6** · 2025 +22.8 · 2026 −3.3.
→ **RESEARCH candidate, not yet WATCHLIST.** Fails two promotion gates: PF 1.119 < 1.20, and **one-year carry** (2024 alone +77.6R > the whole +67.7R total; other 5 yrs ≈ −10R). BUT the session cut flips the model from risk-negative to risk-positive and the IS/OOS stability is genuine — this is the thread to pull.

## Engine-scope gap (must be stated before optimising)
The current engine implements the SMC3 subset of Profile D:
- ✅ pocket = 60m confirmed swing (pivot 3/3); sweep+reclaim; 5m BOS/FVG confirm (latched); 1m BOS/FVG trigger; stop = Recent-Swing / Sweep-Extreme / Wider; fixed-R target; session/direction/buffer/expiry params.
- ❌ **NOT yet built (needed for the full spec):** IFVG *inversion* logic + close-through-speed filter (§F); alternate pocket sources — PDH/PDL, ONH/ONL, weekly, 1H/4H swings, equal-H/L, confluence (§A); pocket zone-width (§B); manipulation-leg definitions (§D); IFVG-timeframe selection 1–5m (§E); TP1/2/3 ladders, trailing, BE, time-stops, DOL targets (§K); limit/retrace entries w/ penetration fills (§H).

So the families the current engine CAN wide-scan now (Stage 1, no new code): sweep rule/buffer/reclaim, context expiry, 5m/1m confirm type (BOS/FVG/both), stop mode/buffer/max/min, fixed-R target, session, direction, HTF pivot len. The IFVG-inversion + alt-pocket + TP-ladder + limit-entry families require an **engine extension** (Stage 0-D) before they can be honestly tested.

## Top-20 tables
Only 2 configs exist → no meaningful top-20 yet. After filtering for n≥100, trades/wk≥0.75, PF>1.10, positive expectancy, no causality violations: **only Candidate 2 (NY-AM) survives, and only on PF($)/net — it FAILS on one-year-carry and PF<1.20.** No config currently clears the WATCHLIST bar. Stage 1 wide scan (running) will populate real top-20 tables.

## Status
- Cells tested (real grid): SMC3 robustness/classification sweep IN PROGRESS (session, stopMode, rrTarget, maxStop, confirm toggles, direction) — will become `01_wide_scan`.
- Artifact count: 0 (no-lookahead asserted).
- Verdict so far: **no WATCHLIST candidate yet; NY-AM is the research lead; full IFVG families await engine extension.**
