"""
Profile MOMENTUM live executor + paper tracker.

Momentum is a POSITION strategy (unlike A/B brackets): the engine emits a target position each bar; the
executor turns a CHANGE into orders through the SAME bot -> TradersPost -> Tradovate bridge as A/B:
  enter   -> market entry (wide catastrophic stop, no target)
  flip    -> market exit (close) + market entry the other way
  flatten -> market exit   (signal went to 0, or no-late gate, or EOD)
Entries are GATED (kill / data-gate / daily-stop) and OVERLAP-SIZED (half when another strategy holds a
same-direction position). EXITS are ALWAYS allowed. The paper tracker models the episode P&L for the
dashboard/journal (mirrors the backtest exec_daily: pos*(exit-entry) - 0.75pt round-turn).

NOT auto-on: wired behind a flag, default OFF. Live also needs its own approval flag + (recommended) its
OWN account/lane so the 14:30 A-guardian flat doesn't cut momentum (which runs to ~15:00). RESEARCH-GRADE.
"""
from __future__ import annotations

import pandas as pd
import bridge_traderspost as BP
import trade_results

MNQ = 2.0
M_COST_PTS = 0.75          # frozen round-turn cost (matches the backtest 2*HC)


class MomentumPaperTracker:
    """Models momentum episode P&L (modeled, fill_backed=False) -> trade_results + journal + Telegram."""
    def __init__(self, account, mode, dpp=MNQ, stop_pts=120.0, path=trade_results.PATH, notify=None, journal=None):
        self.account = account; self.mode = mode; self.dpp = dpp; self.stop_pts = stop_pts
        self.path = path; self.notify = notify; self.journal = journal
        self.open = None          # dict(side,d,entry,qty,ts) or None
        self.closed = 0; self.recorded = []

    def on_entry(self, side, qty, entry_px, ts):
        self.open = dict(side=side, d=1 if side == "long" else -1, entry=float(entry_px), qty=int(qty), ts=str(ts))

    def on_exit(self, exit_px, ts, reason):
        w = self.open
        if not w:
            return None
        self.open = None
        gross = (float(exit_px) - w["entry"]) * w["d"]
        net = gross - M_COST_PTS
        pnl = net * self.dpp * w["qty"]
        rr = gross / self.stop_pts
        row = trade_results.record(date=str(pd.Timestamp(w["ts"]).date()), mode=self.mode, account=self.account,
                                   strategy="M", direction=w["side"], contracts=w["qty"], pnl=pnl,
                                   note=f"paper · Profile M momentum · {reason} · {net:+.1f}pt modeled",
                                   fill_backed=False, path=self.path)
        self.recorded.append(row); self.closed += 1
        if self.notify is not None:
            self.notify.outcome("M", w["side"], rr, pnl, reason, self.mode)
        if self.journal is not None:
            self.journal.on_resolved("M", w["side"], w["qty"], w["entry"], w["entry"] - w["d"] * self.stop_pts,
                                     None, float(exit_px), reason, rr, pnl, w["ts"])
        return row


class MomentumExecutor:
    """Routes ProfileMomentumEngine signals to orders. Owns the live momentum position state."""
    def __init__(self, account, sender, root="MNQ", base_qty=2, stop_pts=120.0, mode="paper",
                 overlap_gate=None, notify=None, tracker=None, basis_offset=0.0,
                 entry_gate=None, killed=None):
        self.account = account; self.sender = sender; self.root = root
        self.base_qty = int(base_qty); self.stop_pts = float(stop_pts); self.mode = mode
        self.gate = overlap_gate; self.notify = notify; self.tracker = tracker
        self.basis = float(basis_offset); self.entry_gate = entry_gate; self.killed = killed
        self.position = 0          # current live momentum direction (+1/0/-1)
        self.qty = 0
        self.sent = self.blocked = 0

    def _send_exit(self, ts, reason, exit_ref):
        payload, err = BP.build_exit(account=self.account, strategy="M", signal_ts=str(ts), root=self.root,
                                     reason=reason, mode_meta=dict(mode="ARES", profile="M"))
        if err:
            print(f"[momentum] exit build failed: {err}", flush=True); return
        self.sender.send(payload)
        if self.gate is not None:
            self.gate.on_close("M")
        if self.tracker is not None and exit_ref is not None:
            self.tracker.on_exit(exit_ref, ts, reason)
        self.position = 0; self.qty = 0

    def _send_entry(self, side, d, ts, ref):
        kill = self.killed() if self.killed else None
        if kill:
            self.blocked += 1; return False
        if self.entry_gate is not None:
            ready, _why = self.entry_gate()
            if not ready:
                self.blocked += 1; return False
        qty = self.base_qty
        if self.gate is not None:
            qty, _halved = self.gate.size("M", d, self.base_qty)
        if qty <= 0:
            self.blocked += 1; return False
        payload, err = BP.build_momentum_entry(account=self.account, signal_ts=str(ts), side=side, qty=qty,
                                               ref_price=ref, stop_pts=self.stop_pts, root=self.root,
                                               mode_meta=dict(mode="ARES", profile="M"))
        if err:
            print(f"[momentum] entry build failed: {err}", flush=True); return False
        self.sender.send(payload)
        if self.gate is not None:
            self.gate.on_open("M", d)
        self.position = d; self.qty = qty; self.sent += 1
        if self.notify is not None:
            self.notify.signal("M", side, qty, ref, ref - d * self.stop_pts, 0, self.mode)
        if self.tracker is not None:
            self.tracker.on_entry(side, qty, ref, ts)
        return True

    def on_signal(self, sig, ts):
        """sig = ProfileMomentumEngine.latest_signal() dict (or None). Acts on enter/flip/flatten."""
        if not sig:
            return
        action = sig.get("action")
        ref = float(sig["close"]) + self.basis
        if action == "hold":
            return
        if action == "flatten":
            self._send_exit(ts, "signal_flat", ref); return
        if action == "flip":
            self._send_exit(ts, "flip", ref)               # close current; fall through to enter new
        if sig.get("position", 0) != 0:                    # enter (fresh or post-flip)
            self._send_entry(sig["side"], int(sig["position"]), ts, ref)

    def eod_flat(self, ts, ref=None):
        """Hard safety flat at momentum EOD (independent of the A 14:30 guardian)."""
        if self.position != 0:
            self._send_exit(ts, "eod", ref)
