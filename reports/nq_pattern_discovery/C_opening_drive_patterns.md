# NQ Pattern Discovery — Workstream C: Opening-Drive Classes

**RESEARCH ONLY — DISCOVERY DISTRIBUTIONS, NOT A STRATEGY.** No entries/stops/backtests are
constructed here. This lane maps WHERE the raw opening-drive / pullback-continuation behaviour
lives; it does not rebuild a strategy. **Prior tombstones (context, not re-litigated)**: KRONOS
continuation (next-bar entry) PF 0.97 — dead; Idea-7 failed-breakout lane — dead on frequency;
VPC = the surviving pullback-continuation implementation elsewhere in this repo.

Script: `~/trading-team/research/nq_pattern_discovery/C_opening_drive_patterns.py` (+
`discovery_common.py`). Output: `C_opening_drive_patterns.csv` (997 rows, same long-format
schema as workstream A). Data: 2016-01-04 -> 2026-05-25, Dukascopy spine.

## Drive definition

For each first-{5,10,15,30}-minute window N (k = N/5 5m-bars from RTH open):
`ret_N = Close[bar k-1] - RTH Open`. **Strong** = `|ret_N| >= 0.35 * atr14_daily_prior` AND the
window's own FINAL 5m bar closes in the same direction as `ret_N` (close-in-direction
confirmation — **assumption/operationalization**, the brief did not give a precise bar-level
rule). Weak = everything else. The four N values are four **separate parallel** classifications
(a day can be strong at N=30 and not at N=5) — not nested.

**Strong-drive frequency drops sharply as N shrinks** (0.35x daily-ATR is a demanding bar over
only 5-10 minutes): N=5m has just **36** strong-drive days across 11 years (~3.3/yr); N=10m 167;
N=15m 200; N=30m 321. This bounds every downstream N=5m/10m result to small-n, descriptive-only
reads (flagged throughout).

## Level-touch classes (touched by the drive's OWN path through the window's end, same side as
## the drive direction only)

