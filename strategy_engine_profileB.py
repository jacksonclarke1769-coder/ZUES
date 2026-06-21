"""Profile B — streaming Opening-Range Breakout engine (the frozen logic from
replay_ab_12mo.b_entries/b_exits, made live/streaming). One trade per RTH day:
  * opening range = first 15 min of RTH (09:30-09:45 ET)
  * a 5m CLOSE beyond OR-high (long) / OR-low (short) arms the entry at that level
  * stop = level -/+ 1.0*ATR(14) ; target = level +/- 1.5*ATR(14)
Profile B NEVER consults D1c (drift_gate scope is A only). Single bracket (not Exit #3).

add_bar(ts,o,h,l,c) every completed 5m bar (ET); latest_signal() returns the pending
B signal once per break, or None. Pure (no I/O, no orders)."""
import pandas as pd

RTH_START = 9 * 60 + 30     # 09:30 ET
RTH_END = 16 * 60           # 16:00 ET
OR_MINUTES = 15


class ProfileBEngine:
    def __init__(self, atr_period=14, stop_mult=1.0, target_mult=1.5):
        self.atr_period = atr_period
        self.sm = stop_mult
        self.tm = target_mult
        self._bars = []                 # (high, low, close) for ATR
        self.cur_day = None
        self.or_high = self.or_low = self.or_end = None
        self.or_set = False
        self.atr_or = None
        self.broke = False
        self._signal = None
        self.signals = []               # audit trail of emitted B signals

    def _atr(self):
        n = self.atr_period
        if len(self._bars) < n + 1:
            return None
        trs = []
        for i in range(len(self._bars) - n, len(self._bars)):
            h, l, _c = self._bars[i]
            pc = self._bars[i - 1][2]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        return sum(trs) / n

    def _reset_day(self, day):
        self.cur_day = day
        self.or_high = self.or_low = self.or_end = None
        self.or_set = False
        self.atr_or = None
        self.broke = False

    def add_bar(self, ts, o, h, l, c):
        ts = pd.Timestamp(ts)
        self._bars.append((h, l, c))
        mins = ts.hour * 60 + ts.minute
        day = ts.normalize()
        if day != self.cur_day:
            self._reset_day(day)
        if not (RTH_START <= mins < RTH_END):
            return                                       # only build/trade inside RTH
        if self.or_end is None:                          # first RTH bar -> start the OR window
            self.or_end = ts + pd.Timedelta(minutes=OR_MINUTES)
        if ts < self.or_end:                             # inside the opening range
            self.or_high = h if self.or_high is None else max(self.or_high, h)
            self.or_low = l if self.or_low is None else min(self.or_low, l)
            return
        # ---- post opening-range ----
        if not self.or_set:
            self.or_set = True
            self.atr_or = self._atr()                    # ATR frozen at OR completion
        if self.broke or self.atr_or in (None, 0) or self.or_high is None:
            return
        for d, lvl in ((1, self.or_high), (-1, self.or_low)):
            if (c > lvl) if d > 0 else (c < lvl):
                self.broke = True                        # one break per day
                stop = lvl - d * self.sm * self.atr_or
                tgt = lvl + d * self.tm * self.atr_or
                self._signal = dict(side="long" if d > 0 else "short",
                                    entry=float(lvl), stop=float(stop), target=float(tgt),
                                    ts_signal=str(ts), liq="orb", profile="B")
                self.signals.append(dict(self._signal))
                break

    def latest_signal(self):
        s = self._signal
        self._signal = None
        return s
