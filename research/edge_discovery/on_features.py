"""Overnight(Globex)->RTH edge discovery. Shared data + feature builder.

REAL Databento NQ 1m only. Overnight session = prior 18:00 ET -> 09:30 ET.
All overnight stats are CAUSAL (use only bars strictly before the 09:30 RTH open).
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

DBNT = "/Users/jacksonclarke/trading-team/data/real_futures/NQ_databento_1m_5y.parquet"
NY = "America/New_York"
PT = 20.0  # $/pt NQ (we work in points; $ only for reference)


def load_1m():
    d1 = pd.read_parquet(DBNT)
    idx = d1.index
    d1.index = idx.tz_convert(NY) if idx.tz else idx.tz_localize("UTC").tz_convert(NY)
    d1 = d1.sort_index()
    d1 = d1[~d1.index.duplicated(keep="first")]
    return d1[["open", "high", "low", "close", "volume"]]


def resample(d1, rule):
    ag = lambda c, h: getattr(d1[c].resample(rule, label="left", closed="left"), h)()
    df = pd.DataFrame({"open": ag("open", "first"), "high": ag("high", "max"),
                       "low": ag("low", "min"), "close": ag("close", "last"),
                       "volume": ag("volume", "sum")}).dropna(subset=["open"])
    return df


def build_daily_features(d1):
    """One row per RTH trading day with overnight (Globex) features known AT 09:30 open.

    ON window: prior calendar day's 18:00 ET (Globex open) -> current day 09:29 ET (last bar before open).
    Prior RTH close: last trade at/<=16:00 ET prior RTH day.
    """
    t = d1.index
    # RTH mask 09:30-15:59
    rth = d1[((t.hour > 9) | ((t.hour == 9) & (t.minute >= 30))) & (t.hour < 16)].copy()
    rth["date"] = rth.index.normalize()
    days = sorted(rth["date"].unique())

    # Precompute prior-RTH-close per day: RTH close = last RTH bar's close on prior RTH day
    rth_close_by_day = rth.groupby("date")["close"].last()

    rows = []
    for i, day in enumerate(days):
        day = pd.Timestamp(day)
        open_ts = day + pd.Timedelta(hours=9, minutes=30)
        # overnight window: 18:00 prior calendar eve -> open_ts (exclusive)
        on_start = day - pd.Timedelta(days=1) + pd.Timedelta(hours=18)
        on = d1.loc[(d1.index >= on_start) & (d1.index < open_ts)]
        if len(on) < 30:
            continue
        # RTH open bar
        if open_ts not in d1.index:
            continue
        rth_open = d1.loc[open_ts, "open"]
        on_high = on["high"].max()
        on_low = on["low"].min()
        on_rng = on_high - on_low
        on_close = on["close"].iloc[-1]  # last globex print before open
        on_vol = on["volume"].sum()
        # prior RTH close
        prior_days = [dd for dd in days if pd.Timestamp(dd) < day]
        if not prior_days:
            continue
        pd_rth_close = rth_close_by_day.loc[prior_days[-1]]
        gap = rth_open - pd_rth_close
        # position of open within ON range: 0=at low,1=at high
        pos = (rth_open - on_low) / on_rng if on_rng > 0 else 0.5
        rows.append(dict(date=day, open_ts=open_ts, rth_open=rth_open,
                         on_high=on_high, on_low=on_low, on_rng=on_rng,
                         on_close=on_close, on_vol=on_vol,
                         prior_rth_close=pd_rth_close, gap=gap, open_pos=pos))
    f = pd.DataFrame(rows).set_index("date")
    # normalize ON range by trailing 20-day median (regime-relative, causal)
    f["on_rng_med20"] = f["on_rng"].rolling(20, min_periods=10).median().shift(1)
    f["on_rng_ratio"] = f["on_rng"] / f["on_rng_med20"]
    f["gap_abs"] = f["gap"].abs()
    return f


def yr(ts):
    return pd.Timestamp(ts).year


if __name__ == "__main__":
    d1 = load_1m()
    print("1m rows", len(d1), d1.index.min(), d1.index.max())
    f = build_daily_features(d1)
    print("daily feature rows", len(f))
    print(f[["on_rng", "on_rng_ratio", "gap", "open_pos"]].describe().round(2).to_string())
    # save
    f.to_parquet("research/edge_discovery/_daily_features.parquet")
    print("saved _daily_features.parquet")
