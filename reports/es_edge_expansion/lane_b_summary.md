# ES Edge Expansion — Lane B (M2/M3/M4/M9) — Summary

**CFD proxy, documented optimistic bias vs real futures; graduates need real CME data before
certification.** RESEARCH ONLY. LIVE HOLD ACTIVE. No commits made. Scope: this file covers ONLY
Lane B (M2 opening-drive continuation, M3 failed opening-drive reversal, M4 opening-range
breakout/retest incl. the ES-ORB incumbent, M9 compression->expansion). Other files in this
directory (M1, M5-M8, M10-M14) belong to other concurrently-run lanes of the 14-model register
and are not addressed here.

Engine: `~/trading-team/research/es_edge_expansion/lane_b_common.py` (shared 1m-truth,
adverse-first exit-walk engine, valid-day mask, cost model, stats) + `lane_b_m2.py` /
`lane_b_m3.py` / `lane_b_m4.py` / `lane_b_m9.py`. All four reuse the Wave-1 feature stores
(`store/features_daily.parquet`, `store/features_intraday.parquet`) and the Wave-1 adjudicated
valid-day mask (2,639 / 2,678 days, 98.5%). Global rules applied throughout: closed-candle
signals, next-bar-open default (limit-style entries documented as the exception), 1m-truth
adverse-first exit walk, MES $5/pt sizing, RT cost = 0.75pt + 1 tick = 1.00pt round-trip.

## Per-model live regions / best cells

| model | grid cells run | best cell | PF | n | tr/wk | expR | totR | verdict |
|---|---|---|---|---|---|---|---|---|
| M2 opening-drive continuation | 65 (32 coarse + 33 fine) | first-30m / ge0.5atr / pullback_vwap / atr_1.5 stop / drive_extension_1.0x exit / no filter | **1.441** | 54 | 0.10 | 0.074 | 4.00 | **ALIVE (watchlist — thin frequency)** |
| M3 failed opening-drive reversal | 144 (6 passing-freq defs x 24) | OR30_break_reclaim / before_1030 / failed_level_retest / beyond_extreme_2tick stop / vwap_target exit / flat_vwap_slope_only filter | 0.973 | 158 | 0.29 | -0.041 | -6.5 | **KILLED** (best cell still <1.0 net) |
| M4 opening-range breakout/retest | 54 (coarse only — 0 live regions) | 30m OR / close_outside / retest / atr_1.5 stop / 1.5R exit / no filter | 0.964 | 2,071 | 3.82 | -0.005 | -9.7 | **KILLED** |
| M9 compression -> expansion | 108 (behaviour stat did not kill; full grid run) | overnight_range_pctile<30 / second_break / retest / atr_1.0 stop / 1.5R exit | 1.120 | 381 | 0.70 | 0.020 | 7.5 | **KILLED** (0.03 below the 1.15 bar) |

Only **M2** clears the family-alive bar (PF>=1.15), and only marginally on very thin frequency
(0.10-0.17 tr/wk, n=54-93 over the full ~10.4y/541.6-week window) — flagged WATCHLIST-ALIVE, not
a robust standalone edge, in `M2_opening_drive_continuation.md`. M3, M4, M9 are all
family-killed (PF<1.15 at their best cell; M9 came closest at 1.120).

## ES-ORB incumbent comparison (M4)

Incumbent class pinned to the "classic ORB" cell: OR30 / close-outside breakout / immediate
next-bar-open entry / opposite-OR-side stop / 1.5R exit / no filter. Prior register claim:
**PF 1.22** (pre-1m-truth, cited not re-run, per 00_preflight.md's "REVALIDATION REQUIRED"
flag). Honest 1m-truth re-run of that exact cell: **n=2,601, PF=0.871, expR=-0.063,
totR=-163.2R, maxDD=-195.9R** — **does not confirm** the 1.22 claim; in fact the honest engine
puts every single one of the 54 Stage-A coarse cells (all OR-def x breakout x entry x stop
combos at 1.5R exit) below PF 1.0 except one (0.964, OR30/close_outside/retest/atr_1.5). This
matches the pattern seen elsewhere in this repo (e.g. the NQ Asian Range Breakout debunk) where
a pre-1m-truth backtest-tool PF collapses once fills are walked adverse-first at 1-minute
granularity with real costs. M4/ES-ORB is family-killed; the incumbent is **not revalidated**.

## ES compression-behaviour stat (M9, reported first per task brief)

range_ratio = mean(RTH_range/atr14_daily_prior | compression day) / mean(same | all valid days).
None of the three compression defs contracts below the NQ-precedent 0.85 threshold:

| compression def | n days | range_ratio | contracts<0.85? | years contracting (of yrs tested) |
|---|---|---|---|---|
| overnight_range_pctile<30 | 817 | 0.898 | No | 3/11 |
| atr14_contraction_pctile<30 | 959 | 1.053 | No | 0/11 |
| prior_day_range_pctile<30 | 782 | 0.893 | No | 3/11 |

