# DOL Exit Audit — Final Verdict

```text
DOL EXIT AUDIT STATUS: KILL  (per the operator's own promotion gates — with one honest nuance recorded below)
```

## The six questions, answered directly

**1. Was fixed 2R a bad representation of the strategy?**
MECHANICALLY YES, ECONOMICALLY NO. The nearest causal DOL is closer than 2R on 86.2% of trades and gets hit before 2R 84.5% of the time — so 2R routinely overshot the liquidity the thesis says to target. BUT the touch-probability ladder is the decisive evidence: P(+0.5R)=66.9%, P(+1R)=50.4%, P(+1.5R)=41.0%, P(+2R)=34.3%, P(+3R)=25.3% — **every rung sits within ~1pp of its own breakeven threshold (1/(1+R)), flat across all 6 years.** The entry carries no directional information at ANY horizon. Fixed 2R wasn't hiding an edge; there was no fixed-R edge to hide.

**2. Did liquidity targeting improve the edge?**
Partially — one specific variant. Naive "nearest of all liquidity" targeting is WORSE than 2R (62% of pooled DOLs sit <0.5R away; costs eat the tiny targets — all headline-7 pooled-DOL models negative). But `dol_htf_pocket_only` (target = the opposite 60m confirmed pocket, the model's own level type) is the best exit found: avgR −0.010 → **+0.084**, PF(R) 1.103, totR +318 on n=3773.

**3. Did DOL exits beat fixed 2R?** The HTF-pocket variant, clearly yes (+0.095R/trade improvement). The pooled-nearest variants, no.

**4. Did DOL exits survive ex-2024?** The HTF-pocket variant, yes: ex-2024 **+0.087**, 5/6 years positive, and it survives 2× costs (+0.070) and −0.02R slip (+0.030, still ex-2024-positive).

**5. Did they avoid Friday-only bias?** Yes: ex-Friday +0.094, ex-both +0.101. Both directions positive (long +0.114 / short +0.058 — not NQ bull-beta). One flag: outsized small-n Sunday-entry contribution (n≈80–103), noted, not excluded.

**6. Should SMC3 remain killed, move to watchlist, or justify a full IFVG build?**
**REMAIN KILLED — the promotion gates fail on magnitude and on the trade profile:**
- PF(R) 1.103 < the 1.20 gate, at baseline AND at every stress level. Fails on size of edge, not robustness.
- WR 21.7% with avg win 4.17R = long losing streaks; **maxDD 125.7R** vs +318R total (Calmar-in-R ≈ 2.5 over 5 years) — prop-account-hostile geometry.
- NY-AM is ex-2024-NEGATIVE for all three positive exit models (−0.037/−0.141/−0.099) — the thin edge isn't where the operator wants to trade it.
- The exit-walker mechanics (nearest-first tranche ordering, stop-tie priority) are new code flagged by the builder itself as the audit-risk area; on a random-walk entry, +0.08R after costs from exit structure alone is *a priori* suspicious and would need independent re-derivation before any promotion.
- Causality: clean — 0 artifacts on 5,052 DOL-bearing trades, `target_known_at ≤ entry_time` asserted, not assumed.

## The honest nuance for the record
This audit changed one conclusion: "no exit can help" → "pocket-targeted exits extract a small, robust-to-stress, both-directions, 5/6-year tail premium (+0.08R) that fixed-R exits cannot see — but it is too thin (PF 1.10), too deep-drawdown, and possibly walker-mechanics-sensitive to trade." The ENTRY remains proven edgeless at every fixed-R horizon. A filter/exit cannot promote a random entry to a fundable strategy.

**Full IFVG engine build: NOT justified.** If anything from this line survives, it is the reusable idea that **"target the opposite HTF pocket" beats fixed-R on liquidity-sweep setups** — worth one cheap test as an exit variant on sweep→OTE (which already has liq-targets and a REAL entry edge), not worth rebuilding a dead entry model.

**Next operator action:** close SMC3 permanently (three entry KILLs + exit audit complete), optionally commit the research record to ZUES, and redirect the pocket-exit idea to the sweep→OTE lane.
```
