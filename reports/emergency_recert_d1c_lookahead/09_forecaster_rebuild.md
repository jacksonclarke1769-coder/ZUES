# 09 — Forecaster Rebuild

HONEST-RECERT DRAFT — pending auditor verdict + operator approval

INC-20260706-1141. LIVE HOLD ACTIVE — no live/config/funded-config changes made. `zeus_server.py`
was NOT touched (per instruction); it serves whatever `reports/eval_day_pnl_50k_1200.json` holds,
so the dashboard's `/api/forecast` now reflects the honest cache automatically, with no code
change. Headline constants hardcoded elsewhere in `zeus_server.py`
(`pass_pct=47.8, bust_pct=15.9, expire_pct=36.2, median_days=16`) remain stale and are already
banner-flagged in `04_invalidated_numbers.md` item 1 pending the operator-approved re-lock.

## 1. Cache regeneration

Ran the EXISTING, unmodified rebuild path:

```
$ python3 tools_eval_forecast.py --rebuild
rebuilding certified day cache (locked A stream, exit3+D1c, 1m truth)…
[saved] reports/eval_day_pnl_50k_1200.json (537 day rows)
```

This calls `tools_account_size_research.day_rows(tools_account_size_research.build_events(rows,
1200, 10), ...)` on the stream from `tools_phase3_config_sweep.a_streams_d1c` — the same import
chain Wave 1 already fixed upstream (`run_d1c_real.attach_drift`, confirmed green this session via
`test_d1c_timestamp_canary.py` + `test_no_future_d1c_attachment.py`, 8 passed). No call-chain edit
was needed in `tools_eval_forecast.py` or `eval_forecast.py` — the fix was already upstream, so
`--rebuild` today produces the honest cache with zero code change.

Regenerated cache: **537 day rows** (`reports/eval_day_pnl_50k_1200.json`), span 2021-06-25 ..
2026-06-18. (For reference, the pre-fix cache this replaced was built on the contaminated stream —
not independently re-verified here since it was already invalidated and overwritten; see
`04_invalidated_numbers.md` item 7.)

## 2. Calibration check

Fresh-seed replay (start balance, start-trail floor, full 30-day clock) against the regenerated
cache:

```python
days = EF.load_distribution()
fc = EF.forecast(days, EF.START, EF.START - EF.TRAIL, EF.EXPIRE_DAYS)
# {'n': 526, 'pass_pct': 31.4, 'bust_pct': 37.3, 'expire_pct': 31.4, 'median_days_to_pass': 16, ...}
```

| | pass% | bust% | expire% | median days (pass) |
|---|---|---|---|---|
| canonical honest row (`tools_sim_parity_check.py` `CANARY_EXPECT`, n=525) | 31.4 | 37.3 | 31.2 | 16 |
| fresh-seed `EF.forecast()` on regenerated cache (n=526) | 31.4 | 37.3 | 31.4 | 16 |
| delta (pp) | 0.0 | 0.0 | 0.2 | 0.0 |

Tolerance: 0.5pp per leg. **Verdict: MATCH (all legs within tolerance).** No STOP triggered.

Precision note (same class of artifact already adjudicated in
`05_honest_machine_certification.md`'s precision note): `n` differs by 1 (526 vs 525) because
`eval_forecast.valid_starts()` filters on `(days[-1][0] - d).days >= days_left` (inclusive) while
`tools_account_size_research`/`tools_sim_parity_check` filter on `> EXPIRE_DAYS` (strict) — a
pre-existing, one-start boundary difference in the two independently-written start-selection
filters, not introduced by this task and not a stream or engine disagreement. It flips one
knife-edge start between BUST and EXPIRE, moving `expire_pct` by 0.2pp — within the 0.5pp
tolerance. Not fixed here (out of scope: `eval_forecast.py` mechanics were not part of this task's
file list).

## 3. `test_eval_forecast.py` — calibration expectations updated (authorized, INC-20260706-1141)

`test_calibration_reproduces_certified` previously asserted the pre-fix 47.8/15.9/36.2 row
(confirmed it FAILS against the regenerated honest cache: `assert 31.4 == 47.8 ± 0.3` → obtained
31.4). Updated to assert the honest row with the calibration tolerance widened to match this task's
0.5pp bar:

```python
assert fc["pass_pct"] == pytest.approx(31.4, abs=0.5)
assert fc["bust_pct"] == pytest.approx(37.3, abs=0.5)
assert fc["expire_pct"] == pytest.approx(31.2, abs=0.5)
```

Full file result after the edit: `12 passed` (was `11 passed, 1 failed` pre-edit, same file).

## 4. Live eval's honest conditional read

Inputs (as instructed): `evidence/eval_campaign.json` state — `current_balance=$49,404.80`,
floor=`$47,500` (start-trail, unratcheted; cushion = `$1,904.80`), `clock_start=2026-06-25`,
`clock_days=30` → expiry `2026-07-25`. As-of **2026-07-07** → **18 days left**.

```
$ python3 tools_eval_forecast.py --as-of 2026-07-07
  balance $49,404.80   floor $47,500.00   cushion $1,904.80
  target  $53,000   to-go $3,595.20   days-left 18
  replayed over 530 historical continuations
  P(PASS)     13.2%
  P(BUST)     33.0%
  P(EXPIRE)   53.8%
  median days-to-target (of passes): 12
  VERDICT: TIME IS THE ENEMY — EXPIRE (53.8%) is the modal outcome, passes finish in ~12d
```

Confirmed the campaign file alone (no manual `--balance/--cushion/--days-left` overrides) drives
this exact result — the honest cache flows through automatically.

| | P(PASS) | P(BUST) | P(EXPIRE) | median days-to-target (of passes) | n |
|---|---|---|---|---|---|
| **Live conditional read, as-of 2026-07-07** | 13.2% | 33.0% | 53.8% | 12 | 530 |
| (reference) certified cap-10 fresh-seed honest row | 31.4% | 37.3% | 31.2% | 16 | 525-526 |

This is markedly worse than the fresh-seed honest row — expected: the live account starts down
~$595 of cushion (vs the fresh $2,500) and has 18 days left, not 30, so a materially larger fraction
of continuations run out the clock (EXPIRE) before reaching target. The edge itself (stream) is
unchanged between the fresh-seed and conditional reads; only the starting handicap differs.

## Firewall (before/after)

```
$ python3 -m pytest test_eval_config_firewall.py test_funded_config_firewall.py -q
5 passed
```
No live/config/funded-config file was touched. `zeus_server.py` was not opened or edited this task.
