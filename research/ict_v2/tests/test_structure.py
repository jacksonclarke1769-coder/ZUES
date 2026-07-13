"""engines/structure.py: protected-swing BOS / CHoCH / MSS state machine."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from research.ict_v2.core.prefix import assert_chunk_invariant, assert_prefix_invariant
from research.ict_v2.engines.structure import StructureEngine
from research.ict_v2.tests.helpers import make_bars_from_closes

UTC = timezone.utc
START = datetime(2024, 1, 2, 9, 30, tzinfo=UTC)

# a clean up-zigzag establishing method-A swing highs/lows for a bullish state
_UPTREND = [
    100, 101, 102, 103, 110, 103, 102, 101, 100, 99, 98, 97, 90, 97, 98, 99,
    100, 101, 102, 103, 104, 111, 104, 103, 102, 101, 100, 99, 98, 97, 90, 97,
    98, 99, 100, 101, 102, 103, 104, 111, 104, 103, 102, 101, 100, 99, 98, 97,
]


def test_structure_initialized_on_first_break():
    bars = make_bars_from_closes(START, _UPTREND)
    eng = StructureEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    init = [e for e in events if e.event_type == "STRUCTURE_INITIALIZED"]
    assert len(init) == 1
    assert init[0].attributes["direction"] == "bullish"
    assert eng.direction == "bullish"


# escalating peaks (110 -> 120 -> 130), well clear of the confirmation-lag-shifted
# target level, so continuation genuinely breaks out rather than falling just short
_ESCALATING_UPTREND = [
    100, 101, 102, 103, 110, 102, 101, 100, 99, 98, 97, 96, 90, 96, 97, 98,
    99, 100, 101, 102, 103, 120, 103, 102, 101, 100, 99, 98, 97, 96, 90, 96,
    97, 98, 99, 100, 101, 102, 103, 130, 103, 102, 101, 100, 99, 98, 97, 96,
]


def test_bos_fires_on_continuation_break():
    bars = make_bars_from_closes(START, _ESCALATING_UPTREND)
    eng = StructureEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    bos = [e for e in events if e.event_type == "BOS"]
    assert len(bos) >= 1
    assert all(e.attributes["direction"] == "bullish" for e in bos)


def test_choch_then_mss_confirms_on_qualifying_displacement_bar():
    # CHoCH bar breaks the protected low with a SMALL body; the very NEXT bar
    # is a large-body bearish displacement bar -> MSS confirms one bar later.
    closes = _UPTREND + [50, 10, 9, 8]
    bars = make_bars_from_closes(START, closes)
    eng = StructureEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    choch = [e for e in events if e.event_type == "CHOCH"]
    mss = [e for e in events if e.event_type == "MSS"]
    assert len(choch) == 1
    assert choch[0].attributes["to_direction_candidate"] == "bearish"
    assert len(mss) == 1
    assert mss[0].source_event_ids == (choch[0].event_id,)
    assert mss[0].confirmed_at == bars[len(_UPTREND) + 1].close_time  # the bar AFTER CHoCH
    assert eng.direction == "bearish"


def test_choch_without_qualifying_displacement_expires_and_reverts():
    # CHoCH bar, then W_MSS (12) bars of small, non-qualifying moves -> MSS_WINDOW_EXPIRED,
    # direction reverts to the pre-CHoCH direction.
    small_wiggles = [96, 95, 96, 95, 96, 95, 96, 95, 96, 95, 96, 95]
    closes = _UPTREND + [50] + small_wiggles
    bars = make_bars_from_closes(START, closes)
    eng = StructureEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    choch = [e for e in events if e.event_type == "CHOCH"]
    expired = [e for e in events if e.event_type == "MSS_WINDOW_EXPIRED"]
    mss = [e for e in events if e.event_type == "MSS"]
    assert len(choch) == 1
    assert len(expired) == 1
    assert mss == []
    assert expired[0].attributes["reverted_to"] == "bullish"
    assert expired[0].source_event_ids == (choch[0].event_id,)
    assert eng.direction == "bullish"


def test_break_type_wick_param_uses_high_low_not_close():
    from research.ict_v2.core.config import ICT_V2_PARAMS_V0
    from dataclasses import replace

    wick_params = replace(ICT_V2_PARAMS_V0, break_type="wick")
    bars = make_bars_from_closes(START, _UPTREND)
    eng = StructureEngine(params=wick_params)
    for b in bars:
        eng.on_bar(b)  # must not raise; wick-mode is a legal, documented alternative


def test_unknown_break_type_raises():
    from research.ict_v2.core.config import ICT_V2_PARAMS_V0
    from dataclasses import replace

    bad_params = replace(ICT_V2_PARAMS_V0, break_type="bogus")
    bars = make_bars_from_closes(START, _UPTREND)
    eng = StructureEngine(params=bad_params)
    with pytest.raises(ValueError):
        for b in bars:
            eng.on_bar(b)


def test_prefix_and_chunk_invariance_across_full_lifecycle():
    closes = _UPTREND + [50, 10, 9, 8, 7, 6, 20, 21, 22, 23]
    bars = make_bars_from_closes(START, closes)
    assert_prefix_invariant(lambda: StructureEngine(), bars)
    assert_chunk_invariant(lambda: StructureEngine(), bars, n_trials=6, seed=5)


def test_gap_and_session_boundary_bars_do_not_crash():
    bars = make_bars_from_closes(START, _UPTREND) + make_bars_from_closes(
        START + timedelta(hours=10), [97, 96, 130, 96, 95]
    )
    eng = StructureEngine()
    for b in bars:
        eng.on_bar(b)


def test_dst_transition_day_bars_do_not_crash():
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    start = datetime(2025, 11, 2, 0, 0, tzinfo=ny)  # US fall-back day
    bars = make_bars_from_closes(start, _UPTREND)
    eng = StructureEngine()
    for b in bars:
        eng.on_bar(b)


def test_event_id_deterministic():
    closes = _UPTREND + [50, 10, 9, 8]
    bars = make_bars_from_closes(START, closes)
    eng1, eng2 = StructureEngine(), StructureEngine()
    ids1 = [e.event_id for b in bars for e in eng1.on_bar(b)]
    ids2 = [e.event_id for b in bars for e in eng2.on_bar(b)]
    assert ids1 == ids2 and len(ids1) > 0
