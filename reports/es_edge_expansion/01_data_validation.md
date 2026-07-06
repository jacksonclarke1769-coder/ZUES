# ES Edge Expansion — 01: Data Validation

**CFD proxy, documented optimistic bias vs real futures; graduates need real CME data before certification.**

Source: `ES_1m_24h.parquet (Dukascopy 24h ET CFD-index proxy for ES)`. Verdict: **STOP** — RTH density <95% on 10.42% of days (>5% threshold)

## Date range
- 2013-12-31 11:00:00-05:00 -> 2026-05-25 12:00:00-04:00  (3,734,525 1m bars)

## Missing days (vs NQ trading calendar)
- ES RTH trading days: 3233  ·  NQ RTH trading days: 3233
- Days present in NQ but missing from ES: 0
- Days present in ES but missing from NQ: 0

## Bar density
- RTH (09:30-16:00 ET, 390 min expected/day): mean density 97.1%, median 100.0%, p10 94.6%
- Days with RTH density < 95%: 337 / 3233 (10.42%)
- 24h day density (vs this feed's own p90-day ceiling of 1335 bars/day): mean 86.0%, median 96.4%  (documented ~75% 24h-density range is expected/normal for this feed; RTH is the number that matters)
- Per-session density (named session windows, engine/data.py SESSIONS):
  - asia: mean 90.8%, median 97.5%, p10 71.9%
  - london: mean 96.2%, median 100.0%, p10 86.7%
  - ny_am: mean 99.2%, median 100.0%, p10 99.3%
  - ny_lunch: mean 97.6%, median 100.0%, p10 94.2%
  - ny_pm: mean 98.4%, median 100.0%, p10 95.6%

### Composition of the sub-95%-RTH-density days
- Total flagged: 337
  - holiday-adjacent (self/prev/next day is a full-closure holiday): 122
  - half-day (day-after-Thanksgiving / Dec 24): 0
  - recurring Dec-30 vendor year-end early cutoff (feed stops ~11:00 ET every Dec 30, confirmed by direct inspection -- vendor artifact, not a market closure): 8
  - UNEXPLAINED (neither holiday, half-day, nor Dec-30 cutoff -- genuine partial-coverage days in this feed): 207
    - sample: ['2014-02-01', '2014-02-22', '2014-03-19', '2014-04-27', '2014-04-29', '2014-04-30', '2014-05-04', '2014-05-05', '2014-05-06', '2014-05-12', '2014-05-13', '2014-05-14', '2014-05-19', '2014-05-21', '2014-05-22']

## Duplicate timestamps
- Raw file `ES_1m_24h.parquet`: 3,734,525 rows, 0 duplicate timestamps pre-dedup (load_spine() already de-dupes (keep='first'); this counts pre-dedup raw file dupes.)

## TZ / DST consistency (4 boundary-date spot-checks)
- Method: RTH-open (09:30 ET) bar's UTC offset, last trading day before vs. first trading day after each Sunday DST changeover (the changeover instant itself is inside CME's Sun 02:00 ET closed window, so a same-day phantom-bar test would be trivially uninformative).
- Overall: PASS
  - 2019-03-10 (spring_forward): before=2019-03-08 09:30:00-05:00 (offset -1 day, 19:00:00, expect -1 days +19:00:00) -> after=2019-03-11 09:30:00-04:00 (offset -1 day, 20:00:00, expect -1 days +20:00:00)  -> PASS
  - 2023-03-12 (spring_forward): before=2023-03-10 09:30:00-05:00 (offset -1 day, 19:00:00, expect -1 days +19:00:00) -> after=2023-03-13 09:30:00-04:00 (offset -1 day, 20:00:00, expect -1 days +20:00:00)  -> PASS
  - 2019-11-03 (fall_back): before=2019-11-01 09:30:00-04:00 (offset -1 day, 20:00:00, expect -1 days +20:00:00) -> after=2019-11-04 09:30:00-05:00 (offset -1 day, 19:00:00, expect -1 days +19:00:00)  -> PASS
  - 2023-11-05 (fall_back): before=2023-11-03 09:30:00-04:00 (offset -1 day, 20:00:00, expect -1 days +20:00:00) -> after=2023-11-06 09:30:00-05:00 (offset -1 day, 19:00:00, expect -1 days +19:00:00)  -> PASS

## Holiday / half-day detection
- Short 24h-days flagged (< 50% of p90 day-length): 83, confirmed via `is_market_holiday`: 24

## Continuous-contract note
- CFD index feed, NOT a rolled futures continuation: NO contract-roll gaps to detect/splice (a convenience), but futures-specific roll/basis behavior is UNTESTED here and needs separate validation once real CME data is available.

## Outlier candles (5m, range > 20x rolling ATR14)
- 0 / 780,757 bars flagged (0.0000%)

## Zero/near-zero volume bars
- 1m 24h: 2.42%  ·  1m RTH: 1.73%
- 5m 24h: 2.30%  ·  5m RTH: 1.66%

## Gaps analysis (intraweek, excludes weekend/holiday closures >=24h)
- 112128 gaps > 1min (3,734,524 bar-to-bar transitions checked); p50=2.0min, p99=106.0min, max=983.0min
- Weekend/holiday closures (>=24h gaps): 647

Runtime: 6.1s

## AUDITOR ADJUDICATION (2026-07-06)
The mechanical STOP is resolved as **USABLE-WITH-MASK**: (a) the unexplained-thin concentration is
2014 (outside window) + **2017 (88 days — genuine vendor coverage gap; per-year stats must show
valid-day counts)**; (b) most other years' thin days are legitimate half-days (early close ⇒ ~54%
density — expected, models handle via earlier EOD-flat, not exclusion). REQUIREMENT for all model
lanes: VALID-DAY MASK = RTH density ≥95% OR half-day profile (density 0.45-0.62 with last bar
≤13:05 ET); signals generated on valid days only; per-year tables carry n_valid_days. The CFD
proxy caveat (optimistic bias) remains on every number; graduates need real CME data.
