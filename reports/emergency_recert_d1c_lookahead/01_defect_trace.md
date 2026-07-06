# D1c Attachment Timestamp Look-Ahead — Defect Trace

INC-20260706-1141. No code changed by this report; `run_d1c_real.py` is being fixed concurrently by
another agent — DO NOT TOUCH. All paths below are absolute-relative to repo roots:
- `~/trading-team/backtests/ict-nq-framework/` (engine/model, read-only per this task)
- `~/trading-team/bot/nq-liq-bot/` (research tooling)

## 1. The emission bug — model01 mislabels a UTC wall-clock string as NY time

File: `~/trading-team/backtests/ict-nq-framework/models/model01_sweep_mss_fvg.py`

```
119  df = features.reset_index().rename(columns={"index": "ts", "timestamp": "ts"})
120  ts = df["ts"].values
...
301  t = pd.Timestamp(ts[fill])
302  trades.append({
303      "date": t.date(), "dow": t.day_name(), "time": t.strftime("%H:%M"),
```

- `features.index` (built from `run_d1c_real.load_1m()` → `real_5m()`) is a tz-aware
  `DatetimeIndex` localized to `America/New_York` (`run_d1c_real.py:32`, see §2).
- Line 119's `reset_index()` still carries that tz-aware dtype in the `ts` column.
- **Line 120 is the exact defect line**: calling `.values` on a tz-aware pandas Series/Index is a
  well-known pandas behavior — it converts the tz-aware timestamps to UTC and returns a **naive**
  `numpy.datetime64[ns]` array. The tz label is silently dropped; the array's wall-clock values are
  now UTC, not NY.
- Line 301 wraps that already-corrupted UTC value in `pd.Timestamp(ts[fill])`, producing a naive
  `Timestamp` whose `.date()`/`.strftime("%H:%M")` (line 303) print the **UTC clock reading with no
  tz marker** — indistinguishable, downstream, from an NY wall-clock string.
- This is the entire defect: a fill that occurred at NY 10:25 is emitted as `"time": "14:25"`
  (EDT, UTC = NY+4h) with nothing in the record to say it isn't NY local time.

## 2. The re-localization bug — run_d1c_real.attach_drift trusts the mislabeled strings

File: `~/trading-team/backtests/ict-nq-framework/run_d1c_real.py`

```
23  NY = "America/New_York"
...
42  def attach_drift(tr, d1):
...
53      ets = pd.Timestamp(f"{t['date']} {t['time']}", tz=NY)
54      day = ets.normalize()
55      op = opens.get(day, np.nan)
56      pos = c_idx.searchsorted(ets, side="right") - 1   # last 1m close <= fill ts
```

- Line 53 is the exact re-localization line: it rebuilds a timestamp from the model01 `date`/`time`
  **strings** and stamps it `tz=NY`. Because those strings actually hold the UTC clock reading
  (§1), this manufactures a timestamp that is the true NY fill instant **plus the UTC offset**
  (+4h EDT / +5h EST — see §4).
- Line 56 then searches the real 1m closes up to that manufactured (future) timestamp, so
  `attach_drift`'s drift computation at every fill reads roughly 4-5 hours of **1m closes that had
  not happened yet at the real fill time** — textbook look-ahead.
- `d1` here (`load_1m()`, line 32) IS correctly NY-localized:
  `d1.index = (d1.index.tz_convert(NY) if d1.index.tz else d1.index.tz_localize("UTC").tz_convert(NY))`.
  The 1m truth data was never wrong — only the fill-time label used to index into it.

## 3. What SHOULD have been used

The tz-aware timestamp already exists on both sides of this join and never needed to leave
`.values`/string form:
- In `model01_sweep_mss_fvg.py`, `features.index[fill]` (or `df["ts"].iloc[fill]`, i.e. the pandas
  Timestamp accessor, not `.values`) is a correct, tz-aware NY Timestamp for the fill bar. The fix
  class stated by the incident ("derive fill ts from the tz-aware index, not the strings") means:
  carry that tz-aware Timestamp (or its `fill_bar` integer index into a still-tz-aware frame)
  through to `attach_drift`, never round-tripping through naive strings.
