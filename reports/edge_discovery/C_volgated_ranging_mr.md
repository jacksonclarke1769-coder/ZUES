# C — Volatility-Gated Ranging Mean-Reversion (NQ) — EDGE DISCOVERY

**VERDICT: NO-EDGE.** A causal volatility/regime gate does **not** rescue VWAP-band
mean-reversion above PF 1.0 after honest costs. Every config tested is a net loser.

Date: 2026-07-13 · Data: REAL Databento NQ futures, 5m 24h + 1m RTH, 2022-01-03 → 2026-06-22
(1,152 RTH days). Nothing armed. Harness: `research/edge_discovery/c_volgated_mr.py`
(+ `c_fillcheck.py`). Full grid: `research/edge_discovery/c_search_full.csv`.

## Hypothesis
Fade extension beyond VWAP ± k·ATR back toward VWAP, but ONLY on detected low-vol/ranging
days (ATLAS meta-law: reversion structure should live in low-vol), standing down on
trend/high-vol days where MR bleeds. Core test: **gate ON vs OFF**.

## Mechanics (honest)
- RTH only (09:30–16:00 ET). Causal session VWAP, ATR14 (5m), Wilder ADX14.
- Signal at CLOSE of bar i (causal): Close beyond VWAP ± band_k·ATR → fade.
- **Primary entry = MARKET at next-bar open** (no limit-fill optimism).
- Exit intrabar on 5m, **adverse-first** (stop checked before target same bar); EOD flat.
- Target = VWAP(entry) or halfway; stop beyond the extreme. **Cost 0.75pt RT** every trade.
- Gates (all causal, prior-day stats only): ADX<20, daily-ATR-percentile<0.40,
  VWAP-cross-count≥3, opening-range/ATR<6. Thresholds fixed a priori (NOT mined).

## Full search — anti-data-mining
**90 configs reported, no winner-picking** (3 band_k × 3 stop_atr × 2 target × 5 gates).
`frac_pf_gt1 = 0.000` for EVERY gate — **not one of the 90 configs clears PF 1.0 on the
full sample.** Best full-sample PF = 0.960.

### Gate ON vs OFF (median PF across the 18 geometry configs)
| gate | med PF (full) | med PF IS | med PF OOS | med N | % configs PF>1 |
|------|------|------|------|------|------|
| off | 0.880 | 0.885 | 0.877 | 2127 | 0% |
| adx | 0.861 | 0.828 | 0.896 | 1208 | 0% |
| **atrpct** (low-vol day) | **0.913** | 0.890 | 0.932 | 875 | 0% |
| orange | 0.879 | 0.881 | 0.877 | 2109 | 0% |
| vcross | 0.889 | 0.884 | 0.868 | 1559 | 0% |

The low-vol-day gate (`atrpct`) helps the MOST — lifts median PF 0.880→0.913 and cuts
loss magnitude by ~60% — **directionally consistent** with the ATLAS meta-law (reversion
is less-bad on quiet days). But it is nowhere near enough: still a structural loser. The
ADX gate actively HURTS. The prior holds: **naive band-fade WR is high (up to 64% on the
half-target) but PF<1 — negative skew, not profit — and no gate flips the sign.**

## Survivors: gauntlet
**0 configs** pass (full + IS + OOS PF>1.0, N≥50). A few gated configs post OOS PF slightly
>1.0 (e.g. atrpct half 2.5/1.0: OOS PF 1.077, +349pt) but their **IS PF is 0.858** → fail IS;
this is small-window (2025-26) noise, not an edge. Per-year sign-consistency, cost×2/×3, and
N≥50 checks are moot with no survivor — and since every config is PF<1 at base 0.75pt cost,
**higher costs only push PF further below 1.0.**

## FILL-REALISM verdict (highest artifact risk for this limit family)
The primary uses market entry (no optimism). A fade is naturally a resting LIMIT at the band,
which fills at a *better* price — the classic artifact. Tested honestly on REAL 1m bars
(price must trade THROUGH the limit; stop/target walked adverse-first on 1m):

| config | fill rate | non-fill risk | honest PF | IS / OOS PF |
|--------|-----------|---------------|-----------|-------------|
| atrpct 2.0/1.5 vwap | 66.1% | 33.9% | **0.760** | 0.714 / 0.846 |
| atrpct 2.5/2.0 vwap | 46.5% | **53.5%** | **0.761** | 0.755 / 0.770 |
| off 2.0/1.5 vwap | 62.9% | 37.1% | **0.721** | 0.707 / 0.742 |

Honest 1m limit fills are **WORSE** than the 5m market version (PF 0.72–0.76 vs 0.86–0.93),
and **34–54% of signals never fill.** The "better entry" is an illusion: the limit fills via
adverse selection (price continues against you) and finer 1m resolution catches stops the 5m
bar smoothed over. The limit route offers **no rescue** and is exactly the artifact trap the
operator was warned about — running the wrong way.

## Conclusion
Volatility-gated ranging mean-reversion on NQ is **NO-EDGE**. The vol/regime gate improves
MR (best on low-vol-day filtering, as theory predicts) but cannot lift it above breakeven
after honest costs — IS or OOS, market or limit entry, at any of the 90 geometries. Clean,
honest confirmation of the team's prior. Do not deploy; do not iterate this family.
