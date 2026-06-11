# Instrument: NQ (Nasdaq-100 Futures, CME)

## Profile A Validation (CME Revalidation, Jun 2026)

### Edge Confirmation
- **60-day overlap test**: 22 identical OTE+NY-AM+2R setups fired on both CFD and CME futures
- **PF comparison**: CFD 1.23 ≈ CME 1.23 (same sample)
- **Verdict**: Edge is NOT a CFD artifact; translates directly to real futures

### Realistic Cost Impact (NQ=F, MNQ micros)
- **Base realistic** ($5 RT commission + 3-tick slippage): PF 1.39 (1043 trades)
- **Stress test** (4-tick + $6 RT): PF 1.32 (still >1.2 gate)
- **Implication**: Deployment-ready; modest slippage tolerance

## Stop & Price Level Mechanics

### Stop Sizes (Profile A)
- **Lifetime average**: ~41 points
- **Recent (NQ ~29k)**: ~67–69 points
- **Reason**: Stops sit below swept lows; wider structure at higher price levels (price inflation)

### NQ Price Scalability
- **Below 25k**: stops tighter (~41–50pt), 1–2 MNQ manageable
- **At 29k+**: stops wider (~67–69pt), requires MNQ for granular sizing
- **Implication**: As NQ rallies, per-trade dollar risk (2R) stays roughly constant, but point risk grows → must downsize contracts or use micros

## Session & Trade Frequency

### NY-AM Activity (08:30–13:00 EST)
- Profile A fires on ~49% of NY-AM days
- Almost always 1 trade/day (max 2–3 in rare high-volatility windows)
- ~141 trades/year (~12/month)

### Blackout Windows (Known Constraints)
- **NFP** (first Friday): use realistic sims with news blackout
- **FOMC**: similar consideration
- **Pre-market vol spikes**: not heavily tested yet; forward testing will reveal

## Micro Contract Mapping

| Full NQ | Dollar Risk | MNQ Equivalent | Topstep $2k Buffer % |
|---|---|---|---|
| 1 | $1,383 (67pt) | 6.9 MNQ | 69% |
| 2 | $2,766 | 13.8 MNQ | 138% (unsustainable) |
| — | — | — | — |
| 1 MNQ | $133 (67pt) | baseline | 6.7% |
| 2 MNQ | $267 | 2x | 13.3% |
| 3 MNQ | $400 | 3x | 20% |
| 4 MNQ | $534 | 4x | 26.7% |
| 5 MNQ | $667 | 5x | 33.3% |

**Best range for funded (50K Topstep): 2–3 MNQ (13–20% of buffer).**

## Forward Testing Priorities

1. **Slippage in real market**: confirm 3-tick assumption holds under various NY-AM volatility regimes
2. **Entry fill quality**: OTE mechanics under spike conditions (first 30min of NY session)
3. **Seasonal volatility**: stops wider in Dec/Jan, tighter in summer — adjust sizing?
4. **Recent vol regime (2026)**: current stops ~67pt; if vol drops, can we scale up?

---
**Last validated**: 2026-06-04 (CME revalidation pass)
