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

# ---- 5m-native convention (the conservative signed economic basis, DEC-20260712 §4) --------------
# The parity canary must cover BOTH exit conventions with their respective certified signatures.
# 5m-native = simulate_day's high/low-referenced trail (VS.vpc_trades_rich); 1m-truth = the
# close-referenced VpcTrail walk above. The DEC pins 5m-native as the signed numeric basis and
# 1m-truth as the live lane's parity TARGET.
FROZEN_N_5M = 408
FROZEN_NET_5M = 4919.17857142856
PF_TOL_5M = 0.002


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


@pytest.fixture(scope="module")
def df5m():
    """The certified 5m-native VPC ledger (VS.vpc_trades_rich) over the real Databento history."""
    import vpc_apex_eval_sim as VS
    feats = VR.v.features(VS.real_rth_5m())
    feats = feats[feats.date >= VR.WINDOW_START]
    return VS.vpc_trades_rich(feats)


def test_5m_native_aggregate_signature(df5m):
    """SECOND convention canary: n=408, net=+4919.178571pt (6-dp exact) — the conservative
    5m-native ledger the signed DEC pins as the numeric basis. Complements the 1m-truth canary
    above so BOTH certified conventions are guarded permanently."""
    assert len(df5m) == FROZEN_N_5M
    net = float(df5m["pnl_pts"].sum())
    assert abs(net - FROZEN_NET_5M) < 1e-6, f"5m-native net={net} vs frozen {FROZEN_NET_5M}"


def test_5m_native_streaming_engine_reproduces_signature():
    """The STREAMING ProfileVEngine + VpcDayGate, walked over a bounded real-data window with the
    certified 5m-native exit, reproduces the certified taken-trade ledger EXACTLY on that window
    (n + net + per-trade entry ts). The FULL-history exact reproduction (n=408, net=4919.178571)
    was verified offline and is guarded by test_vpc_signal_parity's windowed exact-match; this
    canary keeps a fast in-suite proof that the streaming engine == batch backtest on real data."""
    import pandas as pd
    import vpc_apex_eval_sim as VS
    import vpc_paper_harness as PH
    feats = VR.v.features(VS.real_rth_5m())
    w0 = pd.Timestamp("2022-01-01", tz="America/New_York")
    w1 = pd.Timestamp("2022-04-01", tz="America/New_York")
    feats = feats[(feats.date >= w0) & (feats.date < w1)]
    led = PH.replay_5m_native(feats=feats)
    cert = VS.vpc_trades_rich(feats)
    assert len(led) == len(cert), f"window trade count {len(led)} vs certified {len(cert)}"
    assert abs(float(led.pnl_pts.sum()) - float(cert.pnl_pts.sum())) < 1e-6
    # per-trade entry timestamps identical (proves the streaming state machine picks the SAME entries)
    assert [pd.Timestamp(t).isoformat() for t in led.ts] == \
           [pd.Timestamp(t).isoformat() for t in cert.ts]


def _live_shaped_stop_series(bars_1m, atr_5m, idx1_ts, idx5_ts, ei, entry, direction,
                             init_stop_dist, trail_atr):
    """ARM B driver: reconstruct atr_now per 1m bar via an INDEPENDENT streaming j5 mapping (as the
    live lane must) and feed the LIVE VpcTrailManager one bar at a time. Returns (stop_path, exit).
    This is the live path; ARM B asserts it equals the sim walk_1m_trail for the same inputs."""
    from vpc_trail_manager import VpcTrailManager
    sender_log = []
    mgr = VpcTrailManager(account="ARMB", signal_ts="t", side=("long" if direction == 1 else "short"),
                          qty=1, entry=entry, init_stop_dist=init_stop_dist, trail_atr=trail_atr,
                          send_fn=lambda p: (sender_log.append(p) or {"sent": True}))
    n5 = len(idx5_ts)
    j5 = ei
    exit_level = None
    for x in range(len(bars_1m)):
        lo, hi, cl = bars_1m[x]
        while j5 + 1 < n5 and idx1_ts[x] >= idx5_ts[j5 + 1]:
            j5 += 1
        atr_prev = atr_5m[j5 - 1] if j5 - 1 >= 0 else np.nan
        atr_now = atr_prev if not np.isnan(atr_prev) else atr_5m[ei - 1]
        res, level = mgr.on_1m_bar(x, lo, hi, cl, atr_now)
        if res == "exit":
            exit_level = level
            break
    return mgr.trail.stop_path, exit_level


