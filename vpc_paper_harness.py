"""
VPC paper harness — ADDITIVE, sim-only.

Two entry points:

  (1) replay_5m_native(window_start) -> ledger DataFrame
      Drives the STREAMING ProfileVEngine bar-by-bar over the real Databento history, admits its
      triggers through VpcDayGate, and walks the certified 5m-native exit (the exact simulate_day
      trail convention) with SimBot-style next-bar-open MARKET fills. Proves the streaming engine +
      gate reproduce `nq_vwap_pullback.backtest()`'s TAKEN-trade ledger (n=408, net 4919.178571pt)
      end-to-end — i.e. sim-parity of the signal/admission path, independent of the 1m-truth trail
      canary (which lives in test_vpc_trail_parity.py). Signals emitted at bar i are causal by
      construction (the engine reads only bars <= i).

  (2) PaperVpcLane
      A minimal end-to-end SimBot lane: feed 5m bars (signals) and 1m bars (trail) and it wires
      ProfileVEngine -> VpcDayGate -> bridge.build_vpc_entry -> VpcTrailManager (canonical 1m trail)
      with an in-memory SimBot sender (no broker). This is the paper-mode object the lane runs under
      EMISSION_MODE_PAPER; it never touches a live broker.

Nothing here is imported by a live path; it exists for the paper shadow + the parity tests.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))

import nq_vwap_pullback as v
import vpc_apex_eval_sim as VS
import strategy_engine_vpc as EV
import bridge_traderspost as BP
from vpc_trail_manager import VpcTrailManager

NY = "America/New_York"
WINDOW_START = pd.Timestamp("2022-01-01", tz=NY)


def _certified_exit_5m(g_arrays, ei, d, stopdist):
    """The EXACT simulate_day 5m-native exit walk (high/low-referenced peak, adverse-first,
    5.0xATR trail, EOD fallback). Returns (exit_px, exit_i, pnl_pts). Copied semantics from
    vpc_apex_eval_sim.vpc_trades_rich so the paper ledger equals the certified ledger."""
    O, H, L, C, A = g_arrays
    n = len(C)
    trail_atr = VS.CFG["trail_atr"]
    entry = O[ei]
    stop = entry - stopdist if d == 1 else entry + stopdist
    peak = entry
    exit_px = None
    exit_i = n - 1
    for j in range(ei, n):
        if d == 1:
            if L[j] <= stop:
                exit_px = stop; exit_i = j; break
            peak = max(peak, H[j]); ns = peak - trail_atr * A[j]
            stop = max(stop, ns) if not np.isnan(A[j]) else stop
        else:
            if H[j] >= stop:
                exit_px = stop; exit_i = j; break
            peak = min(peak, L[j]); ns = peak + trail_atr * A[j]
            stop = min(stop, ns) if not np.isnan(A[j]) else stop
    if exit_px is None:
        exit_px = C[n - 1]; exit_i = n - 1
    pnl = d * (exit_px - entry) - v.RT_COST
    return exit_px, exit_i, pnl


def replay_5m_native(window_start=WINDOW_START, feats=None):
    """Stream ONE ProfileVEngine + VpcDayGate over real history (a single engine so the buffer
    carries each day's prior tail -> continuous ATR matches the batch), and walk the certified
    5m-native exit. Returns a ledger DataFrame (ts, dir, entry, exit, pnl_pts, stop_pts) sorted by
    ts. The engine resets its armed state per RTH day internally; the gate is reset per day here."""
    if feats is None:
        feats = v.features(VS.real_rth_5m())
        feats = feats[feats.date >= window_start]
    feats = feats.sort_index()
    # per-day OHLC arrays + a map from tz-aware index -> (day, slot) for exit walking
    day_arrays = {}
    for day, g in feats.groupby("date"):
        g = g.sort_values("slot")
        day_arrays[day] = dict(idx=list(g.index), O=g.Open.values, H=g.High.values,
                               L=g.Low.values, C=g.Close.values, A=g.atr.values)
    eng = EV.ProfileVEngine(emission_mode=EV.EMISSION_MODE_PAPER)
    gate = EV.VpcDayGate()
    cur_day = None
    rows = []
    for ts, r in feats.iterrows():
        day = ts.normalize()
        if day != cur_day:
            cur_day = day
            gate.new_day()
        eng.add_bar(ts, r.Open, r.High, r.Low, r.Close, r.Volume)
        sig = eng.latest_signal()
        if sig is None:
            continue
        da = day_arrays[day]
        ei = int(sig["slot"]) + 1                # entry is the NEXT bar's open
        n = len(da["C"])
        if ei >= n:
            continue
        if not gate.admit(ei):
            continue
        d = sig["direction"]; stopdist = sig["stop_dist"]
        exit_px, exit_i, pnl = _certified_exit_5m((da["O"], da["H"], da["L"], da["C"], da["A"]),
                                                  ei, d, stopdist)
        gate.on_resolved(pnl, exit_i)
        # ts = the ENTRY (fill) bar's instant, matching vpc_trades_rich's `ts=idx[ei]` convention
        rows.append(dict(ts=pd.Timestamp(da["idx"][ei]), dir=d, entry=float(da["O"][ei]),
                         exit=float(exit_px), pnl_pts=float(pnl), stop_pts=float(stopdist)))
    df = pd.DataFrame(rows)
    if len(df):
        df = df.sort_values("ts").reset_index(drop=True)
    return df


class _SimBotSender:
    """In-memory sender: records every payload, always 'sent'. No broker, no network."""
    def __init__(self):
        self.sent = []

    def send(self, payload):
        self.sent.append(payload)
        return {"sent": True}


class PaperVpcLane:
    """End-to-end paper lane (EMISSION_MODE_PAPER). Feed 5m bars via on_5m_bar() and 1m bars via
    on_1m_bar(); it opens a SimBot market entry on a gated trigger and manages the canonical 1m
    trail via VpcTrailManager. Exposes .closed_trades for inspection. No live routing."""

    def __init__(self, account="PAPER", trail_atr=None):
        self.account = account
        self.eng = EV.ProfileVEngine(emission_mode=EV.EMISSION_MODE_PAPER)
        self.gate = EV.VpcDayGate()
        self.sender = _SimBotSender()
        self.trail_atr = trail_atr if trail_atr is not None else VS.CFG["trail_atr"]
        self.open_trade = None          # {"mgr":.., "side":.., "entry":.., "ts_signal":..}
        self.pending_entry = None       # a gated trigger awaiting the next 5m open
        self.closed_trades = []
        self._cur_day = None
        self._bar_id = 0

    def on_5m_bar(self, ts, o, h, l, c, vol=0):
        ts = pd.Timestamp(ts)
        day = ts.normalize()
        if day != self._cur_day:
            self._cur_day = day
            self.gate.new_day()
        # fill a pending market entry at THIS bar's open (next-bar-open discipline)
        if self.pending_entry is not None and self.open_trade is None:
            sig = self.pending_entry
            self.pending_entry = None
            payload, err = BP.build_vpc_entry(
                account=self.account, signal_ts=sig["ts_signal"], side=sig["side"],
                qty=1, ref_price=o, stop_price=(o - sig["stop_dist"]) if sig["direction"] == 1
                else (o + sig["stop_dist"]))
            if not err:
                self.sender.send(payload)
                mgr = VpcTrailManager(
                    account=self.account, signal_ts=sig["ts_signal"], side=sig["side"], qty=1,
                    entry=o, init_stop_dist=sig["stop_dist"], trail_atr=self.trail_atr,
                    send_fn=self.sender.send)
                self.open_trade = dict(mgr=mgr, side=sig["side"], entry=o, ts_signal=sig["ts_signal"])
        # generate the next trigger from this closed 5m bar
        self.eng.add_bar(ts, o, h, l, c, vol)
        sig = self.eng.latest_signal()
        if sig is not None and self.open_trade is None and self.pending_entry is None:
            # admission uses the day gate (max 2/day etc.); slot+1 is the entry slot proxy
            if self.gate.admit(sig["slot"] + 1):
                self.pending_entry = sig

    def on_1m_bar(self, ts, low, high, close, atr_now):
        if self.open_trade is None:
            return
        self._bar_id += 1
        res, level = self.open_trade["mgr"].on_1m_bar(self._bar_id, low, high, close, atr_now)
        if res == "exit":
            side = self.open_trade["side"]
            d = 1 if side == "long" else -1
            pnl = d * (level - self.open_trade["entry"]) - v.RT_COST
            self.gate.on_resolved(pnl, self._bar_id)
            self.closed_trades.append(dict(side=side, entry=self.open_trade["entry"],
                                           exit=level, pnl_pts=pnl))
            self.open_trade = None