- Proof this pattern already exists and is correct elsewhere in the same codebase:
  `~/trading-team/bot/nq-liq-bot/tools_phase3_config_sweep.py:60` —
  `rows.append(dict(ts=pd.Timestamp(fi[fb]), ...))` where `fi = feats.index` (tz-aware) and
  `fb = int(t.fill_bar)` — this is the SAME fill-bar integer already present on every trade record
  (`model01_sweep_mss_fvg.py:318`, `"fill_bar": int(fill)`), read straight off the tz-aware index
  instead of through the corrupted `date`/`time` strings. This is what exposed the divergence (§5).

## 4. Offset magnitude

`America/New_York` is UTC-4 during EDT (roughly mid-March to early November) and UTC-5 during EST
(rest of the year). Since the strings hold the UTC clock but get relabeled NY, the manufactured
timestamp is **ahead of the true fill time by +4h (EDT) or +5h (EST)** — matches the incident's
"+4-5 hours" and the worked example ("fill 10:25 ET carries time=14:25", a +4h/EDT case).

## 5. Why prior canaries missed it

- `lookahead_canary.py` (`assert_causal`, lines 35-45) poisons rows of a **feature frame** strictly
  after a timestamp `ts` and asserts a signal function's output at `ts` is unchanged. It is called
  against ENGINE feature/signal functions (the MSS/FVG/sweep detection inside `model01`'s `run()`
  itself, and HTF-resample features via `completed_bucket_slope`) — i.e. it certifies that the
  **entry signal** doesn't peek at future 5m bars. It was never pointed at the D1c **attachment**
  step, which is a separate, post-hoc script (`run_d1c_real.py`) that runs AFTER `model01.run()`
  has already returned trades, joining a completed trade log to the 1m truth stream by string
  timestamp. That join is outside the `fn(df, ts)` shape `assert_causal` checks.
- The 1m-truth EXIT walk (`walk_1m` in `tools_1m_truth_recert.py`, used by `_simulate`/`walk_1m`
  bar-by-bar loops) is a genuinely causal forward walk over bar indices — it never reads ahead of
  the bar it's standing on, and was never in question. It doesn't touch `attach_drift` at all.
  Note `model01_sweep_mss_fvg.py`'s own `_simulate` uses `tsv = pd.DatetimeIndex(df["ts"]).asi8`
  (nanosecond ints, line 161) for gap detection — a completely separate, order-preserving int
  timeline that is not exposed to the tz-string bug; the exit walk was never at risk.
- CERBERUS (2026-06-12, referenced in `drift_gate.py:3`) validated the **live** D1c gate
  (`drift_gate.py`, class `DriftGate`) — that gate is fed real-time via `on_session_open(ts,
  open_price)` and `on_bar_close(ts, close)` called live off the actual feed clock (no
  `reset_index()`/`.values`/string round-trip anywhere in `drift_gate.py`). CERBERUS therefore
  correctly certified a component that was never affected; the defect lives exclusively in the
  RESEARCH re-derivation path (`run_d1c_real.attach_drift`), which the live gate does not call and
  is not built from.
- Net: engine canaries covered signal generation; the exit walk was causal by construction; CERBERUS
  covered the live gate. None of the three exercises the `model01` string emission →
  `run_d1c_real.attach_drift` string re-localization join, because it is a fourth, previously
  uncovered code path (a post-hoc research attachment, not an engine signal, not the exit walk, not
  the live gate).

## 6. Why the new blocking canary caught it

