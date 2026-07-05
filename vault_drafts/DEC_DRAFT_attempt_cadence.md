# DEC DRAFT — attempt cadence & operator policies (NOT a decision)
Proposed (zero-code operator behaviors, adoptable without touching the machine):
1. R1 RECYCLE: after 3 consecutive A losses on an eval, declare the attempt spent — stop
   trading it, start the next weekly account (slot-year EV +~7%; forgone recoveries = 1/395).
2. START TIMING: don't start new evals in holiday-shortened weeks (+2.2pp pass/attempt, 24mo window).
3. CADENCE: maintain-N slots scales ~linearly to N=4 but the Apex 20-account cap binds in
   9-15 months at N≥2 — treat the cap, not the edge, as the growth ceiling; signal-triggered
   starts add nothing (null result).
Caveats: single-historical-path replay, clustered outcomes, funded LTV credited at pass
(ranking convention, not cash flow). Evidence: reports/eval_passrate_sprint/{recycle_rules,account_start_timing,attempt_cadence}.{csv,md}.
