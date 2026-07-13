# A — Volatility Compression → Expansion Breakout (NQ) — HONEST edge discovery

**VERDICT: NO-EDGE.**
The compression→expansion thesis is *falsified* on real Databento NQ: the more you actually
compress the coil, the *worse* the breakout does. The only mildly-positive configs are the ones
that *neutralise* the compression filter — i.e. a generic, weaker cousin of the already-known NQ
momentum trend-runner tail. No new deployable edge.

Date: 2026-07-13 · Family owner run · Nothing armed · REAL DATABENTO ONLY.

---

## Data & harness (honesty controls)
- **Source: REAL DATABENTO NQ futures only.** RTH 5m built by resampling the RTH 1m parquet
  (`tools_vpc_1m_truth.load_1m_rth`) so the signal grid and any 1m fill-truth escalation share one
  byte-identical source. **No yfinance / CFD / TradingView** (the ES-ORB fake-edge vector).
  88,407 5m RTH bars, 1,152 days, 2022-01-03 → 2026-06-22.
- **Cost:** `nq_vwap_pullback.RT_COST` = 0.75 pt round-trip, baked into every trade; plus cost **x2/x3** stress.
- **Entry realism:** breakout via **STOP order** filled at the trigger price (buy-stop above coil high /
  sell-stop below coil low), BOTH sides. No resting limit (avoids the Profile-A stale-limit mirage).
- **Intrabar:** conservative **adverse-first** (stop checked before target on the same 5m bar). EOD flat.
- **No look-ahead:** closed-bar decisions; continuous causal ATR(14); **+1-bar look-ahead canary** run on
  every finalist (edge must not jump — it did not; it *fell*).
- **IS/OOS:** fit view = 2022–2024, HELD-OUT = 2025–2026. Both reported.
- **Anti-data-mining:** FIXED grid of **240 configs** enumerated up front; **every** config's IS & OOS
  written to `research/edge_discovery/vce_grid_results.csv`. No silent winner-picking. 240 = the
  multiple-testing count.

## Parameter grid (240 configs, full results in CSV)
- **Compression detectors (2 families):**
  (1) *ratio* — coil_range over W bars ≤ `c`·ATR, `c ∈ {1.0, 1.5, 2.0}`;
  (2) *ATR-percentile* — ATR in bottom `p` of trailing 100 bars, `p ∈ {0.20, 0.30}`.
- Coil window `W ∈ {4, 6, 12}` · trigger `∈ {1, 4}` ticks beyond coil · expansion window `E ∈ {4, 8}` bars.
- Exit: fixed-R target `{1.5R, 2.0R}` (R = entry→opposite-coil-edge) **or** ATR-trail `{2.0, 3.0}`.
- Survivor bar (must pass ALL): n≥50, **IS PF≥1.10 AND OOS PF≥1.10**, no year deeply negative, survives cost x2.

## Result: **0 survivors.** Configs with IS PF≥1.10 **and** OOS PF≥1.10: **0 / 240.**
- Grid PF distribution: median 0.974; only 37% of configs beat PF 1.0; only 10% beat 1.10 (in-sample).
- The high-OOS-PF configs (up to OOS 1.9) all **LOSE in-sample** (IS PF ~0.75, n~90) — a wrong-direction
  OOS fluke you could never have selected. Discarded.

## The decisive test — does compression actually help?
Same breakout+ATR-trail engine (W=4, trig=1, E=8, trail 3.0ATR), varying only coil tightness `c`:

| c (lower = tighter coil = MORE compression) | n | full PF | IS PF | **OOS PF** |
|---|---|---|---|---|
| 0.75 (tightest genuine coil) | 84 | 0.653 | 1.019 | **0.417** |
| 1.0 | 838 | 0.918 | 1.221 | **0.616** |
| 1.5 | 2726 | 1.025 | 1.161 | **0.841** |
| 2.0 ("winner") | 2891 | 1.140 | 1.187 | **1.068** |
| 3.0 | 2989 | 1.051 | 1.059 | **1.037** |
| **10.0 (NO compression filter at all)** | 3013 | 1.056 | 1.056 | **1.055** |

**Reading:** tighter genuine compression → monotonically **worse** (OOS 0.42 at the tightest). The
c=2.0 "sweet spot" (OOS 1.068) is statistically indistinguishable from taking **every** breakout with
**no** compression filter (c=10 → OOS 1.055) — a **0.013 OOS-PF bump data-mined from 240 configs.**
The compression detector contributes **negative** value; the residual ~1.05 PF is just NQ's generic
intraday breakout/trend-runner tail (already captured, better, by the deployed momentum edge at PF ~1.45).

## Genuine-compression cohort (tight coils only: ratio c≤1.0, or pctile p≤0.20 & W≥6) — 80 configs
- full-sample PF: median **0.957**, frac>1.0 = 0.31 · IS PF median 1.004 · **OOS PF median 0.885**
- configs with BOTH IS>1.05 AND OOS>1.05: **0.** Real coils have no NQ edge.

## Best-looking candidate, fully gauntleted (idx 103, ratio c=2.0/W=4/E=8/trail 3.0ATR)
n=2891 (12.4 tr/wk), WR 39.1%. cost x1 PF 1.140 / x2 1.111 / x3 1.082 (survives). IS 1.187 / OOS 1.068
(x2 OOS 1.045). Per-year all >1.0 (2022 1.17, 2023 1.13, 2024 1.25, **2025 1.02**, 2026 1.16). +1-bar
canary 1.140→1.066 (no jump). **Why it still dies:** it is not a compression edge — its coil gate is
inert (c=2.0 over 4 bars passes ~everything; identical to no filter), so it is a weaker, unfiltered
re-run of the existing momentum tail. OOS is marginal (1.07, 2025 barely 1.02) and 5m same-bar fills
are *optimistic* — 1m adverse-first truth can only lower it, so no escalation can rescue it.

## Single reason it lives or dies
**DIES:** genuine volatility compression on NQ does not predict a tradeable expansion — tightening the
coil monotonically destroys the edge (OOS 0.42 at the tightest coil). The lone positive residual is an
inert-filter artifact re-exposing the already-owned momentum tail at a weaker, cost-fragile OOS PF ~1.05.

## Files
- Engine: `research/edge_discovery/vce_engine.py`
- Sweep: `research/edge_discovery/vce_sweep.py` → `research/edge_discovery/vce_grid_results.csv` (all 240)
- Gauntlet: `research/edge_discovery/vce_gauntlet.py`