`into_pdh_pdl` (drive's High>=PDH / Low<=PDL), `into_onh_onl` (vs overnight high/low),
`into_vwap_band` (path intersects VWAP +/- 0.05*ATR — **assumption**, band width not specified
in the brief), `clean_air` (none touched), `all_strong_drives` (the pooled union / baseline).
Classes are NOT mutually exclusive except `clean_air`.

**Degenerate finding, flagged, not a bug**: `into_vwap_band` is numerically IDENTICAL to
`all_strong_drives` at every N (same n, same every metric, to 3dp) — see CSV. Verified this is
real, not a computation error: session VWAP is a same-day cumulative average anchored at 09:30,
so within the first 5-30 minutes of the session it sits essentially on top of price by
construction — a drive originating at the open will trivially intersect its own contemporaneous
VWAP band. **The VWAP-band touch test, as specified, cannot discriminate anything within the
drive window itself** at these short horizons; it would need to be tested against a LATER
window's VWAP (a different question) to be informative. Same root cause explains
`failure_touched_vwap_rate = 1.000` in every single subset below (a full-retrace-by-11:30 day
trivially recrosses the still-open-anchored VWAP on the way back) — also degenerate/uninformative,
not flagged as a real 100%-probability finding.

## Top 10 strongest CONSISTENCY-FLAGGED cells

All 10 cells that clear the bar (pooled n>=200, same side of 50% in >=8/11 years) are `hold_rate`
/ `failure_rate` pairs at N=15m and N=30m (N=5m/10m never reach n=200):

| # | window | class | metric | value | n | years consistent |
|---|---|---|---|---|---|---|
| 1 | drive_30m | all_strong_drives | hold_rate | **0.860** | 321 | 11/11 |
| 2 | drive_30m | all_strong_drives | failure_rate | **0.146** | 321 | 11/11 |
| 3 | drive_30m | into_vwap_band *(≡ #1, degenerate)* | hold_rate | 0.860 | 321 | 11/11 |
| 4 | drive_30m | into_vwap_band *(≡ #2, degenerate)* | failure_rate | 0.146 | 321 | 11/11 |
| 5 | drive_30m | into_onh_onl | hold_rate | 0.859 | 255 | 11/11 |
| 6 | drive_30m | into_onh_onl | failure_rate | 0.153 | 255 | 10/11 |
| 7 | drive_15m | all_strong_drives | hold_rate | **0.810** | 200 | 11/11 |
| 8 | drive_15m | all_strong_drives | failure_rate | **0.290** | 200 | 11/11 |
| 9 | drive_15m | into_vwap_band *(≡ #7, degenerate)* | hold_rate | 0.810 | 200 | 11/11 |
| 10 | drive_15m | into_vwap_band *(≡ #8, degenerate)* | failure_rate | 0.290 | 200 | 11/11 |

Collapsing the degenerate duplicates (see above), the genuinely distinct findings are 3 pairs:
**strong 30-min opening drives hold their direction into the RTH close 86% of the time** (only
15% fully retrace by 11:30), a result essentially unchanged whether the drive touched the
overnight high/low or not (85.9% hold either way); **strong 15-min drives hold 81% of the time**
(29% fail). Both are large-effect, 11/11-year-stable findings — the strongest, cleanest signal
in this workstream.

**Just below the n=200 bar, not flagged but notable**: `continuation_after_pullback_rate` is
high and consistent everywhere it can be measured — 83-96% across every N/class (e.g. drive_30m
all_strong_drives: 83.5%, n=176), i.e. once a strong-drive day retraces >=38% of its own move,
it goes on to make a NEW extreme beyond the original drive before 11:30 in the large majority of
cases. This is arguably the single strongest directional pattern found in workstream C, but
every one of its n's (24-176) sits under 200 (the >=38%-retrace subset is smaller than the
parent strong-drive population by construction), so it is reported here as an unflagged,
descriptive-only observation, not a certified consistency-flagged cell.

## 5 most decisively null (or degenerate) findings

| finding | value(s) | n |
|---|---|---|
| `into_vwap_band` class = `all_strong_drives` class, identical, every N | tautological (see above) | 36-321 |
| `failure_touched_vwap_rate` = 1.000 in every subset | tautological (see above) | 5-61 |
| `drive_5m` `failure_rate`, all_strong_drives/into_vwap_band | 0.500 (coin flip) | 36 |
| `drive_30m` hold_rate barely moves across classes: all_strong 0.860 / onh_onl 0.859 / pdh_pdl 0.852 / vwap_band 0.860 | spread <1pp | 169-321 |
| `drive_10m` `into_pdh_pdl` `failure_rate` (0.391, n=69) vs `all_strong_drives` at same N (0.365, n=167) | not distinguishable given n<200 | 69-167 |

Reading: **which level the drive's path happens to touch (PDH/PDL vs ONH/ONL vs neither) does
NOT meaningfully change the drive's own hold/failure outcome** once it has already qualified as
strong — the level-touch classification, as specified, adds little discriminating power beyond
the drive-strength threshold itself. The N=5m bucket is too thin (n=36) to say anything beyond
"consistent with a coin flip."

## Limitations / assumptions (flagged, not silently trusted)

1. "Close-in-direction" (the strong-drive confirmation rule) and the VWAP-band width
   (0.05x ATR) are both this lane's own operationalization of brief language that did not fully
   specify a bar-level rule — documented above, not silently assumed correct.
2. "Opposite OR side" for the failure-destination check uses the DRIVE WINDOW ITSELF as the OR
   reference (does price cross beyond the drive's own opposite extreme, a stronger condition
   than a full retrace to open) — a specific, documented choice among several plausible readings
   of "opposite OR side."
3. All continuation/pullback/failure metrics are capped at the 11:30 ET cutoff (bars with
   `minutes_since_open <= 115`) per the brief's own 11:30 anchor for pullback-depth and
   continuation-after-pullback; "additional run" is therefore also capped there, not measured to
   end of day.
4. N=5m and N=10m strong-drive counts (36, 167) are too small for the class-level splits to be
   more than descriptive — flagged inline in every relevant table above rather than omitted.
5. Consistency flag is a descriptive robustness screen (>=8/11 years same side of 50%, pooled
   n>=200), not a significance test — same caveat as workstream A.

## Firewall + runtime

- Firewall (`python3 -m pytest test_funded_config_firewall.py -q`, bot repo): **before 2 passed
  in 0.07s / after 2 passed in 0.07s** — no drift. (Same before/after pair covers both workstream
  A and C scripts, run back-to-back in a single session — no bot-repo file was touched between
  them.)
- `C_opening_drive_patterns.py` runtime: **~1.5s** wall clock (cold cache).
- Combined workstream A+C runtime: **~5.7s** wall clock, well inside any reasonable budget.
