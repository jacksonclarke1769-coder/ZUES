"""
Profile MOMENTUM (Zarattini noise-band) LIVE engine — streaming, live/backtest parity.

The validated refined edge (PF 1.62, Sharpe 1.63 on real futures): per time-of-day slot, a noise band
UB/LB = open*(1 +/- k*sigma_i) where sigma_i = trailing 14-day mean of |return-from-open| at that slot
(prior days only). Go LONG on a close above UB, SHORT below LB, GATED by a 50-day prior-day trend filter
(no shorts in an uptrend / no longs in a downtrend), CONFIRMED by 3 consecutive same-direction bars, with
NO entries in the first 15min (slot<3) or after ~15:00 ET (slot>65). Flat at EOD. NO fixed stop/target —
it is a POSITION that flips on signal change and flattens at the close.

This engine recomputes those SAME causal features on a rolling buffer and returns the latest bar's TARGET
position (+1 long / -1 short / 0 flat). Parity is proven in tests against the backtest functions. The
executor (separate) translates a position CHANGE into a market entry/flip/flatten and goes flat at EOD;
Momentum routes through the same bot -> TradersPost -> Tradovate bridge as A and B.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RTH_START = 9 * 60 + 30          # 09:30 ET
RTH_END = 16 * 60               # 16:00 ET


class ProfileMomentumEngine:
    def __init__(self, nd=14, k=1.0, trend_len=50, confirm_bars=3,
                 skip_slots=3, last_entry_slot=65, buffer_days=90):
        self.nd = nd                       # sigma lookback (days)
        self.k = k                         # band width multiple
        self.trend_len = trend_len         # daily-trend SMA length
        self.cb = confirm_bars             # consecutive same-dir bars required
        self.skip = skip_slots             # no entries in first `skip` slots (15min)
        self.last_slot = last_entry_slot   # no new entries after this slot (~15:00 ET)
        self.buffer_days = buffer_days
        self.buf = pd.DataFrame(columns=["date", "slot", "Open", "High", "Low", "Close", "Volume"])
        self.position = 0                  # last emitted target position (+1/0/-1)

    # ---- feed one CLOSED 5m bar (RTH only; non-RTH bars are ignored) ----
    def add_bar(self, ts, o, h, l, c, v=0.0):
        t = pd.Timestamp(ts)
        et = t.tz_convert("America/New_York") if t.tzinfo else t
        m = et.hour * 60 + et.minute
        if not (RTH_START <= m < RTH_END):
            return
        slot = (m - RTH_START) // 5
        day = pd.Timestamp(et.date())
        self.buf.loc[len(self.buf)] = [day, int(slot), float(o), float(h), float(l), float(c), float(v or 0.0)]
        # trim to the last `buffer_days` distinct days
        days = self.buf["date"].drop_duplicates()
        if len(days) > self.buffer_days:
            cutoff = days.iloc[-self.buffer_days]
            self.buf = self.buf[self.buf["date"] >= cutoff].reset_index(drop=True)

    # ---- the frozen feature/signal math (vectorised; parity-tested vs the backtest) ----
    @staticmethod
    def compute(df, nd=14, k=1.0, trend_len=50, confirm_bars=3, skip_slots=3, last_entry_slot=65):
        df = df.copy()
        op = df.groupby("date")["Open"].transform("first")
        df["rfo"] = df["Close"] / op - 1.0
        # sigma_i: per-slot trailing nd-day mean of |rfo|, prior days only (shift 1)
        piv = df.pivot_table(index="date", columns="slot", values="rfo", aggfunc="last").abs()
        sg = piv.rolling(nd, min_periods=nd // 2).mean().shift(1).stack().rename("sigma")
        df = df.merge(sg, left_on=["date", "slot"], right_index=True, how="left")
        ub = op * (1 + k * df["sigma"]); lb = op * (1 - k * df["sigma"])
        sig = np.where(df["Close"] > ub, 1.0, np.where(df["Close"] < lb, -1.0, 0.0))
        sig[df["sigma"].isna().values] = 0.0
        # 50d prior-day trend filter (no shorts in uptrend / no longs in downtrend; NaN warmup -> allow)
        dclose = df.groupby("date")["Close"].last()
        sma = dclose.rolling(trend_len).mean()
        up = (dclose.shift(1) > sma.shift(1))
        up_b = df["date"].map(up).values
        sig[(up_b == True) & (sig < 0)] = 0.0
        sig[(up_b == False) & (sig > 0)] = 0.0
        # 3-bar confirmation (same direction, same day)
        g = df.groupby("date").ngroup().values
        conf = np.zeros(len(sig))
        for i in range(len(sig)):
            if sig[i] != 0 and i >= confirm_bars - 1 and all(
                    g[i - j] == g[i] and sig[i - j] == sig[i] for j in range(confirm_bars)):
                conf[i] = sig[i]
        # time gates: no entries in first `skip` slots or after `last_entry_slot`
        slot = df["slot"].values
        final = np.where((slot >= skip_slots) & (slot <= last_entry_slot), conf, 0.0)
        return final

    def _ready(self):
        return self.buf["date"].nunique() >= self.trend_len + 2

    def latest_signal(self):
        """Target position for the most recent bar + the implied executor action. None until warmed up."""
        if len(self.buf) < 30 or not self._ready():
            return None
        try:
            final = self.compute(self.buf, self.nd, self.k, self.trend_len, self.cb, self.skip, self.last_slot)
        except Exception as e:                              # noqa: BLE001 — never break the loop
            print(f"[momentum] compute failed: {type(e).__name__}: {e}", flush=True)
            return None
        pos = int(final[-1]); prev = self.position
        self.position = pos
        if pos == prev:
            action = "hold"
        elif prev == 0:
            action = "enter"
        elif pos == 0:
            action = "flatten"
        else:
            action = "flip"
        last = self.buf.iloc[-1]
        return dict(position=pos, prev=prev, changed=(pos != prev), action=action,
                    side=("long" if pos > 0 else "short" if pos < 0 else "flat"),
                    slot=int(last["slot"]), close=float(last["Close"]), date=str(last["date"])[:10])

    # ---- restart safety ----
    def snapshot(self):
        return dict(position=self.position, buf=self.buf.to_dict("list"))

    def restore(self, state):
        if not state:
            return
        try:
            self.position = int(state.get("position", 0))
            b = state.get("buf")
            if b:
                self.buf = pd.DataFrame(b)
        except Exception as e:                              # noqa: BLE001
            print(f"[momentum] restore ignored ({e})", flush=True)
