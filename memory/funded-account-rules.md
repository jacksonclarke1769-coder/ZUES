# Funded Account Rules — Topstep / FTMO (Profile A)

## Survival & Sizing Mechanics

### Per-Trade Risk Cap (Most Critical)
- **Optimal zone**: 20–25% of trailing-drawdown buffer
- **Safe zone**: <15% (bulletproof; edge can compound)
- **Danger zone**: >30% (PF-1.4 edge collapses to ~40% coin flip; single trade resolves account before edge compounds)
- Profile A at ~67pt stops: 1 MNQ = $133 risk; 2–3 MNQ = 13–20% buffer (optimal); 4+ MNQ = 27%+ (risky); 5+ MNQ = blow probability +40%

### Full Contracts vs Micros
- **Full NQ ($20/pt)** is unviable on 50K: at ~67pt stops, 1 full = $1,383 risk (69% of $2k buffer) → 42% coin flip → blowup
  - Full NQ only works at 1 contract on 150K+ ($4,500 DD buffer) or 250K+ ($6,500 DD buffer)
- **MNQ (micros, $2/pt)** mandatory: 1 full NQ = 10 MNQ in dollars; micros permit granular sizing in the 20–25% optimal zone

### Asymmetric Sizing Meta-Strategy
- **Evaluation phase** (Combine): size aggressively (4–5 MNQ) — resets ~$49 each, cheap fails
- **Funded account**: size conservatively (2–3 MNQ) — blowing costs full Combine redo (~$500–800)

## Funded-Account Blow Rates & Scaling Options

### Baseline Blow Rate (First Payout, Before Scaling)
- 2 MNQ: ~11% blow (most conservative; slowest payout)
- 3 MNQ: ~18% blow (balanced)
- 4 MNQ: ~37% blow (aggressive; faster payout but risky)
- 5 MNQ: ~44% blow (most aggressive; fastest but highest churn)

### Best Scaling Schemes (Post-Funding)
- **Scheme C** (recommended): Trade 3 MNQ until first payout, then scale to 2 MNQ = 18% blow, 84% payout probability
- **Scheme E** (alternative): Trade 3 MNQ, de-risk to 1 MNQ after 3 consecutive losses = 18% blow, highest EV (~$3,400/yr)
- **Scheme D** (avoid): Scale UP after payout = 24% blow (worst for survival)

## Challenge Economics & Reset Campaigns

### Fast Funding (With Resets Allowed)
- **5 MNQ**: ~2.3 months to fund, ~$189 total cost, 95% funded within 180d
- **4 MNQ**: ~2.5 months, ~$98 cost, 88% within 180d
- **Rationale**: subscription drag ($49/month) > reset cost; faster failures beat slow grinds (1 MNQ → ~14 months, only 8% within 180d)

### Single Fixed-Window Pass (No Resets)
- **2 MNQ**: optimal (87% within 5-month window)
- **3 MNQ**: 75% within 5-month window

## First Payout = The Real Wall

- **Median time to first payout**: 5.5–6 months (vs Combine pass ~2–3 months)
- **Blow rate before payout**: ~37–40% (each blow = redo Combine + funded account)
- **Only ~50% funded within 180d** (calendar constraint + high payout churn)
- **First payout capped**: ~$2,500; net EV ~+$2,150 (after account costs, resets)
- **4 MNQ slightly safer churn** (37% blow) **than 5 MNQ** (44% blow)

## Profile A Trade Frequency & Constraints

- **Annual**: ~141 trades (~12/month, ~1 every 1.8 trading days)
- **NY-AM session**: fires on ~49% of NY-AM days; almost always 1 trade/day (max 2–3)
- **Daily-loss limits rarely bind** (low frequency)
- **Drawdown window**: recent 6-month (2025-11 to 2026-05, favorable) saw 2/3/4 MNQ at 2/4/5 funded accounts (0/2/2 breaches)

## Recent Empirical Snapshot (2025-11 to 2026-05)

- **Combine pass rates**: 2 MNQ (100% flawless), 3 MNQ (67%, 2 breaches), 4 MNQ (80%, 2 breaches)
- **Sample size**: small, favorable realized conditions, not steady-state
- **Implication**: real forward testing required before scaling up; 2–3 MNQ recommended for first funded account

---
**Operative constraint**: Per-trade risk ≤25–30% of buffer is non-negotiable for the edge to express. Below 15% = safe but slow. Above 30% = coin flip, catastrophic.
