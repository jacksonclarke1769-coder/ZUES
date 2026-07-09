# Profile D (IFVG/SMC) Optimisation — EXECUTIVE SUMMARY

```
IFVG optimisation status: KILL (SMC3/BOS-FVG subset tested; full IFVG-inversion families UNTESTED)
Commit hash:              (pending — reports staged, not yet committed)
Live hold status:         ACTIVE (not armed; no live/funded code touched)
Funded hash status:       UNCHANGED (not touched)
Cells tested:             26 param cells (R-based one-axis robustness) + NY-AM hour/year/Friday deep-dive
Families tested:          session, hour-band, stop mode/buffer/max/min, R-target, 5m confirm type,
                          1m trigger type, direction, sweep buffer, context-expiry, day-of-week
Families killed:          ALL — no family produced a cross-year robust positive-R config
Families graduated:       NONE
Best standalone candidate: SMC3 NY-AM 09:30-12:00 ET
Best standalone stats:    n1624 WR35.5% PF($)1.12 avgR +0.042 totR +67.7 — BUT ex-2024 avgR -0.008
                          (one-year carry: 2024 alone +77.6R > full +67.7R; 3/6 yrs positive)
Best eval candidate:      NONE (no standalone survivor -> eval funnel NOT run, per staged method)
Eval pass/bust/expire:    N/A (not run)
Not-pass:                 N/A
Attempts per pass:        N/A
Slippage/fill tolerance:  N/A (killed before stress stage)
Causal audit:             PASS — no-lookahead asserted per-trade 5056/5056; entry>all-confirm-times
Artifact count:           0 (model is HONEST; it is breakeven, not fraudulent)
Best filters discovered:  Friday-only (avgR +0.10, IS +0.0997 / OOS +0.1011, all 6 yrs +) — but a
                          mechanism-free CALENDAR effect, 1-of-5 weekdays (multiple-testing risk),
                          overlaps the 2024 carry. NOT a signal improvement.
Worst filters discovered: 11:30-12:00 ET (-0.045R); Wed (1/6 yrs+), Thu (0/6 yrs+) consistent losers
Close-through speed verdict:      NOT TESTED — IFVG inversion + close-through not in engine (needs Stage 0-D build)
Highest-timeframe IFVG verdict:   NOT TESTED — needs engine extension
Protected-stop verdict:           Recent-Swing / Sweep-Extreme / Wider all tested -> all breakeven; other
                                  protections (FVG/PDR/PDH-PDL) NOT tested (need engine extension)
Comparison vs live-achievable Profile A: WORSE. SMC3 best honest config is breakeven-to-negative
                                  once the 2024 carry is removed, vs Profile A live-achievable PF 1.037 / +7.4R.
                                  Does NOT clear the bar.
Recommendation:           KILL the SMC3 (sweep->BOS/FVG->1m->2R) signal as a standalone edge. WR is pinned
                          at the ~33% 2R/1R breakeven in EVERY context bucket; no param/session/hour/stop/
                          target/direction moves it. Do NOT run deployment sims. The full IFVG engine
                          extension is a LOW-probability bet on this base; if pursued, test ONLY the one
                          distinguishing mechanism first — close-through-speed (§F) IFVG inversion — as a
                          targeted probe, since it is the only rule that could change the WR distribution.
Live eligibility:         NO
Next operator action:     Choose: (a) targeted probe of close-through-speed IFVG-inversion (the single
                          untested mechanism that might differ from BOS/FVG), or (b) shelve Profile D and
                          keep resources on the sweep->OTE lead + Profile A causal-fork resolution.
```

## One-paragraph honest read
The SMC3/Profile-D structure is a faithful, causal, artifact-free mirror — and that honesty is exactly why it shows the truth: the sweep->confirm->trigger signal has no risk-normalised edge (avg R ~= -0.01, WR pinned near breakeven everywhere). The apparent NY-AM edge is a 2024 window artifact; the only IS/OOS-stable positive is Friday, a calendar coincidence with no mechanism. Nothing here beats live-achievable Profile A. The 13-section IFVG optimisation program is not warranted on this base unless the IFVG-*inversion* + close-through-speed mechanism (the one untested piece that actually changes the entry) is shown to alter the WR distribution — which should be probed cheaply and in isolation before any large engine build.
```
