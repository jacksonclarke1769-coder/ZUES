"""Permanent canary for the latest_signal() timestamp look-ahead fix (real-money arming
blocker; same defect class as INC-20260706-1141).

Defect: ProfileAEngine.latest_signal() (strategy_engine_profileA.py) used to derive each
trade's fill instant by re-parsing model01's `date`/`time` STRING columns with
`pd.Timestamp(f"{date} {time}", tz=NY)`. Those strings are wall-clock-shaped but not
guaranteed to be NY-local at the instant a re-localization assumes -- re-localizing shifts
the instant by hours, corrupting the freshness gate (`(recent - ftime) <= 10min`) that
decides whether a fill is "now" (real-money arming risk: a stale fill can look fresh, or a
fresh fill can look stale, either way trading on the wrong instant).

The fix derives the fill instant directly from `feats.index[fill_bar]` (a tz-aware NY
DatetimeIndex; fill_bar is model01's own positional index, valid by construction) via the
pure helper `_derive_fill_instant`, and RAISES `TimestampReconstructionError` -- never
silently returns None -- when that derivation is impossible (broken plumbing). Ordinary
no-signal conditions (wrong session, already-acted, stale-but-valid fill) are UNCHANGED and
still simply skip/return None.

This test builds tiny synthetic frames (no real data / network needed) and is a PERMANENT
regression guard: it must always be green, and must fail loudly if the lookahead defect (or
an equivalent silent-None swallow) is ever reintroduced.
"""
import json
import os

import pandas as pd
import pytest

import strategy_engine_profileA as SEP
from strategy_engine_profileA import ProfileAEngine, TimestampReconstructionError

import bot as BOT
from store import Store
import config

NY = SEP.NY


# ── fakes ────────────────────────────────────────────────────────────────────────────────
class _FakeM1:
    """Stand-in for model01_sweep_mss_fvg -- returns a canned trades frame so latest_signal()
    is exercised without the real (frozen) framework or real market data."""

    def __init__(self, trades_df):
        self._df = trades_df

    def run(self, feats, symbol, params, realtime=False):
        return self._df.copy()


def _engine_with(feats_index, trades_df, recent, buf_len=2500):
    """A ProfileAEngine wired to synthetic feats/trades, bypassing the real (frozen)
    feature-engineering + model01 pipeline entirely."""
    eng = ProfileAEngine({"nyam_start_min": 570, "nyam_end_min": 690, "flat_min": 870})
    eng.buf = pd.DataFrame(
        {"Open": 0.0, "High": 0.0, "Low": 0.0, "Close": 0.0, "Volume": 0.0},
        index=pd.date_range(end=recent, periods=buf_len, freq="5min", tz=NY),
    )
    feats = pd.DataFrame(index=feats_index)
    eng._features = lambda: feats                      # bypass real D./htf. pipeline
    SEP.M1 = _FakeM1(trades_df)                          # module-level swap, restored by caller
    return eng


def _trade_row(fill_bar, session="ny_am", direction="long", date="corrupt", time="corrupt",
                entry=100.0, stop=99.0, target=102.0, rr=2.0, liq="pdh"):
    return dict(fill_bar=fill_bar, session=session, direction=direction, date=date, time=time,
                entry=entry, stop=stop, target=target, rr=rr, liq_swept=liq)


@pytest.fixture(autouse=True)
def _restore_m1():
    orig = SEP.M1
    yield
    SEP.M1 = orig


# ── 1. round-trip identity ──────────────────────────────────────────────────────────────
def test_round_trip_identity():
    idx = pd.date_range("2024-06-03 09:30", periods=50, freq="5min", tz=NY)
    fb = 11
    got = SEP._derive_fill_instant(idx, fb)
    assert got == idx[fb]
    assert (got - idx[fb]).total_seconds() == 0


def test_round_trip_identity_multiple_positions():
    idx = pd.date_range("2024-06-03 09:30", periods=78, freq="5min", tz=NY)   # 09:30..16:00 ET
    for fb in (0, 2, 25, 40, 77):
        assert SEP._derive_fill_instant(idx, fb) == idx[fb]


# ── 2. no-string-dependence ──────────────────────────────────────────────────────────────
def test_derive_fill_instant_never_reads_strings():
    """The helper's signature doesn't even accept date/time strings -- structurally can't
    depend on them. Confirm end-to-end via latest_signal() with a CORRUPT date/time trade row
    that still has a valid fill_bar landing inside the freshness window."""
    idx = pd.date_range("2024-06-03 09:30", periods=50, freq="5min", tz=NY)
    fb = 30
    true_fill_ts = idx[fb]
    tr = pd.DataFrame([_trade_row(fb, date="", time="not-a-time!!")])
    recent = true_fill_ts + pd.Timedelta(minutes=5)     # within the 10min freshness gate
    eng = _engine_with(idx, tr, recent)

    sig = eng.latest_signal()
    assert sig is not None
    assert sig["ts_signal"] == true_fill_ts.isoformat()
    assert sig["entry"] == 100.0


