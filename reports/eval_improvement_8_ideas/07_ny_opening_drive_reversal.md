# Idea 7 -- NY Opening-Drive Failed-Breakout Reversal (RESEARCH ONLY)

Generated 2026-07-05 23:28:31.606193-04:00. Engine: `ny_fbr_engine.py`. Grid runner: `ny_fbr_grid.py` (both in `~/trading-team/backtests/ict-nq-framework/`). Modifies nothing existing.

## Preregistered priors (printed per brief, not re-derived here)

- reversal-class setups LOSE on NQ historically (turtle-soup PF 0.84-0.91).
- Wyckoff W5 (failed-breakout-into-range) was REJECTED 2026-07-06 -- the closest prior analog.
- opening-drive CONTINUATION is dead (real NQ PF 0.97, KRONOS).
- The burden is on THIS variant (opening-drive FAILED-BREAKOUT REVERSAL, never tested per the idea register) to overcome these priors.

## Setup as coded (summary; full causal detail in `ny_fbr_engine.py` module docstring)

Opening drive anchored at the 09:30 ET RTH-open 5m bar: move over a fixed {15,30}-minute window >= {0.35,0.5}x dailyATR14 (paired as 2 drive-defs, not a 2x2 cross: (15m,0.35x) and (30m,0.5x)), AND the window-end bar's Close breaks a key level in the drive's direction. Failed breakout = a Close within {2,4} 5m bars crosses back through the SAME level the other way. Entry = {reclaim_open (next-bar market), retest_limit (resting limit at the level, 12-bar fill window)}. Stop = beyond the failed-breakout extreme +2 ticks. Targets = {session VWAP (causal, moving), fixed 1R, fixed 2R, Exit#3}; vwap/1R/2R are force-flat at 11:30 ET (time-stop), Exit#3 is exempt (runs to target, 24h safety-net cap). Key levels (5, each separate): premarket 04:00-09:30, overnight 18:00-09:30, prior-day RTH 09:30-16:00, opening-range-15 09:30-09:45, prior RTH close. Costs: flat 1.2pt round-turn.

## Kill gates (mechanical)

- PF < 1.15 after costs -> REJECTED
- < 4/6 last full years (2020-2025) positive -> REJECTED
- < 0.3 trades/wk -> REJECTED (lowered bar for this lane: brief says this lane only needs 0.2-0.4 tr/wk to matter economically, since it would run alongside the certified A+B streams as a rare tertiary lane, not stand alone; retained at 0.3 rather than the usual 0.5 floor)
- canary fail -> DEAD
- PF > 1.8 anywhere -> freeze + flag for auditor (not optimized)
- n < 10 trades in a cell -> not evaluated for PF/year gates (too thin to conclude anything)

## Upfront canary (trust checks)

| level_type | drive | fail | entry | target | passed | poison-future | same-bar-fill | n_baseline |
|---|---|---|---|---|---|---|---|---|
| premarket | (15m,0.35x) | 2 | reclaim_open | fixed2r | True | True | True | 25 |
| overnight | (30m,0.5x) | 4 | retest_limit | vwap | True | True | True | 17 |
| prior_rth | (15m,0.35x) | 4 | reclaim_open | exit3 | True | True | True | 19 |
| opening_range15 | (30m,0.5x) | 2 | retest_limit | fixed1r | True | True | True | 18 |
| prior_close | (30m,0.5x) | 4 | reclaim_open | vwap | True | True | True | 13 |

## Profile A certified stream (for overlap / correlation)

435 trades / 405 unique trade-days.

## Data span
646.9 weeks. Grid runtime 0.8s, total runtime 72.7s.

## Grid summary

40 families (level_type x drive_def x fail_window x entry_style), best target_type variant per family evaluated against the kill gates. SURVIVOR: 0  |  REJECTED: 40

| level_type | drive_def | fail | entry_style | status | best target | n | tr/wk | WR% | PF | expR | totR | maxDD-R | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| premarket | 15m,0.35x | 2 | reclaim_open | REJECTED | fixed1r | 25 | 0.0386 | 56.0 | 1.115 | 0.0555 | 1.39 | -4.4 | PF 1.115 < 1.15 |
| premarket | 15m,0.35x | 2 | retest_limit | REJECTED | fixed2r | 17 | 0.0263 | 29.4 | 0.721 | -0.2177 | -3.7 | -7.4 | PF 0.721 < 1.15 |
| premarket | 15m,0.35x | 4 | reclaim_open | REJECTED | vwap | 39 | 0.0603 | 79.5 | 1.339 | 0.0493 | 1.92 | -2.48 | tr/wk 0.0603 < 0.3 |
| premarket | 15m,0.35x | 4 | retest_limit | REJECTED | fixed2r | 28 | 0.0433 | 35.7 | 0.829 | -0.1111 | -3.11 | -5.9 | PF 0.829 < 1.15 |
| premarket | 30m,0.5x | 2 | reclaim_open | REJECTED | - | 0 | 0 | - | - | - | - | - | n<10 trades (all target_types, max n seen=8) |
| premarket | 30m,0.5x | 2 | retest_limit | REJECTED | - | 0 | 0 | - | - | - | - | - | n<10 trades (all target_types, max n seen=6) |
| premarket | 30m,0.5x | 4 | reclaim_open | REJECTED | vwap | 16 | 0.0247 | 93.8 | 3.684 | 0.1913 | 3.06 | -1.14 | tr/wk 0.0247 < 0.3 |
| premarket | 30m,0.5x | 4 | retest_limit | REJECTED | vwap | 13 | 0.0201 | 92.3 | 3.738 | 0.2442 | 3.17 | -1.16 | tr/wk 0.0201 < 0.3 |
| overnight | 15m,0.35x | 2 | reclaim_open | REJECTED | fixed2r | 22 | 0.034 | 40.9 | 0.996 | -0.0022 | -0.05 | -6.04 | PF 0.996 < 1.15 |
| overnight | 15m,0.35x | 2 | retest_limit | REJECTED | fixed1r | 18 | 0.0278 | 44.4 | 0.661 | -0.2125 | -3.83 | -7.62 | PF 0.661 < 1.15 |
| overnight | 15m,0.35x | 4 | reclaim_open | REJECTED | fixed2r | 32 | 0.0495 | 53.1 | 1.422 | 0.1953 | 6.25 | -4.96 | tr/wk 0.0495 < 0.3 |
| overnight | 15m,0.35x | 4 | retest_limit | REJECTED | fixed2r | 26 | 0.0402 | 38.5 | 0.97 | -0.0185 | -0.48 | -5.78 | PF 0.970 < 1.15 |
| overnight | 30m,0.5x | 2 | reclaim_open | REJECTED | exit3 | 14 | 0.0216 | 50.0 | 2.05 | 0.3384 | 4.74 | -1.14 | tr/wk 0.0216 < 0.3 |
| overnight | 30m,0.5x | 2 | retest_limit | REJECTED | vwap | 10 | 0.0155 | 60.0 | 1.706 | 0.2435 | 2.43 | -2.19 | tr/wk 0.0155 < 0.3 |
| overnight | 30m,0.5x | 4 | reclaim_open | REJECTED | vwap | 22 | 0.034 | 90.9 | 2.551 | 0.1519 | 3.34 | -1.14 | tr/wk 0.0340 < 0.3 |
| overnight | 30m,0.5x | 4 | retest_limit | REJECTED | vwap | 17 | 0.0263 | 70.6 | 1.946 | 0.1943 | 3.3 | -1.49 | tr/wk 0.0263 < 0.3 |
| prior_rth | 15m,0.35x | 2 | reclaim_open | REJECTED | exit3 | 14 | 0.0216 | 42.9 | 1.339 | 0.1546 | 2.16 | -3.09 | tr/wk 0.0216 < 0.3 |
| prior_rth | 15m,0.35x | 2 | retest_limit | REJECTED | vwap | 10 | 0.0155 | 60.0 | 1.424 | 0.0975 | 0.98 | -1.81 | tr/wk 0.0155 < 0.3 |
| prior_rth | 15m,0.35x | 4 | reclaim_open | REJECTED | fixed1r | 19 | 0.0294 | 57.9 | 1.238 | 0.0964 | 1.83 | -3.27 | tr/wk 0.0294 < 0.3 |
| prior_rth | 15m,0.35x | 4 | retest_limit | REJECTED | fixed2r | 15 | 0.0232 | 46.7 | 1.444 | 0.2308 | 3.46 | -3.16 | tr/wk 0.0232 < 0.3 |
| prior_rth | 30m,0.5x | 2 | reclaim_open | REJECTED | - | 0 | 0 | - | - | - | - | - | n<10 trades (all target_types, max n seen=6) |
| prior_rth | 30m,0.5x | 2 | retest_limit | REJECTED | - | 0 | 0 | - | - | - | - | - | n<10 trades (all target_types, max n seen=5) |
| prior_rth | 30m,0.5x | 4 | reclaim_open | REJECTED | vwap | 10 | 0.0155 | 90.0 | 1.651 | 0.0752 | 0.75 | -1.15 | tr/wk 0.0155 < 0.3 |
| prior_rth | 30m,0.5x | 4 | retest_limit | REJECTED | - | 0 | 0 | - | - | - | - | - | n<10 trades (all target_types, max n seen=8) |
| opening_range15 | 15m,0.35x | 2 | reclaim_open | REJECTED | - | 0 | 0 | - | - | - | - | - | n<10 trades (all target_types, max n seen=0) |
| opening_range15 | 15m,0.35x | 2 | retest_limit | REJECTED | - | 0 | 0 | - | - | - | - | - | n<10 trades (all target_types, max n seen=0) |
| opening_range15 | 15m,0.35x | 4 | reclaim_open | REJECTED | - | 0 | 0 | - | - | - | - | - | n<10 trades (all target_types, max n seen=0) |
| opening_range15 | 15m,0.35x | 4 | retest_limit | REJECTED | - | 0 | 0 | - | - | - | - | - | n<10 trades (all target_types, max n seen=0) |
| opening_range15 | 30m,0.5x | 2 | reclaim_open | REJECTED | vwap | 21 | 0.0325 | 76.2 | 0.571 | -0.1111 | -2.33 | -2.98 | PF 0.571 < 1.15 |
| opening_range15 | 30m,0.5x | 2 | retest_limit | REJECTED | vwap | 18 | 0.0278 | 55.6 | 0.519 | -0.2359 | -4.25 | -5.57 | PF 0.519 < 1.15 |
| opening_range15 | 30m,0.5x | 4 | reclaim_open | REJECTED | vwap | 36 | 0.0557 | 80.6 | 0.704 | -0.0638 | -2.3 | -4.37 | PF 0.704 < 1.15 |
| opening_range15 | 30m,0.5x | 4 | retest_limit | REJECTED | exit3 | 32 | 0.0495 | 25.0 | 0.578 | -0.2477 | -7.93 | -10.01 | PF 0.578 < 1.15 |
| prior_close | 15m,0.35x | 2 | reclaim_open | REJECTED | vwap | 19 | 0.0294 | 63.2 | 0.882 | -0.0225 | -0.43 | -2.14 | PF 0.882 < 1.15 |
| prior_close | 15m,0.35x | 2 | retest_limit | REJECTED | fixed2r | 16 | 0.0247 | 31.2 | 0.725 | -0.1941 | -3.11 | -4.89 | PF 0.725 < 1.15 |
| prior_close | 15m,0.35x | 4 | reclaim_open | REJECTED | vwap | 21 | 0.0325 | 66.7 | 0.985 | -0.0026 | -0.05 | -2.09 | PF 0.985 < 1.15 |
| prior_close | 15m,0.35x | 4 | retest_limit | REJECTED | fixed2r | 16 | 0.0247 | 31.2 | 0.725 | -0.1941 | -3.11 | -4.89 | PF 0.725 < 1.15 |
| prior_close | 30m,0.5x | 2 | reclaim_open | REJECTED | - | 0 | 0 | - | - | - | - | - | n<10 trades (all target_types, max n seen=6) |
| prior_close | 30m,0.5x | 2 | retest_limit | REJECTED | - | 0 | 0 | - | - | - | - | - | n<10 trades (all target_types, max n seen=6) |
| prior_close | 30m,0.5x | 4 | reclaim_open | REJECTED | fixed2r | 13 | 0.0201 | 61.5 | 1.44 | 0.1654 | 2.15 | -1.47 | tr/wk 0.0201 < 0.3 |
| prior_close | 30m,0.5x | 4 | retest_limit | REJECTED | vwap | 12 | 0.0186 | 83.3 | 1.929 | 0.1857 | 2.23 | -1.35 | tr/wk 0.0186 < 0.3 |

## Bug-flag cells (PF > 1.8, frozen not optimized)

- {'level_type': 'premarket', 'drive_min': 30, 'atr_mult': 0.5, 'fail_window': 4, 'entry_style': 'reclaim_open', 'target_type': 'vwap', 'n': 16, 'PF': 3.684}
- {'level_type': 'premarket', 'drive_min': 30, 'atr_mult': 0.5, 'fail_window': 4, 'entry_style': 'retest_limit', 'target_type': 'vwap', 'n': 13, 'PF': 3.738}
- {'level_type': 'overnight', 'drive_min': 30, 'atr_mult': 0.5, 'fail_window': 2, 'entry_style': 'reclaim_open', 'target_type': 'vwap', 'n': 14, 'PF': 2.019}
- {'level_type': 'overnight', 'drive_min': 30, 'atr_mult': 0.5, 'fail_window': 2, 'entry_style': 'reclaim_open', 'target_type': 'exit3', 'n': 14, 'PF': 2.05}
- {'level_type': 'overnight', 'drive_min': 30, 'atr_mult': 0.5, 'fail_window': 4, 'entry_style': 'reclaim_open', 'target_type': 'vwap', 'n': 22, 'PF': 2.551}
- {'level_type': 'overnight', 'drive_min': 30, 'atr_mult': 0.5, 'fail_window': 4, 'entry_style': 'reclaim_open', 'target_type': 'fixed1r', 'n': 22, 'PF': 2.33}
- {'level_type': 'overnight', 'drive_min': 30, 'atr_mult': 0.5, 'fail_window': 4, 'entry_style': 'reclaim_open', 'target_type': 'fixed2r', 'n': 22, 'PF': 1.958}
- {'level_type': 'overnight', 'drive_min': 30, 'atr_mult': 0.5, 'fail_window': 4, 'entry_style': 'reclaim_open', 'target_type': 'exit3', 'n': 22, 'PF': 2.175}
- {'level_type': 'overnight', 'drive_min': 30, 'atr_mult': 0.5, 'fail_window': 4, 'entry_style': 'retest_limit', 'target_type': 'vwap', 'n': 17, 'PF': 1.946}
- {'level_type': 'overnight', 'drive_min': 30, 'atr_mult': 0.5, 'fail_window': 4, 'entry_style': 'retest_limit', 'target_type': 'exit3', 'n': 17, 'PF': 1.933}
- {'level_type': 'prior_close', 'drive_min': 30, 'atr_mult': 0.5, 'fail_window': 4, 'entry_style': 'retest_limit', 'target_type': 'vwap', 'n': 12, 'PF': 1.929}
- {'level_type': 'prior_close', 'drive_min': 30, 'atr_mult': 0.5, 'fail_window': 4, 'entry_style': 'retest_limit', 'target_type': 'fixed1r', 'n': 12, 'PF': 1.873}
- {'level_type': 'prior_close', 'drive_min': 30, 'atr_mult': 0.5, 'fail_window': 4, 'entry_style': 'retest_limit', 'target_type': 'fixed2r', 'n': 12, 'PF': 1.836}

## Survivors (if any) -- per-year table (ALL years present, 2016-2026 window highlighted) + overlap vs certified Profile A stream + same-day-R correlation

(none -- no family cleared all kill gates)

## Firewall

`test_eval_config_firewall.py` + `test_funded_config_firewall.py` (bot repo) run BEFORE and AFTER this research task (both pass, unaffected -- this task writes only new files in the ict-nq-framework backtests dir plus this report pair).
