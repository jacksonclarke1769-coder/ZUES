"""INC-20260706-1141 permanent canary.

Defect: `run_d1c_real.attach_drift()` used to derive each trade's D1c-evaluation
timestamp by re-parsing the trade's `date`/`time` strings with `tz=NY`. Those strings
are emitted by `model01_sweep_mss_fvg.py` (FROZEN) from a UTC-valued array (a tz-aware
NY index run through `.values`, which converts to UTC and strips the tzinfo) -- so
re-localizing "{date} {time}" as `tz=NY` silently reinterpreted a UTC wall-clock reading
as an NY one, evaluating D1c drift 4-5h AFTER the true fill (e.g. a true 2021-06-25
10:25 ET fill carried time="14:25", so the gate looked at price ~4h into the future of
the actual fill -- a lookahead defect).

The fix derives the evaluation timestamp directly from a tz-aware `fill_index` (e.g.
`feats.index`) via the trade's integer `fill_bar`, and refuses (raises) rather than
silently falling back to the string-parsing path.

This test builds a tiny synthetic frame + fake trades (no real data / network needed)
and is a PERMANENT regression guard: it must always be green, and must fail loudly if
the lookahead defect (or an equivalent misalignment) is ever reintroduced.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
sys.path.insert(0, FW)
sys.path.insert(0, os.path.join(FW, "engine"))
sys.path.insert(0, os.path.join(FW, "models"))
import run_d1c_real as RD  # noqa: E402

NY = "America/New_York"


def _synthetic_1m(day="2021-06-25"):
    """One RTH session of 1m bars, tz-aware NY, steadily rising after the 09:30 open
    (so drift sign is unambiguous)."""
    idx = pd.date_range(f"{day} 09:30", f"{day} 16:00", freq="1min", tz=NY)
    close = 15000.0 + np.arange(len(idx), dtype=float) * 0.5
    open_ = close - 0.1
    return pd.DataFrame({"open": open_, "close": close}, index=idx)


def _synthetic_fill_index(day="2021-06-25", periods=50):
    return pd.date_range(f"{day} 09:30", periods=periods, freq="5min", tz=NY)


# ── 1. correct path: eval ts is never ahead of the true fill ─────────────────────────
def test_eval_ts_never_ahead_of_true_fill():
    d1 = _synthetic_1m()
    fi = _synthetic_fill_index()
    fill_bar = 11                                   # 09:30 + 55min = 10:25 ET
    true_fill_ts = fi[fill_bar]
    assert true_fill_ts == pd.Timestamp("2021-06-25 10:25", tz=NY)   # mirrors the auditor's worked example

    tr = pd.DataFrame({"fill_bar": [fill_bar], "direction": ["long"]})
    out = RD.attach_drift(tr, d1, fi)

    eval_ts = out["eval_ts"].iloc[0]
    seconds_ahead_used = (eval_ts - true_fill_ts).total_seconds()
    assert seconds_ahead_used <= 0
    assert eval_ts == true_fill_ts     # the fix: eval ts IS the true fill ts, never a UTC-relabeled one


def test_multiple_trades_all_non_future():
    d1 = _synthetic_1m()
    fi = _synthetic_fill_index()
    fill_bars = [2, 11, 25, 40]
    tr = pd.DataFrame({"fill_bar": fill_bars, "direction": ["long", "short", "long", "short"]})
    out = RD.attach_drift(tr, d1, fi)
    for i, fb in enumerate(fill_bars):
        true_fill_ts = fi[fb]
        seconds_ahead_used = (out["eval_ts"].iloc[i] - true_fill_ts).total_seconds()
        assert seconds_ahead_used <= 0


# ── 2. poisoned variant: the OLD date/time-string round-trip is future-evaluated ─────
def test_poisoned_future_evaluated_variant_is_detectable():
    """Reproduce the OLD (pre-INC-20260706-1141) date/time-string round-trip inline and
    show it silently evaluates hours into the future of the true fill -- proving the
    defect class is real and detectable -- then confirm the FIXED attach_drift refuses
    to run any string-only variant of this call at all (no silent fallback)."""
    d1 = _synthetic_1m()
    fi = _synthetic_fill_index()
    fill_bar = 11
    true_fill_ts = fi[fill_bar]

    # model01_sweep_mss_fvg.py's `ts = df["ts"].values` strips tz -> UTC-valued naive
    # array; `t.date()`/`t.strftime("%H:%M")` therefore print UTC wall-clock components.
    utc_naive = fi.tz_convert("UTC").tz_localize(None)
    poisoned_date = utc_naive[fill_bar].date()
    poisoned_time = utc_naive[fill_bar].strftime("%H:%M")

    # the OLD attach_drift's exact re-localization bug:
    poisoned_ets = pd.Timestamp(f"{poisoned_date} {poisoned_time}", tz=NY)
    seconds_ahead_used = (poisoned_ets - true_fill_ts).total_seconds()
    assert seconds_ahead_used > 3600 * 3       # multi-hour future-evaluation -- the defect itself

    # the FIXED attach_drift must FAIL LOUDLY rather than silently accept a
    # date/time-strings-only call (fill_index is required, no fallback exists):
    tr = pd.DataFrame({"date": [poisoned_date], "time": [poisoned_time], "direction": ["long"]})
    with pytest.raises(ValueError, match="INC-20260706-1141"):
        RD.attach_drift(tr, d1, None)


def test_missing_fill_bar_column_raises():
    d1 = _synthetic_1m()
    fi = _synthetic_fill_index()
    tr = pd.DataFrame({"direction": ["long"]})     # no fill_bar column at all
    with pytest.raises(ValueError, match="INC-20260706-1141"):
        RD.attach_drift(tr, d1, fi)


def test_naive_fill_index_raises():
    d1 = _synthetic_1m()
    fi_naive = pd.date_range("2021-06-25 09:30", periods=50, freq="5min")   # no tz
    tr = pd.DataFrame({"fill_bar": [11], "direction": ["long"]})
    with pytest.raises(ValueError, match="INC-20260706-1141"):
        RD.attach_drift(tr, d1, fi_naive)


def test_out_of_session_eval_ts_raises():
    """A misaligned fill_index/fill_bar pairing that resolves outside 09:30-16:00 ET
    must raise loudly rather than silently evaluate drift on a bogus timestamp."""
    d1 = _synthetic_1m()
    fi_overnight = pd.date_range("2021-06-25 02:00", periods=50, freq="5min", tz=NY)
    tr = pd.DataFrame({"fill_bar": [0], "direction": ["long"]})
    with pytest.raises(ValueError, match="INC-20260706-1141"):
        RD.attach_drift(tr, d1, fi_overnight)