# ── 3. invariant vs ordinary (the core design) ───────────────────────────────────────────
def test_out_of_range_fill_bar_raises_specifically():
    idx = pd.date_range("2024-06-03 09:30", periods=50, freq="5min", tz=NY)
    tr = pd.DataFrame([_trade_row(fill_bar=999)])       # out of range for a 50-row index
    recent = idx[-1]
    eng = _engine_with(idx, tr, recent)

    with pytest.raises(TimestampReconstructionError) as ei:
        eng.latest_signal()
    assert ei.value.fill_bar == 999
    assert ei.value.index_len == 50
    assert ei.value.derived_instant is None


def test_stale_but_valid_fill_returns_none_not_raise():
    """A valid, in-range, in-session fill_bar that resolves to an instant OLDER than the
    10-minute freshness window is an ORDINARY no-signal condition -- must return None, must
    NOT raise. This is the load-bearing assertion that proves the two paths are not collapsed."""
    idx = pd.date_range("2024-06-03 09:30", periods=50, freq="5min", tz=NY)
    fb = 10
    true_fill_ts = idx[fb]
    tr = pd.DataFrame([_trade_row(fb)])
    recent = true_fill_ts + pd.Timedelta(minutes=45)    # well outside the 10min gate
    eng = _engine_with(idx, tr, recent)

    assert eng.latest_signal() is None                  # no raise


def test_non_ny_am_session_is_ordinary_skip():
    """Wrong session is an ORDINARY skip (continue), evaluated BEFORE derivation -- even a
    garbage fill_bar on a non-ny_am row must not raise."""
    idx = pd.date_range("2024-06-03 09:30", periods=50, freq="5min", tz=NY)
    tr = pd.DataFrame([_trade_row(fill_bar=99999, session="london")])
    recent = idx[-1]
    eng = _engine_with(idx, tr, recent)
    assert eng.latest_signal() is None                   # no raise: not ny_am, never derived


# ── 4. propagation: bot.py's typed handler ───────────────────────────────────────────────
class _RaisingEngine:
    def __init__(self, err):
        self.err = err

    def add_bar(self, *a, **k):
        pass

    def latest_signal(self):
        raise self.err

    def flat_time(self, ts):
        return False


def test_propagation_writes_incident_and_halt(tmp_path, monkeypatch):
    import watchdog_belief as WB
    monkeypatch.setattr(WB, "WATCHDOG_DIR", str(tmp_path))
    monkeypatch.setattr(WB, "HALT_FLAG_PATH", str(tmp_path / "HALT.flag"))

    st = Store(path=str(tmp_path / "bot.db"))
    b = BOT.SimBot(st, cfg=config, verbose=False)
    err = TimestampReconstructionError(fill_bar=999, index_len=5, derived_instant=None)
    b.engine = _RaisingEngine(err)
    b.trade_from = None

    ts = pd.Timestamp("2024-06-03 10:05", tz=NY)
    # must not raise out of process_bar -- the typed handler catches it and fails closed
    b.process_bar(ts, 100.0, 101.0, 99.0, 100.5)

    halt_path = tmp_path / "HALT.flag"
    assert halt_path.exists(), "HALT.flag was not written by the typed handler"
    halt = json.loads(halt_path.read_text())
    assert halt["invariant"] == "TIMESTAMP_RECONSTRUCTION"

    events = st.events(limit=10)
    assert any(e["level"] == "incident" and "TimestampReconstructionError" in e["msg"]
               for e in events), f"no incident event recorded: {events}"


def test_every_other_exception_is_unaffected(tmp_path, monkeypatch):
    """A different exception from latest_signal() must NOT be caught by the new narrow
    handler -- no widened `except Exception`."""
    import watchdog_belief as WB
    monkeypatch.setattr(WB, "WATCHDOG_DIR", str(tmp_path))
    monkeypatch.setattr(WB, "HALT_FLAG_PATH", str(tmp_path / "HALT.flag"))

    st = Store(path=str(tmp_path / "bot.db"))
    b = BOT.SimBot(st, cfg=config, verbose=False)
    b.engine = _RaisingEngine(ValueError("some unrelated bug"))
    b.trade_from = None

    ts = pd.Timestamp("2024-06-03 10:05", tz=NY)
    with pytest.raises(ValueError, match="some unrelated bug"):
        b.process_bar(ts, 100.0, 101.0, 99.0, 100.5)
    assert not (tmp_path / "HALT.flag").exists()


# ── 5. session-bound ─────────────────────────────────────────────────────────────────────
def test_out_of_session_instant_raises_with_derived_instant_set():
    idx = pd.date_range("2024-06-03 02:00", periods=50, freq="5min", tz=NY)   # overnight
    fb = 0
    with pytest.raises(TimestampReconstructionError) as ei:
        SEP._derive_fill_instant(idx, fb)
    assert ei.value.derived_instant == idx[fb]
    assert ei.value.fill_bar == fb


# ── 6. DST edges ─────────────────────────────────────────────────────────────────────────
def test_dst_spring_forward_round_trip():
    idx = pd.date_range("2024-03-10 09:30", periods=50, freq="5min", tz=NY)
    fb = 20
    assert SEP._derive_fill_instant(idx, fb) == idx[fb]


def test_dst_fall_back_round_trip():
    idx = pd.date_range("2024-11-03 09:30", periods=50, freq="5min", tz=NY)
    fb = 20
    assert SEP._derive_fill_instant(idx, fb) == idx[fb]
