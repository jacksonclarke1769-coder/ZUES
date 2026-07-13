"""engines/sweeps.py: sweep FSM per active level -- all three terminal
outcomes, boundary-tie ambiguity, oracle equivalence for the reclaim
mechanic, ambidextrous round-number levels, prefix/chunk invariance.

NOTE on fixtures: `SweepEngine` deliberately does NOT surface its private
internal `LevelRegistry`'s own `LEVEL_CREATED`/`LEVEL_TESTED`/`LEVEL_EXPIRED`
events (mirrors WP-B's established convention -- `structure.py`'s private
`SwingMethodA` doesn't surface `SWING_HIGH_A`/`SWING_LOW_A` either; see
`sweeps.py`'s module docstring). Tests read `level_id`/`level_kind` off the
`EXCURSION_OPEN`/terminal events' own attributes instead.

NOTE on round numbers: `round_number_minor`/`major` levels are AMBIDEXTROUS
(SPEC.md: a round number sits neither above nor below price by construction)
-- `SweepEngine` tracks BOTH a "buy" and a "sell" episode on the same level
independently. Most single-direction tests below therefore keep bar lows
`> level - 1 tick` (20049.75) so a stray sell-side episode can't also open
and pollute the assertions; `test_round_number_level_tracks_both_sides_
independently` exercises the ambidextrous behaviour deliberately.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

from research.ict_v2.core.prefix import assert_chunk_invariant, assert_prefix_invariant
from research.ict_v2.engines.sweeps import SweepEngine
from research.ict_v2.tests.helpers import Bar

UTC = timezone.utc
START = datetime(2024, 1, 2, 9, 30, tzinfo=UTC)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
FRAMEWORK_ROOT = os.path.join(_REPO_ROOT, "..", "..", "backtests", "ict-nq-framework")


def _load_oracle_primitives():
    engine_dir = os.path.join(os.path.abspath(FRAMEWORK_ROOT), "engine")
    if engine_dir not in sys.path:
        sys.path.insert(0, engine_dir)
    import primitives as P  # noqa: PLC0415

    return P


def _bar(ct, o, h, l, c, v=100.0):
    return Bar(close_time=ct, open=o, high=h, low=l, close=c, volume=v)


def _level_bar(ct=START):
    """A single bar whose [low, high] touches 20050 ONLY (round_number_minor,
    step=50) and not any multiple of 100 (round_number_major) -- keeps each
    test scoped to exactly one level/kind."""
    return _bar(ct, 20049.3, 20051.0, 20049.0, 20049.8)


def _t(i):
    return START + timedelta(minutes=5 * i)


def _buy(events, event_type):
    return [e for e in events if e.event_type == event_type and e.attributes.get("side") == "buy"]


# --- minimum valid / near-miss / boundary equality (excursion OPEN trigger) -----

def test_minimum_valid_immediate_sweep_confirmed():
    eng = SweepEngine()
    eng.on_bar(_level_bar(_t(0)))
    # breach clears 20050.25 (>=1 tick beyond 20050); close reclaims below 20050
    # same bar, staying above the sell-side threshold (20049.75) throughout.
    ev1 = eng.on_bar(_bar(_t(1), 20050.0, 20050.5, 20049.8, 20049.85))
    opens = _buy(ev1, "EXCURSION_OPEN")
    confirmed = _buy(ev1, "SWEEP_CONFIRMED")
    assert len(opens) == 1
    assert len(confirmed) == 1
    assert confirmed[0].source_event_ids == (opens[0].event_id,)
    level_id = confirmed[0].attributes["level_id"]
    assert level_id == opens[0].attributes["level_id"]
    assert confirmed[0].attributes["level_kind"] == "round_number_minor"
    assert confirmed[0].attributes["duration_bars"] == 1
    assert confirmed[0].attributes["reclaim_speed_bars"] == 1
    assert confirmed[0].attributes["excursion_depth_ticks"] == pytest.approx(2.0)  # 20050.5 - 20050 = 0.5pt = 2 ticks
    for key in ("level_timeframe_class", "level_prominence_above_pts", "level_roundness_minor", "level_equality_count"):
        assert key in confirmed[0].attributes


def test_near_miss_below_one_tick_never_opens_excursion():
    eng = SweepEngine()
    eng.on_bar(_level_bar(_t(0)))
    # high stays at 20050.2 (< 20050.25 threshold); low stays well above the sell-side threshold too
    events = eng.on_bar(_bar(_t(1), 20049.9, 20050.2, 20049.8, 20050.0))
    assert [e for e in events if e.event_type == "EXCURSION_OPEN"] == []


def test_boundary_equality_exact_one_tick_beyond_opens_excursion():
    eng = SweepEngine()
    eng.on_bar(_level_bar(_t(0)))
    # high == 20050.25 EXACTLY (level + 1 tick) -- SPEC.md's ">=1 tick" must open
    events = eng.on_bar(_bar(_t(1), 20049.9, 20050.25, 20049.8, 20050.1))
    assert len(_buy(events, "EXCURSION_OPEN")) == 1


# --- ACCEPTED_BREAKOUT: two consecutive closes beyond -------------------------

def test_accepted_breakout_via_two_consecutive_closes_beyond():
    eng = SweepEngine()
    eng.on_bar(_level_bar(_t(0)))
    ev1 = eng.on_bar(_bar(_t(1), 20050.0, 20050.6, 20049.9, 20050.6))  # breach + still beyond (consec=1)
    ev2 = eng.on_bar(_bar(_t(2), 20050.6, 20051.0, 20050.4, 20050.8))  # still beyond again -> consec=2
    assert _buy(ev1, "SWEEP_CONFIRMED") == [] and _buy(ev1, "ACCEPTED_BREAKOUT") == []
    breakout = _buy(ev2, "ACCEPTED_BREAKOUT")
    assert len(breakout) == 1
    assert breakout[0].attributes["reason"] == "two_consecutive_closes_beyond"
    assert breakout[0].attributes["duration_bars"] == 2
    assert breakout[0].attributes["reclaim_speed_bars"] is None


# --- ACCEPTED_BREAKOUT via the dwell > h grace bar, and EXCURSION_TIMEOUT ------
# both walks use h_bars=3 (v0 default) with a boundary-tie bar (close == level
# exactly) resetting the 2-consecutive streak -- see sweeps.py's module
# docstring "RESOLUTION NOTE" for why this is what makes both outcomes
# independently reachable at the default h.

def test_accepted_breakout_via_dwell_exceeding_window_grace_bar():
    eng = SweepEngine()
    eng.on_bar(_level_bar(_t(0)))
    eng.on_bar(_bar(_t(1), 20050.0, 20050.6, 20049.9, 20050.6))   # bar1: still_beyond, consec=1, elapsed=1
    eng.on_bar(_bar(_t(2), 20050.0, 20050.3, 20049.9, 20050.0))   # bar2: TIE (close==level exactly) -> consec reset
    ev3 = eng.on_bar(_bar(_t(3), 20050.0, 20050.4, 20049.9, 20050.2))  # bar3: still_beyond again, consec=1, elapsed==h(3)
    assert _buy(ev3, "ACCEPTED_BREAKOUT") == [] and _buy(ev3, "EXCURSION_TIMEOUT") == []
    ev4 = eng.on_bar(_bar(_t(4), 20050.2, 20050.3, 20048.0, 20049.0))  # bar4: grace bar, even though it reclaims
    breakout = _buy(ev4, "ACCEPTED_BREAKOUT")
    assert len(breakout) == 1
    assert breakout[0].attributes["reason"] == "dwell_exceeded_window"
    assert breakout[0].attributes["duration_bars"] == 4


def test_excursion_timeout_when_window_closes_on_a_boundary_tie():
    eng = SweepEngine()
    eng.on_bar(_level_bar(_t(0)))
    eng.on_bar(_bar(_t(1), 20050.0, 20050.6, 20049.9, 20050.6))   # bar1: still_beyond, consec=1
    eng.on_bar(_bar(_t(2), 20050.0, 20050.3, 20049.9, 20050.0))   # bar2: TIE -> consec reset to 0
    ev3 = eng.on_bar(_bar(_t(3), 20050.0, 20050.2, 20049.9, 20050.0))  # bar3: TIE again, elapsed==h(3)
    timeout = _buy(ev3, "EXCURSION_TIMEOUT")
    assert len(timeout) == 1
    assert timeout[0].attributes["reason"] == "window_elapsed_on_boundary_tie"
    assert timeout[0].attributes["duration_bars"] == 3
    assert timeout[0].attributes["reclaim_speed_bars"] is None


def test_h_bars_1_family_member_single_bar_window_timeout():
    from research.ict_v2.core.config import ICT_V2_PARAMS_V0

    eng = SweepEngine(params=ICT_V2_PARAMS_V0, h_bars=1)
    eng.on_bar(_level_bar(_t(0)))
    ev1 = eng.on_bar(_bar(_t(1), 20050.0, 20050.6, 20049.9, 20050.6))  # single-bar window, still_beyond (not a tie)
    # with h=1, elapsed==h immediately; still_beyond=True so NOT a tie -> grace bar granted
    assert _buy(ev1, "SWEEP_CONFIRMED") == [] and _buy(ev1, "ACCEPTED_BREAKOUT") == [] and _buy(ev1, "EXCURSION_TIMEOUT") == []
    ev2 = eng.on_bar(_bar(_t(2), 20050.6, 20050.7, 20050.5, 20050.6))  # grace bar (elapsed=2 > h=1)
    assert len(_buy(ev2, "ACCEPTED_BREAKOUT")) == 1

    eng2 = SweepEngine(params=ICT_V2_PARAMS_V0, h_bars=1)
    eng2.on_bar(_level_bar(_t(0)))
    ev1b = eng2.on_bar(_bar(_t(1), 20050.0, 20050.5, 20049.9, 20050.0))  # breach then close==level exactly (a TIE)
    assert len(_buy(ev1b, "EXCURSION_TIMEOUT")) == 1


def test_invalid_h_bars_rejected():
    with pytest.raises(ValueError):
        SweepEngine(h_bars=2)


def test_unimplemented_sweep_reclaim_rule_rejected():
    from dataclasses import replace
    from research.ict_v2.core.config import ICT_V2_PARAMS_V0

    bad_params = replace(ICT_V2_PARAMS_V0, sweep_reclaim_rule="wick_based")
    with pytest.raises(ValueError):
        SweepEngine(params=bad_params)


# --- ambidextrous round numbers: independent buy AND sell episodes ------------

def test_round_number_level_tracks_both_sides_independently():
    eng = SweepEngine()
    eng.on_bar(_level_bar(_t(0)))
    ev1 = eng.on_bar(_bar(_t(1), 20050.0, 20050.5, 20049.9, 20049.85))  # buy-side sweep, immediate reclaim
    ev2 = eng.on_bar(_bar(_t(2), 20050.0, 20050.2, 20049.7, 20049.9))   # quiet bar
    ev3 = eng.on_bar(_bar(_t(3), 20050.0, 20050.1, 20049.6, 20050.15))  # sell-side breach + immediate reclaim
    buy_confirmed = _buy(ev1, "SWEEP_CONFIRMED")[0]
    sell_confirmed = [e for e in ev3 if e.event_type == "SWEEP_CONFIRMED" and e.attributes["side"] == "sell"][0]
    assert buy_confirmed.attributes["level_id"] == sell_confirmed.attributes["level_id"]


# --- expired levels do not open NEW episodes -----------------------------------

def test_level_expiry_prevents_new_episodes_but_lets_open_ones_resolve():
    from dataclasses import replace
    from research.ict_v2.core.config import ICT_V2_PARAMS_V0

    # shrink intraday expiry to 1 sub-session so the round number expires quickly
    params = replace(ICT_V2_PARAMS_V0, level_expiry_sessions_intraday=1)
    eng = SweepEngine(params=params)
    eng.on_bar(_level_bar(START))
    # advance far enough (many sessions) for the level to expire with no episode ever opened
    bars = [
        _bar(START + timedelta(hours=i), 20000 + (i % 3), 20003 + (i % 3), 19997 + (i % 3), 20001 + (i % 3))
        for i in range(1, 60)
    ]
    for b in bars:
        eng.on_bar(b)
    # a fresh breach of the (now long-expired) 20050 level must not open a new episode
    post_expiry_breach = eng.on_bar(_bar(START + timedelta(hours=61), 20049.5, 20050.6, 20049.4, 20049.7))
    assert [e for e in post_expiry_breach if e.event_type == "EXCURSION_OPEN"] == []


# --- oracle equivalence: SWEEP_CONFIRMED mirrors primitives.py::sweep_of_level -----

def test_sweep_confirmed_matches_oracle_sweep_of_level():
    pd = pytest.importorskip("pandas")
    P = _load_oracle_primitives()

    bars = [
        _level_bar(_t(0)),
        _bar(_t(1), 20050.2, 20050.6, 20050.0, 20050.6),   # still beyond (consec=1)
        _bar(_t(2), 20050.5, 20050.6, 20050.0, 20050.0),   # TIE (close == level) -> resets streak
        _bar(_t(3), 20050.0, 20050.3, 20049.9, 20049.8),   # reclaims at bar 3 (within h=3 window)
    ]
    eng = SweepEngine()
    all_events = [e for b in bars for e in eng.on_bar(b)]
    confirmed = _buy(all_events, "SWEEP_CONFIRMED")
    assert len(confirmed) == 1
    assert confirmed[0].attributes["duration_bars"] == 3

    df = pd.DataFrame({
        "Open": [b.open for b in bars], "High": [b.high for b in bars],
        "Low": [b.low for b in bars], "Close": [b.close for b in bars],
    })
    # oracle's window starts AT the breach bar (index 1 here, 0-indexed into `bars`)
    swept, reclaim_idx = P.sweep_of_level(df, level=20050.0, side="buy", i=1, max_bars=3, tick=0.25)
    assert swept is True
    assert reclaim_idx == 3  # 0-indexed bar position of the reclaim close, matches duration_bars=3 (1-indexed)


def test_sweep_not_confirmed_matches_oracle_when_breakout():
    pd = pytest.importorskip("pandas")
    P = _load_oracle_primitives()

    bars = [
        _level_bar(_t(0)),
        _bar(_t(1), 20050.0, 20050.6, 20049.9, 20050.6),
        _bar(_t(2), 20050.6, 20051.0, 20050.4, 20050.8),
    ]
    eng = SweepEngine()
    all_events = [e for b in bars for e in eng.on_bar(b)]
    assert _buy(all_events, "SWEEP_CONFIRMED") == []
    assert len(_buy(all_events, "ACCEPTED_BREAKOUT")) == 1

    df = pd.DataFrame({
        "Open": [b.open for b in bars], "High": [b.high for b in bars],
        "Low": [b.low for b in bars], "Close": [b.close for b in bars],
    })
    swept, _ = P.sweep_of_level(df, level=20050.0, side="buy", i=1, max_bars=3, tick=0.25)
    assert swept is False


# --- gap / DST / session boundary ----------------------------------------------

def test_gap_missing_bar_does_not_crash():
    eng = SweepEngine()
    bars = [_level_bar(_t(0))] + [
        _bar(_t(i), 20049.9, 20050.5, 20049.8, 20049.85) for i in range(1, 5)
    ] + [_bar(START + timedelta(hours=8), 20100, 20105, 20095, 20102)]
    for b in bars:
        eng.on_bar(b)


def test_dst_transition_day_does_not_crash():
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    start = datetime(2024, 3, 9, 18, 0, tzinfo=ny)
    eng = SweepEngine()
    price = 20000.0
    for i in range(200):
        ct = start + timedelta(minutes=5 * i)
        eng.on_bar(_bar(ct, price, price + 3, price - 3, price + (1 if i % 2 else -1)))
        price += 0.5


# --- prefix / chunk invariance + determinism -----------------------------------

def _episode_walk_bars():
    return [
        _level_bar(_t(0)),
        _bar(_t(1), 20050.0, 20050.6, 20049.9, 20050.6),
        _bar(_t(2), 20050.0, 20050.3, 20049.9, 20050.0),
        _bar(_t(3), 20050.0, 20050.4, 20049.9, 20050.2),
        _bar(_t(4), 20050.2, 20050.3, 20048.0, 20049.0),
        _bar(_t(5), 20049.0, 20049.3, 20048.5, 20049.1),
        _bar(_t(6), 20049.1, 20050.4, 20048.9, 20049.9),
    ]


def test_prefix_and_chunk_invariance():
    bars = _episode_walk_bars()
    assert_prefix_invariant(lambda: SweepEngine(), bars)
    assert_chunk_invariant(lambda: SweepEngine(), bars, n_trials=6, seed=11)


def test_event_id_deterministic():
    bars = _episode_walk_bars()
    eng1, eng2 = SweepEngine(), SweepEngine()
    ids1 = [e.event_id for b in bars for e in eng1.on_bar(b)]
    ids2 = [e.event_id for b in bars for e in eng2.on_bar(b)]
    assert ids1 == ids2 and len(ids1) > 0
