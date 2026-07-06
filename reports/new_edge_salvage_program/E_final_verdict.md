# New Edge / Salvage Program — Final Verdict (Fable auditor, 2026-07-06)

**HONEST-RECERT DRAFT — pending operator approval. LIVE HOLD ACTIVE. Nothing armed, nothing promoted.**

## The 15 answers

1. **Is honest Profile A viable at any sizing?** Alone for EVALS: no — best cell across 495
   combinations is 23.4/20.7 with 56% expiry (weak-viable, not a business). For FUNDED: **yes** —
   kept-stream $250-300/A4 are FUNDED-VIABLE ($7.2-8.2k, 0-8% observed bust).
2. **Honest D1c vs unfiltered at the funnel level?** **It inverts by phase.** Evals: unfiltered
   dominates (frequency beats the +0.124 PF; the viability shortlist is mostly unfiltered rows).
   Funded: kept dominates (every unfiltered funded cell NOT-VIABLE; D1c's quality is what survival
   is made of). D1c is a funded filter, not an eval filter.
3. **Profile A best as?** One leg of a two-edge eval portfolio + the funded-phase engine (with
   D1c). Not dead, demoted from solo act.
4. **Sizing class with pass > bust and positive EV?** **A@$600/cap-6 + VPC@$600/cap-4: pass 27.8 /
   bust 15.5 / expire 56.7** (2022-2026 window, n=684 starts), ~3.95 trades/wk, funded-per-slot-yr
   4.04, positive every year, **stress-robust to 0.042R uniform slippage** (≈3× every alternative)
   and never below A-alone anywhere in the damage grid. The throughput combos (A@1200-based,
   pass 41-45%) are fill-fragile (flip at 0.015-0.019R) — rejected.
5. **Funded viability under honest truth?** Yes, conservative: kept-A 250/4 → $7,292 / 0% observed
   bust / ~31mo (robust through 0.05R slippage); +VPC@200/2 → $8,567 / 0% observed (degrades at
   heavy damage — VPC funded leg optional/small). Wide-CI caveat stands (n=49 overlapping starts).
6. **Did Exit#3 still dominate?** **No — fixed-1.5R marginally beats it** on the honest stream
   (+96.9R/9.4 maxDD vs +89.2R/10.2). Margin ~8%; exit changes are certification events; fold the
   exit choice into the re-lock certification rather than treating it standalone.
7. **Did any new edge survive?** One: **VPC** — the shelf rescue. Its 2026-07-04 rejection was
   measured against the contaminated machine and is void; on honest truth it is the missing
   second leg (PF 1.29/1.23-harsh, 5/5 yrs, OOS>IS, corr +0.11, uncontaminated by the incident).
   All fresh searches died: B3 level-sweeps 112/112, B5 compression 9/9, B7 stat-scan noise
   (honest multiple-comparisons framing), B8 RTY dead + YM near-miss (1.14) dead-but-noted,
   ES already dead. B1/B2/B6 resolved by prior art (KRONOS, Idea-7, VPC-as-the-thesis).
8. **Meaningful trades/week added?** Yes: VPC ~+1.7/wk on 196 A-flat days → combined ~3.9/wk
   (vs 2.24 kept-alone). The expiry problem's root cause — frequency — is addressed structurally.
9. **Funded-per-slot-year improved?** Yes: 4.04 (balanced combo) vs ~3.4 best single-edge viable.
10. **Combined beat Profile A alone?** Decisively, on every axis, at every tested damage level.
11. **Survived fill/slippage stress?** The balanced combo yes (0.042R); VPC-chase stress mild
    (0.5-1.0pt extra entry barely moves it; its cert already survived 3pt flat). Universal
    caveat: winners'-partial-fill sensitivity (flip at f≈0.86-0.94) — a live-telemetry
    machine-viability line for ALL configs, not a discriminator.
12. **Any denominator artifact?** No — pass counts rise with pass rates everywhere; count columns
    reported throughout per DEC-20260706-1108.
13. **Funded config untouched?** Yes — hash byte-identical through every lane; gate green (851).
14. **Live machine untouched?** Yes — zero tracked modifications; hold never lifted.
15. **Eligible to arm now?** **No.** Outstanding before any arming: the live latest_signal()
    fix (ticketed, operator-gated) → a re-lock certification of whatever config Jackson chooses
    (the balanced combo is the auditor's candidate) → new DEC + explicit approval. VPC live
    integration additionally needs execution-path work (second strategy lane in auto_live — it
    once existed for Profile B; certification event).

## The honest business, in one paragraph

Profile A alone can no longer carry the eval business — that machine died with the look-ahead.
What the evidence supports instead: **a two-edge portfolio** — unfiltered-leaning A at moderate
size plus VPC — passing ~28% with bust ~15% at ~4 trades/week, feeding a **D1c-kept conservative
funded engine** extracting ~$7-8.5k per account over 2-3 years at near-zero observed bust. Slower,
smaller, real. Expected value per eval attempt ≈ 0.278×$8,400−$131 ≈ **~$2,200**, funded-per-slot-
year ≈ 4 — roughly a third of the fictional business, and the first configuration since the
incident where every number survives its own canaries.

## Auditor's recommended next actions (operator's call)
1. Approve + execute the live latest_signal() fix ticket (small, spec'd, line-audit promised).
2. Decide the re-lock candidate: the balanced combo (A@600/6 + VPC@600/4 eval · kept-A 250/4
   funded ± VPC 200/2) — includes the Exit#3-vs-1.5R choice and the D1c-role split (eval
   unfiltered vs funded kept) as explicit DEC items.
3. If approved: full re-lock certification (canaries, fill-sensitivity, config locks, new machine
   page + DEC), THEN revisit the hold. The current live eval (honest conditional 13.2% pass)
   rides or is abandoned per the R1 recycle policy — operator's judgment.
