# Multi-Firm Certification + Five-Year Blueprint (2026-07-02)

Research only — production (Rev B) unchanged. Sandbox sims replayed the certified rev-b stream
through each firm's documented 2026 eval rules with size-to-risk budgets fitted per trail.
Non-Apex rule sets carry MEDIUM confidence (assumptions in session log) — written verification
required before any expansion money moves.

## Certified eval pass rates (identical machine, firm wrapper only)

| firm | budget fit | pass | bust | expiry | med days | avg DD |
|---|---|---|---|---|---|---|
| Tradeify-style | $1,000 | 68.1% | 31.9% | 0 | 15 | $833 |
| MFFU Core | $1,000 | 67.3% | 32.7% | 0 | 19 | $921 |
| Topstep | $1,000 | 65.1% | 34.9% | 0 | 19 | $1,043 |
| Apex 4.0 (baseline) | $1,200 | 61.2% | 28.0% | 10.8% | **11** | $1,129 |
| Lucid | $900 | 49.3% | **50.7%** | 0 | 14 | $559 — DISQUALIFIED (bust > pass) |

Funded (18-mo horizon, 0.4x eval budget, 30d sweeps): Apex $11.9k (near its ~$13k lifetime cap —
annuity ENDS); MFFU/Tradeify $13.0k AND CONTINUING (uncapped); Topstep $12.5k (tighter gates).
Monthly income indistinguishable within horizon ($661-723/mo); the fork is Apex's lifetime cap vs
uncapped funded life elsewhere.

## Verdicts
- Apex = best evaluation THROUGHPUT business (fastest, cheapest, 20 slots) — correct home today.
- MFFU = best per-account LIFETIME business + explicit funded-bot permission — first expansion
  candidate at the fixed trigger (third funded Apex account), after written rule verification.
- Rev B is firm-portable everywhere except Lucid once budget respects the trail.
- The 30-day clock (most-feared rule) costs rev-b almost nothing (median pass 11d).

## Five-year blueprint (full text in session log; essentials)
END STATE: 3 firms / ~35-45 funded — Apex eval-factory (20, churning by design), MFFU income
estate (15-20, uncapped), Topstep ballast (5). Steady state ~$28-32k/mo gross; one-edge ceiling
~$300-500k/yr (ODIN: bottleneck = capital access, not edge). Personal-capital transition fund
(30% of payouts) is the only un-repriceable capital.
ROADMAP GATES (evidence, not dates): S1 live + >=50 telemetried fills within 0.05R of certified ->
S2 fill 20 Apex slots + launchd/VPS debt paid (trigger: 3 funded) -> S3 MFFU after written
verification + fresh cert -> S4 Topstep + transition fund (gate: $20k+/mo x2 quarters) -> S5
harvest or new-edge R&D under the same certification law.
TOP RISKS: firm rule repricing (near-certain; multi-firm + scheduled re-diligence), silent edge
decay (D1c keep-rate tripwire + quarterly recert), automation-policy bans (written permissions),
correlation-1 fleet busts (structural; conservative funded sizing, disclosed in every projection).
DO-DIFFERENTLY (canon): canary on day one; 1m-truth before first cert; positive fill confirmation
before first live order; firm rules = versioned external dependencies; no "temporary" bypass flags.
PRINCIPLES: data over theory, harness over memory, fail closed over fail hopeful, no number
without provenance.

RECOMMENDATION: stay exactly as-is; this document exists so the Stage-3 decision takes an
afternoon when the trigger fires.
