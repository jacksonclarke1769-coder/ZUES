# 06 -- Exit interaction (A+VPC portfolio optimisation, Lane 2)

**NOTICE: exit changes are certification events.** RESEARCH-ONLY comparison; no certified live exit (A exit3, VPC current 5.0xATR trail) is modified by this file. Every row below is a hypothetical re-walk, reported as data, not a recommendation.

A-leg exits reuse `tools_salvage_funded_exits.py`'s A5 machinery verbatim (exit3-current/fixed-1.5R/fixed-2R). A-leg canary: PASS (exit3-current on the FULL stream reproduces n=583 PF=1.361 totR=+89.2R). A-leg rows below are window-restricted to 2022-2026 (shared VPC window) before combining with the VPC leg, mirroring the existing 'PART 3 WINDOW NOTE' convention in `tools_salvage_vpc_reeval.py`.

VPC-leg exits are a self-verified extension of `tools_vpc_1m_truth.py`'s 1m re-walk (`vpc_1m_truth_variant`, this file) -- entries/direction/initial-stop unchanged; only the exit's bar-by-bar rule varies (trail multiple / fixed target / arm-delay / time-stop / hard EOD flatten). Self-check: defaults reproduce `VT.vpc_1m_truth_trades()`'s own re-walk exactly (see run log).

Baseline (A=exit3-current, VPC=current-5.0xATR, overlay=none): PF$=1.377 PF_R=1.364 WR=45.2% totR=+136.5R maxDD$=4,189 pass=28.8% bust=16.4% exp=54.8% n=684. This is the SAME A/VPC trade set as 05's A-current+VPC-full named combo (verified: identical R-multiset, n=513, and identical VPC re-walk) but reproduces pass=28.8%/bust=16.4% here vs pass=28.7%/bust=17.0% in 05 -- ROOT-CAUSED (not a bug in this file): the A-leg's `mae_r` field differs between the two independently-sourced 'identical' A streams (`tools_sim_parity_check.load_rows()`'s own mae_r vs the A5 machinery's `walk_exit3`-re-derived mae, e.g. one specific day, 2022-01-14, has trough -$910 in one stream's mae vs -$453 in the other), which changes the DLL-clamp trough on that day and flips a small number of eval-run outcomes. R itself is byte-identical between the two streams (elementwise multiset check passed); only the adverse-excursion field differs. Called out, not hidden -- not investigated further here (out of this file's scope; a pre-existing discrepancy between two already-certified prior-art pipelines).

`Best-A x Best-VPC` combined row picks, mechanically, the highest dollar-PF variant within each leg's varied rows (baseline included): best A-leg = **fixed-1.5R**, best VPC-leg = **current-5.0xATR**.

Slip probe = 0.015/0.03/0.046R applied to BOTH legs uniformly (`tools_salvage_stress.dmg_slip`, reused verbatim).

## Full table

