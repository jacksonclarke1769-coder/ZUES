"""Adversarial verification: is the overnight-ORB-compressed edge a NEW uncorrelated edge,
or a filtered re-capture of momentum / VPC we already own?

Builds three DAILY P&L streams on REAL data and correlates them:
  ORB  = A_30_comp_breakout_2R (survivor)                     [Databento NQ 1m]
  MOM  = momentum daily P&L (H.m_events, unit size)           [same Databento 5m]
  VPC  = nq_vwap_pullback daily P&L                            [Databento 5m]
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))

import search as S
import sim_engine as SE
import apex_eval_deployed as H
import apex_eval_eod_databento as DB
from profile_momentum_engine import ProfileMomentumEngine as PME

NY = "America/New_York"

# ---------- ORB survivor daily stream ----------
orb = S.fam_A(30, "comp", "breakout", "2R")  # cols: date, side, pnl(points), ...
orb["d"] = pd.to_datetime(orb["date"]).dt.normalize().dt.tz_localize(None)
orb_daily = orb.groupby("d")["pnl"].sum()          # points; one trade/day
orb_side = orb.groupby("d")["side"].first()
print(f"ORB fire-days: {len(orb_daily)}  net {orb_daily.sum():.0f}pt")

# ---------- Momentum daily stream (same Databento data) + direction ----------
df5 = DB.load_databento_5m()
H.M_SIZE = 1
mev = H.m_events(df5)   # one event/day, pnl in $, ts=last bar of day
mom_daily = pd.Series({pd.Timestamp(e["ts"]).normalize().tz_localize(None): e["pnl"] for e in mev})
print(f"MOM days: {len(mom_daily)}  net ${mom_daily.sum():.0f}")

# momentum net DIRECTION per day (sum of held position sign)
d = df5.copy()
mins = d.index.hour * 60 + d.index.minute
d = d[(mins >= 570) & (mins < 960)].copy()
d["date"] = d.index.normalize().tz_localize(None)
d["slot"] = ((d.index.hour * 60 + d.index.minute) - 570) // 5
d = d.reset_index().rename(columns={"index": "ts"})
pos = PME.compute(d[["date", "slot", "Open", "High", "Low", "Close"]].assign(Volume=0))
d["pos"] = pos
mom_dir = d.groupby("date")["pos"].sum().apply(np.sign)   # net long/short/flat that day

# ---------- VPC daily stream ----------
try:
    import vpc_apex_eval_sim as VS
    import nq_vwap_pullback as v
    feats = v.features(VS.real_rth_5m())
    feats = feats[feats.date >= pd.Timestamp("2022-01-01", tz=VS.NY)]
    tr = VS.vpc_trades_rich(feats)
    vev = [(pd.Timestamp(r.ts).normalize().tz_localize(None), r.pnl_pts) for r in tr.itertuples()]
    vpc_daily = pd.Series(dict()).astype(float)
    tmp = {}
    for dt, p in vev:
        tmp[dt] = tmp.get(dt, 0.0) + p
    vpc_daily = pd.Series(tmp)
    print(f"VPC days: {len(vpc_daily)}  net {vpc_daily.sum():.0f}pt")
except Exception as ex:
    print(f"VPC BUILD FAILED: {ex}")
    vpc_daily = None

def corr_report(name, other_daily, other_dir=None):
    print(f"\n===== ORB vs {name} =====")
    # (a) fire-days-only: days ORB trades, paired with other's daily pnl (0 if other didn't trade)
    idx = orb_daily.index
    o = other_daily.reindex(idx).fillna(0.0)
    both = other_daily.reindex(idx).notna()
    print(f"  ORB fire-days={len(idx)}; {name} also traded on {both.sum()} of them ({both.mean()*100:.0f}%)")
    if o.std() > 0 and orb_daily.std() > 0:
        r_fire = np.corrcoef(orb_daily.values, o.values)[0, 1]
        print(f"  (a) daily-P&L corr on ORB fire-days (other=0 if idle): r={r_fire:.3f}")
    # (a2) corr only where BOTH traded
    mask = both.values
    if mask.sum() > 5:
        r_both = np.corrcoef(orb_daily.values[mask], other_daily.reindex(idx)[mask].values)[0, 1]
        print(f"  (a2) daily-P&L corr where BOTH traded (n={mask.sum()}): r={r_both:.3f}")
    # (b) full union series, 0-filled
    allidx = orb_daily.index.union(other_daily.index)
    a = orb_daily.reindex(allidx).fillna(0.0); b = other_daily.reindex(allidx).fillna(0.0)
    r_full = np.corrcoef(a.values, b.values)[0, 1]
    print(f"  (b) daily-P&L corr full union series 0-filled (n={len(allidx)}): r={r_full:.3f}")
    # directional agreement
    if other_dir is not None:
        od = other_dir.reindex(idx)
        dd = pd.DataFrame({"orb": orb_side.reindex(idx), "oth": od}).dropna()
        dd = dd[dd.oth != 0]
        if len(dd) > 5:
            agree = (np.sign(dd.orb) == np.sign(dd.oth)).mean()
            print(f"  directional agreement on shared days (n={len(dd)}): {agree*100:.0f}% same side")

corr_report("MOMENTUM", mom_daily, mom_dir)
if vpc_daily is not None:
    corr_report("VPC", vpc_daily)
