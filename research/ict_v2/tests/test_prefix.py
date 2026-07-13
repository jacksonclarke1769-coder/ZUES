"""core/prefix.py: prefix-invariance + chunk-invariance harness, self-tested
against toy engines (a well-behaved one that must PASS, and deliberately
broken ones that must FAIL -- proving the harness actually catches violations).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List

import pytest

from research.ict_v2.core.events import CausalEvent, compute_event_id
from research.ict_v2.core.prefix import _default_cuts, assert_chunk_invariant, assert_prefix_invariant
from research.ict_v2.tests.helpers import Bar, make_bars_from_closes, make_5m_bars

UTC = timezone.utc
START = datetime(2024, 1, 2, 9, 30, tzinfo=UTC)

# Non-monotonic zigzag: only SOME bars are genuine new-highs relative to the
# true running max. A monotonically-rising series (e.g. plain make_5m_bars)
# would make a running-max reset bug invisible -- every bar would be a "new
# high" regardless of whether state was reset, since there's never a dip.
ZIGZAG_CLOSES = [100, 105, 102, 108, 101, 110, 95, 112, 90, 115, 85, 118, 80, 120, 75, 122, 70, 125, 65, 128]


def _new_high_event(bar: Any, rule_version: str) -> CausalEvent:
    eid = compute_event_id("NEW_HIGH", "NQ", bar.close_time, rule_version)
    return CausalEvent(
        event_id=eid,
        event_type="NEW_HIGH",
        instrument="NQ",
        timeframe="5m",
        origin_time=bar.close_time,
        observed_at=bar.close_time,
        confirmed_at=bar.close_time,
        actionable_at=bar.close_time,
        rule_version=rule_version,
        param_version="TOY_P0",
        price_high=bar.close,
    )


class NewHighEngine:
    """Well-behaved toy engine: emits a NEW_HIGH event whenever a bar's close is
    a new running-maximum close, confirmed on that same bar's close_time.
    Causal by construction: `self._running_max` is genuine per-instance state
    built ONLY from bars actually passed to `on_bar` so far."""

    def __init__(self) -> None:
        self._running_max = None

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        if self._running_max is not None and bar.close <= self._running_max:
            return []
        self._running_max = bar.close
        return [_new_high_event(bar, "TOY1")]


class SharedStateBrokenEngine:
    """Deliberately broken: tracks its running max on a MUTABLE CLASS attribute
    instead of instance state, so successive `engine_factory()` calls are NOT
    actually independent ("fresh") -- state leaks across runs. This is exactly
    the mistake SPEC.md's prefix-invariance definition ("run a FRESH engine
    over bars[:T]") guards against: `assert_prefix_invariant` runs the full
    series first, which pollutes the shared class attribute with the true
    all-time-high close; every subsequent "fresh" prefix engine then silently
    inherits that pollution and under-reports early bars."""

    _shared_running_max: Any = None

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        cls = type(self)
        if cls._shared_running_max is not None and bar.close <= cls._shared_running_max:
            return []
        cls._shared_running_max = bar.close
        return [_new_high_event(bar, "TOY_SHARED_BAD")]


class ChunkSensitiveEngine:
    """Deliberately broken: `on_bars` resets its running-max at the start of
    EVERY chunk instead of carrying state across chunk boundaries, so a
    randomly-chunked feed diverges from the 1-bar-at-a-time baseline (which
    only ever calls `on_bar`, never `on_bars`)."""

    def __init__(self) -> None:
        self._running_max = None

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        if self._running_max is not None and bar.close <= self._running_max:
            return []
        self._running_max = bar.close
        return [_new_high_event(bar, "TOY_CHUNK_BAD")]

    def on_bars(self, bars) -> List[CausalEvent]:
        self._running_max = None  # BUG: forgets state accumulated in prior chunks
        out: List[CausalEvent] = []
        for bar in bars:
            out.extend(self.on_bar(bar))
        return out


@pytest.fixture
def bars():
    return make_5m_bars(START, 40, start_price=20000.0, step=1.0)


@pytest.fixture
def zigzag_bars():
    return make_bars_from_closes(START, ZIGZAG_CLOSES)


def test_well_behaved_engine_passes_prefix_invariance(bars):
    assert_prefix_invariant(NewHighEngine, bars)


def test_well_behaved_engine_passes_prefix_invariance_with_explicit_cuts(bars):
    assert_prefix_invariant(NewHighEngine, bars, cuts=[1, 5, 10, 20, 39, 40])


def test_well_behaved_engine_passes_chunk_invariance(bars):
    assert_chunk_invariant(NewHighEngine, bars, n_trials=8, seed=42)


def test_well_behaved_engine_passes_chunk_invariance_on_zigzag(zigzag_bars):
    assert_chunk_invariant(NewHighEngine, zigzag_bars, n_trials=8, seed=42)


def test_broken_shared_state_engine_fails_prefix_invariance(bars):
    SharedStateBrokenEngine._shared_running_max = None  # isolate from other tests
    with pytest.raises(AssertionError, match="prefix invariance violated"):
        # the internal full-series run (over all 40 bars) pollutes the shared
        # class attribute with the true all-time-high BEFORE the cut=1 "fresh"
        # engine ever gets a bar, so it silently drops the very first NEW_HIGH.
        assert_prefix_invariant(SharedStateBrokenEngine, bars, cuts=[1])
    SharedStateBrokenEngine._shared_running_max = None  # leave clean for other tests


def test_broken_chunk_sensitive_engine_fails_chunk_invariance(zigzag_bars):
    # a strictly-monotonic price series would make this bug invisible (every
    # bar is a "new high" whether or not state resets) -- zigzag closes are
    # required to actually exercise the reset-on-chunk-boundary bug.
    with pytest.raises(AssertionError, match="chunk invariance violated"):
        assert_chunk_invariant(ChunkSensitiveEngine, zigzag_bars, n_trials=8, seed=1)


def test_default_cuts_include_session_boundaries():
    b = [
        Bar(close_time=START, open=1, high=1, low=1, close=1, session="asia"),
        Bar(close_time=START + timedelta(minutes=5), open=1, high=1, low=1, close=1, session="asia"),
        Bar(close_time=START + timedelta(minutes=10), open=1, high=1, low=1, close=1, session="london"),
        Bar(close_time=START + timedelta(minutes=15), open=1, high=1, low=1, close=1, session="london"),
    ]
    cuts = _default_cuts(b, n_default=1)
    assert 3 in cuts  # the bar where session flips asia -> london


def test_default_cuts_covers_every_bar_when_fewer_than_n_default(bars):
    cuts = _default_cuts(bars[:5], n_default=200)
    assert cuts == [1, 2, 3, 4, 5]


def test_empty_bars_yields_no_cuts_and_no_error():
    assert_prefix_invariant(NewHighEngine, [])
    assert_chunk_invariant(NewHighEngine, [])


def test_out_of_range_cut_raises_value_error(bars):
    with pytest.raises(ValueError):
        assert_prefix_invariant(NewHighEngine, bars, cuts=[len(bars) + 1])