| dimension | label | n_a | n_v | pf_dollar | pf_r | wr_pct | totR | maxdd_usd | eligible_starts | pass_count | bust_count | exp_count | pass_pct | bust_pct | exp_pct | med_days_pass | funded_per_slot_year | e_dollar_placeholder |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | BASELINE (A=exit3-current, VPC=current-5.0xATR, overlay=none) | 513 | 408 | 1.377 | 1.364 | 45.2 | 136.5 | 4189 | 684 | 197 | 112 | 375 | 28.8 | 16.4 | 54.8 | 18 | 4.23 | 2173 |
| A-leg | A-leg=fixed-1.5R (VPC=current-5.0xATR) | 513 | 408 | 1.381 | 1.372 | 47.4 | 150.2 | 4353 | 684 | 222 | 131 | 331 | 32.5 | 19.2 | 48.4 | 18 | 4.96 | 2469 |
| A-leg | A-leg=fixed-2R (VPC=current-5.0xATR) | 513 | 408 | 1.374 | 1.371 | 44.6 | 159.4 | 6408 | 684 | 259 | 140 | 285 | 37.9 | 20.5 | 41.7 | 16 | 6.07 | 2901 |
| VPC-leg | VPC-leg=tighter-4.0xATR (A=exit3-current) | 513 | 408 | 1.35 | 1.342 | 44.7 | 125.9 | 4676 | 684 | 185 | 82 | 417 | 27 | 12 | 61 | 20 | 3.85 | 2029 |
| VPC-leg | VPC-leg=looser-6.0xATR (A=exit3-current) | 513 | 408 | 1.365 | 1.354 | 45.7 | 136 | 4374 | 684 | 192 | 111 | 381 | 28.1 | 16.2 | 55.7 | 18 | 4.11 | 2117 |
| VPC-leg | VPC-leg=fixed-2R-target (A=exit3-current) | 513 | 408 | 1.3 | 1.301 | 46.4 | 119.2 | 5551 | 684 | 181 | 135 | 368 | 26.5 | 19.7 | 53.8 | 18 | 3.87 | 1989 |
| VPC-leg | VPC-leg=trail-armed-after-1R (A=exit3-current) | 513 | 408 | 1.366 | 1.354 | 47.1 | 136.4 | 4170 | 684 | 201 | 118 | 365 | 29.4 | 17.3 | 53.4 | 17 | 4.37 | 2221 |
| VPC-leg | VPC-leg=time-stop-120min (A=exit3-current) | 513 | 408 | 1.331 | 1.324 | 48.3 | 113.6 | 4376 | 684 | 154 | 84 | 446 | 22.5 | 12.3 | 65.2 | 21 | 3.08 | 1669 |
| overlay | overlay=flatten-VPC-by-14:30 (A=exit3-current) | 513 | 408 | 1.297 | 1.274 | 45.4 | 72.4 | 4233 | 684 | 57 | 46 | 581 | 8.3 | 6.7 | 84.9 | 25 | 1.05 | 533 |
| overlay | overlay=stop-day-after-portfolio>=+1.0R | 488 | 358 | 1.273 | 1.252 | 43.4 | 89.3 | 5051 | 684 | 125 | 108 | 451 | 18.3 | 15.8 | 65.9 | 20 | 2.52 | 1333 |
| overlay | overlay=stop-day-after-portfolio>=+1.5R | 497 | 376 | 1.311 | 1.295 | 44 | 106.8 | 4946 | 684 | 146 | 105 | 433 | 21.3 | 15.4 | 63.3 | 19 | 3 | 1573 |
| overlay | overlay=stop-day-after-portfolio>=+2.0R | 509 | 405 | 1.352 | 1.342 | 44.9 | 127.7 | 4946 | 684 | 181 | 117 | 386 | 26.5 | 17.1 | 56.4 | 19 | 3.83 | 1989 |
| best-combo | BEST-A(fixed-1.5R) x BEST-VPC(current-5.0xATR) combined | 513 | 408 | 1.381 | 1.372 | 47.4 | 150.2 | 4353 | 684 | 222 | 131 | 331 | 32.5 | 19.2 | 48.4 | 18 | 4.96 | 2469 |

## Slip probe

| dimension | label | slip0.015_pass_pct | slip0.015_bust_pct | slip0.03_pass_pct | slip0.03_bust_pct | slip0.046_pass_pct | slip0.046_bust_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | BASELINE (A=exit3-current, VPC=current-5.0xATR, overlay=none) | 26.5 | 17.7 | 24.9 | 17.4 | 23 | 17.8 |
| A-leg | A-leg=fixed-1.5R (VPC=current-5.0xATR) | 30.7 | 19.9 | 29.4 | 20.8 | 27.8 | 21.3 |
| A-leg | A-leg=fixed-2R (VPC=current-5.0xATR) | 36.5 | 21.8 | 34.4 | 22.4 | 33 | 23.4 |
| VPC-leg | VPC-leg=tighter-4.0xATR (A=exit3-current) | 25.7 | 14.5 | 23.8 | 14.8 | 21.3 | 16.7 |
| VPC-leg | VPC-leg=looser-6.0xATR (A=exit3-current) | 26.5 | 16.8 | 24.7 | 17 | 22.2 | 17.3 |
| VPC-leg | VPC-leg=fixed-2R-target (A=exit3-current) | 25 | 19.9 | 22.1 | 18.9 | 20.5 | 19.2 |
| VPC-leg | VPC-leg=trail-armed-after-1R (A=exit3-current) | 27.3 | 17.8 | 25.6 | 16.7 | 23.7 | 17.3 |
| VPC-leg | VPC-leg=time-stop-120min (A=exit3-current) | 20.2 | 14 | 18.4 | 14 | 16.5 | 15.8 |
| overlay | overlay=flatten-VPC-by-14:30 (A=exit3-current) | 7.2 | 7.6 | 6.7 | 7.9 | 5.3 | 9.6 |
| overlay | overlay=stop-day-after-portfolio>=+1.0R | 16.5 | 17.3 | 15.2 | 17.5 | 14.3 | 17.8 |
| overlay | overlay=stop-day-after-portfolio>=+1.5R | 19 | 16.7 | 18 | 17.7 | 17 | 18.4 |
| overlay | overlay=stop-day-after-portfolio>=+2.0R | 24.4 | 18.1 | 23 | 18 | 21.3 | 18.3 |
| best-combo | BEST-A(fixed-1.5R) x BEST-VPC(current-5.0xATR) combined | 30.7 | 19.9 | 29.4 | 20.8 | 27.8 | 21.3 |

## Firewall before/after

- `config_eval_locked.py`: UNCHANGED
- `config_funded_locked.py`: UNCHANGED
- `config_defaults.py`: UNCHANGED
- `auto_safety.py`: UNCHANGED

## PF freeze check: no cell exceeded PF>1.8.

Runtime (lane 2 only): 20.0s

No recommendation. No commits.