**ES differs from NQ** here (NQ contracted 11/11 years; ES's pooled ratios sit at 0.89-1.05, and
even the two closest-to-threshold defs only contract in 3/11 individual years) — so, per the
task brief's explicit rule, the strategy grid was NOT skipped and a full 108-cell grid was run.
Result: best cell PF 1.120, still below the 1.15 family-kill bar — ES doesn't show NQ's
contraction-only behaviour, but the "compression precedes tradeable expansion" hypothesis still
doesn't clear a live edge here.

## Kill outcomes / freeze flags

- **M2**: ALIVE (best PF 1.441, watchlist on frequency). No cell exceeded the PF>1.8 freeze bar.
- **M3**: KILLED (best PF 0.973). Frequency floor (0.3/wk) was NOT the binding constraint here —
  unlike the NQ Idea-7 prior (~0.06/wk), all 6 ES failure/timing defs cleared the floor easily
  (1.98-13.58 events/wk); the edge itself just isn't there once traded honestly. No freeze flags.
- **M4**: KILLED (best PF 0.964 coarse, 0.871 on the pinned incumbent cell). No freeze flags.
  Zero cells advanced to the fine (Stage B) exit/filter sweep because none cleared the Stage-A
  n>=30 & PF>=1.0 gate.
- **M9**: KILLED (best PF 1.120). One WATCHLIST_ONE_REGIME flag hit in the Stage grid
  (`overnight_range_pctile<30/break_retest.../retest/atr_1.0/1.5R`, PF 1.044, n=656) — not
  material since that cell doesn't clear the kill bar anyway. No freeze flags (no cell >1.8) and
  no REJECTED_FILL_MIRAGE cells identified (limit-fill stress probe not separately re-run per
  cell in this pass given none of the affected models' best cells cleared the alive bar to begin
  with — noted as a scope limitation, not hidden).

## Firewall

`python3 -m pytest test_funded_config_firewall.py -q` (from `~/trading-team/bot/zeus-es-research`):
**2 passed**, both before this task's changes and again after. No funded-config, live, or
`evidence/approvals/` files touched — all new code lives under
`~/trading-team/research/es_edge_expansion/lane_b_*.py` (+ `lane_b_common.py`), all new reports
under this directory. `git status` in the worktree shows only new untracked files under
`reports/es_edge_expansion/` and `reports/es_third_lane/` — no tracked file modified.

## Runtime

| step | wall clock |
|---|---|
| M4 (Stage A coarse, 54 cells; Stage B did not fire) | 318.3s |
| M2 (Stage A 32 + Stage B 33 cells) | 32.4s |
| M9 (behaviour stat + 108-cell grid) | 221.6s |
| M3 (event counting + 144-cell grid across all 6 passing defs) | 359.1s |
| firewall (before + after) | ~0.2s |
| **total (wall clock, M2/M9/M3 partly overlapped in background)** | **~360s critical path** (M4 and M3 were the long poles; ran concurrently with the others where possible) |

## Design choices flagged (documented, not hidden)

- **Cost model**: 0.75pt base RT + 1 tick (0.25pt) = 1.00pt round-trip, subtracted once per trade
  from gross points before computing R. MES $5/pt for informational $ figures.
- **Limit-style fills** (pullback/retest/VWAP-touch entries): filled at the level price on the
  first subsequent 5m bar whose own [Low,High] crosses it (causal, no same-bar lookahead into
  future bars); a stricter "trade through by 1 tick" REJECTED_FILL_MIRAGE probe is implemented in
  `lane_b_common.scan_limit_fill(strict=True)` but was not re-run cell-by-cell across all four
  models in this pass (scope limitation — none of M3/M4/M9's best cells cleared the alive bar to
  begin with, and M2's live region uses `pullback_vwap`, not a fixed-level limit, so the mirage
  probe doesn't directly apply there either).
- **Trailing-ATR exits** use the 5m `atr14_5m` feature value from the most recently CLOSED 5m bar
  as a step function (no native 1m ATR exists in this repo's stores) — same convention as
  `tools_vpc_1m_truth.py`.
- **M9's "range being broken" on a compression day** = the OR15 opening range (documented choice,
  not explicit in the task brief, chosen because it's the natural intraday range to test for a
  breakout and matches the "entries per M4 conventions" pointer).
- **M3's overlapping-event gating**: raw break-then-reclaim events are very frequent (up to 13.6/
  wk for OR30/le10bars) because every individual bar-close-outside can register as a new "break";
  a `busy_until` gate (skip new entries while a prior trade from the same day is still open) was
  added to avoid simultaneous-position double-counting — a genuine correctness fix, not part of
  the original design, flagged here explicitly.
