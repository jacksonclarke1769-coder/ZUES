"""engines/opening_range.py: OR_DEVELOPING / OR_COMPLETED at the 09:30 ET
anchor, v0 duration_minutes=15."""
from __future__ import annotations

from datetime import datetime, time, timedelta

import pytest

from research.ict_v2.core.clock import NY
from research.ict_v2.core.prefix import assert_chunk_invariant, assert_prefix_invariant
from research.ict_v2.engines.opening_range import OpeningRangeEngine
from research.ict_v2.tests.helpers import Bar

START = datetime(2024, 1, 2, 9, 30, tzinfo=NY)  # Tuesday, ordinary trading day


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


def test_minimum_valid_case_completes_at_the_exact_window_boundary():
    bars = _bars(START, 4)  # bars close at 09:35, 09:40, 09:45, 09:50
    eng = OpeningRangeEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    completed = [e for e in events if e.event_type == "OR_COMPLETED"]
    developing = [e for e in events if e.event_type == "OR_DEVELOPING"]
    assert len(completed) == 1
    assert len(developing) == 2  # 09:35, 09:40 (09:45 is the exact boundary -> COMPLETED)
    assert completed[0].confirmed_at == START + timedelta(minutes=15)
    assert completed[0].attributes["n_bars"] == 3
    expected_high = max(b.high for b in bars[:3])
    expected_low = min(b.low for b in bars[:3])
    assert completed[0].price_high == pytest.approx(expected_high)
    assert completed[0].price_low == pytest.approx(expected_low)


def test_near_miss_bar_closing_exactly_before_window_open_is_excluded():
    bar = Bar(close_time=START, open=100, high=101, low=99, close=100)  # closes AT 09:30, not after
    eng = OpeningRangeEngine()
    assert eng.on_bar(bar) == []


def test_boundary_equality_bar_at_window_end_is_included_in_completed_range():
    bars = _bars(START, 4)  # 09:30 (excluded), 09:35, 09:40, 09:45 (exact boundary)
    eng = OpeningRangeEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    completed = [e for e in events if e.event_type == "OR_COMPLETED"][0]
    assert completed.attributes["n_bars"] == 3  # the 09:45 bar itself is folded in


def test_duplicate_extreme_high_across_two_bars_is_still_the_max():
    b1 = Bar(close_time=START + timedelta(minutes=5), open=100, high=105, low=99, close=104)
    b2 = Bar(close_time=START + timedelta(minutes=10), open=104, high=105, low=100, close=101)  # ties the high
    b3 = Bar(close_time=START + timedelta(minutes=15), open=101, high=102, low=98, close=100)
    eng = OpeningRangeEngine()
    events = [e for e in (eng.on_bar(b1) + eng.on_bar(b2) + eng.on_bar(b3))]
    completed = [e for e in events if e.event_type == "OR_COMPLETED"][0]
    assert completed.price_high == 105


def test_gap_missing_exact_boundary_bar_finalizes_on_the_next_observed_bar_using_only_in_window_data():
    b1 = Bar(close_time=START + timedelta(minutes=5), open=100, high=102, low=99, close=101)
    b2 = Bar(close_time=START + timedelta(minutes=10), open=101, high=103, low=100, close=102)
    # the 09:45 bar is MISSING; next bar closes at 09:55 (10 minutes later, past window_end)
    b3 = Bar(close_time=START + timedelta(minutes=25), open=102, high=500, low=1, close=200)
    eng = OpeningRangeEngine()
    events = eng.on_bar(b1) + eng.on_bar(b2) + eng.on_bar(b3)
    completed = [e for e in events if e.event_type == "OR_COMPLETED"]
    assert len(completed) == 1
    # only b1/b2's range counts -- NOT b3's huge range, which is outside the window
    assert completed[0].price_high == 103
    assert completed[0].price_low == 99
    assert completed[0].confirmed_at == b3.close_time  # confirmed when we OBSERVE the gap


def test_total_data_gap_over_the_whole_window_emits_nothing():
    b1 = Bar(close_time=START + timedelta(minutes=25), open=100, high=101, low=99, close=100)
    eng = OpeningRangeEngine()
    assert eng.on_bar(b1) == []


def test_session_boundary_second_trading_day_gets_its_own_completed_event():
    day1 = _bars(START, 4)
    day2_start = datetime(2024, 1, 3, 9, 30, tzinfo=NY)
    day2 = _bars(day2_start, 4, start_price=20100.0)
    eng = OpeningRangeEngine()
    events = [e for b in (day1 + day2) for e in eng.on_bar(b)]
    completed = [e for e in events if e.event_type == "OR_COMPLETED"]
    assert len(completed) == 2
    assert completed[0].attributes["trade_date"] != completed[1].attributes["trade_date"]


def test_dst_transition_day_09_30_anchor_is_correct():
    # 2024-03-10 spring-forward: 09:30 ET must still be the correct wall-clock anchor
    start = datetime(2024, 3, 10, 9, 30, tzinfo=NY)
    bars = _bars(start, 4)
    eng = OpeningRangeEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    completed = [e for e in events if e.event_type == "OR_COMPLETED"]
    assert len(completed) == 1
    assert completed[0].confirmed_at.astimezone(NY).time() == time(9, 45)


def test_duration_param_options():
    for dur in (5, 15, 30):
        eng = OpeningRangeEngine(duration_minutes=dur)
        assert eng.duration_minutes == dur
    with pytest.raises(ValueError):
        OpeningRangeEngine(duration_minutes=7)


def test_prefix_and_chunk_invariance():
    bars = _bars(START, 40)
    assert_prefix_invariant(lambda: OpeningRangeEngine(), bars)
    assert_chunk_invariant(lambda: OpeningRangeEngine(), bars, n_trials=6, seed=4)


def test_event_id_deterministic_and_actionable_after_confirmed():
    bars = _bars(START, 4)
    eng1, eng2 = OpeningRangeEngine(), OpeningRangeEngine()
    ids1 = [e.event_id for b in bars for e in eng1.on_bar(b)]
    ids2 = [e.event_id for b in bars for e in eng2.on_bar(b)]
    assert ids1 == ids2 and len(ids1) > 0
    eng3 = OpeningRangeEngine()
    for e in [e for b in bars for e in eng3.on_bar(b)]:
        assert e.actionable_at > e.confirmed_at
