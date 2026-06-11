"""
Profile A LIVE engine. Reuses the EXACT validated backtest code (ict-nq-framework)
on a rolling 5m bar buffer, so live signals == backtested signals (zero drift).

Flow: the bot feeds each CLOSED 5m bar via add_bar(); latest_signal() rebuilds the
causal feature frame on the buffer, runs the frozen Profile A model, and returns a
signal ONLY if a fresh entry fills at the most recent bar. The bot sizes (eval vs
funded), places the Tradovate OSO bracket, and persists the trade to the store.
"""
import os, sys
import pandas as pd, numpy as np
FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
sys.path.insert(0, os.path.join(FW, "engine")); sys.path.insert(0, os.path.join(FW, "models"))
import data as D, htf, trade_log as TL          # noqa
import model01_sweep_mss_fvg as M1              # the frozen Profile A model

NY = "America/New_York"
BUFFER_DAYS = 35   # enough history for weekly/daily/4H/1H context + sessions

PROFILE_A = dict(entry_type="ote", sessions={"asia", "london", "ny_am", "ny_lunch", "ny_pm"},
                 target_mode="fixed_rr", rr=2.0,
                 partial=[(1, 0.5)])   # Exit #3 (frozen v2): bank 50% at +1R, hold 50% to +2R


class ProfileAEngine:
    def __init__(self, strat_cfg):
        self.c = strat_cfg
        self.buf = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        self.buf.index = pd.DatetimeIndex([], tz=NY)
        self.acted_ts = set()        # fill timestamps already turned into orders

    def add_bar(self, ts, o, h, l, c, v=0):
        """ts: tz-aware ET (or UTC) timestamp of the CLOSED 5m bar."""
        ts = pd.Timestamp(ts);  ts = ts.tz_convert(NY) if ts.tzinfo else ts.tz_localize("UTC").tz_convert(NY)
        self.buf.loc[ts] = [o, h, l, c, v]
        self.buf = self.buf[~self.buf.index.duplicated(keep="last")].sort_index()
        cutoff = self.buf.index.max() - pd.Timedelta(days=BUFFER_DAYS)
        self.buf = self.buf[self.buf.index >= cutoff]

    def _features(self):
        base = self.buf.copy()
        df = D.tag_sessions(base)
        df = htf.add_daily_weekly(df)
        df = htf.add_session_levels(df)
        df = htf.add_htf_swings(df, base, "1h", "h1", 2, 2)
        df = htf.add_htf_swings(df, base, "4h", "h4", 2, 2)
        df.index.name = "timestamp"
        return df

    def latest_signal(self):
        """Return a fresh entry signal dict if Profile A just filled on the last bar."""
        if len(self.buf) < 2000:                 # need warmup (~1 week of 5m bars min)
            return None
        try:
            feats = self._features()
            tr = M1.run(feats, "NQ", PROFILE_A, realtime=True)   # pending-setup reservation -> no phantom signals
        except Exception:
            return None
        if not len(tr):
            return None
        tr["fill_ts"] = pd.to_datetime(tr["date"].astype(str) + " " + tr["time"])
        recent = self.buf.index.max()
        # a fresh fill = a trade whose fill timestamp is the most recent 1-2 bars, NY-AM, unacted
        for _, t in tr.tail(3).iterrows():
            key = f"{t['date']} {t['time']}"
            if t["session"] != "ny_am" or key in self.acted_ts:
                continue
            ftime = pd.Timestamp(f"{t['date']} {t['time']}", tz=NY)
            if (recent - ftime) <= pd.Timedelta(minutes=10):    # filled now (this bar or last)
                self.acted_ts.add(key)
                d = 1 if t["direction"] == "long" else -1
                return dict(side=t["direction"], entry=float(t["entry"]), stop=float(t["stop"]),
                            target=float(t["target"]), rr=float(t["rr"]), liq=t["liq_swept"],
                            ts_signal=key)
        return None

    def in_entry_window(self, ts):
        e = pd.Timestamp(ts).tz_convert(NY) if pd.Timestamp(ts).tzinfo else pd.Timestamp(ts)
        m = e.hour * 60 + e.minute
        return self.c["nyam_start_min"] <= m < self.c["nyam_end_min"]

    def flat_time(self, ts):
        e = pd.Timestamp(ts).tz_convert(NY) if pd.Timestamp(ts).tzinfo else pd.Timestamp(ts)
        return (e.hour * 60 + e.minute) >= self.c["flat_min"]