def test_live_shaped_parity_arm_B():
    """ARM B (was REQUIRED-BEFORE-ARM STUB, now BUILT): feed the LIVE VpcTrailManager the SAME
    inputs as the sim's walk_1m_trail but delivered one bar at a time with atr_now reconstructed by
    an independent streaming j5 mapping, and assert the resulting stop series + exit are identical.
    This proves live/sim parity of the trail MANAGER, not just that the refactor is
    behavior-preserving (ARM A). Three deterministic scenarios: a long that ratchets then stops, a
    short that ratchets then stops, and a runner that reaches EOD without stopping."""
    trail_atr = 2.0
    # 5m ATR series (constant here) + 5m timestamps at 5-min spacing; 1m bars at 1-min spacing.
    base5 = pd.Timestamp("2024-03-01 10:00:00", tz="America/New_York")
    idx5_ts = np.array([base5 + pd.Timedelta(minutes=5 * k) for k in range(40)])
    atr_5m = np.full(40, 1.0)
    ei = 2

    def one_min_index(nbars):
        start = idx5_ts[ei]
        return np.array([start + pd.Timedelta(minutes=k) for k in range(nbars)])

    scenarios = []
    # (1) long runner that ratchets up then stops out
    entry = 100.0
    long_bars = [(99.5, 101.0, 100.8), (100.0, 102.0, 101.9), (101.0, 103.0, 102.8),
                 (99.0, 102.5, 100.0), (95.0, 100.0, 96.0)]   # last bar takes out the trailed stop
    scenarios.append((long_bars, 1, entry, 5.0))
    # (2) short runner that ratchets down then stops out
    short_entry = 100.0
    short_bars = [(99.0, 100.5, 99.2), (97.0, 99.5, 97.5), (95.0, 97.0, 95.5),
                  (95.0, 101.0, 100.0)]                       # last bar takes out the trailed stop
    scenarios.append((short_bars, -1, short_entry, 5.0))
    # (3) long that never stops -> runs to end of feed (no exit)
    run_bars = [(99.6, 100.5, 100.3), (100.1, 101.0, 100.8), (100.5, 101.5, 101.3)]
    scenarios.append((run_bars, 1, 100.0, 5.0))

    for bars_1m, d, entry_px, init_stop_dist in scenarios:
        idx1_ts = one_min_index(len(bars_1m))
        H1 = np.array([b[1] for b in bars_1m]); L1 = np.array([b[0] for b in bars_1m])
        C1 = np.array([b[2] for b in bars_1m])
        # SIM path (canonical historical wrapper)
        sim_exit, sim_reason, sim_path = VT.walk_1m_trail(
            idx1_ts, H1, L1, C1, atr_5m, idx5_ts, ei, entry_px, d, init_stop_dist, trail_atr)
        # LIVE path (VpcTrailManager fed one bar at a time)
        live_path, live_exit = _live_shaped_stop_series(
            bars_1m, atr_5m, idx1_ts, idx5_ts, ei, entry_px, d, init_stop_dist, trail_atr)
        assert live_path == sim_path, f"ARM B stop-series mismatch (dir={d})"
        if sim_reason == "stop":
            assert live_exit == sim_exit, f"ARM B exit mismatch (dir={d})"
        else:
            assert live_exit is None, "ARM B: sim ran to EOD but live reported a stop exit"


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
        "SUPERSEDED by test_live_shaped_parity_arm_B (built in Phase 3): the live-shaped bar-close "
        "feed arm now drives VpcTrailManager one bar at a time and asserts stop-series parity with "
        "the sim walk. This stub remains only as the historical scaffold; the REAL-DATA extension "
        "(driving arm_B over the certified 408-trade 1m slices, not just synthetic scenarios) is a "
        "MUST-AUDIT follow-up recorded in the build report."
    )
