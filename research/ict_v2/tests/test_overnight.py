"""engines/overnight.py: OVERNIGHT_COMPLETED at 09:30 ET (18:00 prior day ->
09:30 ET), gap vs prior RTH close, overnight net return."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from research.ict_v2.core.clock import NY
from research.ict_v2.core.prefix import assert_chunk_invariant, assert_prefix_invariant
from research.ict_v2.engines.overnight import OvernightEngine
from research.ict_v2.tests.helpers import Bar


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


def _full_day(day_date, price_before_close=20000.0):
    """ny_pm bar ending the RTH day (sets prior_rth_close) + the full overnight
    span (18:00 -> 09:25 next morning, 186 5m bars, ALL still `in_overnight`).
    The caller adds its own triggering bar at/after 09:30."""
    ny_pm_close_bar = Bar(
        close_time=datetime.combine(day_date, datetime.min.time(), tzinfo=NY).replace(hour=14, minute=55),
        open=price_before_close - 1, high=price_before_close + 1, low=price_before_close - 2,
        close=price_before_close,
    )
    asia_start = datetime.combine(day_date, datetime.min.time(), tzinfo=NY).replace(hour=18, minute=0)
    overnight_bars = _bars(asia_start, 186, start_price=price_before_close)  # 18:00 -> next 09:25 (5m steps)
    return [ny_pm_close_bar] + overnight_bars


def test_minimum_valid_case_completes_with_gap_and_net_return():
    bars = _full_day(datetime(2024, 1, 2).date(), price_before_close=20000.0)
    trigger = Bar(
        close_time=bars[-1].close_time + timedelta(minutes=5), open=20050.0, high=20055.0, low=20045.0, close=20051.0,
    )
    eng = OvernightEngine()
    events = [e for b in (bars + [trigger]) for e in eng.on_bar(b)]
    completed = [e for e in events if e.event_type == "OVERNIGHT_COMPLETED"]
    assert len(completed) == 1
    ev = completed[0]
    assert ev.attributes["prior_rth_close"] == pytest.approx(20000.0)
    assert ev.attributes["gap_vs_prior_rth_close"] == pytest.approx(trigger.open - 20000.0)
    assert ev.price_high is not None and ev.price_low is not None
    assert ev.attributes["overnight_range"] == pytest.approx(ev.price_high - ev.price_low)


def test_warmup_when_no_prior_rth_close_known_at_start_of_stream():
    # stream starts mid-overnight with no RTH bar ever seen before it
    asia_start = datetime(2024, 1, 2, 18, 0, tzinfo=NY)
    overnight_bars = _bars(asia_start, 186, start_price=20000.0)
    trigger = Bar(close_time=overnight_bars[-1].close_time + timedelta(minutes=5), open=20050, high=20055, low=20045, close=20051)
    eng = OvernightEngine()
    events = [e for b in (overnight_bars + [trigger]) for e in eng.on_bar(b)]
    warmup = [e for e in events if e.event_type == "OVERNIGHT_WARMUP"]
    completed = [e for e in events if e.event_type == "OVERNIGHT_COMPLETED"]
    assert len(warmup) == 1
    assert completed == []
    assert "no_prior_rth_close" in warmup[0].attributes["reason"]


def test_warmup_when_trade_date_has_zero_overnight_bars():
    # RTH close bar, then jump STRAIGHT to the first ny_am bar (no overnight bars at all)
    rth_close = Bar(close_time=datetime(2024, 1, 2, 14, 55, tzinfo=NY), open=19999, high=20001, low=19998, close=20000)
    trigger = Bar(close_time=datetime(2024, 1, 3, 9, 35, tzinfo=NY), open=20010, high=20020, low=20005, close=20015)
    eng = OvernightEngine()
    events = [e for b in (rth_close, trigger) for e in eng.on_bar(b)]
    warmup = [e for e in events if e.event_type == "OVERNIGHT_WARMUP"]
    assert len(warmup) == 1
    assert "no_overnight_bars" in warmup[0].attributes["reason"]


def test_gap_missing_exact_ny_am_bar_still_triggers_on_first_bar_seen_in_ny_am():
    bars = _full_day(__import__("datetime").date(2024, 1, 2), price_before_close=20000.0)
    # skip straight to 10:00 (past 09:30) instead of the immediately-next bar
    late_trigger = Bar(close_time=datetime(2024, 1, 3, 10, 0, tzinfo=NY), open=20100, high=20110, low=20090, close=20105)
    eng = OvernightEngine()
    events = [e for b in (bars + [late_trigger]) for e in eng.on_bar(b)]
    completed = [e for e in events if e.event_type == "OVERNIGHT_COMPLETED"]
    assert len(completed) == 1
    assert completed[0].confirmed_at == late_trigger.close_time


def test_duplicate_extremes_within_overnight_window_still_max_correctly():
    day = __import__("datetime").date(2024, 1, 2)
    rth_close = Bar(close_time=datetime(2024, 1, 2, 14, 55, tzinfo=NY), open=19999, high=20001, low=19998, close=20000)
    o1 = Bar(close_time=datetime(2024, 1, 2, 19, 0, tzinfo=NY), open=20000, high=20050, low=19990, close=20010)
    o2 = Bar(close_time=datetime(2024, 1, 2, 20, 0, tzinfo=NY), open=20010, high=20050, low=19985, close=20005)  # ties the high
    trigger = Bar(close_time=datetime(2024, 1, 3, 9, 35, tzinfo=NY), open=20020, high=20030, low=20010, close=20025)
    eng = OvernightEngine()
    events = [e for b in (rth_close, o1, o2, trigger) for e in eng.on_bar(b)]
    completed = [e for e in events if e.event_type == "OVERNIGHT_COMPLETED"][0]
    assert completed.price_high == 20050
    assert completed.price_low == 19985


def test_dst_transition_day_does_not_crash():
    day = __import__("datetime").date(2024, 3, 9)  # overnight spans the spring-forward night
    bars = _full_day(day, price_before_close=20000.0)
    trigger = Bar(close_time=bars[-1].close_time + timedelta(minutes=5), open=20050, high=20055, low=20045, close=20051)
    eng = OvernightEngine()
    for b in bars + [trigger]:
        eng.on_bar(b)


def test_prefix_and_chunk_invariance():
    bars = _full_day(__import__("datetime").date(2024, 1, 2), price_before_close=20000.0)
    trigger = Bar(close_time=bars[-1].close_time + timedelta(minutes=5), open=20050, high=20055, low=20045, close=20051)
    all_bars = bars + [trigger]
    assert_prefix_invariant(lambda: OvernightEngine(), all_bars)
    assert_chunk_invariant(lambda: OvernightEngine(), all_bars, n_trials=5, seed=6)


def test_event_id_deterministic_and_actionable_after_confirmed():
    bars = _full_day(__import__("datetime").date(2024, 1, 2), price_before_close=20000.0)
    trigger = Bar(close_time=bars[-1].close_time + timedelta(minutes=5), open=20050, high=20055, low=20045, close=20051)
    all_bars = bars + [trigger]
    eng1, eng2 = OvernightEngine(), OvernightEngine()
    ids1 = [e.event_id for b in all_bars for e in eng1.on_bar(b)]
    ids2 = [e.event_id for b in all_bars for e in eng2.on_bar(b)]
    assert ids1 == ids2 and len(ids1) > 0
    eng3 = OvernightEngine()
    for e in [e for b in all_bars for e in eng3.on_bar(b)]:
        assert e.actionable_at > e.confirmed_at
