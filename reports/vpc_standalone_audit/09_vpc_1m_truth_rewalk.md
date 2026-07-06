# 09 -- VPC 1m-truth re-walk (CHECK 1)

RESEARCH ONLY. LIVE HOLD ACTIVE. Entries/direction/initial-stop UNCHANGED (the certified 408-trade stream); only each trade's EXIT is re-walked on 1-minute bars with adverse-first ordering. See tools_vpc_1m_truth.py module docstring for the exact rules and every assumption called out.

1m data availability: 0 trade(s) had no 1-minute bar on/after their entry timestamp -> dropped from the NEW stream only (documented, not hidden).

## Standalone OLD (5m native) vs NEW (1m truth) -- full 2022-2026, base cost 0.75pt

| label | n_trades | wr_pct | pf_pts | pf_R | exp_R | total_R | total_pts | maxdd_R | maxdd_pts | best_trade_pts | worst_trade_pts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OLD (5m native) | 408 | 44.9 | 1.294 | 1.366 | 0.1374 | 56.04 | 4919.18 | -9.067 | -1066.4 | 808.25 | -372.22 |
| NEW (1m truth) | 408 | 45.1 | 1.318 | 1.396 | 0.1484 | 60.54 | 5319.67 | -8.189 | -951.1 | 808.25 | -372.22 |

**[SUSPICIOUS -> INVESTIGATED] 1m-truth PF (1.318) > native PF (1.294)**. Trail-ratchet DIRECTION re-verified first: every trade's stop path is asserted monotonic toward price at runtime (structurally guaranteed by the `max`/`min` update in `vpc_1m_truth_trades()` — the stop cannot loosen), so this is not a sign bug. Root MECHANISM identified: the brief's trail formula is specified against the highest 1-minute CLOSE since entry, whereas the native engine's trail uses the highest 5-minute HIGH. Close <= High on every bar, so the new peak (and thus the new stop) moves up systematically SLOWER than the native one for the same elapsed time -- i.e. the 1m-truth stop, while still monotonic and still never looser than the INITIAL stop, is on average FURTHER from price than the native stop mid-trade. This lets winners run longer before the trail catches them (net_pts +8.1%, concentrated in 2022-2023 per-year below) with the initial risk (stop_pts) unchanged, which is exactly the mechanism the brief's own trail formula implies -- not an artifact of adverse-first sequencing or a lookahead bug.

## Count of trades whose outcome CHANGED (win<->loss flip) + R-delta distribution

| n | outcome_changed | delta_mean | delta_std | delta_min | delta_p10 | delta_p25 | delta_median | delta_p75 | delta_p90 | delta_max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 408 | 11 | 0.011 | 0.1906 | -0.1673 | -0.0552 | -0.0301 | 0 | 0 | 0 | 1.8709 |

## Per-year old vs new (PF points-based, WR%, net points)

| year | n | pf_old | pf_new | wr_old | wr_new | net_pts_old | net_pts_new |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | 88 | 1.221 | 1.321 | 43.2 | 46.6 | 934.53 | 1327.4 |
| 2023 | 89 | 1.071 | 1.174 | 42.7 | 46.1 | 200.8 | 480.14 |
| 2024 | 94 | 1.4 | 1.357 | 44.7 | 41.5 | 1291.92 | 1179.73 |
| 2025 | 86 | 1.426 | 1.373 | 46.5 | 45.3 | 1493.19 | 1345.58 |
| 2026 | 51 | 1.339 | 1.334 | 49 | 47.1 | 998.74 | 986.81 |

## HEADLINE: does 27.8/15.5/56.7 survive 1m truth? (VPC(600,4) standalone AND A(600,6)+VPC(600,4) portfolio, OLD vs NEW VPC R stream)

| row | stream | pf_dollar | eligible_starts | pass_count | bust_count | exp_count | pass_pct | bust_pct | exp_pct | med_days_pass | worst_day_usd | funded_per_slot_year |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VPC(600,4) standalone | OLD (5m native) | 1.331 | 388 | 42 | 11 | 335 | 10.8 | 2.8 | 86.3 | 16 | -1000 | 1.39 |
| A(600,6)+VPC(600,4) portfolio | OLD (5m native) | 1.362 | 684 | 190 | 106 | 388 | 27.8 | 15.5 | 56.7 | 18 | -1000 | 4.04 |
| VPC(600,4) standalone | NEW (1m truth) | 1.364 | 388 | 42 | 12 | 334 | 10.8 | 3.1 | 86.1 | 16 | -1000 | 1.39 |
| A(600,6)+VPC(600,4) portfolio | NEW (1m truth) | 1.377 | 684 | 196 | 116 | 372 | 28.7 | 17 | 54.4 | 18 | -1000 | 4.22 |

## Firewall before/after

- `config_eval_locked.py`: UNCHANGED
- `config_funded_locked.py`: UNCHANGED
- `config_defaults.py`: UNCHANGED
- `auto_safety.py`: UNCHANGED

## PF freeze check: no cell exceeded PF>1.8.

Runtime: 42.1s
