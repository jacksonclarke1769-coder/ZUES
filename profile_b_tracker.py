"""Profile B paper-P&L tracker. Mirrors the validated b_exits fill model so B trades
resolve and land on the dashboard calendar (like Profile A's PaperTracker does for A):
  * limit at the OR-break level fills on a retest within `fill_window` bars (else cancels)
  * after fill: stop-first, then target, then EOD/timeout close (max_hold bars)
  * records to trade_results as a MODELED paper fill (fill_backed=False -> hypothetical,
    per CONFIGLOCK: paper P&L is never realised until broker-confirmed).
Pure book-keeping — never places, modifies, or cancels a real order.
"""
import pandas as pd
import trade_results

RTH_START = 9 * 60 + 30
RTH_END = 16 * 60
B_COST_PTS = 0.75            # frozen Profile B cost (slippage + commission, points)


SNAP_KEY = "b_tracker_snapshot"


class ProfileBPaperTracker:
    def __init__(self, store, account, mode, dpp=2.0, fill_window=6, max_hold=24,
                 path=trade_results.PATH):
        self.store = store
        self.account = account
        self.mode = mode
        self.dpp = dpp
        self.fw = fill_window
        self.mh = max_hold
        self.path = path
        self.open = []          # pending/working B trades
        self.closed = 0
        self.recorded = []      # audit of recorded rows (this run)
        self.recorded_keys = set()   # idempotency: a B trade is booked at most once across restarts
        self._restore()         # survive a restart: reload open watches + closed count

    @staticmethod
    def _key(w):
        return f"{w['ts']}|{w['side']}|{w['sbar']}"

    # ---- restart safety (mirrors Profile A's PaperTracker) ----
    def snapshot(self):
        return dict(open=self.open, closed=self.closed, recorded_keys=sorted(self.recorded_keys))

    def persist(self):
        if self.store is not None:
            try:
                self.store.set_state(**{SNAP_KEY: self.snapshot()})
            except Exception:                            # noqa: BLE001 — tracking never breaks the loop
                pass

    def _restore(self):
        if self.store is None:
            return
        try:
            snap = self.store.get_state(SNAP_KEY)
            if snap:
                self.open = list(snap.get("open", []))
                self.closed = int(snap.get("closed", 0))
                self.recorded_keys = set(snap.get("recorded_keys", []))
        except Exception:                                # noqa: BLE001
            pass

    def on_signal(self, sig, qty, bar_i, ts):
        if int(qty) <= 0:
            return
        d = 1 if sig["side"] == "long" else -1
        self.open.append(dict(side=sig["side"], d=d, entry=float(sig["entry"]),
                              stop=float(sig["stop"]), target=float(sig["target"]),
                              qty=int(qty), sbar=int(bar_i), ts=str(ts), filled=None))
        self.persist()

    def on_bar(self, bar_i, ts, o, h, l, c):
        ts = pd.Timestamp(ts)
        mins = ts.hour * 60 + ts.minute
        rth = RTH_START <= mins < RTH_END
        keep = []
        for w in self.open:
            if w["filled"] is None:
                if bar_i <= w["sbar"]:               # signal bar / earlier — wait for next
                    keep.append(w); continue
                if l <= w["entry"] <= h:             # limit retest -> filled
                    w["filled"] = bar_i; keep.append(w); continue
                if bar_i > w["sbar"] + self.fw:      # window expired -> cancel (no trade)
                    continue
                keep.append(w); continue
            # ---- filled: resolve the exit (stop-first, conservative) ----
            d = w["d"]; ex = reason = None
            if (l <= w["stop"]) if d > 0 else (h >= w["stop"]):
                ex, reason = w["stop"], "stop"
            elif (h >= w["target"]) if d > 0 else (l <= w["target"]):
                ex, reason = w["target"], "target"
            elif (not rth and bar_i > w["filled"]) or bar_i >= w["filled"] + self.mh:
                ex, reason = c, ("eod" if not rth else "timeout")
            if ex is None:
                keep.append(w); continue
            self._record(w, ex, reason)
            self.closed += 1
        self.open = keep
        self.persist()

    def _record(self, w, ex, reason):
        key = self._key(w)
        if key in self.recorded_keys:                    # already booked (restart) -> never double-record
            return None
        self.recorded_keys.add(key)
        risk = abs(w["entry"] - w["stop"]) or 1e-9
        gross_pts = (ex - w["entry"]) * w["d"]
        net_pts = gross_pts - B_COST_PTS
        pnl = net_pts * self.dpp * w["qty"]
        rr = gross_pts / risk
        row = trade_results.record(
            date=str(pd.Timestamp(w["ts"]).date()), mode=self.mode, account=self.account,
            strategy="B", direction=w["side"], contracts=w["qty"], pnl=pnl,
            note=f"paper · Profile B ORB · {reason} · {rr:+.2f}R modeled",
            fill_backed=False, path=self.path)
        self.recorded.append(row)
        return row
