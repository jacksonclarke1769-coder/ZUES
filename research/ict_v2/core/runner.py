"""Batch runner: feeds bars sequentially, in order, to one or more registered
engines (SPEC.md "Core contracts" -> core/runner.py).

Engine protocol (minimal; WP-B/C detectors build against this):

  - `on_bar(bar) -> Iterable[CausalEvent]`  (REQUIRED)
    Consume exactly ONE completed bar and return zero or more newly-emitted
    events -- candidates AND terminal outcomes alike (SPEC.md hard rule 4: no
    silent filters; a rejection is itself a recorded event). Called once per
    bar, strictly in bar order. This is the only method the plain batch runner
    (`run_engine` / `BatchRunner`) calls -- "a batch runner just feeds bars in
    order" (SPEC.md rule 2); it does no buffering, look-ahead, or reordering.

  - `on_bars(bars) -> Iterable[CausalEvent]`  (OPTIONAL)
    A batch/vectorized shortcut for a contiguous chunk of bars. If an engine
    implements this (e.g. for a numpy-vectorized rolling computation), it MUST
    produce output identical to calling `on_bar` once per bar in order --
    `core/prefix.py::assert_chunk_invariant` is the harness that proves this.
    Engines that don't need vectorization simply omit it.

A "bar" is any object the engine understands; the only field the runner/harness
themselves rely on is a tz-aware `close_time` (used by `core/prefix.py` as the
causal cut boundary). Individual engines document whatever OHLCV/session fields
they additionally require.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Protocol, Sequence, runtime_checkable

from .events import CausalEvent, EventStore


@runtime_checkable
class EngineProtocol(Protocol):
    def on_bar(self, bar: Any) -> Iterable[CausalEvent]: ...


def run_engine(engine: EngineProtocol, bars: Sequence[Any]) -> EventStore:
    """Feed `bars` to a single engine, in order, into a fresh EventStore."""
    store = EventStore()
    for bar in bars:
        store.extend(engine.on_bar(bar))
    return store


class BatchRunner:
    """Feeds bars sequentially, in order, to every registered engine. Each engine
    gets its own EventStore -- engines never share state or read each other's
    events in Phase 2 (cross-engine confluence is a later phase; SPEC.md's
    "salience COMPONENTS (no weights)" language is deliberate)."""

    def __init__(self) -> None:
        self._engines: Dict[str, EngineProtocol] = {}
        self._stores: Dict[str, EventStore] = {}

    def register(self, name: str, engine: EngineProtocol) -> None:
        if name in self._engines:
            raise ValueError(f"engine already registered: {name!r}")
        self._engines[name] = engine
        self._stores[name] = EventStore()

    def engines(self) -> Dict[str, EngineProtocol]:
        return dict(self._engines)

    def run(self, bars: Sequence[Any]) -> Dict[str, EventStore]:
        for bar in bars:
            for name, engine in self._engines.items():
                events: List[CausalEvent] = list(engine.on_bar(bar))
                if events:
                    self._stores[name].extend(events)
        return dict(self._stores)

    def store(self, name: str) -> EventStore:
        return self._stores[name]
