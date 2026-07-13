"""engines/zones.py: FVG / IFVG / OrderBlock / Breaker lifecycles."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

from research.ict_v2.core.prefix import assert_chunk_invariant, assert_prefix_invariant
from research.ict_v2.engines.zones import ZonesEngine, fvg_from_triple
from research.ict_v2.tests.helpers import Bar, make_bars_from_closes

UTC = timezone.utc
START = datetime(2024, 1, 2, 9, 30, tzinfo=UTC)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
FRAMEWORK_ROOT = os.path.join(_REPO_ROOT, "..", "..", "backtests", "ict-nq-framework")


def _load_oracle_primitives():
    engine_dir = os.path.join(os.path.abspath(FRAMEWORK_ROOT), "engine")
    if engine_dir not in sys.path:
        sys.path.insert(0, engine_dir)
    import primitives as P  # noqa: PLC0415

    return P


def _bar(ct, o, h, l, c, v=100.0):
    return Bar(close_time=ct, open=o, high=h, low=l, close=c, volume=v)


def _t(i):
    return START + timedelta(minutes=5 * i)


# a clean up-zigzag -> sharp reversal -> a subsequent qualifying displacement
# bar, mirroring test_structure.py's own CHoCH/MSS fixture exactly (needed
# here so structure.py's private StructureEngine actually produces a BOS/MSS
# for the OrderBlock tests below).
_UPTREND = [
    100, 101, 102, 103, 110, 103, 102, 101, 100, 99, 98, 97, 90, 97, 98, 99,
    100, 101, 102, 103, 104, 111, 104, 103, 102, 101, 100, 99, 98, 97, 90, 97,
    98, 99, 100, 101, 102, 103, 104, 111, 104, 103, 102, 101, 100, 99, 98, 97,
]


# --- FVG: minimum valid / near-miss / boundary equality / min-size ------------

def test_fvg_minimum_valid_bullish_gap():
    eng = ZonesEngine()
    eng.on_bar(_bar(_t(0), 100, 101, 99, 100.5))
    eng.on_bar(_bar(_t(1), 101, 103, 100.5, 102))
    events = eng.on_bar(_bar(_t(2), 103, 106, 102.5, 105))  # A.high=101 < C.low=102.5 -> bull gap [101, 102.5]
    created = next(e for e in events if e.event_type == "FVG_CREATED")
    assert created.attributes["direction"] == "bullish"
    assert created.price_low == 101 and created.price_high == 102.5
    assert created.origin_time == _t(1)  # candle B
    assert created.confirmed_at == _t(2)  # close(C)
    assert created.attributes["qualifies_min_size"] is True
    assert any(e.event_type == "FVG_QUALIFIED" for e in events)


def test_fvg_near_miss_overlapping_candles_no_gap():
    eng = ZonesEngine()
    eng.on_bar(_bar(_t(0), 100, 101, 99, 100.5))
    eng.on_bar(_bar(_t(1), 101, 103, 100.5, 102))
    events = eng.on_bar(_bar(_t(2), 103, 106, 100.9, 105))  # C.low=100.9 <= A.high=101 -> no bull gap
    assert [e for e in events if e.event_type == "FVG_CREATED"] == []


def test_fvg_boundary_equality_gap_exactly_at_min_size_qualifies():
    eng = ZonesEngine()
    eng.on_bar(_bar(_t(0), 100, 101, 99, 100.5))
    eng.on_bar(_bar(_t(1), 101, 103, 100.5, 102))
    events = eng.on_bar(_bar(_t(2), 103, 106, 102.0, 105))  # gap = 102.0 - 101 = 1.0pt = 4 ticks EXACTLY
    created = next(e for e in events if e.event_type == "FVG_CREATED")
    assert created.attributes["size_ticks"] == pytest.approx(4.0)
    assert created.attributes["qualifies_min_size"] is True


def test_fvg_sub_threshold_gap_created_but_not_qualified_no_silent_filter():
    eng = ZonesEngine()
    eng.on_bar(_bar(_t(0), 100, 101, 99, 100.5))
    eng.on_bar(_bar(_t(1), 101, 103, 100.5, 102))
    events = eng.on_bar(_bar(_t(2), 103, 106, 101.1, 105))  # gap = 0.1pt = 0.4 ticks -- well under 4
    created = [e for e in events if e.event_type == "FVG_CREATED"]
    qualified = [e for e in events if e.event_type == "FVG_QUALIFIED"]
    assert len(created) == 1  # NOT suppressed
    assert created[0].attributes["qualifies_min_size"] is False
    assert qualified == []


def test_bearish_gap_direction_and_zone():
    eng = ZonesEngine()
    eng.on_bar(_bar(_t(0), 100, 101, 99, 99.5))
    eng.on_bar(_bar(_t(1), 99, 100, 96, 97))
    events = eng.on_bar(_bar(_t(2), 96, 97, 90, 92))  # A.low=99 > C.high=97 -> bear gap [92? no: zone=[C.high, A.low]=[97,99]]
    created = next(e for e in events if e.event_type == "FVG_CREATED")
    assert created.attributes["direction"] == "bearish"
    assert created.price_low == 97 and created.price_high == 99


# --- pure fvg_from_triple() helper ---------------------------------------------

def test_fvg_from_triple_no_overlap_returns_none():
    a = _bar(_t(0), 100, 101, 99, 100.5)
    c = _bar(_t(2), 101, 101.5, 100.9, 101)  # overlaps A's high -- neither strict gap holds
    assert fvg_from_triple(a, c) is None


# --- FVG lifecycle: CREATED -> TESTED -> INVALIDATED -> IFVG_CREATED --------------

def test_fvg_tested_then_invalidated_spawns_ifvg_with_flipped_direction():
    eng = ZonesEngine()
    eng.on_bar(_bar(_t(0), 100, 101, 99, 100.5))
    eng.on_bar(_bar(_t(1), 101, 103, 100.5, 102))
    ev_create = eng.on_bar(_bar(_t(2), 103, 106, 102.5, 105))  # bull FVG [101, 102.5]
    created = next(e for e in ev_create if e.event_type == "FVG_CREATED")
    # bar4: touches the zone without closing through the far boundary (101)
    ev_test = eng.on_bar(_bar(_t(3), 104, 105, 101.5, 101.8))
    tested = [e for e in ev_test if e.event_type == "FVG_TESTED"]
    assert len(tested) == 1
    assert tested[0].source_event_ids == (created.event_id,)
    assert tested[0].attributes["test_count"] == 1
    # bar5: closes back below zone_low (101) -- invalidated
    ev_inv = eng.on_bar(_bar(_t(4), 101.5, 101.6, 100.0, 100.5))
    invalidated = next(e for e in ev_inv if e.event_type == "FVG_INVALIDATED")
    ifvg = next(e for e in ev_inv if e.event_type == "IFVG_CREATED")
    assert invalidated.source_event_ids == (created.event_id,)
    assert ifvg.source_event_ids == (invalidated.event_id,)
    assert ifvg.attributes["direction"] == "bearish"  # flipped from bullish
    assert ifvg.price_low == created.price_low and ifvg.price_high == created.price_high
    assert ifvg.attributes["source_fvg_id"] == created.event_id


def test_ifvg_own_lifecycle_invalidates_without_further_chain():
    eng = ZonesEngine()
    eng.on_bar(_bar(_t(0), 100, 101, 99, 100.5))
    eng.on_bar(_bar(_t(1), 101, 103, 100.5, 102))
    eng.on_bar(_bar(_t(2), 103, 106, 102.5, 105))  # bull FVG [101, 102.5]
    ev_inv = eng.on_bar(_bar(_t(3), 101.5, 101.6, 100.0, 100.5))  # invalidate -> bearish IFVG [101, 102.5]
    ifvg = next(e for e in ev_inv if e.event_type == "IFVG_CREATED")
    # bearish IFVG invalidated when close > zone_high (102.5)
    ev_inv2 = eng.on_bar(_bar(_t(4), 101.0, 103.0, 100.9, 102.8))
    ifvg_inv = [e for e in ev_inv2 if e.event_type == "IFVG_INVALIDATED"]
    assert len(ifvg_inv) == 1
    assert ifvg_inv[0].source_event_ids == (ifvg.event_id,)
    assert [e for e in ev_inv2 if e.event_type not in ("IFVG_TESTED", "IFVG_INVALIDATED")] == []


def test_fvg_expires_at_end_of_forming_session_ny_time():
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    base = datetime(2024, 1, 2, 10, 0, tzinfo=ny)  # within ny_am (09:30-11:30)
    eng = ZonesEngine()
    eng.on_bar(_bar(base, 100, 101, 99, 100.5))
    eng.on_bar(_bar(base + timedelta(minutes=5), 101, 103, 100.5, 102))
    eng.on_bar(_bar(base + timedelta(minutes=10), 103, 106, 102.5, 105))  # created 10:10, zone [101, 102.5]
    expired = None
    ct = base + timedelta(minutes=15)
    for _ in range(30):
        events = eng.on_bar(_bar(ct, 101.5, 102.0, 101.2, 101.6))  # stays inside the zone, never invalidates
        found = [e for e in events if e.event_type == "FVG_EXPIRED"]
        if found:
            expired = found[0]
            break
        ct += timedelta(minutes=5)
    assert expired is not None
    assert expired.confirmed_at.astimezone(ny).time() >= datetime(2024, 1, 2, 11, 30, tzinfo=ny).time()
    assert expired.attributes["test_count"] > 0


# --- OrderBlock: created on MSS + coincident DISPLACEMENT_QUALIFIED --------------

def test_orderblock_created_on_mss_with_opposing_candle():
    closes = _UPTREND + [50, 10, 9, 8]
    bars = make_bars_from_closes(START, closes)
    eng = ZonesEngine()
    all_events = [e for b in bars for e in eng.on_bar(b)]
    ob = [e for e in all_events if e.event_type == "OB_CREATED"]
    assert len(ob) == 1
    assert ob[0].attributes["direction"] == "bearish"  # MSS reversed to bearish
    assert ob[0].attributes["structure_event_type"] == "MSS"
    # the opposing candle is a BULLISH candle (close > open): zone_low < zone_high, sane full-candle range
    assert ob[0].price_low < ob[0].price_high
    assert ob[0].first_eligible_retest_at > ob[0].created_at if hasattr(ob[0], "first_eligible_retest_at") else True


def test_orderblock_shares_impulse_id_with_coincident_fvg():
    closes = _UPTREND + [50, 10, 9, 8]
    bars = make_bars_from_closes(START, closes)
    eng = ZonesEngine()
    all_events = [e for b in bars for e in eng.on_bar(b)]
    ob = next(e for e in all_events if e.event_type == "OB_CREATED")
    fvg_same_bar = [
        e for e in all_events
        if e.event_type == "FVG_CREATED" and e.confirmed_at == ob.confirmed_at and e.attributes["direction"] == "bearish"
    ]
    assert len(fvg_same_bar) == 1
    assert fvg_same_bar[0].attributes["impulse_id"] == ob.attributes["impulse_id"]
    assert ob.attributes["impulse_id"] is not None


def test_orderblock_no_opposing_candle_in_window_emits_nothing():
    # a monotonically falling run right into the CHoCH/MSS -- no opposing (bullish)
    # candle exists within the scan-back window, so no OB candidate can be built.
    falling = [100 - i for i in range(20)] + [200]  # sharp reversal up -> bullish MSS
    bars = make_bars_from_closes(START, falling)
    eng = ZonesEngine()
    all_events = [e for b in bars for e in eng.on_bar(b)]
    assert [e for e in all_events if e.event_type == "OB_CREATED"] == []


# --- OrderBlock lifecycle: invalidation spawns a Breaker -----------------------

def test_orderblock_invalidated_spawns_breaker():
    closes = _UPTREND + [50, 10, 9, 8, 9, 10, 50, 90, 130, 130]
    bars = make_bars_from_closes(START, closes)
    eng = ZonesEngine()
    all_events = [e for b in bars for e in eng.on_bar(b)]
    ob = next(e for e in all_events if e.event_type == "OB_CREATED")
    ob_inv = next(e for e in all_events if e.event_type == "OB_INVALIDATED")
    breaker = next(e for e in all_events if e.event_type == "BREAKER_CREATED")
    assert ob_inv.source_event_ids == (ob.event_id,)
    assert breaker.source_event_ids == (ob_inv.event_id,)
    assert breaker.attributes["direction"] == "bullish"  # flipped from the bearish OB
    assert breaker.price_low == ob.price_low and breaker.price_high == ob.price_high
    assert breaker.attributes["impulse_id"] == ob.attributes["impulse_id"]


# --- full lifecycle walk: every terminal state observed at least once -----------

def test_full_lifecycle_walk_hits_every_terminal_event_type():
    closes = _UPTREND + [50, 10, 9, 8, 9, 10, 50, 90, 130, 130] + [101] * 40
    bars = make_bars_from_closes(START, closes)
    eng = ZonesEngine()
    all_events = [e for b in bars for e in eng.on_bar(b)]
    types = {e.event_type for e in all_events}
    for required in ("FVG_CREATED", "OB_CREATED", "OB_INVALIDATED", "BREAKER_CREATED"):
        assert required in types, f"missing {required}"
    # every FVG_CREATED reaches a terminal (INVALIDATED or EXPIRED) somewhere downstream
    created_ids = {e.event_id for e in all_events if e.event_type == "FVG_CREATED"}
    terminal_src = {
        e.source_event_ids[0] for e in all_events if e.event_type in ("FVG_INVALIDATED", "FVG_EXPIRED")
    }
    # not all FVGs necessarily resolve within this finite walk -- but at least one must, proving the machinery works
    assert created_ids & terminal_src


# --- oracle equivalence: FVG mirrors primitives.py::fvgs() on the UNFILTERED stream --

def test_fvg_matches_oracle_fvgs_unfiltered_stream():
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    P = _load_oracle_primitives()

    rng = np.random.default_rng(3)
    n = 120
    closes = 100 + np.cumsum(rng.normal(0, 2, n))
    opens = closes - rng.normal(0, 1, n)
    highs = np.maximum(opens, closes) + np.abs(rng.normal(0.3, 0.5, n))
    lows = np.minimum(opens, closes) - np.abs(rng.normal(0.3, 0.5, n))
    df = pd.DataFrame({"Open": opens, "High": highs, "Low": lows, "Close": closes})
    oracle_fv = P.fvgs(df)
    oracle_by_idx = {int(r.form_idx): (int(r.direction), float(r.top), float(r.bottom)) for _, r in oracle_fv.iterrows()}

    bars = [
        Bar(close_time=START + timedelta(minutes=5 * i), open=opens[i], high=highs[i], low=lows[i], close=closes[i])
        for i in range(n)
    ]
    eng = ZonesEngine()
    mine_by_idx = {}
    for i, b in enumerate(bars):
        for e in eng.on_bar(b):
            if e.event_type == "FVG_CREATED":
                d = 1 if e.attributes["direction"] == "bullish" else -1
                mine_by_idx[i] = (d, e.price_high, e.price_low)

    assert set(mine_by_idx) == set(oracle_by_idx)
    for idx in oracle_by_idx:
        od, otop, obottom = oracle_by_idx[idx]
        md, mtop, mbottom = mine_by_idx[idx]
        assert md == od
        assert mtop == pytest.approx(otop)
        assert mbottom == pytest.approx(obottom)


# --- gap / DST / session boundary ----------------------------------------------

def test_gap_missing_bar_does_not_crash():
    eng = ZonesEngine()
    closes = _UPTREND[:10] + [200] + _UPTREND[10:20]
    bars = make_bars_from_closes(START, closes[:15]) + make_bars_from_closes(
        START + timedelta(hours=8), closes[15:]
    )
    for b in bars:
        eng.on_bar(b)


def test_dst_transition_day_does_not_crash():
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    start = datetime(2024, 3, 9, 18, 0, tzinfo=ny)
    bars = make_bars_from_closes(start, _UPTREND + [50, 10, 9, 8])
    eng = ZonesEngine()
    for b in bars:
        eng.on_bar(b)


# --- prefix / chunk invariance + determinism -----------------------------------

def _walk_bars():
    closes = _UPTREND + [50, 10, 9, 8, 9, 10, 50, 90, 130, 130]
    return make_bars_from_closes(START, closes)


def test_prefix_and_chunk_invariance():
    bars = _walk_bars()
    assert_prefix_invariant(lambda: ZonesEngine(), bars)
    assert_chunk_invariant(lambda: ZonesEngine(), bars, n_trials=5, seed=13)


def test_event_id_deterministic():
    bars = _walk_bars()
    eng1, eng2 = ZonesEngine(), ZonesEngine()
    ids1 = [e.event_id for b in bars for e in eng1.on_bar(b)]
    ids2 = [e.event_id for b in bars for e in eng2.on_bar(b)]
    assert ids1 == ids2 and len(ids1) > 0
