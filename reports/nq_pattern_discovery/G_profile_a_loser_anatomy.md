# G — Profile A Loser Anatomy (the program's crown jewel)

RESEARCH ONLY. Discovery lane F+G. Input: `store/profile_a_context.parquet` (705 unfiltered
honest A trades). Firewall (`python3 -m pytest test_funded_config_firewall.py -q`, from
`~/trading-team/bot/nq-liq-bot`) checked **2/2 PASS** immediately before and after this work.
Runtime: 8.3s (shared with F, single script run).

Losers = R<0: **403/705** (unfiltered), **321/583** (kept).

## (1) Loser-concentration lift table — TOP 10 (unfiltered_705, n>=20)

Lift = (loser-share of trades with this tag value) / (trade-share of trades with this tag value).
Lift > 1 means the tag is over-represented among losers (loser-concentrated); lift < 1 means the
tag is under-represented among losers (loser-avoiding / where the edge is healthiest).

| stream | tag | value | n | loser_share_pct | trade_share_pct | lift | WR_inside | PF_inside | expR_inside | n_losers_inside |
|---|---|---|---|---|---|---|---|---|---|---|
| unfiltered_705 | vwap_slope_side | flat | 60 | 11.2 | 8.5 | 1.312 | 25.0 | 0.6 | -0.241 | 45 |
| unfiltered_705 | with_against_drive | neutral_drive | 57 | 9.9 | 8.1 | 1.228 | 29.8 | 0.631 | -0.216 | 40 |
| unfiltered_705 | opening_drive_class | flat | 57 | 9.9 | 8.1 | 1.228 | 29.8 | 0.631 | -0.216 | 40 |
| unfiltered_705 | month | 10 | 58 | 9.9 | 8.2 | 1.206 | 31.0 | 0.695 | -0.176 | 40 |
| unfiltered_705 | regime_gap_and_go_1000 | True | 82 | 13.9 | 11.6 | 1.195 | 31.7 | 0.742 | -0.148 | 56 |
| unfiltered_705 | drift_strength_quintile | driftQ1 | 138 | 23.3 | 19.6 | 1.192 | 31.9 | 0.762 | -0.14 | 94 |
| unfiltered_705 | month | 1 | 58 | 9.7 | 8.2 | 1.176 | 32.8 | 0.794 | -0.112 | 39 |
| unfiltered_705 | d1c_keep | False | 122 | 20.3 | 17.3 | 1.176 | 32.8 | 0.784 | -0.119 | 82 |
| unfiltered_705 | near_pdh_10 | True | 57 | 9.4 | 8.1 | 1.166 | 33.3 | 0.869 | -0.069 | 38 |
| unfiltered_705 | near_pdl_10 | True | 33 | 5.5 | 4.7 | 1.166 | 33.3 | 0.735 | -0.142 | 22 |


## Bottom 5 (loser-avoiding, unfiltered_705, n>=20)

| stream | tag | value | n | loser_share_pct | trade_share_pct | lift | WR_inside | PF_inside | expR_inside | n_losers_inside |
|---|---|---|---|---|---|---|---|---|---|---|
| unfiltered_705 | stop_bucket | 90-inf | 72 | 7.2 | 10.2 | 0.705 | 59.7 | 2.013 | 0.287 | 29 |
| unfiltered_705 | drift_strength_quintile | driftQ5 | 138 | 14.4 | 19.6 | 0.735 | 58.0 | 2.323 | 0.376 | 58 |
| unfiltered_705 | stop_bucket | 75-90 | 49 | 5.2 | 7.0 | 0.75 | 57.1 | 1.855 | 0.278 | 21 |
| unfiltered_705 | month | 9 | 68 | 7.9 | 9.6 | 0.823 | 52.9 | 1.839 | 0.316 | 32 |
| unfiltered_705 | time_pocket | 30-60m(10:00-10:30) | 204 | 24.1 | 28.9 | 0.832 | 52.5 | 1.843 | 0.306 | 97 |


Full lift table (261 rows, both streams, all 35 tag dimensions):
`G_loser_concentration_lift.csv`.

## (2) MFE-before-stop distribution of losers

**Data-availability note**: the pinned `walk_1m` / `profile_a_join._walk_1m_with_mfe` only carry
per-trade scalar summaries (`mae_r`, `mfe_r`), not a bar-level time series — so `time-to-stop` and
`time-to-TP1` (requested in the brief) are **NOT available** in this feature store. Reporting the
available proxy only: the distribution of `mfe_r` (max favorable excursion, in R) among losers,
i.e., how far a losing trade ran in its favor before eventually stopping out.

| stream | n losers | <0 (never favorable) | 0-0.25R | 0.25-0.5R | 0.5-0.75R | 0.75-1.0R | >=1.0R | >=0.5R favorable-first |
|---|---|---|---|---|---|---|---|---|
| unfiltered_705 | 403 | 0.0% | 11.7% | 26.1% | 19.1% | 16.9% | 26.3% | 251 (62.3%) |
| kept_583 | 321 | 0.0% | 11.2% | 27.7% | 18.7% | 16.5% | 25.9% | 196 (61.1%) |

