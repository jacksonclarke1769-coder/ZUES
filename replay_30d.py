"""Quick: a FUNDED 50K @ 2 MNQ account started 30 days ago, run on the real Profile A v2 signals
(realistic 2pt-slip fills), MFFU EOD-trailing rules. Where would we be today?"""
import os, sys, pandas as pd
import paper_live, strategy_engine_profileA as E, config
import model01_sweep_mss_fvg as M1
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
from funded_sim import Acct, ACCOUNTS

DPP, COMM, SPLIT = 4, 3.0, 0.90        # 2 MNQ; MFFU 90/10
E.BUFFER_DAYS = 70
eng = E.ProfileAEngine(config.STRAT)
for ts, o, h, l, c in paper_live.DukascopyLiveFeed(warmup_days=72).history():
    eng.add_bar(ts, o, h, l, c)
feats = eng._features()
tr = M1.run(feats, "NQ", {**E.PROFILE_A, "slip_ticks": 8})    # realistic 2pt slippage
tr = tr[tr.session == "ny_am"].copy()
tr["ts"] = pd.to_datetime(tr["date"].astype(str))
last = eng.buf.index.max().normalize().tz_localize(None)
start = last - pd.Timedelta(days=30)
tr = tr[tr.ts >= start].sort_values("fill_bar").reset_index(drop=True)
tr["pnl"] = tr.r_result * (tr.entry - tr.stop).abs() * DPP - COMM
tr["mae"] = tr.mae_r * (tr.entry - tr.stop).abs() * DPP

a = Acct(ACCOUNTS["50K"], funded=True)
print(f"FUNDED 50K @ 2 MNQ · started {start.date()} (30d ago) · {len(tr)} signals · realistic 2pt-slip fills")
print(f"{'date':12}{'dir':7}{'R':>7}{'day P&L':>10}{'balance':>11}{'note':>10}")
peak = 50000.0; maxdd = 0.0; payout_th = 0.0
for day, g in tr.groupby(tr.ts.dt.date):
    rows = [(t.pnl, t.mae, 0.0) for t in g.itertuples()]
    b0 = a.bal
    res = a.day(rows)
    peak = max(peak, a.bal); maxdd = max(maxdd, peak - a.bal)
    note = ""
    if res == "BREACH": note = "BLOWN"
    if res == "PAYOUT": note = "PAYOUT"; payout_th += (a.paid * SPLIT)   # approx
    dirs = "/".join(t.direction[0] for t in g.itertuples())
    print(f"{str(day):12}{dirs:7}{g.r_result.sum():>7.2f}{a.bal-b0:>10.0f}{a.bal:>11,.0f}{note:>10}")
    if res == "BREACH": break

floor = min(a.peakE - a.R["dd"], a.R["start"])
print("-" * 60)
print(f"  Ending balance : ${a.bal:,.0f}   (start $50,000 -> profit ${a.bal-50000:,.0f})")
print(f"  Win days       : {a.wd}/5 needed for a payout   ·   trades: {len(tr)}")
print(f"  Max drawdown   : ${maxdd:,.0f}   ·   trailing floor now: ${floor:,.0f}  (cushion ${a.bal-floor:,.0f})")
print(f"  Payouts taken  : {a.payouts}   (gross ${a.paid:,.0f}{', ~$'+format(a.paid*SPLIT,',.0f')+' take-home' if a.paid else ''})")
print(f"  Status         : {'BLOWN' if a.dead else 'ALIVE & funded'}")
