# NQ Pattern Discovery — Workstream A: Time-of-Day Conditional Behaviour

**RESEARCH ONLY — DISCOVERY DISTRIBUTIONS, NOT A STRATEGY.** No entries/stops/backtests are
constructed here. This is raw conditional/unconditional statistical behaviour of NQ 5m bars
across time-of-day windows, 2016-01-04 -> 2026-05-25 (Dukascopy spine, `engine/data.py`,
`load_spine("NQ","5m")`). Graduation decisions (does any of this become a strategy candidate)
belong to the auditor, not this lane.

Script: `~/trading-team/research/nq_pattern_discovery/A_time_of_day_behaviour.py` (+
`discovery_common.py`). Output: `A_time_of_day_behaviour.csv` (4,549 rows, long format:
`section, window, condition_type, condition_value, horizon, metric, year, value, n,
events_per_week, consistency_flag, years_consistent, pooled_n`).

## Windows analyzed

- **8 x 15-min RTH windows**, 09:30 -> 11:30 ET (`0930_0945` ... `1115_1130`).
- **4 named sessions** (ONE anchor per day at the session's own start, not subdivided):
  `pre_ny` 08:00-09:30 ET (**assumption** — not in the pinned `engine/data.py` SESSIONS dict,
  which has no `pre_ny` entry; documented choice: the 90 minutes before RTH open), `london`
  02:00-05:00 ET (matches `engine/data.py` SESSIONS exactly), `asia` 18:00-00:00 ET (matches
  exactly), `power_hour` 13:30-15:00 ET (matches `SESSIONS["ny_pm"]` exactly).
- **`control_24h_all_bars`**: every 5m bar in the full continuous spine, any time of day — the
  "no time-of-day conditioning" baseline. Flagged limitation: heavily overlapping windows
  (adjacent 5m bars share almost all of their forward path), so this is a distributional
  baseline, not an independent-sample statistic.

Forward stats measured from the window/session **start** (anchor Open). `valid_h` guards every
forward-return computation against weekend/holiday/thin-session gaps (only counted if the
elapsed time to the +k-bar mark is exactly right, never a fake multi-hour move). Per-cell
reporting: n, events/week, mean/median return (pts + ATR-normalized), MFE/MAE p25/50/75 (pooled
only), **up-fraction per year 2016-2026 + CONSISTENCY FLAG** (pooled up-fraction's side of 50%
matches in >=8/11 years, pooled n>=200).

## Unconditional baseline (30m horizon, selected columns)

| window | mean ret (pts) | up-fraction | MFE p50 | MAE p50 |
|---|---|---|---|---|
| 0930_0945 | +1.49 | 0.527 | 23.5 | 22.0 |
| 0945_1000 | +1.58 | 0.533 | 19.7 | 19.4 |
| 1000_1015 | +0.15 | 0.538 | 17.6 | 18.0 |
| 1015_1030 | +0.77 | 0.544 | 17.5 | 15.1 |
| 1030_1045 | -0.74 | 0.527 | 16.1 | 15.2 |
| 1045_1100 | -0.36 | 0.526 | 14.0 | 15.9 |
| 1100_1115 | +1.17 | 0.552 | 14.8 | 13.2 |
| 1115_1130 | +0.57 | 0.523 | 13.6 | 13.0 |
| pre_ny | +0.38 | 0.509 | 8.6 | 8.5 |
| london | +0.58 | 0.511 | 5.5 | 6.3 |
| asia | +1.32 | 0.528 | 7.4 | 6.5 |
| power_hour | +0.39 | 0.521 | 11.3 | 10.3 |
| control_24h_all_bars | +0.23 | 0.520 | 8.1 | 7.8 |

No unconditional window/session clears the up-fraction consistency bar on its own (all sit in
the 0.49-0.55 range, close to the 0.52 control baseline) — directional tilt at the unconditional
level is thin everywhere; the signal in this workstream is almost entirely in the **conditional**
splits below.

## Top 10 strongest CONSISTENCY-FLAGGED cells

| # | section | window | condition | horizon | value | n | years consistent |
|---|---|---|---|---|---|---|---|
| 1 | A_ny_open_failure | ny_open_1000_check | (day-level) | to_1000 | **failure_rate 0.210** | 2,671 | 11/11 |
| 2 | A_cond_first15m_dir | 1015_1030 | first15m up | 60m | up-frac 0.578 | 1,412 | 11/11 |
| 3 | A_cond_first5m_dir | 1100_1115 | first5m up | 60m | up-frac 0.577 | 1,381 | 11/11 |
| 4 | A_cond_first15m_dir | 1100_1115 | first15m up | 15m | up-frac 0.574 | 1,414 | 11/11 |
| 5 | A_cond_or30_break | 1030_1045 | break_up | 30m | up-frac 0.574 | 671 | 10/11 |
| 6 | A_cond_or30_break | 1100_1115 | inside_or | 60m | up-frac 0.570 | 1,223 | 11/11 |
| 7 | A_cond_first15m_dir | 1100_1115 | first15m up | 60m | up-frac 0.570 | 1,413 | 11/11 |
| 8 | A_cond_disp_1000_1015 | 1100_1115 | displaced=yes | 15m | up-frac 0.569 | 371 | 8/11 |
| 9 | A_cond_first5m_dir | 1100_1115 | first5m up | 15m | up-frac 0.568 | 1,384 | 11/11 |
| 10 | A_cond_first15m_dir | 1100_1115 | first15m up | 30m | up-frac 0.566 | 1,414 | 11/11 |

**Reading**: #1 is by far the dominant effect — the day's first-15m direction is only reversed by
10:00 in ~21% of days (79% "hold"), stable 17-25% every single year 2016-2026 (see per-year table
in the CSV: `A_ny_open_failure` rows). #2-10 are all variants of the same modest, robust
continuation tilt: conditioning on an "up" early move (first-5m, first-15m, OR30-break-up)
nudges later-window up-fraction from the ~0.52 baseline to ~0.56-0.58 — real and 8-11/11-year
consistent, but small in magnitude (a ~6-8pp tilt off a coin flip), concentrated in the
**1030-1130** windows (late in the ICT `ny_am` session). No cell in this list exceeds ~58%
up-fraction — this is a mild-continuation regime, not a strong-momentum one.

## VWAP mean-reversion probability (P(touch VWAP within 30/60m) | |dist| >= 0.5 ATR at window start)

| window | n (30m pop) | P(touch) 30m | n (60m pop) | P(touch) 60m |
|---|---|---|---|---|
| 0945_1000 | 6 | 0.167 | 6 | 0.500 |
| 1000_1015 | 22 | 0.273 | 22 | 0.455 |
| 1015_1030 | 25 | 0.080 | 25 | 0.280 |
| 1030_1045 | 38 | 0.053 | 38 | 0.105 |
| 1045_1100 | 52 | 0.019 | 52 | 0.115 |
| 1100_1115 | 58 | 0.034 | 58 | 0.155 |
| 1115_1130 | 73 | 0.014 | 72 | 0.111 |

**No consistency flag fires anywhere in this table — n never reaches 200.** The brief's premise
(does MR-to-VWAP probability rise for 10:30+ windows) doesn't get a clean answer here because the
qualifying population (|vwap_dist_atr| >= 0.5 at window start) is itself rare and shrinking the
earlier in the session you look: VWAP is a same-session cumulative average anchored at 09:30, so
it mechanically hasn't had time to diverge 0.5 ATR from price by 09:45-10:15 (n=6-25) — it only
becomes a meaningfully-sized population by 10:30+ (n=38-73), and even then stays under the n=200
bar. Read as: **the 0.5-ATR-distance condition is itself the dominant time-of-day effect here**
(it's essentially unobservable before ~10:30), and the population that does qualify shows *falling*,
not rising, touch-probability into late morning — the opposite of the brief's hypothesized
direction, but on samples too thin to flag either way.

## NY-open first-move failure rate (day-level, standalone)

Failure (first-15m direction reversed by the 10:00 price check): pooled **21.0%** (n=2,671),
per-year range 17.1%-25.2%, **11/11 years same side of 50%** — see table in
`A_ny_open_failure` rows of the CSV. This is the single strongest, cleanest cell in this
workstream: the RTH open's first 15 minutes is a genuinely durable directional anchor for the
following 45 minutes, every year in the 11-year sample.

## 5 most decisively null cells

| section | window | condition | horizon | value | n |
|---|---|---|---|---|
| A_cond_first15m_dir | 1045_1100 | first15m up | 15m | up-frac 0.501 | 1,414 |
| A_unconditional | london | (unconditional) | 60m | up-frac 0.501 | 2,488 |
| A_cond_first5m_dir | 1045_1100 | first5m down | 15m | up-frac 0.496 | 1,281 |
| A_unconditional | pre_ny | (unconditional) | 15m | up-frac 0.504 | 2,668 |
| A_cond_or30_break | 1045_1100 | inside_or | 15m | up-frac 0.496 | 1,304 |

All five sit within 0.5pp of 50%, on large samples (n=1,281-2,668) — genuinely no directional
edge, not a thin-sample artifact. Notably, **the 1045_1100 window is the one place in the whole
09:30-11:30 block where the conditional continuation tilt (seen everywhere else) disappears**:
first-5m, first-15m and OR30-inside conditioning all land almost exactly on 50% there, unlike
every neighboring window. `london` and `pre_ny` also show no unconditional directional tilt on
very large samples — consistent with the "no meaningful edge outside RTH-adjacent windows"
reading from the unconditional table above.

## Limitations / assumptions (flagged, not silently trusted)

1. `pre_ny` (08:00-09:30 ET) is this lane's own definition — not in the pinned
   `engine/data.py` SESSIONS dict (which has no `pre_ny` entry despite a stale prior-session
   preflight note claiming one was added; grepped, confirmed absent).
2. Consistency flag is a descriptive robustness screen (same side of 50% in >=8/11 years, pooled
   n>=200), **not** a significance test — no correction for the heavy overlap between adjacent
   forward-return windows (the "control" baseline in particular reuses every 5m bar, so its
   pooled n (~635k) is not ~635k independent observations).
3. VWAP mean-reversion table: no cell reaches the n>=200 bar; read as descriptive, not flagged.
4. First-5m/first-15m/OR30-break/displacement conditionals are scoped to RTH windows only
   (documented in the script docstring) — applying them to pre_ny/london/asia/power_hour would
   be causally backwards (those sessions occur before the RTH day's own first-5m/15m exist) or
   meaningless (OR30 is an RTH-day concept).
5. "10:00-10:15 displacement" rolling-mean-body baseline is defined as the SAME window's own
   trailing 20-trading-day body size (not a within-day bar-count rolling mean) — the brief did
   not fully specify this; documented choice.

## Firewall + runtime

- Firewall (`python3 -m pytest test_funded_config_firewall.py -q`, bot repo): **before 2 passed
  in 0.07s / after 2 passed in 0.07s** — no drift.
- `A_time_of_day_behaviour.py` runtime: **~4.2s** wall clock (cold cache, full spine load +
  4,549-row CSV).
