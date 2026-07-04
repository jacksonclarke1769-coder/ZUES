"""
RECERT edge #2 — NQ VWAP-Pullback Continuation (VPC).
Prior 'validated' numbers (PF 1.28-1.52) were on Dukascopy CFD 5m @ 0.75pt cost.
This re-runs the EXACT locked VPC config on REAL Databento NQ 1m->5m RTH, with the
honest hostile cost ladder (0.75 / 1.0 / 2.0 / 3.0 pt RT), IS/OOS split, per-year,
and a look-ahead poison canary. Same conventions as the certified machine.
"""
import os, sys
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))  # locate nq_vwap_pullback from anywhere
import numpy as np, pandas as pd
import nq_vwap_pullback as v   # provides features(), backtest(), RT_COST global

NY = "America/New_York"
DBNT = os.path.expanduser("~/trading-team/data/real_futures/NQ_databento_1m_5y.parquet")
CFG = dict(atr_stop=2.5, trail_atr=5.0, slot_min=6, slot_max=66, max_trades=2,
           slope_mult=0.3, trend_mult=0.5, daily_stop=120)


def real_rth_5m():
    """Real Databento 1m -> 5m, RTH 09:30-16:00 ET, z.load()-compatible (date+slot)."""
    d1 = pd.read_parquet(DBNT)
    d1.index = (d1.index.tz_convert(NY) if d1.index.tz else d1.index.tz_localize("UTC").tz_convert(NY))
    d1 = d1.sort_index(); d1 = d1[~d1.index.duplicated(keep="first")]
    g = lambda c, how: getattr(d1[c].resample("5min", label="left", closed="left"), how)()
    df = pd.DataFrame({"Open": g("open", "first"), "High": g("high", "max"),
                       "Low": g("low", "min"), "Close": g("close", "last"),
                       "Volume": g("volume", "sum")}).dropna(subset=["Open"])
    # RTH cash session only: 09:30 <= t < 16:00 ET
    t = df.index
    df = df[((t.hour > 9) | ((t.hour == 9) & (t.minute >= 30))) & (t.hour < 16)]
    df["date"] = df.index.normalize()
    df["slot"] = df.groupby("date").cumcount()
    return df


def metrics(t):
    if len(t) == 0:
        return dict(n=0)
    net = t.pnl.sum(); gp = t.pnl[t.pnl > 0].sum(); gl = abs(t.pnl[t.pnl < 0].sum())
    daily = t.groupby(pd.to_datetime(t.date).dt.normalize()).pnl.sum()
    eq = daily.cumsum(); dd = (eq.cummax() - eq).max()
    wks = max((pd.Timestamp(t.date.max()) - pd.Timestamp(t.date.min())).days / 7.0, 1)
    return dict(n=len(t), pf=(gp/gl if gl else 9.99), wr=100*(t.pnl > 0).mean(),
                exp=t.pnl.mean(), net=net, ptswk=net/wks, tpw=len(t)/wks,
                maxdd_pt=dd, worst_day=daily.min())


def line(tag, m):
    if m.get("n", 0) == 0:
        print(f"  {tag:22} —"); return
    print(f"  {tag:22} n={m['n']:4d} | PF {m['pf']:.2f} | WR {m['wr']:2.0f}% | "
          f"exp {m['exp']:+.2f}pt | {m['ptswk']:+6.1f} pts/wk | {m['tpw']:.1f} tr/wk | "
          f"maxDD {m['maxdd_pt']:.0f}pt (${m['maxdd_pt']*20:,.0f}) | worstday {m['worst_day']:.0f}pt")


def main():
    df = real_rth_5m()
    df = df[df.date >= pd.Timestamp("2022-01-01", tz=NY)]
    feats = v.features(df)
    print("=" * 100)
    print(f"VPC RECERT — REAL Databento NQ 1m->5m RTH | {feats.date.nunique()} days "
          f"{feats.date.min().date()} -> {feats.date.max().date()} | CFG={CFG}")
    print("=" * 100)

    orig_cost = v.RT_COST
    print("\n### COST LADDER (full history)")
    ladder = {}
    for c in [0.75, 1.0, 2.0, 3.0]:
        v.RT_COST = c
        t = v.backtest(feats, **CFG)
        ladder[c] = t
        line(f"cost {c:.2f}pt RT", metrics(t))

    # IS/OOS on the base (0.75) then re-confirm at harsh 2.0
    for c in [0.75, 2.0]:
        t = ladder[c].sort_values("date").reset_index(drop=True)
        if len(t) == 0:
            continue
        d = pd.to_datetime(t.date)
        split = d.min() + (d.max() - d.min()) * 0.6
        print(f"\n### IS/OOS @ cost {c:.2f}pt  (split {split.date()})")
        line("IS  (first 60%)", metrics(t[d <= split]))
        line("OOS (last 40%)", metrics(t[d > split]))
        print(f"### PER-YEAR @ cost {c:.2f}pt")
        yr = pd.to_datetime(t.date).dt.year
        for y in sorted(yr.unique()):
            line(str(y), metrics(t[yr.values == y]))

    # ---- LOOK-AHEAD CANARY: poison all bars after a cut date; trades before must be identical ----
    print("\n### LOOK-AHEAD CANARY (poison-the-future)")
    v.RT_COST = orig_cost
    base = v.backtest(feats, **CFG).sort_values("date").reset_index(drop=True)
    cut = pd.Timestamp("2024-06-01", tz=NY)
    poisoned = feats.copy()
    mask = poisoned.index >= cut
    # blow up every price field on future bars — a causal strategy can't see these for earlier trades
    for col in ["Open", "High", "Low", "Close", "vwap", "vwap6", "atr", "dayopen"]:
        if col in poisoned.columns:
            poisoned.loc[mask, col] = poisoned.loc[mask, col] * 3.0 + 99999.0
    pois = v.backtest(poisoned, **CFG).sort_values("date").reset_index(drop=True)
    # stable, disambiguated compare (sort_values('date') alone is unstable on same-day ties)
    keys = ["date", "dir", "entry", "exit", "pnl"]
    a = base[pd.to_datetime(base.date) < cut].sort_values(keys, kind="mergesort").reset_index(drop=True)
    b = pois[pd.to_datetime(pois.date) < cut].sort_values(keys, kind="mergesort").reset_index(drop=True)
    same = (len(a) == len(b)) and np.allclose(a.pnl.values, b.pnl.values, atol=1e-6)
    print(f"  pre-cut trades base={len(a)} poisoned={len(b)}  "
          f"pnl identical={same}  ->  {'CAUSAL (canary PASS)' if same else 'LOOK-AHEAD DETECTED (FAIL)'}")

    v.RT_COST = orig_cost


if __name__ == "__main__":
    main()
