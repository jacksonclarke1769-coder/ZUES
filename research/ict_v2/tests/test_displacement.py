"""engines/displacement.py: per-bar normalized displacement components +
DISPLACEMENT_QUALIFIED. Equivalence vs the frozen oracle's
`displacement_strength` threshold (required by SPEC.md's test requirements).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

from research.ict_v2.core.prefix import assert_chunk_invariant, assert_prefix_invariant
from research.ict_v2.engines.displacement import DisplacementEngine
from research.ict_v2.tests.helpers import Bar, make_5m_bars

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


def _bars_with_bodies(start, bodies, wick=0.3):
    bars = []
    price = 20000.0
    for i, b in enumerate(bodies):
        ct = start + timedelta(minutes=5 * i)
        o = price
        c = price + b
        h = max(o, c) + wick
        lo = min(o, c) - wick
        bars.append(Bar(close_time=ct, open=o, high=h, low=lo, close=c, volume=100.0 + i))
        price = c
    return bars


def test_no_events_are_ever_silently_dropped_exactly_one_or_two_per_bar():
    bars = make_5m_bars(START, 25, step=1.0)
    eng = DisplacementEngine()
    for b in bars:
        events = eng.on_bar(b)
        types = {e.event_type for e in events}
        assert types <= {"DISPLACEMENT_QUALIFIED", "DISPLACEMENT_WARMUP", "DISPLACEMENT_COMPONENTS"}
        # exactly one of WARMUP/COMPONENTS, plus an optional QUALIFIED
        assert len([t for t in types if t in ("DISPLACEMENT_WARMUP", "DISPLACEMENT_COMPONENTS")]) == 1


def test_qualified_minimum_valid_case_body_at_1_5x_mean():
    # 20 bars of body=1.0 (warms up mean-20-body to 1.0), then a body=1.5 bar
    bodies = [1.0] * 20 + [1.5]
    bars = _bars_with_bodies(START, bodies)
    eng = DisplacementEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    qualified = [e for e in events if e.event_type == "DISPLACEMENT_QUALIFIED"]
    assert len(qualified) == 1
    assert qualified[0].attributes["ratio"] == pytest.approx(1.5)
    assert qualified[0].attributes["direction"] == "bullish"


def test_near_miss_body_just_under_threshold_does_not_qualify():
    bodies = [1.0] * 20 + [1.4999]
    bars = _bars_with_bodies(START, bodies)
    eng = DisplacementEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    assert [e for e in events if e.event_type == "DISPLACEMENT_QUALIFIED"] == []


def test_warmup_emitted_before_20_bars_of_body_history():
    bars = _bars_with_bodies(START, [1.0] * 5)
    eng = DisplacementEngine()
    events = [e for b in bars for e in eng.on_bar(b)]
    assert all(e.event_type == "DISPLACEMENT_WARMUP" for e in events if e.event_type != "DISPLACEMENT_QUALIFIED")


def test_qualified_equivalence_vs_frozen_oracle():
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    P = _load_oracle_primitives()

    rng = np.random.default_rng(7)
    n = 150
    closes = 20000 + np.cumsum(rng.normal(0, 3, n))
    opens = closes - rng.normal(0, 2, n)
    highs = np.maximum(opens, closes) + np.abs(rng.normal(0.5, 1, n))
    lows = np.minimum(opens, closes) - np.abs(rng.normal(0.5, 1, n))
    vols = np.abs(rng.normal(100, 20, n))
    df = pd.DataFrame({"Open": opens, "High": highs, "Low": lows, "Close": closes})
    ds = P.displacement_strength(df, 20)
    oracle_qualified = np.abs(ds) >= 1

    bars = [
        Bar(close_time=START + timedelta(minutes=5 * i), open=opens[i], high=highs[i], low=lows[i],
            close=closes[i], volume=vols[i])
        for i in range(n)
    ]
    eng = DisplacementEngine()
    qualified_idx = set()
    for i, b in enumerate(bars):
        for e in eng.on_bar(b):
            if e.event_type == "DISPLACEMENT_QUALIFIED":
                qualified_idx.add(i)
    my_qualified = [i in qualified_idx for i in range(n)]
    assert my_qualified == list(oracle_qualified)


def test_ofi_depth_spread_are_always_none_and_flagged_data_gated():
    bars = _bars_with_bodies(START, [1.0] * 22)
    eng = DisplacementEngine()
    for b in bars:
        for e in eng.on_bar(b):
            if e.event_type in ("DISPLACEMENT_COMPONENTS", "DISPLACEMENT_WARMUP"):
                assert e.attributes["ofi"] is None
                assert e.attributes["depth_imbalance"] is None
                assert e.attributes["spread"] is None
                assert e.attributes["data_gated"] is True


def test_sigma_tod_warmup_transitions_to_components_at_the_20th_prior_occurrence():
    start = datetime(2024, 1, 2, 9, 30, tzinfo=UTC)
    bars = []
    price = 20000.0
    for day in range(25):
        ct = start + timedelta(days=day)
        c = price + (1.0 if day % 2 == 0 else -1.0)
        bars.append(Bar(close_time=ct, open=price, high=max(price, c) + 0.3, low=min(price, c) - 0.3, close=c))
        price = c
    eng = DisplacementEngine()
    seq = []
    for b in bars:
        for e in eng.on_bar(b):
            if e.event_type in ("DISPLACEMENT_WARMUP", "DISPLACEMENT_COMPONENTS"):
                seq.append(e.event_type)
    assert seq[:20] == ["DISPLACEMENT_WARMUP"] * 20
    assert seq[20:] == ["DISPLACEMENT_COMPONENTS"] * 5

    eng2 = DisplacementEngine()
    all_events = [e for b in bars for e in eng2.on_bar(b)]
    comps = [e for e in all_events if e.event_type == "DISPLACEMENT_COMPONENTS"]
    assert comps[-1].attributes["body_vs_tod"] is not None


def test_boundary_equality_zero_range_bar_close_location_none():
    b = Bar(close_time=START, open=100.0, high=100.0, low=100.0, close=100.0, volume=10.0)
    eng = DisplacementEngine()
    events = eng.on_bar(b)
    comp = [e for e in events if e.event_type in ("DISPLACEMENT_WARMUP", "DISPLACEMENT_COMPONENTS")][0]
    assert comp.attributes["close_location"] is None
    assert comp.attributes["range_vs_atr"] is None  # ATR20 also not warmed up yet


def test_gap_and_session_boundary_bars_do_not_crash():
    bars = make_5m_bars(START, 10) + make_5m_bars(START + timedelta(hours=6), 10)
    eng = DisplacementEngine()
    for b in bars:
        eng.on_bar(b)


def test_dst_transition_day_bars_do_not_crash():
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    start = datetime(2024, 3, 10, 0, 0, tzinfo=ny)
    bars = make_5m_bars(start, 40, step=0.5)
    eng = DisplacementEngine()
    for b in bars:
        eng.on_bar(b)


def test_prefix_and_chunk_invariance():
    bars = _bars_with_bodies(START, [1.0, 2.0, 0.5, 3.0, 1.0] * 10)
    assert_prefix_invariant(lambda: DisplacementEngine(), bars)
    assert_chunk_invariant(lambda: DisplacementEngine(), bars, n_trials=6, seed=8)


def test_event_id_deterministic_and_actionable_after_confirmed():
    bars = _bars_with_bodies(START, [1.0] * 25)
    eng1, eng2 = DisplacementEngine(), DisplacementEngine()
    ids1 = [e.event_id for b in bars for e in eng1.on_bar(b)]
    ids2 = [e.event_id for b in bars for e in eng2.on_bar(b)]
    assert ids1 == ids2 and len(ids1) > 0
    for b in bars:
        for e in DisplacementEngine().on_bar(b):
            assert e.actionable_at > e.confirmed_at
