"""EMIT-001 canary (prereg/EMIT-001.md, DEC-20260711-EMIT-001): the new EMISSION_MODE toggle
on ProfileAEngine.latest_signal().

Scope: signal DELIVERY only. certified_gate (DEFAULT, no emission_mode kwarg passed) must stay
byte-identical to pre-EMIT-001 behaviour -- the <=10min poll-time freshness gate on tail(3).
emit_at_fill removes ONLY that poll-time staleness check; every other condition (ny_am session
filter, acted_ts dedup, the ets<=recent causal safety net, the tail(3) scan window itself) is
shared, untouched code path. No detection/exit/risk/param change; model01 is never imported by
this file except via the existing _FakeM1 stand-in (mirrors test_latest_signal_timestamp_canary.py).

This is a PERMANENT regression guard: emit_at_fill must never emit ahead of causal availability
(ets > recent) and certified_gate must never drift from the original <=10min gate.
"""
import pandas as pd
import pytest

import strategy_engine_profileA as SEP
from strategy_engine_profileA import (
    ProfileAEngine,
    EMISSION_MODE_CERTIFIED_GATE,
    EMISSION_MODE_EMIT_AT_FILL,
)

NY = SEP.NY


# ── fakes (mirrors test_latest_signal_timestamp_canary.py) ──────────────────────────────────
class _FakeM1:
    def __init__(self, trades_df):
        self._df = trades_df

    def run(self, feats, symbol, params, realtime=False):
        return self._df.copy()


def _engine_with(feats_index, trades_df, recent, buf_len=2500, emission_mode=None):
    eng = ProfileAEngine({"nyam_start_min": 570, "nyam_end_min": 690, "flat_min": 870},
                          emission_mode=emission_mode)
    eng.buf = pd.DataFrame(
        {"Open": 0.0, "High": 0.0, "Low": 0.0, "Close": 0.0, "Volume": 0.0},
        index=pd.date_range(end=recent, periods=buf_len, freq="5min", tz=NY),
    )
    feats = pd.DataFrame(index=feats_index)
    eng._features = lambda: feats
    SEP.M1 = _FakeM1(trades_df)
    return eng


def _trade_row(fill_bar, session="ny_am", direction="long", date="d", time="t",
               entry=100.0, stop=99.0, target=102.0, rr=2.0, liq="pdh"):
    return dict(fill_bar=fill_bar, session=session, direction=direction, date=date, time=time,
                entry=entry, stop=stop, target=target, rr=rr, liq_swept=liq)


@pytest.fixture(autouse=True)
def _restore_m1():
    orig = SEP.M1
    yield
    SEP.M1 = orig


# ── 1. default / unknown-mode fail-closed ────────────────────────────────────────────────────
def test_default_mode_is_certified_gate():
    eng = ProfileAEngine({"nyam_start_min": 570, "nyam_end_min": 690, "flat_min": 870})
    assert eng.emission_mode == EMISSION_MODE_CERTIFIED_GATE


def test_unknown_emission_mode_raises_valueerror():
    with pytest.raises(ValueError):
        ProfileAEngine({"nyam_start_min": 570, "nyam_end_min": 690, "flat_min": 870},
                        emission_mode="not_a_real_mode")


# ── 2. certified_gate (DEFAULT / explicit) unchanged: stale -> None ─────────────────────────
@pytest.mark.parametrize("mode", [None, EMISSION_MODE_CERTIFIED_GATE])
def test_certified_gate_still_drops_stale_fill(mode):
    idx = pd.date_range("2024-06-03 09:30", periods=50, freq="5min", tz=NY)
    fb = 10
    true_fill_ts = idx[fb]
    tr = pd.DataFrame([_trade_row(fb)])
    recent = true_fill_ts + pd.Timedelta(minutes=45)     # well outside the 10min gate
    eng = _engine_with(idx, tr, recent, emission_mode=mode)
    assert eng.latest_signal() is None


