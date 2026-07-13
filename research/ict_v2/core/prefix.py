"""Prefix-invariance and chunk-invariance harness (SPEC.md "Core contracts" ->
core/prefix.py). Every WP-B/C detector engine is tested against this.

  1. Prefix invariance: a FRESH engine run over `bars[:T]` must emit an event
     history identical (event-for-event, in order -- every field, not just
     event_id, so a bug that leaks future data into an event's `attributes`
     without changing its identity is still caught) to the full run's
     `history_through(bars[T-1].close_time)`. This proves the engine's output at
     any point in time depends ONLY on bars it has actually seen so far -- the
     causality contract holds structurally, not merely by convention.

  2. Chunk invariance: feeding the same bars one-at-a-time vs in randomly-sized
     chunks (via an engine's optional `on_bars` batch method, see
     `core/runner.py`) must produce an identical EventStore. This guards against
     a vectorized/batch shortcut silently depending on chunk boundaries (e.g. a
     rolling window that resets at the start of every chunk instead of
     spanning across them).
"""
from __future__ import annotations

import random
from typing import Any, Callable, List, Optional, Sequence

from .events import CausalEvent, EventStore
from .runner import EngineProtocol


def _run_full(engine_factory: Callable[[], EngineProtocol], bars: Sequence[Any]) -> EventStore:
    engine = engine_factory()
    store = EventStore()
    for bar in bars:
        store.extend(engine.on_bar(bar))
    return store


def _events(store: EventStore) -> List[CausalEvent]:
    return list(store.all)


def _default_cuts(bars: Sequence[Any], n_default: int = 200) -> List[int]:
    """Cut points T (1..len(bars)): up to `n_default` evenly-spaced positions
    plus every session-boundary bar (a bar whose `.session` differs from the
    prior bar's, when bars carry that attribute), de-duplicated and sorted."""
    n = len(bars)
    if n == 0:
        return []
    if n <= n_default:
        cuts = set(range(1, n + 1))
    else:
        step = n / n_default
        cuts = {min(n, max(1, round(k * step))) for k in range(1, n_default + 1)}
    prior_session = None
    for idx, bar in enumerate(bars, start=1):
        sess = getattr(bar, "session", None)
        if sess is not None and sess != prior_session:
            cuts.add(idx)
        prior_session = sess
    return sorted(c for c in cuts if 1 <= c <= n)


def assert_prefix_invariant(
    engine_factory: Callable[[], EngineProtocol],
    bars: Sequence[Any],
    cuts: Optional[Sequence[int]] = None,
) -> None:
    """`engine_factory` must return a FRESH, freshly-initialized engine each call
    (no shared state across invocations, or the check is meaningless)."""
    full_store = _run_full(engine_factory, bars)
    cut_points = list(cuts) if cuts is not None else _default_cuts(bars)
    for t in cut_points:
        if not (1 <= t <= len(bars)):
            raise ValueError(f"cut {t} out of range for {len(bars)} bars")
        prefix_store = _run_full(engine_factory, bars[:t])
        cutoff_time = bars[t - 1].close_time
        expected = list(full_store.history_through(cutoff_time))
        actual = _events(prefix_store)
        if actual != expected:
            actual_ids, expected_ids = [e.event_id for e in actual], [e.event_id for e in expected]
            first_bad = next(
                (i for i, (a, b) in enumerate(zip(actual, expected)) if a != b),
                min(len(actual), len(expected)),
            )
            raise AssertionError(
                f"prefix invariance violated at cut T={t} (cutoff={cutoff_time!r}): "
                f"prefix run emitted {len(actual)} event(s) {actual_ids}, full-run "
                f"history_through(cutoff) has {len(expected)} {expected_ids}; first "
                f"divergence at index {first_bad}"
            )


def assert_chunk_invariant(
    engine_factory: Callable[[], EngineProtocol],
    bars: Sequence[Any],
    n_trials: int = 5,
    seed: int = 0,
) -> None:
    """`engine_factory` must return a FRESH engine each call."""
    baseline_store = _run_full(engine_factory, bars)
    baseline_events = _events(baseline_store)

    n = len(bars)
    rng = random.Random(seed)
    for trial in range(n_trials):
        engine = engine_factory()
        store = EventStore()
        i = 0
        while i < n:
            size = rng.randint(1, n - i)
            chunk = bars[i : i + size]
            if hasattr(engine, "on_bars"):
                events: List[CausalEvent] = list(engine.on_bars(chunk))
            else:
                events = [e for bar in chunk for e in engine.on_bar(bar)]
            store.extend(events)
            i += size
        trial_events = _events(store)
        if trial_events != baseline_events:
            raise AssertionError(
                f"chunk invariance violated on trial {trial} (seed={seed}): chunked feed "
                f"emitted {len(trial_events)} event(s) "
                f"{[e.event_id for e in trial_events]} vs {len(baseline_events)} "
                f"{[e.event_id for e in baseline_events]} for the 1-bar-at-a-time baseline"
            )
