"""Ranges/OTE (SPEC.md "Engine definitions (v0 pins)" -> "Ranges/OTE"):
`DealingRange` objects from WHITELISTED anchors only -- completed prior
session, completed prior day, latest completed Method-B leg -- plus the
`location(P) = (P-L)/(H-L)` helper and band-touch tracking for the OTE band
`[0.62, 0.79]` and its two control bands `[0.38, 0.55]` / `[0.80, 0.97]`.

Anchors, each producing its own `DEALING_RANGE_CREATED` event (`anchor_kind`
in attributes):

  * `prior_session` -- completed PRIMARY_ORDER session H/L (`core/clock.py`'s
    `asia`/`london`/`ny_am`/`ny_lunch`/`ny_pm`, ALL FIVE -- a deliberate,
    documented WIDER choice than `levels.py`'s own session-level kind, which
    SPEC.md's "Levels" section narrows to exactly `asia`/`london`/`ny_am`;
    "Ranges/OTE" carries no such narrowing language, and a dealing range is
    meaningful for any completed session, non-blocking judgment call).
    Recomputed INTERNALLY via a private `BucketHL` per session name, same
    "don't cross-read another engine's events" convention `levels.py` itself
    uses for its own OR/overnight bucketing.
  * `prior_day` -- completed CME trade_date H/L, likewise recomputed
    internally via a private `BucketHL`.
  * `method_b_leg` -- the leg between the two most recently confirmed
    Method-B swings (`engines/swings.py::SwingMethodB`, run as a private
    internal instance -- SwingMethodB's own FSM guarantees strict high/low
    alternation, so every newly confirmed swing always completes exactly one
    new leg with the prior one). `direction` = "bullish" (low -> high leg) or
    "bearish" (high -> low leg), recorded as raw context (no interpretation).

Every `DealingRange` is FROZEN the instant it's created (an immutable
`_RangeState`, never mutated in place); "re-anchoring" always means a brand
new `DEALING_RANGE_CREATED` event with its own id, never an edit to a prior
one. Ranges do not expire (SPEC.md's "Ranges/OTE" section states no expiry
rule, unlike "Zones"'s explicit terminal-event requirement) -- they remain
active for band-touch tracking for the life of the engine.

`location(price, low, high)` is exposed as a pure, stateless helper (mirrors
`fvg_from_triple()`'s standalone-function pattern in `zones.py`) -- SPEC.md
states this ONE non-directional formula (`(P-L)/(H-L)`, 0=low/1=high) for
every range regardless of anchor kind; the three fixed fractional bands (OTE
`[0.62, 0.79]` + controls `[0.38, 0.55]` / `[0.80, 0.97]`) are converted to
absolute price sub-ranges at creation time and recorded on `DEALING_RANGE_
CREATED`. NOTE: this deliberately does NOT reproduce the oracle's
`primitives.py::ote_zone()` DIRECTIONAL retracement convention (measured
backward from the impulse end) -- SPEC.md's "Ranges/OTE" section (unlike
"Sweep FSM"/"Zones") states only the plain, non-directional `location()`
formula and does not ask for oracle parity here, so none is attempted;
flagged for Fable's review as a scope boundary, non-blocking. Every bar
whose `[low, high]` overlaps a band's absolute price sub-range emits a
`BAND_TOUCH` (all three bands treated identically -- SPEC.md: "controls are
first-class, no interpretation").
"""
from __future__ import annotations

from typing import Any, List, Optional

from ..core.clock import SessionEngine
from ..core.config import ICT_V2_PARAMS_V0, ParamSet
from ..core.events import CausalEvent, compute_event_id
from ._util import BucketHL, next_actionable
from .swings import SwingMethodB

RULE_VERSION = "RANGES_V0"

_SESSION_NAMES = ("asia", "london", "ny_am", "ny_lunch", "ny_pm")


def location(price: float, low: float, high: float) -> Optional[float]:
    """`(price - low) / (high - low)`; `None` for a degenerate (zero-width or
    inverted) range -- never fabricated."""
    if high <= low:
        return None
    return (price - low) / (high - low)


class _RangeState:
    __slots__ = ("range_id", "low", "high", "anchor_kind", "direction", "bands", "touch_counts")

    def __init__(self, range_id: str, low: float, high: float, anchor_kind: str, direction: Optional[str], bands: dict):
        self.range_id = range_id
        self.low = low
        self.high = high
        self.anchor_kind = anchor_kind
        self.direction = direction
        self.bands = bands  # name -> (price_lo, price_hi)
        self.touch_counts = {name: 0 for name in bands}


