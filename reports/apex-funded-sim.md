# Apex Funded-Rules Sim — Profile A under Apex trailing drawdown
**SIM / RESEARCH ONLY · Dukascopy NQ CFD PROXY · numbers VERIFY vs your Apex contract.**
- Trade stream: 585 frozen Profile A NY-AM trades · 2022-05-18 -> 2026-06-26 · 3 MNQ.
- Method: rolling-start Apex evals (an eval started at every signal) through the unrealized trailing-threshold model (`funded_rules.ApexAcct`). Per-trade give-back via model01 mfe_r/mae_r.
- Apex model: threshold trails the unrealized peak by `trailing`, locks at start+$100; no daily limit; 30% consistency for payout.

| Apex size | Trailing | Target | Eval PASS % | BREACH % | give-back share of breaches | median trades→pass |
|---|--:|--:|--:|--:|--:|--:|
| 50K | $2,500 | $3,000 | 90.3% | 6.4% | 89.2% | 41 |
| 100K | $3,000 | $6,000 | 94.4% | 0.0% | 0.0% | 95 |
| 150K | $5,000 | $9,000 | 92.5% | 0.0% | 0.0% | 130 |

**Caveat:** per-trade approximation is slightly optimistic vs the true tick path (an intra-trade dip below the locked floor that recovers to a positive close would breach in reality but not here). At larger Apex contract sizes (10/14/17) breach risk scales up roughly with size. Proxy data — reproduce on CME before trusting. Apex = SEMI-AUTO ONLY (confirm-to-trade), so any live use runs the human-in-the-loop path, never auto-execute.
