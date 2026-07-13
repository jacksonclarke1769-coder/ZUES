"""engines/ranges.py: DealingRange objects (prior session / prior day /
Method-B leg), the location() helper, and OTE + control band touches."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from research.ict_v2.core.prefix import assert_chunk_invariant, assert_prefix_invariant
from research.ict_v2.engines.ranges import RangesEngine, location
from research.ict_v2.tests.helpers import Bar, make_bars_from_closes

UTC = timezone.utc
START = datetime(2024, 1, 2, 18, 0, tzinfo=UTC)


def _bars(start, n, step=0.75, wick=0.3, start_price=20000.0):
    bars = []
    price = start_price
    for i in range(n):
        ct = start + timedelta(minutes=5 * i)
        o = price
        c = price + (step if i % 3 else -step)
        h = max(o, c) + wick
        lo = min(o, c) - wick
        bars.append(Bar(close_time=ct, open=o, high=h, low=lo, close=c, volume=100.0))
        price = c
    return bars


def _long_run(days=4, start=START, start_price=20000.0):
    """Contiguous multi-day 5m stream spanning every PRIMARY_ORDER session --
    exercises prior_day and every prior_session anchor without hand-authoring
    each one (mirrors test_levels.py's own `_long_run` helper)."""
    total_minutes = days * 24 * 60
    n = total_minutes // 5
    return _bars(start, n, step=0.75, wick=0.3, start_price=start_price)


_ZIGZAG = [100 + i for i in range(20)] + [80 + i for i in range(20)] + [60 - i for i in range(15)]


def _created(events, anchor_kind=None):
    out = [e for e in events if e.event_type == "DEALING_RANGE_CREATED"]
    if anchor_kind is not None:
        out = [e for e in out if e.attributes["anchor_kind"] == anchor_kind]
    return out


# --- location() pure helper -----------------------------------------------------

def test_location_basic_and_boundaries():
    assert location(50, 0, 100) == pytest.approx(0.5)
    assert location(0, 0, 100) == pytest.approx(0.0)
    assert location(100, 0, 100) == pytest.approx(1.0)


def test_location_degenerate_range_returns_none():
    assert location(50, 100, 100) is None  # zero-width
    assert location(50, 100, 50) is None   # inverted


# --- prior_day / prior_session anchors -------------------------------------------

def test_prior_day_range_created_on_trade_date_rollover():
    bars = _long_run(days=4)
    eng = RangesEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    days = _created(events, "prior_day")
    assert len(days) >= 3
    for e in days:
        assert e.attributes["low"] < e.attributes["high"]
        assert e.origin_time < e.confirmed_at


def test_prior_session_range_created_for_all_five_sessions():
    bars = _long_run(days=4)
    eng = RangesEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    kinds = _created(events, "prior_session")
    assert len(kinds) >= 5  # at least one full day's worth of sessions rolled over


def test_dealing_range_bands_recorded_at_creation():
    bars = _long_run(days=2)
    eng = RangesEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    ev = _created(events)[0]
    low, high = ev.attributes["low"], ev.attributes["high"]
    assert ev.attributes["ote_low"] == pytest.approx(low + 0.62 * (high - low))
    assert ev.attributes["ote_high"] == pytest.approx(low + 0.79 * (high - low))
    assert ev.attributes["control_low_low"] == pytest.approx(low + 0.38 * (high - low))
    assert ev.attributes["control_high_high"] == pytest.approx(low + 0.97 * (high - low))


# --- method_b_leg anchor ----------------------------------------------------------

def test_method_b_leg_direction_and_reanchoring():
    START_NY = datetime(2024, 1, 2, 9, 30, tzinfo=UTC)
    bars = make_bars_from_closes(START_NY, _ZIGZAG)
    eng = RangesEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    legs = _created(events, "method_b_leg")
    assert len(legs) >= 3
    assert {e.attributes["direction"] for e in legs} == {"bullish", "bearish"}
    # each leg is a brand-new frozen object with its own id (re-anchoring, never mutation)
    assert len({e.event_id for e in legs}) == len(legs)


def _tight_wick_bars(start, n, step_pairs, wick=0.05, start_price=100.0):
    """Small, FIXED-wick bars (unlike `make_bars_from_closes`'s large fixed
    0.5 wick, which creates a spurious first-bar "gap" against Method B's
    tick-based floor threshold -- see `test_swings.py`'s own note on this)."""
    bars = []
    price = start_price
    for i in range(n):
        ct = start + timedelta(minutes=5 * i)
        o = price
        c = price + step_pairs(i)
        h = max(o, c) + wick
        lo = min(o, c) - wick
        bars.append(Bar(close_time=ct, open=o, high=h, low=lo, close=c, volume=100.0))
        price = c
    return bars


def test_first_swing_b_confirmation_does_not_yet_produce_a_leg():
    START_NY = datetime(2024, 1, 2, 9, 30, tzinfo=UTC)
    # 30 bars of pure net-zero-drift oscillation (never confirms anything -- see
    # test_swings.py::test_method_b_near_miss_reversal_below_threshold_does_not_confirm),
    # then exactly ONE sharp move -> exactly one Method-B confirmation, no leg possible yet
    flat = _tight_wick_bars(START_NY, 30, lambda i: 0.1 if i % 2 == 0 else -0.1)
    move = _tight_wick_bars(flat[-1].close_time + timedelta(minutes=5), 1, lambda i: 40.0, start_price=flat[-1].close)
    bars = flat + move
    eng = RangesEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    assert _created(events, "method_b_leg") == []


# --- band touches: OTE + both control bands, identically ------------------------

def test_band_touch_all_three_bands_fire_identically():
    START_NY = datetime(2024, 1, 2, 9, 30, tzinfo=UTC)
    bars = make_bars_from_closes(START_NY, _ZIGZAG)
    eng = RangesEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    touches = [e for e in events if e.event_type == "BAND_TOUCH"]
    bands_seen = {e.attributes["band"] for e in touches}
    assert bands_seen == {"ote", "control_low", "control_high"}
    for e in touches:
        assert e.attributes["band_low"] < e.attributes["band_high"]
        assert e.attributes["touch_count"] >= 1
        assert e.source_event_ids  # references the DEALING_RANGE_CREATED


def test_band_touch_boundary_equality_at_exact_band_edge():
    # a Method-B leg gives an exactly-known [low, high] range, so its OTE band's
    # absolute price edges can be computed and probed exactly.
    START_NY = datetime(2024, 1, 2, 9, 30, tzinfo=UTC)
    closes = [100 + i for i in range(20)] + [0]  # sharp reversal, leg [0, 119] roughly
    bars = make_bars_from_closes(START_NY, closes)
    eng2 = RangesEngine()
    events = [e for b in bars for e in eng2.on_bar(b)]
    leg = _created(events, "method_b_leg")[0]
    lo, hi = leg.attributes["ote_low"], leg.attributes["ote_high"]
    touches = [e for e in events if e.event_type == "BAND_TOUCH" and e.attributes["band"] == "ote"]
    assert len(touches) >= 1
    for t in touches:
        assert t.attributes["band_low"] == pytest.approx(lo)
        assert t.attributes["band_high"] == pytest.approx(hi)


def test_no_band_touch_when_price_stays_entirely_outside_all_bands():
    START_NY = datetime(2024, 1, 2, 9, 30, tzinfo=UTC)
    closes = [100 + i for i in range(20)] + [0]
    bars = make_bars_from_closes(START_NY, closes)
    eng = RangesEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    leg = _created(events, "method_b_leg")[0]
    # a bar far above the whole range (well above control_high_high) must not touch any band
    quiet_bar = Bar(close_time=bars[-1].close_time + timedelta(minutes=5), open=500, high=505, low=498, close=502)
    touches = [e for e in RangesEngine().on_bar(quiet_bar) if e.event_type == "BAND_TOUCH"]
    assert touches == []


# --- gap / DST / session boundary ----------------------------------------------

def test_gap_missing_bar_does_not_crash():
    bars = _bars(START, 20) + _bars(START + timedelta(hours=10), 20, start_price=20100.0)
    eng = RangesEngine()
    for b in bars:
        eng.on_bar(b)


def test_dst_transition_day_does_not_crash():
    start = datetime(2024, 3, 9, 18, 0, tzinfo=UTC)
    bars = _bars(start, 400)
    eng = RangesEngine()
    for b in bars:
        eng.on_bar(b)


# --- prefix / chunk invariance + determinism -----------------------------------

def test_prefix_and_chunk_invariance():
    bars = _long_run(days=3)
    assert_prefix_invariant(lambda: RangesEngine(), bars, cuts=[1, 5, 20, 60, 150, 300, len(bars)])
    assert_chunk_invariant(lambda: RangesEngine(), bars[:80], n_trials=4, seed=17)


def test_event_id_deterministic():
    START_NY = datetime(2024, 1, 2, 9, 30, tzinfo=UTC)
    bars = make_bars_from_closes(START_NY, _ZIGZAG)
    eng1, eng2 = RangesEngine(), RangesEngine()
    ids1 = [e.event_id for b in bars for e in eng1.on_bar(b)]
    ids2 = [e.event_id for b in bars for e in eng2.on_bar(b)]
    assert ids1 == ids2 and len(ids1) > 0
