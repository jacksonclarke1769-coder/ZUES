"""Point-in-time macro-calendar interface -- STUB, no CSV data loaded in Phase 2.

CSV schema (point-in-time discipline: an event's `known_at_utc` must never be
earlier than what a live system could actually have known -- consumers must
never look a macro print up using a timestamp later than when it was truly
public, and must never use a REVISED value as if it were known at the original
release instant; that retroactive-revision lookahead is the macro-calendar
analogue of the D1c string-localization bug):

    release_time_utc,known_at_utc,event_name,country,importance,actual,forecast,previous,revised_from

    - release_time_utc : ISO-8601 UTC timestamp of the scheduled release.
    - known_at_utc     : ISO-8601 UTC timestamp the value was actually publicly
                          known. Usually == release_time_utc; later for a revision.
    - event_name       : e.g. "CPI YoY", "FOMC Rate Decision", "NFP".
    - country          : ISO country code, e.g. "US".
    - importance       : "high" | "medium" | "low".
    - actual           : the released value (float; blank if not yet released).
    - forecast         : consensus estimate as of release (float; blank if none).
    - previous         : prior period's value AS PUBLISHED AT THAT TIME (float).
    - revised_from     : the prior `actual` this row revises, blank if not a
                          revision (a revision is a NEW row with a later
                          `known_at_utc`, never an edit of the original row).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List

from . import DataGated

__all__ = ["DataGated", "MACRO_CSV_SCHEMA", "MacroCalendarInterface"]

MACRO_CSV_SCHEMA = (
    "release_time_utc,known_at_utc,event_name,country,importance,"
    "actual,forecast,previous,revised_from"
)


class MacroCalendarInterface:
    """Placeholder surface for a point-in-time macro calendar. Gated: no CSV
    data loaded in Phase 2."""

    def events_known_by(self, t: datetime) -> List[Any]:
        """All macro events with `known_at_utc <= t`. Gated: no data loaded."""
        raise DataGated("point-in-time macro calendar: no CSV data loaded in Phase 2 (docket D1)")
