"""Which EVAL size would PASS the 50K eval within the last 30 days? Sweep 1-5 MNQ + 1 NQ.
MFFU rules: +$3,000 target, $2,000 EOD trailing DD, 50% single-day consistency, min 2 days.
Realistic 2pt-slip fills. Reports pass/blow/in-progress + the binding blocker."""
import os, sys, pandas as pd
import paper_live, strategy_engine_profileA as E, config
import model01_sweep_mss_fvg as M1
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
from funded_sim import Acct, ACCOUNTS

DPP = {"1 MNQ": (2, 1.5), "2 MNQ": (4, 3.0), "3 MNQ": (6, 4.5), "4 MNQ": (8, 6.0),
       "5 MNQ": (10, 7.5), "1 NQ": (20, 0.0)}
E.BUFFER_DAYS = 70
eng = E.ProfileAEngine(config.STRAT)
for ts, o, h, l, c in paper_live.DukascopyLiveFeed(warmup_days=72).history():
    eng.add_bar(ts, o, h, l, c)
feats = eng._features()
tr = M1.run(feats, "NQ", {**E.PROFILE_A, "slip_ticks": 8})
tr = tr[tr.session == "ny_am"].copy(); tr["ts"] = pd.to_datetime(tr["date"].astype(str))
last = eng.buf.index.max().normalize().tz_localize(None); start = last - pd.Timedelta(days=30)
tr = tr[tr.ts >= start].sort_values("fill_bar").reset_index(drop=True)
days = list(tr.groupby(tr.ts.dt.date))
print(f"50K EVAL over {start.date()} -> {last.date()} (30d) · {len(tr)} signals · realistic fills\n")
print(f"{'size':7}{'result':16}{'pass day':12}{'peak bal':>10}{'end bal':>10}{'maxDD$':>9}{'blocker':>22}")

for label, (dpp, comm) in DPP.items():
    a = Acct(ACCOUNTS["50K"], funded=False)
    peak = 50000.0; maxdd = 0.0; passed = None; blown = None; target_hit = False; cons_block = False
    for day, g in days:
        rows = [(t.r_result * abs(t.entry - t.stop) * dpp - comm,
                 t.mae_r * abs(t.entry - t.stop) * dpp, 0.0) for t in g.itertuples()]
        res = a.day(rows)
        peak = max(peak, a.bal); maxdd = max(maxdd, peak - a.bal)
        if a.bal >= 53000:
            target_hit = True
            if a.maxday > 0.5 * (a.bal - 50000):
                cons_block = True
        if res == "PASS": passed = day; break
        if res == "BREACH": blown = day; break
    if passed:
        result, blocker = "PASSED", "-"
    elif blown:
        result, blocker = "BLOWN", f"breached DD {blown}"
    else:
        if target_hit and cons_block:
            blocker = "50% consistency rule"
        elif a.bal < 53000:
            blocker = f"short ${53000-a.bal:,.0f} of target"
        else:
            blocker = "min-days / timing"
        result = "in eval (no pass)"
    print(f"{label:7}{result:16}{str(passed or '-'):12}{peak:>10,.0f}{a.bal:>10,.0f}{maxdd:>9,.0f}{blocker:>22}")

print("\nNote: consistency = max single day must be <=50% of total profit (ratio -> doesn't improve with size).")
