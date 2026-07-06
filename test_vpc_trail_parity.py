"""test_vpc_trail_parity.py — PHASE-0-SIM-ONLY permanent parity canary for the vpc_trail.py
refactor. RESEARCH ONLY. LIVE HOLD ACTIVE.

Two arms:

  ARM A (ACTIVE, historical replay) -- proves the vpc_trail.py extraction + tools_vpc_1m_truth.py
  rewire reproduce the trail's CURRENT behavior byte-identically. Runs the refactored
  `tools_vpc_1m_truth.vpc_1m_truth_trades()` over the real 2022-2026 Databento data and checks:
    (1) the aggregate 1m-truth stream signature: n=408, net=+5319.67pt (tol +-0.5pt), PF=1.318
        (tol +-0.002) -- the SAME numbers `tools_vpc_1m_truth.py`'s own canaries certify.
    (2) a bit-identical stop-series check for a FIXED, deterministic sample of 5 trades (sorted-ts
        index 0, 100, 200, 300, 407) against a FROZEN snapshot (exit reason, pnl, and a SHA-256
        content hash of the trade's full stop_path) generated ONCE from the refactored code and
        hard-coded below (SAMPLE_SNAPSHOTS) -- any future drift in vpc_trail.py's trail math
        changes the hash and fails this test.
    (3) a whole-stream guard: a SHA-256 hash of every trade's `pnl_pts_new` (in sorted-ts order)
        matches a frozen value (PNL_STREAM_HASH) -- catches any change/reordering the aggregate
        sum+PF check alone might not (e.g. two trades' pnl swapping while the sum stays put).

  A PASSING ARM A proves the vpc_trail.py refactor did NOT change tools_vpc_1m_truth.py's
  behavior. It does NOT prove sim/live parity -- a future live bar-close feed calling the same
  `VpcTrail` stepper could still diverge from this historical replay for reasons outside the
  refactor's scope (feed timing, bar-close semantics, reconnects, etc.). That is ARM B's job, and
  ARM B is REQUIRED-BEFORE-ARM (not built yet) -- see its docstring below.

  ARM B (STUBBED, live-shaped input, REQUIRED-BEFORE-ARM) -- `test_live_shaped_parity_arm_STUB`.
  Skipped via `pytest.skip(...)`; the intended assertion is shown as a commented scaffold so the
  eventual test is visible in code, not just described in prose.
"""
import hashlib
import os
import sys
import warnings

import pytest

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

import tools_vpc_1m_truth as T
import tools_salvage_vpc_reeval as VR
import vpc_trail as VT


# ==================================================================================================
# FROZEN reference values -- generated ONCE from the refactored code (2026-07-07), hard-coded here
# so future drift in vpc_trail.py / tools_vpc_1m_truth.py's rewire fails this test.
# ==================================================================================================
FROZEN_N = 408
FROZEN_NET_NEW = 5319.669642857123
FROZEN_PF = 1.3175890009642746
NET_TOL = 0.5
PF_TOL = 0.002

# Fixed, deterministic sample: sorted-by-ts index positions {0, 100, 200, 300, 407} out of 408.
SAMPLE_SNAPSHOTS = {
    0: dict(
        ts=pd.Timestamp("2022-01-14 15:10:00"), exit_reason_new="stop",
        pnl_pts_new=-105.553571, n_steps=169,
        first=(15393.0625, 15393.0625), last=(15434.196429, 15434.196429),
        stop_path_hash="cffbdb387550a276d4df49a13e40d807fd027ac58cc3911d539f5b2613979cdd",
    ),
    100: dict(
        ts=pd.Timestamp("2023-02-16 15:10:00"), exit_reason_new="stop",
        pnl_pts_new=28.553571, n_steps=295,
        first=(12468.714286, 12468.714286), last=(12609.803571, 12609.803571),
        stop_path_hash="6ac0f2360fb8b6b6dd3cb5a80a79fb04cdebc1b0815dbdf0cb65ee9a6b2af5e9",
    ),
    200: dict(
        ts=pd.Timestamp("2024-03-21 14:15:00"), exit_reason_new="stop",
        pnl_pts_new=-56.053571, n_steps=127,
        first=(18758.392857, 18758.392857), last=(18701.553571, 18701.553571),
        stop_path_hash="f78ee94290494c1fccc4b0883b8ac091318fcbe52c88ed241d24c8dd7fd92a03",
    ),
    300: dict(
        ts=pd.Timestamp("2025-05-21 17:15:00"), exit_reason_new="stop",
        pnl_pts_new=-62.535714, n_steps=2,
        first=(21392.464286, 21392.464286), last=(21392.464286, 21392.464286),
        stop_path_hash="989b1aae7cc36cef16ee69f3a65cfe824bcc8dd9a9c6ac37552dfab4ec44c7cd",
    ),
    407: dict(
        ts=pd.Timestamp("2026-06-19 14:05:00"), exit_reason_new="eod",
        pnl_pts_new=-31.5, n_steps=175,
        first=(30580.383929, 30580.383929), last=(30634.125, 30634.125),
        stop_path_hash="f939355bc28053d1a7a0cb178a4dce8b5d66b4f11a3f206e7be10f6e2084543a",
    ),
}

