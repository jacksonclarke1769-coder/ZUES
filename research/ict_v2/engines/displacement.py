"""Displacement (SPEC.md "Engine definitions (v0 pins)" -> "Displacement"):
per-completed-bar normalized displacement components, plus the
`DISPLACEMENT_QUALIFIED` candidate event.

Per bar, up to TWO independent events may be emitted:

  1. `DISPLACEMENT_QUALIFIED` iff `body >= displacement_body_mult * mean-20
     body` (SAME formula as the frozen oracle `primitives.py::body_ratio` /
     `displacement_strength` -- prior-20-bar mean, shifted by one bar so the
     current bar never normalizes against itself; `engines/_util.py
     ::RollingMean`). Independent of everything else below -- this is the
     "V1 convention" DISPLACEMENT_QUALIFIED threshold SPEC.md pins for parity
     with model01, computed with an internal `RollingMean(20)` (structure.py
     computes the identical formula independently too, per BatchRunner's "no
     cross-engine state sharing" rule -- both engines mirror the same math,
     neither reads the other's events).

  2. Either `DISPLACEMENT_COMPONENTS` or `DISPLACEMENT_WARMUP` (mutually
     exclusive, always exactly one per bar), carrying the four score
     components:
       - `body_vs_tod = |C-O| / sigma_TOD`, where `sigma_TOD` = the median
         |C-O| ("5m return", in points -- same units as the numerator) for
         THIS bar's time-of-day slot over the trailing
         `displacement_sigma_tod_lookback_sessions` (v0=20) PRIOR occurrences
         of that slot (one occurrence per trading day in the ordinary case;
         `engines/_util.py::RollingMedian`, keyed by ET wall-clock
         hour:minute). While fewer than 20 prior occurrences of this bar's
         slot have been seen, `sigma_TOD` -- and therefore `body_vs_tod` --
         is UNDEFINED; the event type is `DISPLACEMENT_WARMUP` and
         `body_vs_tod` stays `None` (never fabricated, per SPEC.md).
       - `range_vs_atr = (H-L) / ATR20`, ATR20 INCLUSIVE of the current bar
         (mirrors the oracle's non-shifted `atr_arr` convention -- see
         `engines/_util.py::ATR` and `engines/swings.py`'s Method B
         docstring for the same convention/rationale). `None` during ATR
         warmup (first 19 bars), independent of the sigma_TOD warmup above.
       - `close_location = (C-L) / (H-L)`, `None` on a zero-range bar
         (H == L).
       - `volume_z = (volume - mean20_volume) / std20_volume`, prior-20
         shifted (`RollingMeanStd`), `None` during warmup or a zero-variance
         window.
     `ofi` / `depth_imbalance` / `spread` are always present as attribute
     keys, always `None`, with `data_gated=True` (Court docket D1 -- no live
     order-flow/depth feed in Phase 2, `gated/orderflow.py`).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.clock import NY
from ..core.config import ICT_V2_PARAMS_V0, ParamSet
from ..core.events import CausalEvent, compute_event_id
from ._util import ATR, RollingMean, RollingMeanStd, RollingMedian, body, next_actionable

RULE_VERSION = "DISPLACEMENT_V0"


class DisplacementEngine:
    def __init__(
        self,
        instrument: str = "NQ",
        timeframe: str = "5m",
        params: ParamSet = ICT_V2_PARAMS_V0,
    ) -> None:
        self.instrument = instrument
        self.timeframe = timeframe
        self.params = params
        self._body_mean = RollingMean(20)
        self._atr = ATR(20)
        self._volume_stats = RollingMeanStd(params.displacement_volume_z_lookback_bars)
        self._sigma_tod: Dict[Any, RollingMedian] = {}

    def _slot(self, bar: Any) -> Any:
        ny = bar.close_time.astimezone(NY)
        return (ny.hour, ny.minute)

    def _event(
        self,
        event_type: str,
        bar: Any,
        attributes: dict,
        discriminator: str,
    ) -> CausalEvent:
        eid = compute_event_id(event_type, self.instrument, bar.close_time, RULE_VERSION, discriminator=discriminator)
        return CausalEvent(
            event_id=eid,
            event_type=event_type,
            instrument=self.instrument,
            timeframe=self.timeframe,
            origin_time=bar.close_time,
            observed_at=bar.close_time,
            confirmed_at=bar.close_time,
            actionable_at=next_actionable(bar.close_time, self.timeframe),
            rule_version=RULE_VERSION,
            param_version=self.params.param_version,
            attributes=attributes,
        )

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        events: List[CausalEvent] = []
        bar_body = body(bar.open, bar.close)

        # 1) DISPLACEMENT_QUALIFIED -- independent of the components/warmup below.
        prior_mean_body = self._body_mean.update(bar_body)
        if prior_mean_body is not None and prior_mean_body > 0:
            ratio = bar_body / prior_mean_body
            direction = "bullish" if bar.close > bar.open else "bearish" if bar.close < bar.open else None
            if ratio >= self.params.displacement_body_mult and direction is not None:
                events.append(
                    self._event(
                        "DISPLACEMENT_QUALIFIED",
                        bar,
                        {
                            "body": bar_body,
                            "mean20_body": prior_mean_body,
                            "ratio": ratio,
                            "direction": direction,
                            "threshold_mult": self.params.displacement_body_mult,
                        },
                        discriminator="qualified",
                    )
                )

        # 2) DISPLACEMENT_COMPONENTS / DISPLACEMENT_WARMUP -- exactly one per bar.
        slot = self._slot(bar)
        roller = self._sigma_tod.setdefault(slot, RollingMedian(self.params.displacement_sigma_tod_lookback_sessions))
        sigma_tod = roller.update(bar_body)

        atr20 = self._atr.update(bar.high, bar.low, bar.close)
        range_vs_atr = (bar.high - bar.low) / atr20 if atr20 not in (None, 0) else None

        close_location: Optional[float] = (
            (bar.close - bar.low) / (bar.high - bar.low) if bar.high > bar.low else None
        )

        prior_vol_mean, prior_vol_std = self._volume_stats.update(bar.volume)
        volume_z = (
            (bar.volume - prior_vol_mean) / prior_vol_std
            if prior_vol_mean is not None and prior_vol_std not in (None, 0)
            else None
        )

        gated_attrs = {"ofi": None, "depth_imbalance": None, "spread": None, "data_gated": True}

        if sigma_tod is None or sigma_tod == 0:
            events.append(
                self._event(
                    "DISPLACEMENT_WARMUP",
                    bar,
                    {
                        "body_vs_tod": None,
                        "warmup_reason": "sigma_tod" if sigma_tod is None else "sigma_tod_zero",
                        "time_slot": f"{slot[0]:02d}:{slot[1]:02d}",
                        "sessions_needed": self.params.displacement_sigma_tod_lookback_sessions,
                        "range_vs_atr": range_vs_atr,
                        "close_location": close_location,
                        "volume_z": volume_z,
                        **gated_attrs,
                    },
                    discriminator="warmup",
                )
            )
        else:
            events.append(
                self._event(
                    "DISPLACEMENT_COMPONENTS",
                    bar,
                    {
                        "body_vs_tod": bar_body / sigma_tod,
                        "sigma_tod": sigma_tod,
                        "time_slot": f"{slot[0]:02d}:{slot[1]:02d}",
                        "range_vs_atr": range_vs_atr,
                        "close_location": close_location,
                        "volume_z": volume_z,
                        **gated_attrs,
                    },
                    discriminator="components",
                )
            )

        return events
