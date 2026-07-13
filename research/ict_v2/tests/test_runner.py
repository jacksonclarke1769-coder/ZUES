"""core/runner.py: EngineProtocol + run_engine + BatchRunner."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List

import pytest

from research.ict_v2.core.events import CausalEvent, compute_event_id
from research.ict_v2.core.runner import BatchRunner, EngineProtocol, run_engine
from research.ict_v2.tests.helpers import make_5m_bars

UTC = timezone.utc
START = datetime(2024, 1, 2, 9, 30, tzinfo=UTC)


class EveryBarEngine:
    """Emits exactly one event per bar it is fed -- useful for asserting call
    counts / ordering without any real detection logic."""

    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.calls: List[Any] = []

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        self.calls.append(bar)
        eid = compute_event_id("TICK", "NQ", bar.close_time, self.tag)
        return [
            CausalEvent(
                event_id=eid,
                event_type="TICK",
                instrument="NQ",
                timeframe="5m",
                origin_time=bar.close_time,
                observed_at=bar.close_time,
                confirmed_at=bar.close_time,
                actionable_at=bar.close_time,
                rule_version=self.tag,
                param_version="TOY_P0",
            )
        ]


class SilentEngine:
    def on_bar(self, bar: Any) -> List[CausalEvent]:
        return []


def test_engine_protocol_runtime_checkable():
    assert isinstance(EveryBarEngine("R1"), EngineProtocol)
    assert not isinstance(object(), EngineProtocol)


def test_run_engine_feeds_bars_in_order_and_collects_events():
    bars = make_5m_bars(START, 5)
    engine = EveryBarEngine("R1")
    store = run_engine(engine, bars)
    assert len(store) == 5
    assert engine.calls == bars  # fed in order, one call per bar
    assert [e.origin_time for e in store.all] == [b.close_time for b in bars]


def test_run_engine_with_no_events_returns_empty_store():
    store = run_engine(SilentEngine(), make_5m_bars(START, 3))
    assert len(store) == 0


def test_batch_runner_feeds_every_engine_the_same_bars_in_order():
    bars = make_5m_bars(START, 6)
    runner = BatchRunner()
    e1, e2 = EveryBarEngine("R1"), EveryBarEngine("R2")
    runner.register("engine_one", e1)
    runner.register("engine_two", e2)
    stores = runner.run(bars)

    assert set(stores) == {"engine_one", "engine_two"}
    assert len(stores["engine_one"]) == 6
    assert len(stores["engine_two"]) == 6
    assert e1.calls == bars
    assert e2.calls == bars


def test_batch_runner_engines_have_independent_stores():
    bars = make_5m_bars(START, 4)
    runner = BatchRunner()
    runner.register("ticks", EveryBarEngine("R1"))
    runner.register("silent", SilentEngine())
    stores = runner.run(bars)
    assert len(stores["ticks"]) == 4
    assert len(stores["silent"]) == 0
    assert runner.store("ticks") is stores["ticks"]


def test_batch_runner_rejects_duplicate_registration():
    runner = BatchRunner()
    runner.register("a", EveryBarEngine("R1"))
    with pytest.raises(ValueError):
        runner.register("a", EveryBarEngine("R2"))


def test_batch_runner_store_unknown_name_raises_keyerror():
    runner = BatchRunner()
    with pytest.raises(KeyError):
        runner.store("nope")
