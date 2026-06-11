# Winning Strategies — Ready to Ship

| Name | Version | Promoted | Instrument | Expectancy (R) | Max DD | Report | Funded Status |
|---|---|---|---|---|---|---|---|
| Profile A (OTE+NY-AM+2R) | 1.0 | 2026-06-04 | NQ (CME futures via MNQ micros) | 1.42 (1043t hist) / 1.23 (22t CME) | ~18% | backtests/ict-nq-framework/ | Deployment-ready; pending 30-60d live micro forward test |

---
**Promotion criteria met**:
- Logic score ≥ 7/10 (ICT smart-money, repeatable structural setups)
- Backtest ≥ 30 trades (1043 historical + 22 CME overlap)
- Realistic costs included ($5 RT commission + 3-tick slippage; stress to 4-tick + $6 RT)
- CME revalidation passed: same edge, not CFD artifact
- PF 1.39+ after realistic costs (>1.2 gate)

**Funded-account constraints** (Topstep 50K):
- Trade size: 2–3 MNQ funded (2–3 per trade risk vs 1 for evaluation); scale conservatively
- Stop sizes: ~41pt average, ~67pt recent → $133–$267 risk/MNQ
- Per-trade risk cap: ≤25–30% of trailing-DD buffer ($2,000) = 2–3 MNQ optimal
- Trade frequency: ~141/yr (~1.8 days), ~49% NY-AM days fire
- First-payout blow rate: ~11% (2 MNQ), ~18% (3 MNQ), ~37% (4 MNQ)

**Next action**: Live micro ($50 stakes or similar) for 30–60 days to validate entry mechanics and slippage in real conditions.