The 8-ideas sprint (near-miss lane, halted mid-flight per the incident) hit a blocking canary
failure during a byte-parity reproduction exercise. The mechanism, evidenced in the existing
codebase pattern it follows:
- `~/trading-team/bot/nq-liq-bot/tools_profileC_a_enhancement.py:87-113` (`build_raw_and_kept`)
  independently reimplements the certified stream: it calls `RD.attach_drift(tr, d1_tz)` (line 93,
  same corrupted call as production) to get `d1c_keep`, but stamps each row's own `ts` field
  straight off the tz-aware `feats.index` at the trade's `fill_bar` (line 106:
  `rec = dict(ts=pd.Timestamp(fi[fb]), ...)`) — i.e. it carries BOTH the corrupted keep/drop
  decision AND the TRUE causal fill timestamp on the same row.
- `assert_parity()` (`tools_profileC_a_enhancement.py:115-123`) checks this reimplementation's
  `kept` rows byte-for-byte against `tools_sim_parity_check.load_rows()` (the certified loader) —
  and matches, because both sides used the same corrupted `d1c_keep` bool. This firewall alone
  could not have caught the bug (it only proves two callers of the same defective function agree).
- The near-miss-lane sprint went one step further: it recomputed the D1c drift **sign** directly and
  causally from the true fill timestamp (the same `drift_value_at()`/`ts=pd.Timestamp(fi[fb])`
  pattern seen in `tools_8ideas_stream_studies.py:188-194,207-224`, which reads `t["ts"]` — the true
  bar-indexed timestamp, never the `date`/`time` strings) and compared that recomputed keep/drop
  sign against the stored `d1c_keep` bool for the same 705 pre-drop signals. Because the stored bool
  was computed at the wrong (future, +4-5h) instant, 234/705 signs disagreed (66.8% agreement) — a
  divergence between "independently reimplemented, causally correct" and "certified, corrupted" that
  a byte-parity check against the SAME defective source (as `assert_parity()` alone does) can never
  surface. This is what the incident calls the "blocking canary failure": an independent
  reimplementation of the keep/drop decision from ground truth, not just a structural parity check.

## 7. Consumer graph — every downstream of the D1c kept-stream

Root of contamination: `~/trading-team/bot/nq-liq-bot/tools_phase3_config_sweep.py:35-62`
(`a_streams_d1c`) — calls `RD.attach_drift(tr, d1_tz)` (line 41, `RD = run_d1c_real`), filters on
`t["d1c_keep"]` (line 49) to build the "kept" stream (the certified 435-trade set for the deployed
`exit3` variant). Every consumer below imports `a_streams_d1c` (or the loader that wraps it)
directly — verified by grep of each file's imports:

```
tools_phase3_config_sweep.a_streams_d1c            <- RD.attach_drift (THE DEFECT)
  |
  +-- tools_sim_parity_check.py:60,80  (load_rows() = certified_load_rows(), the canonical loader)
  |     |
  |     +-- tools_profileC_a_enhancement.py:55  (certified_load_rows import; also calls
  |     |     RD.attach_drift directly again at line 93 in build_raw_and_kept)
  |     |     +-- tools_wyckoff_a_tags.py:68        (imports from tools_profileC_a_enhancement)
  |     |     +-- tools_8ideas_stream_studies.py:67-70 (imports load_frames/build_raw_and_kept/
  |     |           assert_parity/CANARY_EXPECT from tools_profileC_a_enhancement)
  |     |
  |     +-- tools_sprint_state_policies.py:3-27  (imports load_rows/group_by_day/SPEC_50K/EXPIRE_DAYS)
  |     +-- tools_sprint_cap_risk.py:42,44        (imports tools_sim_parity_check as PARITY +
  |     |     tools_account_size_research as ASR)
  |     +-- tools_sprint_fill_sensitivity.py:33,453 (PARITY.load_rows())
  |     +-- tools_sprint_cadence.py:60             (imports tools_sim_parity_check as P)
  |
  +-- tools_account_size_research.py:22,25,150  (imports a_streams_d1c directly; produces the
  |     47.8/15.9/36.2 row -> reports/apex_validation.json "cap10_relock_2026-07-05")
  |     +-- apex_validation.json cap10_relock_2026-07-05 section (harness:
  |     |     ["tools_account_size_research.py"])
  |     +-- tools_eval_sizing_sweep.py:36-37  (imports a_streams_d1c AND
  |     |     tools_account_size_research.day_rows/eval_run) -> reports/eval_sizing_sweep_2026-07-05.json
  |     |     (cap x budget matrix, state policies, cadence sprint numbers)
  |     +-- apex_funded_40.py:28-31  (imports a_streams_d1c) -> funded model ($12.6-12.8k lifetime/PA)
  |     +-- tools_funded_funnel.py:26-29  (imports a_streams_d1c) -> funded funnel report
  |
  +-- tools_eval_forecast.py:31-50 (_rebuild_cache calls a_streams_d1c directly, line 44) ->
        reports/eval_day_pnl_50k_1200.json  (the certified per-day cache)
        +-- eval_forecast.py:26 (CACHE_PATH) -> conditional P(pass) reads for the live eval
              ("~20% conditional read" in the incident)
```

