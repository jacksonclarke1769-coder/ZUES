"""engines/amd.py: AMD FSM -- SEARCH -> ACCUMULATION_ACTIVE -> EXCURSION ->
MANIPULATION_CANDIDATE -> DISTRIBUTION_CONFIRMED, plus every AMD_FAILED_<STATE>
timeout branch. All scenarios below are built from a shared "volatile phase
(inflates ATR20) then a tight phase (rolling 12-bar range collapses)" base
-- the range-window(12) < 0.6*ATR20 condition can ONLY be satisfied transiently
while ATR is still elevated from the volatile phase's history (see amd.py's
own module docstring); this is a real, non-degenerate property of the FSM,
not a test-only artifact."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from research.ict_v2.core.prefix import assert_chunk_invariant, assert_prefix_invariant
from research.ict_v2.engines.amd import AmdEngine
from research.ict_v2.tests.helpers import Bar

UTC = timezone.utc
START = datetime(2024, 1, 2, 9, 30, tzinfo=UTC)


def _bar(ct, o, h, l, c, v=100.0):
    return Bar(close_time=ct, open=o, high=h, low=l, close=c, volume=v)


def _t(k):
    return START + timedelta(minutes=5 * k)


def _volatile_then_tight(n_vol=25, vol_swing=6.0, vol_wick=1.0, n_tight=17, tight_step=0.1, tight_wick=0.1, start_price=100.0):
    """`n_vol` bars of large alternating swings (inflates ATR20), then
    `n_tight` bars of a small net-zero-drift oscillation (the rolling 12-bar
    range collapses well below the still-elevated ATR20 for several bars --
    exactly the transient window `ACCUMULATION_ACTIVE` fires in). Returns
    `(bars, last_price)`."""
    bars = []
    price = start_price
    for i in range(n_vol):
        ct = _t(i)
        o = price
        c = price + (vol_swing if i % 2 == 0 else -vol_swing)
        h, lo = max(o, c) + vol_wick, min(o, c) - vol_wick
        bars.append(_bar(ct, o, h, lo, c))
        price = c
    for i in range(n_tight):
        ct = _t(n_vol + i)
        o = price
        c = price + (tight_step if i % 2 == 0 else -tight_step)
        h, lo = max(o, c) + tight_wick, min(o, c) - tight_wick
        bars.append(_bar(ct, o, h, lo, c))
        price = c
    return bars, price


def _by_type(events, event_type):
    return [e for e in events if e.event_type == event_type]


# --- SEARCH -> ACCUMULATION_ACTIVE: minimum valid / near miss / boundary --------

def test_minimum_valid_accumulation_active_after_streak():
    bars, _ = _volatile_then_tight()  # verified to trigger at bar index 41
    eng = AmdEngine()
    all_events = [e for b in bars for e in eng.on_bar(b)]
    active = _by_type(all_events, "AMD_ACCUMULATION_ACTIVE")
    assert len(active) == 1
    assert active[0].attributes["frozen_low"] < active[0].attributes["frozen_high"]
    assert active[0].attributes["window_bars"] == 12
    assert eng.state == "ACCUMULATION_ACTIVE"


def test_near_miss_pure_tight_oscillation_alone_never_triggers():
    # NO preceding volatile phase -- in true steady state, the 12-bar range
    # window and ATR20 converge to the SAME magnitude (rng == ATR), so
    # rng < 0.6*ATR can never hold (see amd.py's module docstring).
    bars, _ = _volatile_then_tight(n_vol=0, n_tight=60)
    eng = AmdEngine()
    all_events = [e for b in bars for e in eng.on_bar(b)]
    assert _by_type(all_events, "AMD_ACCUMULATION_ACTIVE") == []


def test_boundary_equality_range_exactly_at_threshold_does_not_count():
    # hand-solved so the rolling 12-bar range EXACTLY equals 0.6*ATR20 at the
    # bar where the streak would otherwise be 4 (bars before it: streak 1,2,3
    # strictly satisfy '<'; the exact-equality bar must reset it to 0).
    bars, _ = _volatile_then_tight(n_vol=20, vol_swing=11.0, vol_wick=0.0, n_tight=20, tight_step=3.0, tight_wick=0.0)
    eng = AmdEngine()
    streaks = []
    for b in bars:
        eng.on_bar(b)
        streaks.append(eng._streak)
    # streak climbs 1, 2, 3 then resets to 0 exactly where range == threshold
    idx = next(i for i, s in enumerate(streaks) if s == 3)
    assert streaks[idx + 1] == 0
    assert streaks[idx - 1] == 2 and streaks[idx - 2] == 1


# --- full success path: EXCURSION -> MANIPULATION_CANDIDATE -> DISTRIBUTION -----

def test_full_success_path_distribution_confirmed():
    bars, price = _volatile_then_tight()
    n0 = len(bars)
    bars.append(_bar(_t(n0), price, 112.0, price - 0.2, 111.5))       # breakout up -> EXCURSION
    price = 111.5
    bars.append(_bar(_t(n0 + 1), price, 111.6, 105.0, 105.5))         # reclaim -> MANIPULATION_CANDIDATE
    price = 105.5
    bars.append(_bar(_t(n0 + 2), price, 105.8, 105.2, 105.6))         # filler
    price = 105.6
    bars.append(_bar(_t(n0 + 3), price, 105.7, 95.0, 96.0))           # big bearish displacement -> DISTRIBUTION_CONFIRMED

    eng = AmdEngine()
    all_events = [e for b in bars for e in eng.on_bar(b)]
    active = _by_type(all_events, "AMD_ACCUMULATION_ACTIVE")[0]
    excursion = _by_type(all_events, "AMD_EXCURSION")[0]
    manip = _by_type(all_events, "AMD_MANIPULATION_CANDIDATE")[0]
    dist = _by_type(all_events, "AMD_DISTRIBUTION_CONFIRMED")[0]

    assert excursion.attributes["direction"] == "up"
    assert manip.source_event_ids == (excursion.event_id,)
    assert dist.source_event_ids[0] == manip.event_id
    assert dist.attributes["distribution_direction"] == "bearish"
    # origin_time is carried forward from the very first event of the episode (structure.py convention)
    assert excursion.origin_time == active.origin_time == manip.origin_time == dist.origin_time
    assert eng.state == "SEARCH"  # ready for the next episode


# --- every AMD_FAILED_<STATE> timeout branch ------------------------------------

def test_amd_failed_accumulation_timeout():
    bars, _ = _volatile_then_tight(n_tight=30)  # accumulation active at bar 41, then no boundary break for 13+ more bars
    eng = AmdEngine()
    all_events = [e for b in bars for e in eng.on_bar(b)]
    failed = _by_type(all_events, "AMD_FAILED_ACCUMULATION")
    assert len(failed) == 1
    assert failed[0].source_event_ids == (_by_type(all_events, "AMD_ACCUMULATION_ACTIVE")[0].event_id,)
    assert eng.state == "SEARCH"


def test_amd_failed_excursion_timeout():
    bars, price = _volatile_then_tight()
    n0 = len(bars)
    bars.append(_bar(_t(n0), price, 112.0, price - 0.2, 111.5))  # breakout up -> EXCURSION
    price = 111.5
    for i in range(8):  # never reclaims back below frozen_high for 8 bars (> reclaim_bars=6)
        o = price
        c = price + 0.5
        bars.append(_bar(_t(n0 + 1 + i), o, c + 0.2, o - 0.2, c))
        price = c

    eng = AmdEngine()
    all_events = [e for b in bars for e in eng.on_bar(b)]
    excursion = _by_type(all_events, "AMD_EXCURSION")[0]
    failed = _by_type(all_events, "AMD_FAILED_EXCURSION")
    assert len(failed) == 1
    assert failed[0].source_event_ids == (excursion.event_id,)
    assert failed[0].attributes["bars_since_excursion"] == 7
    assert eng.state == "SEARCH"


def test_amd_failed_manipulation_timeout():
    bars, price = _volatile_then_tight()
    n0 = len(bars)
    bars.append(_bar(_t(n0), price, 112.0, price - 0.2, 111.5))     # breakout up -> EXCURSION
    price = 111.5
    bars.append(_bar(_t(n0 + 1), price, 111.6, 105.0, 105.5))       # reclaim -> MANIPULATION_CANDIDATE
    price = 105.5
    for i in range(13):  # 13 small, non-qualifying bars -- no bearish DISPLACEMENT_QUALIFIED within 12
        o = price
        c = price + (0.1 if i % 2 == 0 else -0.1)
        bars.append(_bar(_t(n0 + 2 + i), o, max(o, c) + 0.1, min(o, c) - 0.1, c))
        price = c

    eng = AmdEngine()
    all_events = [e for b in bars for e in eng.on_bar(b)]
    manip = _by_type(all_events, "AMD_MANIPULATION_CANDIDATE")[0]
    failed = _by_type(all_events, "AMD_FAILED_MANIPULATION")
    assert len(failed) == 1
    assert failed[0].source_event_ids == (manip.event_id,)
    assert eng.state == "SEARCH"


# --- symmetric bearish episode (excursion down -> distribution bullish) ---------

def test_bearish_excursion_needs_bullish_distribution():
    bars, price = _volatile_then_tight()
    n0 = len(bars)
    bars.append(_bar(_t(n0), price, price + 0.2, 95.0, 95.5))       # breakdown -> EXCURSION down
    price = 95.5
    bars.append(_bar(_t(n0 + 1), price, 106.5, price - 0.2, 106.0))  # reclaim (close >= frozen_low) -> MANIPULATION_CANDIDATE
    price = 106.0
    bars.append(_bar(_t(n0 + 2), price, 106.3, 105.8, 106.1))
    price = 106.1
    bars.append(_bar(_t(n0 + 3), price, 118.0, price - 0.2, 117.0))  # big bullish displacement -> DISTRIBUTION_CONFIRMED

    eng = AmdEngine()
    all_events = [e for b in bars for e in eng.on_bar(b)]
    excursion = _by_type(all_events, "AMD_EXCURSION")[0]
    dist = _by_type(all_events, "AMD_DISTRIBUTION_CONFIRMED")
    assert excursion.attributes["direction"] == "down"
    assert len(dist) == 1
    assert dist[0].attributes["distribution_direction"] == "bullish"


# --- gap / DST / session boundary ----------------------------------------------

def test_gap_missing_bar_does_not_crash():
    bars, price = _volatile_then_tight(n_tight=10)
    bars.append(_bar(START + timedelta(hours=8), price, price + 5, price - 5, price + 2))
    eng = AmdEngine()
    for b in bars:
        eng.on_bar(b)


def test_dst_transition_day_does_not_crash():
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    start = datetime(2024, 3, 9, 18, 0, tzinfo=ny)
    bars = []
    price = 100.0
    for i in range(60):
        ct = start + timedelta(minutes=5 * i)
        o = price
        c = price + (3 if i % 4 == 0 else -1)
        bars.append(_bar(ct, o, max(o, c) + 0.5, min(o, c) - 0.5, c))
        price = c
    eng = AmdEngine()
    for b in bars:
        eng.on_bar(b)


# --- prefix / chunk invariance + determinism -----------------------------------

def _walk_bars():
    bars, price = _volatile_then_tight()
    n0 = len(bars)
    bars.append(_bar(_t(n0), price, 112.0, price - 0.2, 111.5))
    price = 111.5
    bars.append(_bar(_t(n0 + 1), price, 111.6, 105.0, 105.5))
    price = 105.5
    bars.append(_bar(_t(n0 + 2), price, 105.8, 105.2, 105.6))
    price = 105.6
    bars.append(_bar(_t(n0 + 3), price, 105.7, 95.0, 96.0))
    return bars


def test_prefix_and_chunk_invariance():
    bars = _walk_bars()
    assert_prefix_invariant(lambda: AmdEngine(), bars)
    assert_chunk_invariant(lambda: AmdEngine(), bars, n_trials=5, seed=19)


def test_event_id_deterministic():
    bars = _walk_bars()
    eng1, eng2 = AmdEngine(), AmdEngine()
    ids1 = [e.event_id for b in bars for e in eng1.on_bar(b)]
    ids2 = [e.event_id for b in bars for e in eng2.on_bar(b)]
    assert ids1 == ids2 and len(ids1) > 0
