# Tested Strategies Registry

| Name | Version | Instrument | Window | Trades | Win% | Expectancy (R) | Max DD | Verdict | Report / Notes |
|---|---|---|---|---|---|---|---|---|---|
| Profile A (OTE+NY-AM+2R) | 1.0 (CME validation) | NQ=F (micros) | 2019+ (1043) + 60d CME overlap (22) | 1043 + 22 | 48% | 1.42 (full) / 1.23 (CME 22t) | ~18% | SHIP | CME revalidation passed; edge NOT CFD artifact. Realistic costs ($5 RT + 3tk slippage) = PF 1.39. Stress test (4tk + $6 RT) = PF 1.32 > 1.2 gate. Ready for funded micro forward test. |

---
**Notes**:
- Profile A: OTE entry (Order Template Entry), NY-AM session, fixed 2R stop.
- CME revalidation (Jun 2026): fires on 22 identical setups (vs 23 CFD), PF 1.23, matches historical edge.
- Realistic-cost PF 1.39 = deployment-ready.
- Next: 30-60d live micro forward test on Topstep.
