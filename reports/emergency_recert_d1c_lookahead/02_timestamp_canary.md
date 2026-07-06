# D1c Attachment Timestamp Look-Ahead — Permanent Canary Report

INC-20260706-1141. Two permanent regression tests were added to the repo root (join the
main `gate.sh` suite, must always be green):

- `test_d1c_timestamp_canary.py` — synthetic-data unit canary, no external data required.
- `test_no_future_d1c_attachment.py` — regression against a small REAL Databento slice
  (skips if the research data mirror is absent).

Both import the FIXED `run_d1c_real.attach_drift` from
`~/trading-team/backtests/ict-nq-framework/run_d1c_real.py` (research-side, outside this
repo) via an explicit `sys.path.insert(FW)` at the top of each file — the fixed function
is not vendored/copied into these tests.

## `test_d1c_timestamp_canary.py`

6 tests, synthetic tz-aware 1m frame + synthetic 5m `fill_index`, no real data needed.

| Test | Assertion |
|---|---|
| `test_eval_ts_never_ahead_of_true_fill` | Builds a 09:30-16:00 ET synthetic day, `fill_bar=11` (09:30+55min = **10:25 ET**, the auditor's exact worked example). Asserts `seconds_ahead_used = (eval_ts - true_fill_ts).total_seconds() <= 0` AND `eval_ts == true_fill_ts` exactly. |
| `test_multiple_trades_all_non_future` | Same check across 4 trades at different `fill_bar`s (long+short mixed). |
| `test_poisoned_future_evaluated_variant_is_detectable` | Reproduces the OLD buggy formula inline: takes the tz-aware `fi[fill_bar]`, converts it to UTC-naive (mirrors `model01`'s `.values` tz-strip), extracts `date()`/`strftime("%H:%M")` (mirrors `t["date"]`/`t["time"]`), then re-localizes as `tz=NY` (the exact old `attach_drift` line). Asserts the resulting `poisoned_ets` is `>3600*3` seconds (i.e. `>3h`, comfortably inside the incident's stated 4-5h) AFTER the true fill. Then asserts the FIXED `attach_drift` raises `ValueError` matching `"INC-20260706-1141"` when called with the legacy 2-positional-arg shape (`fill_index=None`) — i.e. it refuses to run the poisoned path at all rather than silently reproducing it. |
| `test_missing_fill_bar_column_raises` | `tr` without a `fill_bar` column -> raises `ValueError("INC-20260706-1141: ...")`. |
| `test_naive_fill_index_raises` | `fill_index` without tz -> raises `ValueError("INC-20260706-1141: ...")`. |
| `test_out_of_session_eval_ts_raises` | `fill_index` deliberately built from an overnight (02:00 ET) bar range -> the derived `eval_ts` fails the 09:30-16:00 ET hard assertion -> raises `ValueError("INC-20260706-1141: ...")`. |

### Poisoned example (actual output, from the test)

```
true_fill_ts        = 2021-06-25 10:25:00-04:00   (America/New_York)
poisoned_date/time   = 2021-06-25 / "14:25"        (UTC wall-clock, mislabeled)
poisoned_ets (OLD)   = 2021-06-25 14:25:00-04:00   (America/New_York)  <- WRONG, +4h
seconds_ahead_used   = 14400.0s  (4h00m ahead of the true fill)
```
This is the exact incident-quoted example ("a true 2021-06-25 10:25 ET fill carried
time=14:25").

### Actual run

```
$ python3 -m pytest test_d1c_timestamp_canary.py -q
......                                                                   [100%]
6 passed in 0.39s
```

## `test_no_future_d1c_attachment.py`

Runs the REAL pipeline (`run_d1c_real.load_1m` + `real_5m`, real `htf.build_features`,
the real FROZEN `model01_sweep_mss_fvg.run`, the FIXED `attach_drift`) on a small real
slice — 2021-05-01 to 2021-08-31 (summer/DST season, contains the auditor's worked
example day) — restricted to `ny_am` session, `exit3` params. Runs in ~1.2s.

| Test | Assertion |
|---|---|
| `test_every_eval_ts_at_or_before_true_fill` | For every trade in the real slice: `seconds_ahead_used = (eval_ts - feats.index[fill_bar]).total_seconds() <= 0`, and `eval_ts == feats.index[fill_bar]` exactly. |
| `test_old_string_path_would_have_been_future_evaluated_in_dst_season` | Using each real trade's own `date`/`time` strings (still emitted unchanged by the FROZEN model01 — they are UTC wall-clock numbers), reconstructs what the OLD `attach_drift` would have used (`pd.Timestamp(f"{date} {time}", tz=NY)`), and asserts at least one real trade in this DST-season slice diverges from its true fill-bar timestamp by `>=3600s` (actual max divergence observed: **14400s = 4h**, matching EDT offset, on every trade in the slice — not just one). |

### Actual run

```
$ python3 -m pytest test_no_future_d1c_attachment.py -q
..                                                                       [100%]
2 passed in 1.23s
```

### Actual output (spot check, matches the canary's synthetic example on real data)

```
fill_bar=719  true fill ts (feats.index[719]) = 2021-06-25 10:25:00-04:00
  model01 date/time fields:                     date=2021-06-25 time=14:25
  OLD attach_drift would have used:              2021-06-25 14:25:00-04:00  (+14400s / +4h)
  FIXED attach_drift eval_ts (this run):          2021-06-25 10:25:00-04:00  (0s ahead)
```

## Gate wiring

Both files use the repo's `test_*.py` naming convention (`pytest.ini`: `python_files =
test_*.py`) and require no fixtures beyond `pytest`/`pandas`/`numpy` — they run as part
of the plain `python3 -m pytest -q` collection in `gate.sh` step (a).