class RangesEngine:
    def __init__(
        self,
        instrument: str = "NQ",
        timeframe: str = "5m",
        params: ParamSet = ICT_V2_PARAMS_V0,
    ) -> None:
        self.instrument = instrument
        self.timeframe = timeframe
        self.params = params
        self._sessions = SessionEngine()
        self._day_hl = BucketHL()
        self._session_hl = {name: BucketHL() for name in _SESSION_NAMES}
        self._swings_b = SwingMethodB(instrument, timeframe, params)
        self._last_swing_b: Optional[CausalEvent] = None
        self._active: List[_RangeState] = []

    # -- event construction ---------------------------------------------------

    def _event(self, event_type, origin_time, confirmed_at, price_low, price_high, discriminator, attributes, source_event_ids=()) -> CausalEvent:
        eid = compute_event_id(event_type, self.instrument, origin_time, RULE_VERSION, discriminator=discriminator)
        return CausalEvent(
            event_id=eid,
            event_type=event_type,
            instrument=self.instrument,
            timeframe=self.timeframe,
            origin_time=origin_time,
            observed_at=confirmed_at,
            confirmed_at=confirmed_at,
            actionable_at=next_actionable(confirmed_at, self.timeframe),
            rule_version=RULE_VERSION,
            param_version=self.params.param_version,
            price_low=price_low,
            price_high=price_high,
            source_event_ids=source_event_ids,
            attributes=attributes,
        )

    def _bands_for(self, low: float, high: float) -> dict:
        specs = {
            "ote": self.params.ote_band,
            "control_low": self.params.ote_control_band_low,
            "control_high": self.params.ote_control_band_high,
        }
        bands = {}
        for name, (f_lo, f_hi) in specs.items():
            bands[name] = (low + f_lo * (high - low), low + f_hi * (high - low))
        return bands

    def _create_range(self, anchor_kind: str, low: float, high: float, origin_time, confirmed_at, direction: Optional[str], discriminator: str) -> CausalEvent:
        bands = self._bands_for(low, high)
        attrs = {"anchor_kind": anchor_kind, "low": low, "high": high, "direction": direction}
        for name, (lo, hi) in bands.items():
            attrs[f"{name}_low"] = lo
            attrs[f"{name}_high"] = hi
        ev = self._event("DEALING_RANGE_CREATED", origin_time, confirmed_at, low, high, discriminator, attrs)
        self._active.append(_RangeState(ev.event_id, low, high, anchor_kind, direction, bands))
        return ev

    # -- anchors: prior session / prior day -----------------------------------

    def _bucket_ranges(self, bar: Any) -> List[CausalEvent]:
        events: List[CausalEvent] = []
        trade_date = self._sessions.trade_date(bar.close_time)

        finalized = self._day_hl.update(trade_date, bar)
        if finalized:
            disc = f"prior_day|{finalized['key']}"
            events.append(
                self._create_range(
                    "prior_day", finalized["low"], finalized["high"], finalized["first_close_time"],
                    bar.close_time, None, disc,
                )
            )

        label = self._sessions.session(bar.close_time)
        if label in self._session_hl:
            finalized = self._session_hl[label].update(trade_date, bar)
            if finalized:
                disc = f"prior_session|{label}|{finalized['key']}"
                ev = self._create_range(
                    "prior_session", finalized["low"], finalized["high"], finalized["first_close_time"],
                    bar.close_time, None, disc,
                )
                events.append(ev)
        return events

    # -- anchor: latest completed Method-B leg --------------------------------

    def _leg_ranges(self, bar: Any) -> List[CausalEvent]:
        events: List[CausalEvent] = []
        for ev in self._swings_b.on_bar(bar):
            prior = self._last_swing_b
            self._last_swing_b = ev
            if prior is None:
                continue
            prior_price = prior.price_high if prior.event_type == "SWING_HIGH_B" else prior.price_low
            new_price = ev.price_high if ev.event_type == "SWING_HIGH_B" else ev.price_low
            low, high = min(prior_price, new_price), max(prior_price, new_price)
            direction = "bullish" if ev.event_type == "SWING_HIGH_B" else "bearish"
            disc = f"method_b_leg|{prior.event_id}|{ev.event_id}"
            events.append(
                self._create_range("method_b_leg", low, high, prior.origin_time, ev.confirmed_at, direction, disc)
            )
        return events

    # -- band-touch tracking ----------------------------------------------------

    def _band_touches(self, bar: Any) -> List[CausalEvent]:
        events: List[CausalEvent] = []
        for rng in self._active:
            for name, (lo, hi) in rng.bands.items():
                if bar.low <= hi and bar.high >= lo:
                    rng.touch_counts[name] += 1
                    disc = f"{rng.range_id}|{name}|{rng.touch_counts[name]}"
                    events.append(
                        self._event(
                            "BAND_TOUCH", bar.close_time, bar.close_time, lo, hi, disc,
                            attributes={
                                "range_id": rng.range_id, "anchor_kind": rng.anchor_kind, "band": name,
                                "band_low": lo, "band_high": hi, "touch_count": rng.touch_counts[name],
                            },
                            source_event_ids=(rng.range_id,),
                        )
                    )
        return events

    # -- main loop ------------------------------------------------------------

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        events: List[CausalEvent] = []
        events.extend(self._bucket_ranges(bar))
        events.extend(self._leg_ranges(bar))
        events.extend(self._band_touches(bar))
        return events
