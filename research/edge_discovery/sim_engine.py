"""1m intrabar trade sim engine (adverse-first, causal, market/stop fills — no resting limit).

A trade = (day, side, entry_level, stop, target_mode). Entry triggers when a 1m bar in the
trigger window trades through entry_level (stop-order semantics). Exit walks 1m bars adverse-first:
if both stop and target lie inside a bar, the STOP is taken (conservative). RTH close forces exit.
Cost (points, round trip) subtracted from every closed trade.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

NY = "America/New_York"


def rth_1m_by_day(d1):
    t = d1.index
    rth = d1[((t.hour > 9) | ((t.hour == 9) & (t.minute >= 30))) & (t.hour < 16)].copy()
    rth["date"] = rth.index.normalize()
    return rth


def simulate(trades, rth, cost_pts, entry_delay=0):
    """trades: list of dict(date, side(+1/-1), entry_level, trig_start, trig_end(ts),
                            stop, target(price or None), exit_ts(force close), trail_atr(None or pts)).
    Returns DataFrame of executed trades with pnl in points (net of cost)."""
    out = []
    by_day = {d: g for d, g in rth.groupby("date")}
    for tr in trades:
        g = by_day.get(pd.Timestamp(tr["date"]))
        if g is None:
            continue
        side = tr["side"]
        lvl = tr["entry_level"]
        win = g[(g.index >= tr["trig_start"]) & (g.index <= tr["trig_end"])]
        # find entry bar: first bar trading through level
        ent_px = None; ent_ts = None
        wl = list(win.iterrows())
        for i, (ts, b) in enumerate(wl):
            trig = (side == 1 and b["high"] >= lvl) or (side == -1 and b["low"] <= lvl)
            if trig:
                if entry_delay > 0:
                    j = i + entry_delay
                    if j >= len(wl):
                        break
                    dts, db = wl[j]
                    ent_px = db["open"]; ent_ts = dts  # canary: enter delayed bar's open
                else:
                    ent_px = (max(lvl, b["open"]) if side == 1 else min(lvl, b["open"]))
                    ent_ts = ts
                break
        if ent_px is None:
            continue
        stop = tr["stop"]; tgt = tr.get("target"); trail = tr.get("trail_atr")
        exit_ts_force = tr["exit_ts"]
        post = g[(g.index >= ent_ts) & (g.index <= exit_ts_force)]
        exit_px = None; ext = None
        trail_stop = stop
        for ts, b in post.iterrows():
            if ts == ent_ts:
                # entry bar: only allow adverse (stop) to hit same bar, not target (conservative)
                if side == 1 and b["low"] <= trail_stop:
                    exit_px = trail_stop; ext = ts; break
                if side == -1 and b["high"] >= trail_stop:
                    exit_px = trail_stop; ext = ts; break
                # update trail on entry bar
                if trail is not None:
                    if side == 1:
                        trail_stop = max(trail_stop, b["high"] - trail)
                    else:
                        trail_stop = min(trail_stop, b["low"] + trail)
                continue
            # adverse first: stop
            if side == 1 and b["low"] <= trail_stop:
                exit_px = trail_stop; ext = ts; break
            if side == -1 and b["high"] >= trail_stop:
                exit_px = trail_stop; ext = ts; break
            # target
            if tgt is not None:
                if side == 1 and b["high"] >= tgt:
                    exit_px = tgt; ext = ts; break
                if side == -1 and b["low"] <= tgt:
                    exit_px = tgt; ext = ts; break
            # update trail
            if trail is not None:
                if side == 1:
                    trail_stop = max(trail_stop, b["high"] - trail)
                else:
                    trail_stop = min(trail_stop, b["low"] + trail)
        if exit_px is None:
            # force close at last bar of window
            last = post.iloc[-1]
            exit_px = last["close"]; ext = post.index[-1]
        pnl = side * (exit_px - ent_px) - cost_pts
        out.append(dict(date=tr["date"], side=side, ent_ts=ent_ts, ent_px=ent_px,
                        ext_ts=ext, exit_px=exit_px, pnl=pnl, tag=tr.get("tag", "")))
    return pd.DataFrame(out)


def stats(df):
    if df is None or len(df) == 0:
        return dict(n=0, pf=np.nan, wr=np.nan, tot=np.nan, avg=np.nan)
    w = df[df.pnl > 0]["pnl"].sum(); l = -df[df.pnl < 0]["pnl"].sum()
    pf = w / l if l > 0 else np.inf
    return dict(n=len(df), pf=round(pf, 3), wr=round((df.pnl > 0).mean(), 3),
                tot=round(df.pnl.sum(), 1), avg=round(df.pnl.mean(), 3))


def by_year(df):
    if df is None or len(df) == 0:
        return {}
    df = df.copy(); df["yr"] = pd.to_datetime(df["date"]).dt.year
    return {int(y): stats(g) for y, g in df.groupby("yr")}
