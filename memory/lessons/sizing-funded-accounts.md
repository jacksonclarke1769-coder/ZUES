# Lesson: Funded-Account Sizing & Survival Mechanics

**Profile A (OTE+NY-AM+2R) on CME NQ micros | Session 2026-06-04 sims**

## TL;DR

Per-trade risk **≤25–30% of trailing-DD buffer** is the survival threshold. Below 15% = bulletproof. Above 30% = the edge collapses to a coin flip before it can compound. Profile A at recent ~67pt stops = 1 MNQ ($133 risk) is 6.7% of the Topstep $2k buffer; 2–3 MNQ = 13–20% (optimal); 4+ MNQ = blowup probability >30%.

## Why This Matters

The backtest shows PF 1.42 (1043 trades), but that expectancy only *manifests* if you size small enough to survive a streak of 3–5 losses without breaching the trailing-drawdown limit. A single oversized trade (67pt stop, 5+ MNQ = 50%+ buffer) can resolve the account *before* the edge fires 10 times. The edge is real; the account blow-up is a sizing problem, not a strategy problem.

## Empirical Findings

### Stop Sizes (Profile A Recent)
- Lifetime average: ~41 points
- Recent (NQ ~29k): ~67–69 points
- Reason: stops sit below swept lows; wider structure at higher price levels

### MNQ Risk Per Trade
- 1 MNQ: $133/trade (6.7% of $2k buffer)
- 2 MNQ: $267/trade (13.3%)
- 3 MNQ: $400/trade (20%)
- 4 MNQ: $534/trade (26.7%)
- 5 MNQ: $667/trade (33.3%)

### Funded-Account Blow Rates (First Payout)
- 1 MNQ: <5% (too slow)
- 2 MNQ: ~11% (safe, slow)
- 3 MNQ: ~18% (balanced)
- 4 MNQ: ~37% (aggressive)
- 5 MNQ: ~44% (high risk)

### Full NQ is Unviable on 50K
At 67pt stops, 1 full NQ = $1,383 risk (69% of buffer) → account resolves in 1–2 trades → 42% coin flip instead of 1.42 PF edge. Full NQ needs 150K+ ($4.5k DD buffer) for 1 contract to work; 250K for 2 contracts.

## Best Funded-Account Schemes

**Scheme C** (recommended for first payout survival):
- Trade 3 MNQ until first payout
- Scale to 2 MNQ post-payout
- Result: 18% blow, 84% payout probability, good EV

**Scheme E** (high-EV alternative):
- Trade 3 MNQ
- De-risk to 1 MNQ after 3 consecutive losses
- Result: 18% blow, ~$3,400/yr EV, keeps 3-MNQ upside without catastrophic tail risk

**Avoid**: Scheme D (scale UP after payout) = 24% blow, worst survival.

## The Reset Economics Paradox

For funded challenges WITH resets (Topstep Combine):
- 5 MNQ: ~2.3 months, ~$189 cost, 95% within 180d
- 1 MNQ: ~14 months, ~$715 cost (subscription drag), only 8% within 180d

**Fast failures beat slow grinds** because the monthly subscription ($49) dominates. But once you're *funded*, you have no resets — so asymmetric sizing makes sense:
- **Evaluation**: 4–5 MNQ (aggressive, resets are cheap)
- **Funded**: 2–3 MNQ (conservative, blow costs full Combine redo)

## First Payout is the Real Wall

- Median time: 5.5–6 months (vs Combine pass 2–3 months)
- Pre-payout blow rate: ~37–40%
- Only ~50% funded accounts reach first payout within 180 days
- First payout capped: ~$2,500; net EV after account costs ~+$2,150

The Combine pass is easy; the payout is the bottleneck.

## Trade Frequency Effect

Profile A fires ~141 trades/year (~12/month, 1 every 1.8 days), almost always 1 per day. Daily-loss limits rarely bind. This low frequency means:
- No need for micro-intra-day risk management
- Seasonal / weekend risk is minimal
- Each loss is independent (no streak amplification)
- Sizing formula holds: per-trade risk cap = function of account size + expected DD, not frequency

---

**Operative constraint**: Do not exceed 30% of trailing buffer per trade, ever. It breaks the edge.
