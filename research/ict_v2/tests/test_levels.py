"""engines/levels.py: the level registry -- every kind's creation trigger,
LEVEL_TESTED / LEVEL_EXPIRED lifecycle, and salience components."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from research.ict_v2.core.clock import NY
from research.ict_v2.core.prefix import assert_chunk_invariant, assert_prefix_invariant
from research.ict_v2.core.runner import run_engine
from research.ict_v2.engines.levels import LevelRegistry
from research.ict_v2.tests.helpers import Bar

START = datetime(2024, 1, 2, 9, 30, tzinfo=NY)


def _bars(start, n, step=0.5, wick=0.2, start_price=20000.0):
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


def _long_run(days=8, start=datetime(2024, 1, 2, 18, 0, tzinfo=NY), start_price=20000.0):
    """A long, contiguous, deterministic multi-day 5m bar stream spanning
    overnight/asia/london/ny_am/ny_lunch/ny_pm every day -- exercises every
    bucket kind (day/week/session/OR/overnight) without hand-authoring each."""
    total_minutes = days * 24 * 60
    n = total_minutes // 5
    return _bars(start, n, step=0.75, wick=0.3, start_price=start_price)


def _kinds_of(events):
    return [e.attributes["kind"] for e in events if e.event_type == "LEVEL_CREATED"]


# --- bucketed kinds: pdh/pdl, pwh/pwl, session H/L --------------------------------

def test_pdh_pdl_finalize_on_trade_date_rollover():
    bars = _long_run(days=4)
    store = run_engine(LevelRegistry(), bars)
    created = [e for e in store.all if e.event_type == "LEVEL_CREATED"]
    pdh = [e for e in created if e.attributes["kind"] == "pdh"]
    pdl = [e for e in created if e.attributes["kind"] == "pdl"]
    assert len(pdh) >= 3 and len(pdl) >= 3
    # each PDH's origin is strictly before its confirmed_at (learned on rollover)
    for e in pdh:
        assert e.origin_time < e.confirmed_at


def test_pwh_pwl_finalize_on_week_rollover_and_are_weekly_class():
    bars = _long_run(days=10)
    store = run_engine(LevelRegistry(), bars)
    created = [e for e in store.all if e.event_type == "LEVEL_CREATED"]
    pwh = [e for e in created if e.attributes["kind"] == "pwh"]
    assert len(pwh) >= 1
    assert pwh[0].attributes["timeframe_class"] == "weekly"


def test_session_high_low_only_for_asia_london_ny_am():
    bars = _long_run(days=3)
    store = run_engine(LevelRegistry(), bars)
    created = [e for e in store.all if e.event_type == "LEVEL_CREATED"]
    sessions_seen = {e.attributes["session"] for e in created if e.attributes["kind"] in ("session_high", "session_low")}
    assert sessions_seen <= {"asia", "london", "ny_am"}
    assert sessions_seen  # at least one fired


# --- OR / overnight (internal) ---------------------------------------------------

def test_or_high_low_created_once_per_trading_day():
    bars = _long_run(days=3)
    store = run_engine(LevelRegistry(), bars)
    created = [e for e in store.all if e.event_type == "LEVEL_CREATED"]
    or_levels = [e for e in created if e.attributes["kind"] in ("or_high", "or_low")]
    assert len(or_levels) >= 2  # at least one trading day's worth (high+low)


def test_overnight_high_low_created_once_per_trading_day():
    bars = _long_run(days=3)
    store = run_engine(LevelRegistry(), bars)
    created = [e for e in store.all if e.event_type == "LEVEL_CREATED"]
    on_levels = [e for e in created if e.attributes["kind"] in ("overnight_high", "overnight_low")]
    assert len(on_levels) >= 2


# --- Method-A swing levels + equal highs/lows -------------------------------------

def test_swing_a_levels_created_for_every_confirmed_pivot():
    from research.ict_v2.tests.helpers import make_bars_from_closes

    closes = [100, 101, 102, 103, 110, 103, 102, 101, 100, 99, 98, 97, 90, 97, 98, 99, 100]
    bars = make_bars_from_closes(START, closes)
    store = run_engine(LevelRegistry(), bars)
    created = [e for e in store.all if e.event_type == "LEVEL_CREATED"]
    swings = [e for e in created if e.attributes["kind"] in ("swing_high_a", "swing_low_a")]
    assert len(swings) == 2  # one high pivot (110), one low pivot (90)


def test_equal_highs_duplicate_extremes_use_outermost_price():
    from research.ict_v2.tests.helpers import make_bars_from_closes

    closes = ([100, 101, 102, 103, 110, 103, 102, 101, 100, 99, 98, 97, 90, 97, 98, 99, 100] +
              [101, 102, 103, 110.4, 103, 102, 101, 100, 99, 98, 97, 90, 97, 98, 99, 100, 101])
    bars = make_bars_from_closes(START, closes)
    store = run_engine(LevelRegistry(), bars)
    created = [e for e in store.all if e.event_type == "LEVEL_CREATED"]
    equal_highs = [e for e in created if e.attributes["kind"] == "equal_highs"]
    assert len(equal_highs) == 1
    assert equal_highs[0].attributes["price"] == pytest.approx(110.9)  # outermost of {110.5, 110.9}
    assert equal_highs[0].attributes["equality_count"] == 2


def test_equal_highs_near_miss_outside_tolerance_no_match():
    from research.ict_v2.tests.helpers import make_bars_from_closes

    # second peak is 5 points higher -- way outside equal_level_tolerance_ticks (2 ticks = 0.5pt)
    closes = ([100, 101, 102, 103, 110, 103, 102, 101, 100, 99, 98, 97, 90, 97, 98, 99, 100] +
              [101, 102, 103, 120, 103, 102, 101, 100, 99, 98, 97, 90, 97, 98, 99, 100, 101])
    bars = make_bars_from_closes(START, closes)
    store = run_engine(LevelRegistry(), bars)
    created = [e for e in store.all if e.event_type == "LEVEL_CREATED"]
    assert [e for e in created if e.attributes["kind"] == "equal_highs"] == []


def test_equal_highs_near_miss_too_close_in_bars_no_match():
    from research.ict_v2.core.config import ICT_V2_PARAMS_V0
    from dataclasses import replace
    from research.ict_v2.tests.helpers import make_bars_from_closes

    # two matching pivots only 1 bar apart (origin-to-origin) -- below min_bars_apart (5)
    closes = [100, 101, 102, 110, 102, 108, 110.1, 102, 101, 100]
    bars = make_bars_from_closes(START, closes)
    params = replace(ICT_V2_PARAMS_V0, swing_left=1, swing_right=1)
    store = run_engine(LevelRegistry(params=params), bars)
    created = [e for e in store.all if e.event_type == "LEVEL_CREATED"]
    swings = [e for e in created if e.attributes["kind"] == "swing_high_a"]
    assert len(swings) == 2  # both pivots confirm...
    assert [e for e in created if e.attributes["kind"] == "equal_highs"] == []  # ...but too close to pair


# --- round numbers -----------------------------------------------------------------

def test_round_number_registered_lazily_and_deduped():
    b1 = Bar(close_time=START, open=19998, high=20001, low=19997, close=20000.5)  # touches 20000 (major+minor) and 19950-ish? no
    b2 = Bar(close_time=START + timedelta(minutes=5), open=20000.5, high=20003, low=19999, close=20001)  # re-touches 20000
    store = run_engine(LevelRegistry(), [b1, b2])
    created = [e for e in store.all if e.event_type == "LEVEL_CREATED"]
    majors = [e for e in created if e.attributes["kind"] == "round_number_major" and e.attributes["price"] == 20000]
    assert len(majors) == 1  # registered once despite being touched by both bars


def test_round_number_near_miss_bar_never_reaches_a_multiple():
    b = Bar(close_time=START, open=20011, high=20014, low=20009, close=20012)  # stays within (20000,20050)
    store = run_engine(LevelRegistry(), [b])
    created = [e for e in store.all if e.event_type == "LEVEL_CREATED"]
    assert [e for e in created if "round_number" in e.attributes["kind"]] == []


# --- LEVEL_TESTED / LEVEL_EXPIRED lifecycle ----------------------------------------

def test_level_tested_boundary_equality_at_exact_tick_tolerance():
    b1 = Bar(close_time=START, open=19998, high=20001, low=19997, close=20000.5)  # creates round_number_major @ 20000
    # tolerance = 1 tick = 0.25pt; a bar trading down to 19999.75 (exactly level - tol) must test it
    b2 = Bar(close_time=START + timedelta(minutes=10), open=20010, high=20011, low=19999.75, close=20005)
    eng = LevelRegistry()
    events = eng.on_bar(b1) + eng.on_bar(b2)
    tested = [e for e in events if e.event_type == "LEVEL_TESTED" and e.attributes["kind"] == "round_number_major"]
    assert len(tested) == 1
    assert tested[0].attributes["test_count"] == 1


def test_level_tested_near_miss_just_outside_tolerance():
    b1 = Bar(close_time=START, open=19998, high=20001, low=19997, close=20000.5)  # creates round_number_major @ 20000
    # bar's own low sits 0.3pt ABOVE the level -- outside the 1-tick (0.25pt) tolerance,
    # so the level is never actually reached by this bar's [low, high] range.
    b2 = Bar(close_time=START + timedelta(minutes=10), open=20005, high=20011, low=20000.3, close=20005)
    eng = LevelRegistry()
    events = eng.on_bar(b1) + eng.on_bar(b2)
    tested = [e for e in events if e.event_type == "LEVEL_TESTED" and e.attributes["kind"] == "round_number_major"]
    assert tested == []


def test_full_lifecycle_walk_creation_test_expiry_no_test_after_expiry():
    bars = _long_run(days=6)
    store = run_engine(LevelRegistry(), bars)
    created_by_id = {e.event_id: e for e in store.all if e.event_type == "LEVEL_CREATED"}
    tested = [e for e in store.all if e.event_type == "LEVEL_TESTED"]
    expired = [e for e in store.all if e.event_type == "LEVEL_EXPIRED"]
    assert created_by_id and tested and expired  # every stage of the lifecycle actually occurred

    # every LEVEL_TESTED/LEVEL_EXPIRED references a real, earlier LEVEL_CREATED
    for e in tested + expired:
        assert len(e.source_event_ids) == 1
        src = created_by_id[e.source_event_ids[0]]
        assert src.confirmed_at <= e.confirmed_at

    # no level is tested strictly after its own expiry
    expired_at_by_level = {e.source_event_ids[0]: e.confirmed_at for e in expired}
    for e in tested:
        level_id = e.source_event_ids[0]
        if level_id in expired_at_by_level:
            assert e.confirmed_at <= expired_at_by_level[level_id]


def test_expires_at_recorded_and_intraday_class_shorter_than_weekly():
    bars = _long_run(days=10)
    store = run_engine(LevelRegistry(), bars)
    created = [e for e in store.all if e.event_type == "LEVEL_CREATED"]
    pdh = next(e for e in created if e.attributes["kind"] == "pdh")
    pwh = next(e for e in created if e.attributes["kind"] == "pwh")
    assert (pdh.attributes["expires_at"] - pdh.confirmed_at) < (pwh.attributes["expires_at"] - pwh.confirmed_at)


# --- salience components: no weights, no score ------------------------------------

def test_salience_components_present_and_no_score_field():
    bars = _long_run(days=3)
    store = run_engine(LevelRegistry(), bars)
    for e in store.all:
        if e.event_type != "LEVEL_CREATED":
            continue
        for key in ("timeframe_class", "prominence_above_pts", "prominence_below_pts",
                    "roundness_major", "roundness_minor", "equality_count"):
            assert key in e.attributes
        assert "score" not in e.attributes
        assert "weight" not in e.attributes


# --- gap / DST / session boundary --------------------------------------------------

def test_gap_missing_bar_does_not_crash():
    bars = _bars(START, 10) + _bars(START + timedelta(hours=8), 10, start_price=20100.0)
    eng = LevelRegistry()
    for b in bars:
        eng.on_bar(b)


def test_dst_transition_day_does_not_crash():
    start = datetime(2024, 3, 9, 18, 0, tzinfo=NY)  # overnight spans the spring-forward night
    bars = _bars(start, 250)
    eng = LevelRegistry()
    for b in bars:
        eng.on_bar(b)


# --- prefix / chunk invariance + determinism ---------------------------------------

def test_prefix_and_chunk_invariance():
    bars = _long_run(days=4)
    assert_prefix_invariant(lambda: LevelRegistry(), bars, cuts=[1, 5, 20, 60, 150, 300, len(bars)])
    assert_chunk_invariant(lambda: LevelRegistry(), bars[:80], n_trials=4, seed=9)


def test_event_id_deterministic():
    bars = _long_run(days=2)
    eng1, eng2 = LevelRegistry(), LevelRegistry()
    ids1 = [e.event_id for b in bars for e in eng1.on_bar(b)]
    ids2 = [e.event_id for b in bars for e in eng2.on_bar(b)]
    assert ids1 == ids2 and len(ids1) > 0
