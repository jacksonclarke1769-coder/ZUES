# Eval Pass-Rate Expansion Sprint — Executive Summary (2026-07-05)

**SIM CONDITIONAL — pending live fill evidence. No number here is a forecast; nothing here is
promoted. Live machine unchanged: A10 · $1,200 · certified 47.8/15.9/36.2.**

Auditor: Fable (architecture, validity calls, this verdict). Implementation: 5 Sonnet lanes +
1 Haiku scout. Every lane reproduced the certified baseline exactly before any variant ran;
funded firewall verified before/after every lane and at sprint close.

## What was tested

- **WS1:** 48-cell cap×budget matrix (8 caps × 6 budgets); 6 stop-bucket cap policies; 5
  cushion-aware policies; 5 positive-streak policies; 5 near-target policies; 5 recycle rules;
  7 start-timing rules; 6 cadence/slot models.
- **WS2:** 11 Asia/London candidates — 8 already dead in the register (cited, not re-run),
  1 on preregistered watch (L1), 3 genuinely new tested on the 10.4y harness (L6/L10/L11),
  L6's suspicious survivor result adversarially killed at 1m truth.
- **Fill sensitivity:** 4 damage families × 5 sizing cells incl. NEW touch-without-fill
  (neutral + adverse bounds) and a tight-stop-only penalty variant.

## What survived

| Candidate | Type | Funnel (SIM COND) | Fill survival | Label / path |
|---|---|---|---|---|
| **Cap 15 × $1,000** | eval sizing | 55.2 / 13.4 / 31.4 · E$ ~6,894 | survives ALL families; adverse touch-without-fill break-even **16.4%** → kill line tightened to **15%** | **SIM CONDITIONAL** — unchanged promotion path: telemetry N≥30 (~late Oct) + re-cert + DEC |
| **R1 recycle** (stop attempt after 3 consecutive losses) | operator policy | pass −0.2pp; **slot-year EV +~7%** (throughput) | n/a (no size change) | RESEARCH ONLY → adoptable by DEC as *operator behavior*, zero code |
| **Skip holiday-shortened weeks** (start timing) | operator policy | +2.2pp pass, best E$/attempt in 24mo window | n/a | RESEARCH ONLY → adoptable by DEC, zero code |
| Maintain-N slots (N 2-4) | cadence | funded/mo scales ~linearly; **20-acct cap binds in 9-15mo at N≥2** | n/a | RESEARCH ONLY — capital/ops decision, not code |

## What died (labels final)

- **(20/25/30 × $1,100) raw-E$ maxima** ($7.5-7.9k/attempt on paper): **REJECTED** — size-scaled
  slippage break-even k*≈0.0125-0.0163 R/extra-contract, inside plausible damage. Their entire
  edge over A10 sits in the exact fill regime live data is most likely to tax.
- **All stop-bucket cap policies** (B2-B5): REJECTED — none beats flat-15 at same base (−0.2pp).
- **All cushion-aware policies**: REJECTED for pass-rate — C2 converts bust→expiry at *identical*
  pass (47.8=47.8); mechanism confirmed, E$ unmoved. ("Bust and expiry cost the same" re-proven.)
- **All positive-streak policies**: REJECTED — S1's +2.8pp is base-fragile (reverses at cap-15
  base) and single-year-concentrated. Streak overfit.
- **All near-target policies**: REJECTED — ±0.3pp noise.
- **Signal-triggered eval starts**: REJECTED — null result (signals too sparse to beat
  weekday anchoring; median 1 day to first trade either way).
- **Asia/London L2,L3,L4,L5,L7,L8,L9**: DEAD — NEVER QUOTE (register citations, not re-run).
  **L10, L11**: REJECTED (PF 0.90-0.91 best cells, cost-fragile, 2/6 years).
  **L6**: **DEAD — KILLED** (5m PF 2.01 → 1m-truth 0.29-0.39, negative every year; granularity
  artifact — a ~6pt stop/target race arbitrated by 5m candles; 38% of trades sub-5pt stops).
  **L1**: WATCHED (existing preregistered quarterly gate; untouched).

## The 11 auditor answers

1. **Beat A10 on pass, bust, expiry AND E$?** In-sim, only (15,$1,000) — and it remains SIM
   CONDITIONAL; no candidate earns those axes under *proven* fills yet.
2. **Improved pass but worsened business EV?** Yes — the 20-30×$1,100 cells (fill-fragility) and
   S1 streak sizing (bust +2.1pp, robustness fail).
3. **Reduced expiry without unacceptable bust?** The cap raises reduce expiry as their main
   mechanism; only cap-15 does it inside fill-survivable territory.
4. **Survived realistic fill damage?** (15,$1,000) only, of the sizing cells.
5. **Depended on perfect fills?** (20/25/30 × $1,100) — yes, effectively.
6. **Asia/London added meaningful independent frequency?** No. 11/11 dead or watched.
7. **Combined funnel improved?** No survivor existed to combine.
8. **Anything look too good?** L6 (PF 2.01) — adversarially killed exactly per the preregistered
   prediction. The workspace prior ("PF>1.8 = bug") is now 7-for-7.
9. **Lookahead canaries clean?** All five funnel lanes reproduced 47.8/15.9/36.2 exactly;
   WS2 used next-bar-open causality; L6's failure was granularity, not causality.
10. **Funded config untouched?** Verified before/after every lane + sprint-close hash match.
11. **Promote anything live now?** **No.** Cap-15 stays SIM CONDITIONAL behind telemetry N≥30 +
    re-cert + Jackson's DEC. R1 recycle + holiday-week start rules are zero-code operator
    policies that may be adopted by DEC without touching the machine.

## What live telemetry must prove before any promotion

Entry slippage ≥ −0.05R avg · size-scaled slippage < 0.02R/extra-contract · winners' fill ≥50% ·
**adverse touch-without-fill < 15%** (tightened from 20% by this sprint) · tight-stop bucket live
WR not materially below certified.

## Sprint outcome class

**"Still useful" bordering "acceptable":** A10 re-confirmed as the correct live baseline; the
candidate path is unchanged and now carries a sharper kill line; two zero-code operator policies
(R1, holiday-week starts) are ready for DEC; the Asia/London program is closed with clean evidence
(3 new candidates tested honestly, all dead — the register grows by three tombstones). A failed
idea with clean evidence is a win.
