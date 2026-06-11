"""
Live phased strategy engine — mirrors NQ_LiqSession_Phased.pine / nq_liq_forensics.py.
Stateless w.r.t. orders: given a rolling buffer of CLOSED 5m bars (ET-indexed) plus the
daily vol-gate, it returns a signal dict at each new closed bar, or None.

Phase is decided by the caller (eval vs funded) based on realized account progress.
No lookahead: only uses closed bars; the caller fills at the NEXT bar's open.
"""
import pandas as pd, numpy as np

def daily_vol_gate(bars_5m):
    """prior-day ATR14 >= 20d SMA of it (lagged). bars_5m: DataFrame[o,h,l,c] ET index."""
    d = bars_5m.copy()
    d["date"] = d.index.normalize()
    g = d.groupby("date").agg(H=("h","max"), L=("l","min"), C=("c","last"))
    tr = pd.concat([g.H-g.L, (g.H-g.C.shift()).abs(), (g.L-g.C.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    ok = (atr >= atr.rolling(20).mean()).shift(1)
    return ok.to_dict(), (atr.iloc[-1] if len(atr) else np.nan), (atr.rolling(20).mean().iloc[-1] if len(atr) else np.nan)


class PhasedStrategy:
    def __init__(self, cfg):
        self.c = cfg                      # STRAT dict from config
        self.reset_day()

    def reset_day(self):
        self.asia_hi = None
        self.asia_lo = None
        self.traded_today = False
        self.cur_day = None

    def _etmin(self, ts):
        return ts.hour*60 + ts.minute

    def update_asia(self, ts, h, l):
        e = self._etmin(ts)
        in_asia = (e >= self.c["asia_start_min"]) or (e < self.c["asia_end_min"])
        if in_asia:
            self.asia_hi = h if self.asia_hi is None else max(self.asia_hi, h)
            self.asia_lo = l if self.asia_lo is None else min(self.asia_lo, l)

    def on_closed_bar(self, bars, phase, vol_gate_on):
        """
        bars: DataFrame[o,h,l,c] ET-indexed, last row = the just-closed bar.
        phase: 'EVAL' or 'FUNDED'. vol_gate_on: bool (today's gate).
        Returns signal dict or None. Caller enters at NEXT bar open.
        """
        ts = bars.index[-1]
        o, h, l, cl = (bars.o.iloc[-1], bars.h.iloc[-1], bars.l.iloc[-1], bars.c.iloc[-1])
        # new ET calendar day -> reset intraday state (Asia is rebuilt 18:00->02:00)
        day = ts.normalize()
        if self.cur_day is None: self.cur_day = day
        if day != self.cur_day and self._etmin(ts) >= self.c["asia_start_min"]:
            # 18:00 marks the start of a new trade-day block
            pass
        # rebuild Asia from the buffer each call is expensive; we incrementally track instead.
        self._maybe_new_session(ts)
        self.update_asia(ts, h, l)

        e = self._etmin(ts)
        # EVAL uses the FULL killzone + multi/day (max shots at a runner); FUNDED is one/day
        if phase == "EVAL":
            ent_end = self.c.get("eval_ent_end_kz", self.c["eval_ent_end"])
            one_per_day = self.c.get("eval_one_per_day", True)
        else:
            ent_end = self.c["fund_ent_end"]; one_per_day = True
        in_win = (self.c["ent_start_min"] <= e < ent_end)
        if self.c["use_vgate"] and not vol_gate_on:
            return None
        if not in_win or (one_per_day and self.traded_today) or self.asia_hi is None or self.asia_lo is None:
            return None

        # continuation long break of Asian high + displacement (FVG) on closed bar
        if not (cl > self.asia_hi + self.c["min_sweep"]):
            return None
        if self.c["need_fvg"]:
            h2 = bars.h.iloc[-3] if len(bars) >= 3 else np.inf
            if not (l > h2):           # bullish FVG: this low above the high 2 bars back
                return None

        # build the order spec for next-bar-open entry
        if phase == "EVAL":
            stop_pts = self.c["eval_stop_pts"]
            qty = self.c["eval_qty"]
            spec = dict(kind="EVAL", stop_mode="fixed", stop_pts=stop_pts, target=None,
                        qty=qty, ride_eod=True)
        else:
            stop_px = min(l, self.asia_lo) - self.c["fund_stop_pad"]
            qty = self.c["fund_qty"]
            spec = dict(kind="FUNDED", stop_mode="structure", stop_px=stop_px,
                        rr=self.c["fund_rr"], qty=qty, ride_eod=False)
        self.traded_today = True
        return dict(side="long", ts_signal=str(ts), asia_hi=self.asia_hi, asia_lo=self.asia_lo,
                    signal_close=cl, **spec)

    def _maybe_new_session(self, ts):
        # a session block starts at 18:00 ET; reset Asia accumulation & per-day flag then
        e = self._etmin(ts)
        block = ts.normalize() + (pd.Timedelta(days=1) if e >= self.c["asia_start_min"] else pd.Timedelta(0))
        if getattr(self, "_block", None) != block:
            self._block = block
            self.asia_hi = None
            self.asia_lo = None
            self.traded_today = False

    def end_of_day_flat(self, ts):
        return self._etmin(ts) >= self.c["flat_min"]


def compute_levels(spec, fill_px):
    """Given a signal spec and the actual fill price, return (stop_px, target_px)."""
    if spec["stop_mode"] == "fixed":
        stop = fill_px - spec["stop_pts"]
        target = None if spec.get("ride_eod") else fill_px + spec.get("rr",3)*spec["stop_pts"]
    else:
        stop = spec["stop_px"]
        risk = fill_px - stop
        target = fill_px + spec["rr"]*risk if risk > 0 else None
    return stop, target
