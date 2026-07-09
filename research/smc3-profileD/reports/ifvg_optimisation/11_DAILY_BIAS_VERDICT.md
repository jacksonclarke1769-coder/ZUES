# Daily-Bias Research Pass — Final Verdict

```text
DAILY BIAS STATUS: KILL

Best bias rule:          F6.shorts_only_VWAP_slope_down — the ONLY rule clearing the numeric
                         gates (PF 1.212, ex-2024 +0.206, survives 2x costs & −0.01R)
Best bias stats:         n=282 of 4,956 in-scope (94.3% trade reduction), 3/6 years positive,
                         P(+2R)=39.0%
Why it still fails:      REJECTED_DENOMINATOR_TRICK — 94.3% reduction is the exact pattern
                         this research line rejects everywhere else; 3/6 years; tiny n.
Cleanest honest rule:    F5.rev_30mLow_sweptFailed_long (30m low swept-and-failed → long bias):
                         n=938, avgR +0.058, ex-2024 +0.052, 6/6 YEARS POSITIVE, no denominator
                         flag, survives 2x costs (+0.026) and −0.02R (+0.038) — the single
                         cleanest finding in the entire SMC3 arc. But PF(R) 1.089 < 1.20 gate.
                         Too thin to trade; recorded, not promoted.
Comparison vs fixed 2R:  baseline avgR −0.0105 / P(+2R) 34.34%. Best clean rules reach
                         +0.05-0.07 avgR but P(+2R) only 35.9-36.8%.
Comparison vs DOL exit:  combined direction-of-DOL + target-DOL = avgR −0.041 / PF 0.781 —
                         WORSE than fixed-2R on the same subset and far worse than
                         dol_htf_pocket_only (+0.084 / PF 1.103). Clear negative result.
Did bias improve target selection?  NO — the one exit-changing combo degraded results.
Did bias reduce chop?    NO new information. All top rules are shorts-only trend-alignment
                         (short only when already below open/prev-close/VWAP) — composition
                         reshuffling, not signal: avgR moves a lot while P(+2R) barely moves.
                         Notably NOT simple bull-drift capture (unconditional shorts −0.019
                         are the weaker side), but still regime composition, not edge.
Mechanism test (decisive): NO rule lifts P(+2R-before-stop) materially above the 34.3%
                         breakeven rung (range 32.0-39.0%; clean survivors 35.9-36.8%).
                         Daily bias adds NO information to the entry at the +2R horizon.
Causality:               0 artifacts across all 32 rules / 5,056 trades (strictly-prior-bar
                         features, known_at ≤ entry_time asserted).
DOWNGRADE of prior finding: the day-sequence "direction-lock = chop diagnostic" does NOT
                         replicate on the full book (full-set avgR −0.001, ex-2024 −0.006 vs
                         NY-AM-only +0.056/+0.016). Reusable-insight #1 is demoted to
                         "NY-AM-only, likely regime noise." Insight #2 (target-the-opposite-
                         HTF-pocket exit) remains standing.
Recommendation:          CLOSE the SMC3 research line for good. Six independent passes
                         (baseline, param/context, IFVG probe, day-sequence, DOL exits,
                         daily bias) all converge: the entry is structurally breakeven and
                         every apparent improvement is composition, regime, calendar, or
                         denominator. The answer to "did daily bias improve SMC3?" is NO —
                         the entry is still structurally breakeven.
Live eligibility:        NO
Next operator action:    Stop testing SMC3 wrappers. Redirect: (a) the opposite-HTF-pocket
                         exit idea to sweep→OTE; (b) optionally record the 30m-failed-sweep
                         long-bias as a candidate FEATURE for future models with real entries;
                         (c) commit the smc3/ research record to ZUES.
```
