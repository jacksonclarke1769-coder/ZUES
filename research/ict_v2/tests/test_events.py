"""core/events.py: CausalEvent + EventStore (event-id determinism, append-only /
no-mutation, causality-order assertion, history_through correctness).
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from research.ict_v2.core.events import CausalEvent, EventStore, compute_event_id

UTC = timezone.utc


def _ts(h, m=0, s=0, day=1):
    return datetime(2024, 1, day, h, m, s, tzinfo=UTC)


def _event(event_type="SWEEP_CONFIRMED", instrument="NQ", origin_h=9, discriminator="", **overrides):
    origin = _ts(origin_h)
    kwargs = dict(
        event_id=compute_event_id(event_type, instrument, origin, "R1", discriminator=discriminator),
        event_type=event_type,
        instrument=instrument,
        timeframe="5m",
        origin_time=origin,
        observed_at=origin,
        confirmed_at=origin,
        actionable_at=origin,
        rule_version="R1",
        param_version="ICT_V2_PARAMS_V0",
    )
    kwargs.update(overrides)
    return CausalEvent(**kwargs)


# --- event_id determinism -----------------------------------------------------

def test_event_id_deterministic_same_inputs():
    origin = _ts(9, 30)
    id1 = compute_event_id("SWEEP_CONFIRMED", "NQ", origin, "R1")
    id2 = compute_event_id("SWEEP_CONFIRMED", "NQ", origin, "R1")
    assert id1 == id2


def test_event_id_differs_by_type_instrument_origin_rule_discriminator():
    origin = _ts(9, 30)
    base = compute_event_id("SWEEP_CONFIRMED", "NQ", origin, "R1")
    assert base != compute_event_id("SWEEP_TIMEOUT", "NQ", origin, "R1")
    assert base != compute_event_id("SWEEP_CONFIRMED", "ES", origin, "R1")
    assert base != compute_event_id("SWEEP_CONFIRMED", "NQ", _ts(9, 35), "R1")
    assert base != compute_event_id("SWEEP_CONFIRMED", "NQ", origin, "R2")
    assert base != compute_event_id("SWEEP_CONFIRMED", "NQ", origin, "R1", discriminator="pdl")


def test_event_id_same_instant_different_tz_representation_is_identical():
    # 09:30 UTC == 04:30 America/New_York (EST, UTC-5) -- identity is the instant,
    # not the display timezone.
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    origin_utc = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
    origin_ny = origin_utc.astimezone(ny)
    assert compute_event_id("X", "NQ", origin_utc, "R1") == compute_event_id("X", "NQ", origin_ny, "R1")


def test_event_id_rejects_naive_origin_time():
    with pytest.raises(ValueError):
        compute_event_id("X", "NQ", datetime(2024, 1, 1, 9, 30), "R1")


def test_causal_event_id_is_a_hash_no_randomness_module_used():
    # sha256 hex digest is 64 chars; regression guard that we didn't switch to uuid.
    origin = _ts(9, 30)
    eid = compute_event_id("X", "NQ", origin, "R1")
    assert isinstance(eid, str) and len(eid) == 64
    int(eid, 16)  # must be valid hex


# --- causality-order assertion ------------------------------------------------

def test_valid_ordering_constructs_fine():
    e = _event(observed_at=_ts(9, 0), confirmed_at=_ts(9, 5), actionable_at=_ts(9, 5), origin_h=9)
    assert e.origin_time <= e.observed_at <= e.confirmed_at <= e.actionable_at


@pytest.mark.parametrize(
    "field_overrides",
    [
        dict(observed_at=_ts(8, 55)),  # observed before origin
        dict(confirmed_at=_ts(8, 50)),  # confirmed before observed (and origin)
        dict(actionable_at=_ts(8, 45)),  # actionable before confirmed
    ],
)
def test_causality_violation_raises_on_construction(field_overrides):
    with pytest.raises(ValueError):
        _event(**field_overrides)


def test_invalidated_at_must_be_after_confirmed_at():
    with pytest.raises(ValueError):
        _event(invalidated_at=_ts(8, 0))
    e = _event(invalidated_at=_ts(9, 30))
    assert e.invalidated_at == _ts(9, 30)


def test_naive_timestamp_rejected():
    origin = _ts(9, 30)
    with pytest.raises(ValueError):
        CausalEvent(
            event_id=compute_event_id("X", "NQ", origin, "R1"),
            event_type="X",
            instrument="NQ",
            timeframe="5m",
            origin_time=origin,
            observed_at=datetime(2024, 1, 1, 9, 30),  # naive!
            confirmed_at=origin,
            actionable_at=origin,
            rule_version="R1",
            param_version="P0",
        )


def test_price_low_must_not_exceed_price_high():
    with pytest.raises(ValueError):
        _event(price_low=100.0, price_high=90.0)


def test_store_append_reasserts_causality_defense_in_depth():
    """CausalEvent's own __post_init__ already blocks construction of an invalid
    event; simulate a hypothetical corrupted event (bypassing frozen via
    object.__setattr__, as no normal code path can do) to prove EventStore.append
    ALSO enforces the global assertion independently at the append boundary."""
    e = _event()
    object.__setattr__(e, "actionable_at", _ts(8, 0))  # corrupt after construction
    store = EventStore()
    with pytest.raises(AssertionError):
        store.append(e)


# --- append-only / no-mutation -------------------------------------------------

def test_causal_event_is_frozen():
    e = _event()
    with pytest.raises(FrozenInstanceError):
        e.event_type = "OTHER"  # type: ignore[misc]


def test_attributes_mapping_is_immutable():
    e = _event(attributes={"depth_ticks": 3})
    with pytest.raises(TypeError):
        e.attributes["depth_ticks"] = 99  # type: ignore[index]
    # mutating the dict passed in afterwards must not affect the stored copy
    original = {"depth_ticks": 3}
    e2 = _event(origin_h=10, attributes=original)
    original["depth_ticks"] = 999
    assert e2.attributes["depth_ticks"] == 3


def test_source_event_ids_frozen_as_tuple():
    e = _event(source_event_ids=["a", "b"])
    assert e.source_event_ids == ("a", "b")
    assert isinstance(e.source_event_ids, tuple)


def test_store_append_returns_same_event_and_rejects_duplicate_id():
    store = EventStore()
    e = _event()
    ret = store.append(e)
    assert ret is e
    with pytest.raises(ValueError):
        store.append(e)  # duplicate event_id -- append-only, no silent overwrite


def test_store_all_is_a_tuple_and_external_mutation_cannot_affect_store():
    store = EventStore()
    e1, e2 = _event(origin_h=9), _event(origin_h=10)
    store.extend([e1, e2])
    snapshot = store.all
    assert snapshot == (e1, e2)
    assert isinstance(snapshot, tuple)
    with pytest.raises(TypeError):
        snapshot[0] = e2  # type: ignore[index]
    assert len(store) == 2  # unaffected


def test_store_by_type_and_by_id():
    store = EventStore()
    e1 = _event(event_type="SWEEP_CONFIRMED", origin_h=9)
    e2 = _event(event_type="ACCEPTED_BREAKOUT", origin_h=10)
    store.extend([e1, e2])
    assert store.by_type("SWEEP_CONFIRMED") == (e1,)
    assert store.by_id(e2.event_id) is e2
    assert store.by_id("nonexistent") is None
    assert e1.event_id in store
    assert "nonexistent" not in store


def test_store_rejects_non_causal_event_type():
    store = EventStore()
    with pytest.raises(TypeError):
        store.append(object())  # type: ignore[arg-type]


# --- history_through correctness -----------------------------------------------

def test_history_through_filters_by_confirmed_at_inclusive():
    store = EventStore()
    e_early = _event(
        origin_h=9, discriminator="early", observed_at=_ts(9, 0), confirmed_at=_ts(9, 5), actionable_at=_ts(9, 5)
    )
    e_boundary = _event(
        origin_h=9, discriminator="boundary",
        observed_at=_ts(9, 55), confirmed_at=_ts(10, 0), actionable_at=_ts(10, 0),
    )
    e_late = _event(
        origin_h=9, discriminator="late",
        observed_at=_ts(10, 55), confirmed_at=_ts(11, 0), actionable_at=_ts(11, 0),
    )
    store.extend([e_early, e_boundary, e_late])

    through = store.history_through(_ts(10, 0))
    assert through == (e_early, e_boundary)  # boundary is inclusive (<=)
    assert e_late not in through


def test_history_through_preserves_append_order():
    store = EventStore()
    # append out of chronological order deliberately
    e_late = _event(origin_h=11, confirmed_at=_ts(11, 0), observed_at=_ts(11, 0), actionable_at=_ts(11, 0))
    e_early = _event(origin_h=9, confirmed_at=_ts(9, 0), observed_at=_ts(9, 0), actionable_at=_ts(9, 0))
    store.extend([e_late, e_early])
    assert store.history_through(_ts(12, 0)) == (e_late, e_early)


def test_history_through_rejects_naive_cutoff():
    store = EventStore()
    with pytest.raises(ValueError):
        store.history_through(datetime(2024, 1, 1, 10, 0))


def test_with_invalidation_references_source_and_does_not_mutate_original():
    original = _event(event_type="FVG_CREATED", origin_h=9)
    inv = original.with_invalidation(
        "FVG_INVALIDATED",
        observed_at=_ts(10, 0),
        confirmed_at=_ts(10, 0),
        actionable_at=_ts(10, 0),
    )
    assert inv.source_event_ids == (original.event_id,)
    assert inv.event_id != original.event_id
    assert original.event_type == "FVG_CREATED"  # unchanged
    store = EventStore()
    store.append(original)
    store.append(inv)
    assert len(store) == 2
