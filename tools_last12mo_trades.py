"""Day-by-day Profile A trade extract for the last 12 months.
Runs the frozen SimBot engine (same signals + conservative stop-first fills the
live path uses) and reports, per day: #trades and realized R-multiple per trade.
R = realized_pts / risk_pts, where risk_pts = |entry - stop| (qty-independent)."""
import pandas as pd
from collections import defaultdict
from bot import run_sim

START, END = "2025-06-20", "2026-06-20"
bot = run_sim(START, END, reset=True, warmup_days=45,
              db_path="data/_bt12mo.db", cost=0.0, verbose=False)

trs = bot.st.trades()
by_day = defaultdict(list)
for t in trs:
    d = str(t["ts_entry"])[:10]
    risk = abs(float(t["entry_px"]) - float(t["stop_px"]))
    R = (float(t["pnl_pts"]) / risk) if risk else 0.0   # pnl_pts already realized/qty
    by_day[d].append(dict(side=t["direction"], R=R, pts=float(t["pnl_pts"]),
                          reason=t["reason"]))

# full trading-day calendar from the bar spine (to count zero-trade days honestly)
import sys, os
FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
sys.path.insert(0, os.path.join(FW, "engine"))
import data as D
spine = D.load_spine("NQ", "5m")
lo, hi = pd.Timestamp(START, tz="America/New_York"), pd.Timestamp(END, tz="America/New_York")
days = sorted({ts.date() for ts in spine.index if lo <= ts < hi})

print(f"\n=== PROFILE A — DAY BY DAY ({START} -> {END}) ===")
print(f"{'DATE':12s} {'#':>2s}  {'RR per trade (realized R)':40s}")
print("-" * 70)
tot_tr = wins = 0
all_R = []
traded_days = 0
for d in days:
    ds = str(d)
    if ds not in by_day:
        continue
    traded_days += 1
    row = by_day[ds]
    tot_tr += len(row)
    rs = []
    for x in row:
        all_R.append(x["R"])
        if x["R"] > 0:
            wins += 1
        rs.append(f"{x['side'][0].upper()} {x['R']:+.2f}R")
    print(f"{ds:12s} {len(row):>2d}  {', '.join(rs)}")

n_days = len(days)
zero = n_days - traded_days
wk = n_days / 5.0
import statistics as S
print("-" * 70)
print(f"trading days in window : {n_days}  (traded {traded_days}, zero-trade {zero})")
print(f"total trades           : {tot_tr}   ({tot_tr/ (n_days/5):.2f}/week, {tot_tr/n_days:.2f}/day avg)")
print(f"win rate               : {wins}/{tot_tr} = {100*wins/tot_tr:.0f}%")
print(f"avg realized R/trade   : {S.mean(all_R):+.3f}R   (median {S.median(all_R):+.2f}R)")
print(f"R range                : {min(all_R):+.2f}R .. {max(all_R):+.2f}R")
exp = S.mean(all_R)
print(f"expectancy             : {exp:+.3f}R/trade  ->  {exp*tot_tr:+.1f}R over 12mo")
# trades-per-day distribution
dist = defaultdict(int)
for d in days:
    dist[len(by_day.get(str(d), []))] += 1
print(f"trades/day distribution: " + "  ".join(f"{k}t:{v}d" for k, v in sorted(dist.items())))
print("\n(R = realized points / risk points; gross of slippage. side L/S.)")