Every file in the `tools_*` "July research sprint" family (`tools_wyckoff_a_tags.py`,
`tools_profileC_a_enhancement.py`, `tools_sprint_state_policies.py`, `tools_sprint_cap_risk.py`,
`tools_sprint_fill_sensitivity.py`, `tools_sprint_cadence.py`, `tools_8ideas_stream_studies.py`,
`tools_eval_sizing_sweep.py`) explicitly documents, in its own header comment, that it reuses
`tools_sim_parity_check.load_rows()` (or `tools_profileC_a_enhancement`'s parity-checked
reconstruction of it) as "the certified stream" — meaning the contamination is single-point-of-origin
(`run_d1c_real.attach_drift`) but fans out through one shared loader to essentially the entire July
research tree. `tools_1m_truth_recert.py` itself is NOT contaminated — it exposes `M1Map`/`walk_1m`/
`A_PARAMS`/`b_streams`/`DPP`/`B_COST` (reused as plumbing by `a_streams_d1c` and others) and its own
`a_streams()` function (no `d1c`, no `attach_drift` call) is the unfiltered honest stream that
survives (see `10_recent_research_reassessment.md`).

## Sources cited

- `~/trading-team/backtests/ict-nq-framework/models/model01_sweep_mss_fvg.py:119-120,301-303,318`
- `~/trading-team/backtests/ict-nq-framework/run_d1c_real.py:23,30-33,42-64`
- `~/trading-team/bot/nq-liq-bot/lookahead_canary.py:35-45`
- `~/trading-team/bot/nq-liq-bot/drift_gate.py:1-17,25-87`
- `~/trading-team/bot/nq-liq-bot/tools_1m_truth_recert.py` (`a_streams`, `walk_1m`, no `d1c`)
- `~/trading-team/bot/nq-liq-bot/tools_phase3_config_sweep.py:35-62`
- `~/trading-team/bot/nq-liq-bot/tools_sim_parity_check.py:57-80`
- `~/trading-team/bot/nq-liq-bot/tools_profileC_a_enhancement.py:55-56,87-123`
- `~/trading-team/bot/nq-liq-bot/tools_8ideas_stream_studies.py:67-70,188-224`
- `~/trading-team/bot/nq-liq-bot/tools_account_size_research.py:22-25,150`
- `~/trading-team/bot/nq-liq-bot/tools_eval_sizing_sweep.py:33-37`
- `~/trading-team/bot/nq-liq-bot/apex_funded_40.py:28-31`
- `~/trading-team/bot/nq-liq-bot/tools_funded_funnel.py:26-29`
- `~/trading-team/bot/nq-liq-bot/tools_eval_forecast.py:31-50`
- `~/trading-team/bot/nq-liq-bot/eval_forecast.py:17,26`
- `~/trading-team/bot/nq-liq-bot/reports/apex_validation.json` (`cap10_relock_2026-07-05`)
- `/Users/jacksonclarke/Documents/Zues/07 Bugs & Incidents/INC-20260706-1141-...md`