@pytest.mark.parametrize("mode", [None, EMISSION_MODE_CERTIFIED_GATE])
def test_certified_gate_still_emits_fresh_fill(mode):
    idx = pd.date_range("2024-06-03 09:30", periods=50, freq="5min", tz=NY)
    fb = 30
    true_fill_ts = idx[fb]
    tr = pd.DataFrame([_trade_row(fb)])
    recent = true_fill_ts + pd.Timedelta(minutes=5)      # inside the 10min gate
    eng = _engine_with(idx, tr, recent, emission_mode=mode)
    sig = eng.latest_signal()
    assert sig is not None
    assert sig["ts_signal"] == true_fill_ts.isoformat()
    assert sig["emission_mode"] == EMISSION_MODE_CERTIFIED_GATE


# ── 3. emit_at_fill recovers a DELAYED (>10min stale) fill ──────────────────────────────────
def test_emit_at_fill_recovers_stale_fill_certified_gate_would_drop():
    idx = pd.date_range("2024-06-03 09:30", periods=50, freq="5min", tz=NY)
    fb = 10
    true_fill_ts = idx[fb]
    tr = pd.DataFrame([_trade_row(fb)])
    recent = true_fill_ts + pd.Timedelta(minutes=45)     # DELAYED-class staleness (INC-20260707)

    gated = _engine_with(idx, tr, recent, emission_mode=EMISSION_MODE_CERTIFIED_GATE)
    assert gated.latest_signal() is None                 # certified_gate: dropped (unchanged)

    fill = _engine_with(idx, tr, recent, emission_mode=EMISSION_MODE_EMIT_AT_FILL)
    sig = fill.latest_signal()
    assert sig is not None                                # emit_at_fill: recovered
    assert sig["ts_signal"] == true_fill_ts.isoformat()
    assert sig["entry"] == 100.0 and sig["stop"] == 99.0 and sig["target"] == 102.0
    assert sig["emission_mode"] == EMISSION_MODE_EMIT_AT_FILL


def test_emit_at_fill_still_dedupes_via_acted_ts():
    idx = pd.date_range("2024-06-03 09:30", periods=50, freq="5min", tz=NY)
    fb = 10
    true_fill_ts = idx[fb]
    tr = pd.DataFrame([_trade_row(fb)])
    recent = true_fill_ts + pd.Timedelta(minutes=45)
    eng = _engine_with(idx, tr, recent, emission_mode=EMISSION_MODE_EMIT_AT_FILL)
    first = eng.latest_signal()
    assert first is not None
    second = eng.latest_signal()                          # same tr, same fill -> already acted
    assert second is None


def test_emit_at_fill_respects_ny_am_session_filter():
    idx = pd.date_range("2024-06-03 09:30", periods=50, freq="5min", tz=NY)
    tr = pd.DataFrame([_trade_row(fill_bar=99999, session="london")])
    recent = idx[-1]
    eng = _engine_with(idx, tr, recent, emission_mode=EMISSION_MODE_EMIT_AT_FILL)
    assert eng.latest_signal() is None                    # ordinary skip, no raise


# ── 4. causal safety net: emit_at_fill must NEVER emit ets > recent ────────────────────────
def test_emit_at_fill_never_emits_ahead_of_recent():
    """Look-ahead guard: even in emit_at_fill mode, a fill instant strictly AFTER the most
    recent closed bar must never be emitted. Unreachable via the real model01/engine wiring
    (fill_bar is always <= the buffer's own last row) but asserted directly here as the
    permanent canary for the causal-safety net (`if ets > recent: continue`)."""
    idx = pd.date_range("2024-06-03 09:30", periods=50, freq="5min", tz=NY)
    fb = 40
    future_fill_ts = idx[fb]
    tr = pd.DataFrame([_trade_row(fb)])
    recent = future_fill_ts - pd.Timedelta(minutes=15)     # recent is BEFORE the "fill"
    eng = _engine_with(idx, tr, recent, emission_mode=EMISSION_MODE_EMIT_AT_FILL)
    assert eng.latest_signal() is None


def test_certified_gate_never_emits_ahead_of_recent_either():
    idx = pd.date_range("2024-06-03 09:30", periods=50, freq="5min", tz=NY)
    fb = 40
    future_fill_ts = idx[fb]
    tr = pd.DataFrame([_trade_row(fb)])
    recent = future_fill_ts - pd.Timedelta(minutes=15)
    eng = _engine_with(idx, tr, recent, emission_mode=EMISSION_MODE_CERTIFIED_GATE)
    assert eng.latest_signal() is None