**Reading**: ~62% of losers (both streams) were favorable by >=0.5R at some point before
eventually stopping out, and ~26% ran to >=1.0R favorable before reversing and stopping — a large
exit-improvement surface exists in principle (report only, no exit-rule recommendation made here;
that is a separate certification decision).

## (3) AVOID-TAG NOMINEES

PRIORS (printed verbatim per brief): no filter raises total R (7 replications); denominator-artifact rule: pass% up while pass-count down = auto-reject (DEC-20260706-1108).

Method: pinned funnel (`run_cell`, structurally identical to
`tools_account_size_research.build_events`/`day_rows`/`eval_run`, canary-verified above) at BOTH
sizing bases **(cap=10, $1,200)** and **(cap=6, $600)**, on BOTH streams (unfiltered-705,
kept-583). For every tag value: remove all trades carrying it, recompute
`funded_per_slot_year = (365.25/mean_days_per_attempt) * (pass_count/eligible_starts)` before vs
after. **520** (stream x base x tag x value) cells tested.

A **TRUE nominee** must, for the same (stream, tag, value), satisfy at **BOTH** bases
simultaneously: (a) `funded_per_slot_year` RISES after removal, (b) `pass_count` does NOT fall
(guards the DEC-20260706-1108 denominator-artifact rule — pass% up while pass-count down is an
auto-reject regardless of the funded_per_slot_year reading), (c) holds in >=4/6 A-years (per-year
pass_pct at least as good as baseline). `month`/`year` tags and the `unknown`
(cross-vendor-join-miss) bucket are excluded from nominee candidacy as non-substantive (calendar
cherry-picking / data-quality gaps, not a real ex-ante filterable trading condition) — reported
in the full CSV but not eligible to be a nominee.

**Result: 0 TRUE cross-basis nominees.**

No tag survives both bases simultaneously.

Near-misses (passed the raise+hold+no-artifact bar at ONE basis only — did not replicate at the
other basis, i.e. failed cross-basis robustness):

| stream | base | tag | value | n_removed | before_pass_pct | after_pass_pct | before_pass_count | after_pass_count | before_funded_per_slot_year | after_funded_per_slot_year | delta_funded_per_slot_year | years_hold | auto_reject_denominator_artifact |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| unfiltered_705 | 10,$1200 | trade_seq | third_plus | 1 | 34.0 | 34.0 | 212 | 212 | 6.8289 | 6.886 | 0.0571 | 6 | False |
| unfiltered_705 | 6,$600 | after_first_loss | yes | 40 | 11.9 | 12.0 | 74 | 75 | 1.5253 | 1.5383 | 0.013 | 5 | False |
| kept_583 | 6,$600 | time_pocket | 120-150m(11:30-12:00) | 15 | 8.0 | 8.4 | 42 | 43 | 1.0036 | 1.0513 | 0.0477 | 5 | False |
| kept_583 | 6,$600 | time_pocket | 150m+(12:00+) | 1 | 8.0 | 8.0 | 42 | 42 | 1.0036 | 1.0056 | 0.002 | 6 | False |
| kept_583 | 6,$600 | vwap_slope_side | flat | 30 | 8.0 | 8.7 | 42 | 44 | 1.0036 | 1.0965 | 0.0929 | 5 | False |
| kept_583 | 6,$600 | opening_drive_class | flat | 41 | 8.0 | 10.0 | 42 | 49 | 1.0036 | 1.2633 | 0.2597 | 6 | False |
| kept_583 | 6,$600 | with_against_drive | neutral_drive | 41 | 8.0 | 10.0 | 42 | 49 | 1.0036 | 1.2633 | 0.2597 | 6 | False |
| kept_583 | 6,$600 | near_pmh_10 | True | 40 | 8.0 | 8.6 | 42 | 42 | 1.0036 | 1.0755 | 0.0719 | 4 | False |
| kept_583 | 6,$600 | regime_trend_up_dev_1000 | True | 11 | 8.0 | 8.2 | 42 | 42 | 1.0036 | 1.0228 | 0.0192 | 5 | False |
| kept_583 | 6,$600 | after_first_loss | no | 22 | 8.0 | 8.4 | 42 | 44 | 1.0036 | 1.0551 | 0.0515 | 5 | False |


Every one of these single-basis passes is at the smaller **(6,$600)** basis and either reverses
sign or becomes a denominator artifact at **(10,$1200)** — e.g. `opening_drive_class==flat` /
`with_against_drive==neutral_drive` (same 41 trades) raises funded_per_slot_year +0.26 at
(6,$600) but at (10,$1200) pass_pct rises 31.4->32.4 while pass_count FALLS 165->158 (auto-reject
artifact). Consistent with the priors above ("no filter raises total R" — this replication makes
it 8; every avoid-filter family to date has died on cross-check).

Full computed table (all 520 cells, all count columns): `G_avoid_tag_nominees_full.csv`.
