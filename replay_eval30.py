"""Realistic: start the 50K EVAL 30 days ago (hot 4 MNQ), and if it passes, run FUNDED (2 MNQ).
Did we pass the eval? Where would we be? MFFU EOD rules, realistic 2pt-slip fills, 90/10 split."""
import os, sys, pandas as pd
import paper_live, strategy_engine_profileA as E, config
import model01_sweep_mss_fvg as M1
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
from funded_sim import Acct, ACCOUNTS

EVAL_MNQ, FUND_MNQ, SPLIT = 4, 2, 0.90
DPP = {2: (4, 3.0), 4: (8, 6.0)}        # MNQ -> (dollars/pt, comm)
E.BUFFER_DAYS = 70
eng = E.ProfileAEngine(config.STRAT)
for ts, o, h, l, c in paper_live.DukascopyLiveFeed(warmup_days=72).history():
    eng.add_bar(ts, o, h, l, c)
feats = eng._features()
tr = M1.run(feats, "NQ", {**E.PROFILE_A, "slip_ticks": 8})
tr = tr[tr.session == "ny_am"].copy(); tr["ts"] = pd.to_datetime(tr["date"].astype(str))
last = eng.buf.index.max().normalize().tz_localize(None); start = last - pd.Timedelta(days=30)
tr = tr[tr.ts >= start].sort_values("fill_bar").reset_index(drop=True)


def pnl(row, mnq):
    dpp, comm = DPP[mnq]; r = abs(row.entry - row.stop)
    return row.r_result * r * dpp - comm, row.mae_r * r * dpp


a = Acct(ACCOUNTS["50K"], funded=False)        # start in EVAL
phase = "EVAL"; mnq = EVAL_MNQ; pass_day = None; fund_start_bal = None
print(f"Start EVAL {start.date()} @ {EVAL_MNQ} MNQ (hot) -> FUNDED @ {FUND_MNQ} MNQ on pass · realistic fills")
print(f"{'date':12}{'phase':7}{'R':>7}{'day P&L':>10}{'balance':>11}{'event':>14}")
for day, g in tr.groupby(tr.ts.dt.date):
    rows = [pnl(t, mnq) for t in g.itertuples()]
    rows = [(p, m, 0.0) for p, m in rows]
    b0 = a.bal; res = a.day(rows); ev = ""
    if res == "PASS":
        pass_day = day; ev = "PASSED EVAL"
        prof_left = None
        a = Acct(ACCOUNTS["50K"], funded=True); phase = "FUND"; mnq = FUND_MNQ; fund_start_bal = a.bal
    elif res == "BREACH":
        ev = "BLOWN"
    elif res == "PAYOUT":
        ev = "PAYOUT"
    print(f"{str(day):12}{phase if not ev.startswith('PASS') else 'EVAL':7}{g.r_result.sum():>7.2f}{a.bal-b0:>10.0f}{a.bal:>11,.0f}{ev:>14}")
    if res == "BREACH": break

print("-" * 64)
if pass_day:
    print(f"  EVAL: PASSED on {pass_day} ({(pd.Timestamp(pass_day)-start).days}d in)")
    print(f"  Now FUNDED · balance ${a.bal:,.0f} (funded profit ${a.bal-50000:,.0f}) · win days {a.wd}/5 · payouts {a.payouts}")
else:
    need = 53000 - a.bal
    print(f"  EVAL: NOT passed yet · balance ${a.bal:,.0f} of $53,000 target (need +${need:,.0f} more) · {'BLOWN' if a.dead else 'still in eval, alive'}")
print(f"  Status: {'BLOWN' if a.dead else ('FUNDED & trading' if pass_day else 'still in EVAL')}")