PNL_STREAM_HASH = "445964f62be16f0033adffa3bdf58a9285201caf1463ab4b71ad74fb90ddcc26"


def _hash_stop_path(stop_path):
    """Deterministic SHA-256 content hash of a trade's full stop_path (list of (old, new) stop
    tuples), rounded to 6 decimals for stable repr across runs."""
    h = hashlib.sha256()
    for a, b in stop_path:
        h.update(repr(round(float(a), 6)).encode())
        h.update(b",")
        h.update(repr(round(float(b), 6)).encode())
        h.update(b";")
    return h.hexdigest()


def _hash_pnl_stream(pnl_values):
    h = hashlib.sha256()
    for x in pnl_values:
        h.update(repr(round(float(x), 6)).encode())
        h.update(b";")
    return h.hexdigest()


@pytest.fixture(scope="module")
def df1m():
    """Runs the refactored (vpc_trail.py-backed) 1m-truth re-walk over the real data ONCE and
    shares the result across this module's tests."""
    v, VS = VR.v, VR.VS
    feats = v.features(VS.real_rth_5m())
    feats = feats[feats.date >= VR.WINDOW_START]
    d1rth = T.load_1m_rth()
    df, n_skipped = T.vpc_1m_truth_trades(feats, d1rth)
    assert n_skipped == 0, f"expected 0 dropped-fill trades, got {n_skipped}"
    return df


def test_arm_a_aggregate_signature(df1m):
    """n=408, net_new=+5319.67pt (tol +-0.5), PF=1.318 (tol +-0.002) -- the same headline numbers
    tools_vpc_1m_truth.py's own run_canaries() certifies for the 1m-truth stream."""
    assert len(df1m) == FROZEN_N

    net_new = float(df1m["pnl_pts_new"].sum())
    assert abs(net_new - FROZEN_NET_NEW) < NET_TOL, f"net_new={net_new} vs frozen {FROZEN_NET_NEW}"

    gp = float(df1m.loc[df1m.pnl_pts_new > 0, "pnl_pts_new"].sum())
    gl = float(-df1m.loc[df1m.pnl_pts_new < 0, "pnl_pts_new"].sum())
    pf = gp / gl
    assert abs(pf - FROZEN_PF) < PF_TOL, f"pf={pf} vs frozen {FROZEN_PF}"


def test_arm_a_sample_stop_path_bit_identical(df1m):
    """Fixed sample of 5 trades (sorted-ts index 0/100/200/300/407): exit reason, pnl, and a
    content hash of the FULL stop_path must equal the frozen snapshot -- any drift in the trail
    math (vpc_trail.VpcTrail.step / walk_1m_trail) changes the hash and fails here."""
    for i, expected in SAMPLE_SNAPSHOTS.items():
        row = df1m.iloc[i]
        stop_path = row["stop_path_new"]
        assert row["ts"] == expected["ts"], f"trade {i}: ts mismatch"
        assert row["exit_reason_new"] == expected["exit_reason_new"], f"trade {i}: exit_reason mismatch"
        assert abs(float(row["pnl_pts_new"]) - expected["pnl_pts_new"]) < 1e-6, f"trade {i}: pnl mismatch"
        assert len(stop_path) == expected["n_steps"], f"trade {i}: stop_path length mismatch"
        if stop_path:
            first = tuple(round(float(x), 6) for x in stop_path[0])
            last = tuple(round(float(x), 6) for x in stop_path[-1])
            assert first == expected["first"], f"trade {i}: first stop_path tuple mismatch"
            assert last == expected["last"], f"trade {i}: last stop_path tuple mismatch"
        got_hash = _hash_stop_path(stop_path)
        assert got_hash == expected["stop_path_hash"], (
            f"trade {i}: stop_path content hash mismatch (got {got_hash}, "
            f"expected {expected['stop_path_hash']}) -- the trail math changed"
        )


