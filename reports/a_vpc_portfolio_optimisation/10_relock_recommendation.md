# A+VPC Optimisation — Re-Lock Recommendation (Fable auditor, 2026-07-06)
LIVE HOLD ACTIVE · research/cert-prep only · nothing armed.

## The 18 answers
1. Highest pass surviving stress: A900/6+VPC700/3 → 39.3/19.6/41.1, flip 0.076R.
2. Best balanced: **A900/6+VPC600/3 → 37.4/18.0/44.6, flip 0.068R, f/slot 5.89** (auditor pick).
3. Best conservative: A700/4+VPC600/6 → 30.7/11.7/57.6, flip 0.067R.
4. Beats A600/6+VPC600/4? **Yes, decisively and robustly.**
5. By how much: balanced = +8.7pp pass / +1.0pp bust / f-slot 4.22→5.89 / E$ +$696 (+32%) /
   flip 0.055→0.068R (MORE damage-tolerant, not less).
6. Survives 0.035R? Yes (all finalists; balanced flips at 0.068).
7. Survives 0.046R? Yes (balanced margin still positive at 0.046 probe and beyond).
8. Survives 75% winner-fill? NO — and neither does the baseline nor any honest PF-1.35 machine
   (arithmetic: 1.35×0.75≈breakeven). Machine-level condition; governed by the armed 15%
   touch-without-fill kill line + fill telemetry (N≥30). Not a config discriminator.
9. Pass > bust? Yes (37.4 vs 18.0; 2.08:1).
10. Bust ≤ 22? Yes (18.0).
11. Improves funded/slot-year? Yes: 4.22 → 5.89 (+40%).
12. Reduces expiry without unacceptable bust? Yes: 54.4 → 44.6 at +1.0pp bust.
13. Conflict rule: R0 naive union — every alternative is null or a denominator artifact; the
    lanes rarely collide (near-zero same-60min overlap).
14. Daily risk: shared $550 stop, $1,000 DLL clamp — unchanged; 25 variants all worse or artifact.
15. VPC window: FULL 10:00-15:00 — every restriction starves the calendar-widener.
16. Priority: none needed (no collisions to arbitrate); lanes run independent.
17. Exit change worth a re-cert event? A-fixed-1.5R lifts pass ~+4pp at baseline sizing with
    worse maxDD — genuine but not bundled; decide it INSIDE the re-lock DEC as an explicit
    separate line (it also shifts funded numbers, which must be re-run at the chosen exit).
18. Eligible to arm now? **No.** Path unchanged: operator re-lock DEC (now with this frontier) →
    live latest_signal() fix → VPC execution lane build+audit → paper shadow → arming approval.

## What the re-lock DEC now decides (operator)
(a) The sizing row: balanced A900/6+VPC600/3 (auditor pick) vs conservative vs throughput.
(b) The exit line: keep Exit#3 vs certify fixed-1.5R (separate certification event).
(c) Funded config re-run at the chosen row (funded numbers in prior reports used A250/4 cells —
    unaffected by this eval-side choice, but E$ placeholder should be replaced with the honest
    funded value at the final DEC).
NOTE: one prerequisite re-run before the DEC is signed — the pandas-2.3.3-pinned environment
canary and the 1m-truth VPC stream are the certified basis; any future pandas migration or VPC
engine change re-opens this frontier.
