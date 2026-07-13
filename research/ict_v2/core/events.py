"""CausalEvent + EventStore (SPEC.md "Core contracts" -> CausalEvent).

CausalEvent is a frozen (immutable) record. Lifecycle changes NEVER mutate an
existing event -- they append a NEW event (e.g. `*_INVALIDATED`, `*_TESTED`)
that references the original via `source_event_ids`. EventStore is append-only:
once an event is added it can never be removed or edited, and every append is
checked against the global causality contract:

    origin_time <= observed_at <= confirmed_at <= actionable_at  (<= invalidated_at, if set)

`event_id` is a deterministic hash of the event's identity (type + instrument +
origin instant + rule_version [+ an optional caller-supplied discriminator for
detectors that can emit multiple distinct candidates at the same origin, e.g.
one sweep event per liquidity level tested on the same bar) -- NEVER uuid4(),
random(), or a wall-clock read (datetime.now()/Date.now()). Same inputs always
produce the same id, which is what makes prefix/chunk invariance checkable by
comparing id sequences (core/prefix.py).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


def _require_tz_aware(name: str, ts: Any) -> None:
    if ts is None:
        return
    if getattr(ts, "tzinfo", None) is None:
        raise ValueError(
            f"{name} must be a tz-aware timestamp (got naive {ts!r}); never tz_localize a "
            "naive wall-clock string -- construct with an explicit tzinfo/UTC anchor instead"
        )


def compute_event_id(
    event_type: str,
    instrument: str,
    origin_time: datetime,
    rule_version: str,
    *,
    discriminator: str = "",
) -> str:
    """Deterministic event_id: sha256 of (event_type, instrument, origin instant in UTC,
    rule_version, discriminator). NO uuid/random/wall-clock reads. `discriminator` lets a
    detector disambiguate multiple candidates sharing the same origin bar (e.g. two
    liquidity levels swept on the same bar) -- callers choose a stable, content-derived
    string (e.g. the level name), never a counter that depends on call order across runs.
    """
    _require_tz_aware("origin_time", origin_time)
    origin_utc = origin_time.astimezone(timezone.utc).isoformat()
    key = "\x1f".join([event_type, instrument, origin_utc, rule_version, discriminator])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CausalEvent:
    """One immutable causal event. Field order differs slightly from the prose order in
    SPEC.md (fields without defaults must precede fields with defaults in a dataclass);
    semantics are unchanged."""

    event_id: str
    event_type: str
    instrument: str
    timeframe: str
    origin_time: datetime
    observed_at: datetime
    confirmed_at: datetime
    actionable_at: datetime
    rule_version: str
    param_version: str
    invalidated_at: Optional[datetime] = None
    price_low: Optional[float] = None
    price_high: Optional[float] = None
    source_event_ids: Tuple[str, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("origin_time", "observed_at", "confirmed_at", "actionable_at", "invalidated_at"):
            _require_tz_aware(name, getattr(self, name))
        if not (self.origin_time <= self.observed_at <= self.confirmed_at <= self.actionable_at):
            raise ValueError(
                "causality contract violated: origin_time <= observed_at <= confirmed_at <= "
                f"actionable_at required; got origin={self.origin_time!r} "
                f"observed={self.observed_at!r} confirmed={self.confirmed_at!r} "
                f"actionable={self.actionable_at!r}"
            )
        if self.invalidated_at is not None and self.invalidated_at < self.confirmed_at:
            raise ValueError(
                f"invalidated_at ({self.invalidated_at!r}) must be >= confirmed_at "
                f"({self.confirmed_at!r})"
            )
        if self.price_low is not None and self.price_high is not None and self.price_low > self.price_high:
            raise ValueError(f"price_low ({self.price_low}) must be <= price_high ({self.price_high})")
        # freeze the mutable defaults so a caller can't mutate an emitted event in place
        object.__setattr__(self, "source_event_ids", tuple(self.source_event_ids))
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))

    def __hash__(self) -> int:
        # event_id already encodes identity deterministically; hashing on it keeps
        # CausalEvent usable in sets/dict keys without requiring `attributes` (a Mapping)
        # to be hashable.
        return hash(self.event_id)

    def with_invalidation(
        self,
        event_type: str,
        *,
        observed_at: datetime,
        confirmed_at: datetime,
        actionable_at: datetime,
        rule_version: Optional[str] = None,
        param_version: Optional[str] = None,
        attributes: Optional[Mapping[str, Any]] = None,
        discriminator: str = "",
    ) -> "CausalEvent":
        """Convenience for the common lifecycle pattern: build a NEW event of type
        `event_type` (e.g. "FVG_INVALIDATED") that references `self` via
        `source_event_ids`. Does not mutate `self` or append anything -- the caller
        still owns appending the result to an EventStore."""
        rv = rule_version or self.rule_version
        pv = param_version or self.param_version
        new_id = compute_event_id(
            event_type, self.instrument, self.origin_time, rv, discriminator=discriminator or self.event_id
        )
        return CausalEvent(
            event_id=new_id,
            event_type=event_type,
            instrument=self.instrument,
            timeframe=self.timeframe,
            origin_time=self.origin_time,
            observed_at=observed_at,
            confirmed_at=confirmed_at,
            actionable_at=actionable_at,
            rule_version=rv,
            param_version=pv,
            price_low=self.price_low,
            price_high=self.price_high,
            source_event_ids=(self.event_id,),
            attributes=attributes or {},
        )


class EventStore:
    """Append-only event log + indices by type/id. Never mutates or removes an
    event once appended. `history_through(t)` is the prefix-invariance primitive:
    it returns exactly the events an engine could have known about as of wall-clock
    (or bar-close) time `t`, using `confirmed_at` as the causal cutoff."""

    def __init__(self) -> None:
        self._events: List[CausalEvent] = []
        self._by_type: Dict[str, List[CausalEvent]] = {}
        self._by_id: Dict[str, CausalEvent] = {}

    def append(self, event: CausalEvent) -> CausalEvent:
        if not isinstance(event, CausalEvent):
            raise TypeError(f"EventStore only accepts CausalEvent, got {type(event)!r}")
        # Defense-in-depth: CausalEvent.__post_init__ already enforces this at
        # construction time (and frozen=True means it can never be un-enforced
        # afterwards), but the store re-asserts it explicitly at the append boundary
        # per SPEC.md ("global assertion ... on append").
        if not (event.origin_time <= event.observed_at <= event.confirmed_at <= event.actionable_at):
            raise AssertionError(
                f"EventStore.append: causality contract violated for event_id={event.event_id}"
            )
        if event.event_id in self._by_id:
            raise ValueError(
                f"EventStore.append: duplicate event_id {event.event_id!r} "
                "(append-only store; construct a new lifecycle event instead of re-appending)"
            )
        self._events.append(event)
        self._by_type.setdefault(event.event_type, []).append(event)
        self._by_id[event.event_id] = event
        return event

    def extend(self, events: Iterable[CausalEvent]) -> None:
        for e in events:
            self.append(e)

    @property
    def all(self) -> Tuple[CausalEvent, ...]:
        return tuple(self._events)

    def by_type(self, event_type: str) -> Tuple[CausalEvent, ...]:
        return tuple(self._by_type.get(event_type, ()))

    def by_id(self, event_id: str) -> Optional[CausalEvent]:
        return self._by_id.get(event_id)

    def history_through(self, t: datetime) -> Tuple[CausalEvent, ...]:
        """Events with confirmed_at <= t, in append (insertion) order."""
        _require_tz_aware("t", t)
        return tuple(e for e in self._events if e.confirmed_at <= t)

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self):
        return iter(self._events)

    def __contains__(self, event_id: str) -> bool:
        return event_id in self._by_id
