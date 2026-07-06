# Pattern Discovery — Artifact Audit (Fable auditor, 2026-07-06)
- Canaries: baselines exact (unfiltered 705/PF1.237, kept 583/PF1.361, (10,$1200) row); 40/40 store
  causality spot-checks; F-lane quintile canary reproduced before the direction split; base-machine
  row reproduced exactly in Wave 2; A6-stress precedent cross-matched at slip 0.02/0.05.
- Too-good audit: the program's strongest finding (vwap_slope Q1 PF 2.52) was ADJUDICATED A
  CONFOUND — quintiles Q1/Q5 are ≥90-100% single-direction by OTE construction; the independent
  residue (Q3 flat-slope bad both directions) is real but funnel-null. Lesson: direction-pooled
  context stats on a directional strategy are confound-prone; interaction check is now standard.
- Denominator rule: zero artifact flags across all avoid/sizing tests (520 G-cells + 5 Wave-2
  variants), count columns everywhere.
- Multiple comparisons: H reported 21 nominees vs ~794 expected under null — decisive null,
  stated with the binomial math.
- Honest structural disclosures: two features unusable at the 10:00 stamp (per-day window resets);
  into_vwap_band drive class tautological near the open; vendor-tail join misses 13-17/705;
  implementer-flagged injection-lookalike tool outputs correctly ignored (F+G lane).
- Boundary stops: one clean BLOCKED (missing-path) resolved with absolute paths — no fabrication.
