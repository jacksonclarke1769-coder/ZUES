"""engines/swings.py: Method A (symmetric fractal), Method B (directional
change), Method C (trailing extreme). Equivalence vs the frozen oracle
(`primitives.py::last_known_swings`) for Method A, plus prefix/chunk
invariance and the standard synthetic-bar boundary cases for all three.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

from research.ict_v2.core.prefix import assert_chunk_invariant, assert_prefix_invariant
from research.ict_v2.engines.swings import SwingMethodA, SwingMethodB, SwingMethodC
from research.ict_v2.tests.helpers import Bar, make_bars_from_closes, make_5m_bars

UTC = timezone.utc
START = datetime(2024, 1, 2, 9, 30, tzinfo=UTC)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
FRAMEWORK_ROOT = os.path.join(_REPO_ROOT, "..", "..", "backtests", "ict-nq-framework")


def _load_oracle_primitives():
    """Read-only import of the frozen oracle (never edited)."""
    engine_dir = os.path.join(os.path.abspath(FRAMEWORK_ROOT), "engine")
    if engine_dir not in sys.path:
        sys.path.insert(0, engine_dir)
    import primitives as P  # noqa: PLC0415

    return P


# --- Method A: minimum valid / near-miss / boundary equality / duplicates -----

def test_method_a_minimum_valid_pivot_high():
    # a single clean local peak surrounded by strictly smaller bars on both sides
    closes = [100, 101, 102, 110, 103, 102, 101]
    bars = make_bars_from_closes(START, closes)
    eng = SwingMethodA(left=3, right=3)
    events = [e for b in bars for e in eng.on_bar(b)]
    highs = [e for e in events if e.event_type == "SWING_HIGH_A"]
    assert len(highs) == 1
    assert highs[0].price_high == 110.5  # make_bars_from_closes: high = max(o,c)+0.5
    assert highs[0].origin_time == bars[3].close_time
    assert highs[0].confirmed_at == bars[6].close_time  # close of i+right


def test_method_a_near_miss_tie_on_left_window_is_not_a_pivot():
    # left window uses STRICT '>' (mirrors primitives.py) -- a tie on the LEFT
    # side must NOT qualify as a pivot high, even though the right side ties too.
    closes = [100, 101, 105, 105, 101, 100, 99]  # bar index2 ties bar index... constructed below
    bars = make_bars_from_closes(START, closes)
    eng = SwingMethodA(left=3, right=3)
    events = [e for b in bars for e in eng.on_bar(b)]
    highs = [e for e in events if e.event_type == "SWING_HIGH_A"]
    # center (index3) high must exceed the max of bars[0:3] strictly; bar index2
    # and index3 are equal, so it cannot.
    assert highs == []


def test_method_a_boundary_equality_right_window_allows_tie():
    # right window uses '>=' (mirrors primitives.py) -- a tie on the RIGHT side
    # DOES still qualify, provided the left side is strictly exceeded.
    closes = [90, 91, 92, 100, 93, 100, 89]
    bars = make_bars_from_closes(START, closes)
    eng = SwingMethodA(left=3, right=3)
    events = [e for b in bars for e in eng.on_bar(b)]
    highs = [e for e in events if e.event_type == "SWING_HIGH_A"]
    assert len(highs) == 1
    assert highs[0].origin_time == bars[3].close_time


def test_method_a_duplicate_extremes_both_confirmed_as_separate_events():
    # two separated local peaks of the identical price must each fire their own event
    closes = [100, 101, 102, 110, 102, 101, 100, 101, 102, 110, 102, 101, 100]
    bars = make_bars_from_closes(START, closes)
    eng = SwingMethodA(left=3, right=3)
    events = [e for b in bars for e in eng.on_bar(b)]
    highs = [e for e in events if e.event_type == "SWING_HIGH_A"]
    assert len(highs) == 2
    assert highs[0].event_id != highs[1].event_id
    assert highs[0].price_high == highs[1].price_high == 110.5


def test_method_a_matches_frozen_last_known_swings():
    """Equivalence test vs the frozen oracle (required by SPEC.md's test
    requirements for swings-A): random synthetic OHLC, several (left,right)
    combinations, causal reconstruction of sh_at/sl_at from emitted events
    must equal `primitives.py::last_known_swings` bar-for-bar."""
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    P = _load_oracle_primitives()

    rng = np.random.default_rng(42)
    n = 150
    closes = 20000 + np.cumsum(rng.normal(0, 3, n))
    opens = closes - rng.normal(0, 1, n)
    highs = np.maximum(opens, closes) + np.abs(rng.normal(0.5, 1, n))
    lows = np.minimum(opens, closes) - np.abs(rng.normal(0.5, 1, n))
    df = pd.DataFrame({"Open": opens, "High": highs, "Low": lows, "Close": closes})

    bars = [
        Bar(close_time=START + timedelta(minutes=5 * i), open=opens[i], high=highs[i], low=lows[i], close=closes[i])
        for i in range(n)
    ]

    for left, right in [(3, 3), (2, 2), (1, 4)]:
        sh_at, sl_at, _, _ = P.last_known_swings(df, left, right)
        eng = SwingMethodA(left=left, right=right)
        my_sh = [float("nan")] * n
        my_sl = [float("nan")] * n
        cur_sh = cur_sl = float("nan")
        for i, b in enumerate(bars):
            for ev in eng.on_bar(b):
                if ev.event_type == "SWING_HIGH_A":
                    cur_sh = ev.price_high
                elif ev.event_type == "SWING_LOW_A":
                    cur_sl = ev.price_low
            my_sh[i] = cur_sh
            my_sl[i] = cur_sl

        for i in range(n):
            if pd.isna(sh_at[i]):
                assert pd.isna(my_sh[i]), f"left={left} right={right} idx={i}"
            else:
                assert my_sh[i] == pytest.approx(sh_at[i]), f"left={left} right={right} idx={i}"
            if pd.isna(sl_at[i]):
                assert pd.isna(my_sl[i]), f"left={left} right={right} idx={i}"
            else:
                assert my_sl[i] == pytest.approx(sl_at[i]), f"left={left} right={right} idx={i}"


def test_method_a_session_boundary_and_gap_do_not_crash():
    bars = make_5m_bars(START, 5) + make_bars_from_closes(
        START + timedelta(hours=6), [100, 105, 95, 110, 90, 108, 92]
    )
    eng = SwingMethodA()
    for b in bars:
        eng.on_bar(b)  # must not raise across a large timestamp gap


def test_method_a_dst_transition_day_bars_do_not_crash():
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    start = datetime(2024, 3, 10, 0, 0, tzinfo=ny)  # US spring-forward day
    bars = make_bars_from_closes(start, [100 + (i % 5) for i in range(20)])
    eng = SwingMethodA()
    for b in bars:
        eng.on_bar(b)


def test_method_a_prefix_and_chunk_invariance():
    closes = [100, 101, 102, 110, 103, 95, 90, 88, 92, 105, 101, 99, 115, 80, 100, 101]
    bars = make_bars_from_closes(START, closes)
    assert_prefix_invariant(lambda: SwingMethodA(), bars)
    assert_chunk_invariant(lambda: SwingMethodA(), bars, n_trials=8, seed=1)


def test_method_a_event_id_deterministic_and_no_mutation():
    closes = [100, 101, 102, 110, 103, 102, 101]
    bars = make_bars_from_closes(START, closes)
    eng1, eng2 = SwingMethodA(), SwingMethodA()
    ev1 = [e for b in bars for e in eng1.on_bar(b)]
    ev2 = [e for b in bars for e in eng2.on_bar(b)]
    assert [e.event_id for e in ev1] == [e.event_id for e in ev2]
    for e in ev1:
        assert e.actionable_at > e.confirmed_at  # actionable_at = next bar


# --- Method B -------------------------------------------------------------------

def _tight_wick_bars(start, n, step_pairs, wick=0.05, start_price=100.0):
    """Bars with a SMALL, fixed wick on both sides (unlike `make_bars_from_
    closes`'s fixed 0.5, which is large enough to create spurious same-bar
    "reversals" against Method B's tick-based floor threshold on tightly
    oscillating synthetic data -- see WP-B summary). `step_pairs(i)` returns
    the bar-over-bar price delta for bar i."""
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


def test_method_b_minimum_valid_reversal_confirms_pivot():
    # a clean rise (small per-bar wick so no same-bar wick alone can trip the
    # tick-based floor threshold) followed by a sharp reversal well beyond it
    bars = _tight_wick_bars(START, 30, lambda i: 0.5) + _tight_wick_bars(
        START + timedelta(minutes=5 * 30), 1, lambda i: -30.0, start_price=100.0 + 0.5 * 30
    )
    eng = SwingMethodB()
    events = [e for b in bars for e in eng.on_bar(b)]
    highs = [e for e in events if e.event_type == "SWING_HIGH_B"]
    assert len(highs) == 1
    assert highs[0].confirmed_at == bars[-1].close_time  # confirmed at the reversal bar's own close


def test_method_b_near_miss_reversal_below_threshold_does_not_confirm():
    # small, NET-ZERO-DRIFT oscillations (tight wick) -- reversal magnitude from
    # every running extreme stays well under max(8 ticks, 0.25*ATR20) throughout
    bars = _tight_wick_bars(START, 35, lambda i: 0.1 if i % 2 == 0 else -0.1)
    eng = SwingMethodB()
    events = [e for b in bars for e in eng.on_bar(b)]
    assert events == []


def test_method_b_prefix_and_chunk_invariance():
    closes = [100 + i for i in range(20)] + [80 + i for i in range(20)] + [60 - i for i in range(15)]
    bars = make_bars_from_closes(START, closes)
    assert_prefix_invariant(lambda: SwingMethodB(), bars)
    assert_chunk_invariant(lambda: SwingMethodB(), bars, n_trials=6, seed=2)


def test_method_b_gap_bar_does_not_crash():
    closes = [100 + i for i in range(25)] + [50]  # large one-bar gap down
    bars = make_bars_from_closes(START, closes)
    eng = SwingMethodB()
    for b in bars:
        eng.on_bar(b)


# --- Method C -------------------------------------------------------------------

def test_method_c_no_event_before_warmup():
    bars = make_5m_bars(START, 19, step=1.0)
    eng = SwingMethodC()
    events = [e for b in bars for e in eng.on_bar(b)]
    assert events == []  # lookback_bars default = 20; 19 bars is not yet warmed up


def test_method_c_emits_from_the_20th_bar_onward_with_correct_extremes():
    closes = [100 + i for i in range(20)]
    bars = make_bars_from_closes(START, closes)
    eng = SwingMethodC()
    events = [e for b in bars for e in eng.on_bar(b)]
    assert len(events) == 1
    ev = events[0]
    expected_high = max(b.high for b in bars)
    expected_low = min(b.low for b in bars)
    assert ev.price_high == pytest.approx(expected_high)
    assert ev.price_low == pytest.approx(expected_low)
    assert ev.attributes["lookback_bars"] == 20


def test_method_c_window_slides_and_drops_old_extremes():
    # a spike early in the series must roll OFF the trailing window once 20
    # bars have passed, causing the trailing high to fall back down.
    closes = [100] * 5 + [200] + [100] * 25
    bars = make_bars_from_closes(START, closes)
    eng = SwingMethodC()
    events = [e for b in bars for e in eng.on_bar(b)]
    highs = [e.price_high for e in events]
    assert max(highs) >= 200  # the spike is captured while inside the window
    assert highs[-1] < 200  # and rolls off by the end


def test_method_c_prefix_and_chunk_invariance():
    closes = [100] * 5 + [200] + [100] * 25 + [50] + [100] * 5
    bars = make_bars_from_closes(START, closes)
    assert_prefix_invariant(lambda: SwingMethodC(), bars)
    assert_chunk_invariant(lambda: SwingMethodC(), bars, n_trials=6, seed=3)
