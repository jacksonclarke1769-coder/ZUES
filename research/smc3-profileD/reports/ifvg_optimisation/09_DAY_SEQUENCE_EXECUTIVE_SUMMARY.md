# SMC3 Day-Sequence Optimisation — Executive Summary

```text
DAY-SEQUENCE OPTIMISATION STATUS: KILL

Commit hash:              (uncommitted — research tree; reports staged under smc3/reports/ifvg_optimisation/)
Live hold status:         ACTIVE (not armed; no live/funded/dashboard/ProfileA-VPC code touched)
Funded hash status:       UNCHANGED
Baseline tested:          SMC3 NY-AM 09:30–12:00 ET (reproduced exact: n=1624, WR 35.5%,
                          avgR +0.042, totR +67.7, ex-2024 avgR −0.008)
Rules tested:             34 isolated causal day-replay rules (A max-trades, B signal-order,
                          C stop-after-loss, D continue-after-win, E profit-locks,
                          F direction-locks, G cooldowns; H/I skipped per token policy —
                          gated on A–G promise, which did not materialise)
Best rule:                F.dir_lock_first_sweep (one direction per day, first sweep's direction)
Best rule stats:          n=1438, avgR +0.056, ex-2024 +0.016, ex-Friday +0.049,
                          ex-both +0.008, 5/6 years positive, 11.5% trade reduction
Baseline stats:           n=1624, avgR +0.042, ex-2024 −0.008, 3/6 years positive
Improvement vs baseline:  +0.014R/trade; ex-2024 flips −0.008 → +0.016 (real but ~2 ticks/trade thin)
Trades kept:              1438 (88.5%)
Trades removed:           186 (11.5%)
Jun 29-style loser clustering reduced:    PARTIALLY — but the clustering hypothesis itself
                          is WRONG in general: 2-trade days are the BEST day bucket
                          (day-WR 55.9%); only 3-trade days bleed (28.7%). Signal-order
                          shows NO decay (#1 +0.039, #2 +0.027, #3 +0.074, #4+ +0.247) —
                          later trades are NOT worse. Repeat entries are not the failure mode.
Jul 2-style good-day participation preserved: YES for F-family (only 4–12% removed)
2024 included result:     +0.056R (best rule)
2024 excluded result:     +0.016R (positive but thin)
Friday included result:   +0.056R
Friday excluded result:   +0.049R (ex-both +0.008 — barely positive)
Year stability:           improves 3/6 → 5/6 positive years (the one genuine improvement)
Stress result:            FATAL. All three legitimate F-rules die at 2x costs
                          (ex-2024 → −0.007/−0.012/−0.014), at −0.02R slip (two of three
                          at −0.01R), and at 90% winner-fill. The B signal-#3/#4+ rows
                          survive costs but are denominator tricks (91–98% reduction, n≤145).
Denominator-trick audit:  enforced — all E profit-locks / caps / cooldowns / stop-after-loss
                          rows either ex-2024-negative or REJECTED_DENOMINATOR_TRICK
                          (one-year carry). F-family passes the audit but fails stress.
Recommendation:           KILL. Day-sequencing does not revive SMC3. The one real finding is
                          mechanistic, not tradeable: intraday DIRECTION-FLIPPING = chop
                          (locking to the first sweep's direction is worth ~+0.02R/trade and
                          lifts year-stability to 5/6) — but the resulting edge is ~2 ticks
                          per trade and evaporates under any realistic cost/slippage stress.
                          Per stop-conditions: no filter reaches PF>1.20; survivors are
                          stress-fragile; stop searching. Note the direction-flip insight as
                          a reusable chop-diagnostic for OTHER models (e.g. sweep→OTE overlay
                          research), then shelve SMC3 permanently.
Live eligibility:         NO
Next operator action:     Close the SMC3/Profile-D research line. Optionally: (a) commit the
                          smc3/ research record to ZUES; (b) test the direction-lock chop
                          signal as an overlay hypothesis on the sweep→OTE lane (the live
                          research lead), which has real per-trade margin to protect.
```

## One-paragraph honest read
The operating hypothesis — SMC3 bleeds because it re-fires on bad/choppy days — is **refuted by the data**: later same-day signals are not worse (no signal-order decay), and 2-trade days are the *best* day bucket. What the battery actually surfaced is that **direction flipping within a day is the chop marker**: locking each day to its first sweep direction is the only filter family that is simultaneously causal, non-denominator, ex-2024-positive, ex-Friday-positive and 5/6-years-positive. But the surviving edge is ~+0.016R ex-2024 — about two ticks per trade — and it dies at 2x costs, −0.01/−0.02R slippage, and 90% winner-fill. A filter cannot rescue a structurally breakeven core; it can only stop self-harm, and there wasn't much self-harm to stop. KILL stands.