def test_arm_a_whole_stream_guard(df1m):
    """SHA-256 hash of every trade's pnl_pts_new, in sorted-ts order, matches a frozen value --
    catches drift the aggregate sum/PF check alone might miss (e.g. two trades' pnl swapping)."""
    got = _hash_pnl_stream(df1m["pnl_pts_new"].values)
    assert got == PNL_STREAM_HASH, f"pnl stream hash mismatch (got {got}, expected {PNL_STREAM_HASH})"


def test_arm_a_ratchet_never_loosens():
    """Structural guard directly on the canonical stepper (not just the historical replay): the
    trail can never move the stop away from price, for both directions."""
    long_trail = VT.VpcTrail(entry=100.0, direction=1, init_stop_dist=5.0, trail_atr=2.0)
    prev_stop = long_trail.stop
    for bar in [(96, 102, 101, 1.0), (98, 105, 104, 1.0), (99, 103, 100, 1.0)]:
        flag, level = long_trail.step(*bar)
        if flag == "stop":
            break
        assert level >= prev_stop
        prev_stop = level

    short_trail = VT.VpcTrail(entry=100.0, direction=-1, init_stop_dist=5.0, trail_atr=2.0)
    prev_stop = short_trail.stop
    for bar in [(98, 104, 99, 1.0), (95, 100, 96, 1.0), (97, 99, 100, 1.0)]:
        flag, level = short_trail.step(*bar)
        if flag == "stop":
            break
        assert level <= prev_stop
        prev_stop = level


def test_live_shaped_parity_arm_STUB():
    """ARM B (REQUIRED-BEFORE-ARM, NOT BUILT): would feed a mock live bar-close stream into the
    SAME `VpcTrail` stepper used by ARM A's historical replay and assert the resulting stop_path
    is identical to ARM A's for the same trade -- i.e. that live/sim parity holds, not just that
    the refactor is behavior-preserving.

    A passing ARM A (this file's other tests) proves the vpc_trail.py extraction did not change
    tools_vpc_1m_truth.py's existing behavior. It does NOT prove sim/live parity: a live feed has
    different timing/bar-close/reconnect semantics that this historical replay never exercises.
    That gap is ARM B's job, and it is explicitly gated as NOT YET BUILT (Phase-0 scope is
    sim-only) -- do not treat a green ARM A as evidence live will match sim.

    Intended shape once built (commented scaffold, not executed):

        # trail_sim = VT.VpcTrail(entry, direction, init_stop_dist, trail_atr)
        # sim_path = []
        # for bar_low, bar_high, bar_close, atr_now in historical_bars_for_trade(sample_trade):
        #     flag, level = trail_sim.step(bar_low, bar_high, bar_close, atr_now)
        #     sim_path.append((flag, level))
        #     if flag == "stop":
        #         break
        #
        # trail_live = VT.VpcTrail(entry, direction, init_stop_dist, trail_atr)
        # live_path = []
        # for bar in mock_live_feed.stream_bar_closes(sample_trade):  # NOT BUILT: no mock live
        #     flag, level = trail_live.step(bar.low, bar.high, bar.close, bar.atr_now)
        #     live_path.append((flag, level))
        #     if flag == "stop":
        #         break
        #
        # assert sim_path == live_path  # sim/live parity -- THE claim ARM A cannot make
    """
    pytest.skip(
        "REQUIRED-BEFORE-ARM: live-shaped bar-close feed arm not built; Phase-0 proves refactor "
        "clean, NOT that live matches sim"
    )
