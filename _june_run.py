"""Real June 8-21 2026 backtest at 3 MNQ, on live Dukascopy 5m bars (the CFD proxy
the strategy was validated on). Runs the actual frozen SimBot engine — same code
path as the live bot — with 45d warmup so prior-day/HTF levels are populated."""
import sys, os
from datetime import datetime
import pandas as pd
import config
config.SIZING = dict(getattr(config, "SIZING", {}), eval_qty=3)   # 3 MNQ (ARES 50K-conservative)
from store import Store
from bot import SimBot
from paper_live import DukascopyLiveFeed
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework/engine"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework/models"))
from strategy_engine_profileA import NY

WARM_START = datetime(2026, 4, 25); FETCH_END = datetime(2026, 6, 21, 23, 0)
TRADE_FROM = pd.Timestamp("2026-06-08", tz=NY); WIN_END = pd.Timestamp("2026-06-22", tz=NY)

feed = DukascopyLiveFeed(); feed.connect()
print("fetching Dukascopy 5m NQ ...", flush=True)
bars = feed._fetch(WARM_START, FETCH_END)
print(f"got {len(bars)} bars: {bars[0][0]} -> {bars[-1][0]}", flush=True)

st = Store("data/_june.db"); st.reset()
bot = SimBot(st, cost_per_contract=2.0)          # ~2 ticks slip + comm per MNQ RT
bot.trade_from = TRADE_FROM
for ts, o, h, l, c in bars:
    bot.process_bar(pd.Timestamp(ts), o, h, l, c)
if bot.cur_day is not None:
    bot.final_eod(pd.Timestamp(bars[-1][0]))

PV = config.POINT_VALUE  # 2.0 (MNQ); qty=3 -> $6/pt already in pnl_usd
def _naive(x):
    t = pd.Timestamp(x)
    return t.tz_localize(None) if t.tz is None else t.tz_convert(NY).tz_localize(None)
LO, HI = TRADE_FROM.tz_localize(None), WIN_END.tz_localize(None)
sigs = [s for s in bot.signals if LO <= _naive(s["ts_signal"]) < HI]
trades = [t for t in st.trades() if LO <= _naive(t["ts_entry"]) < HI]

print(f"\n=== REAL JUNE 8-21 2026 · Profile A · 3 MNQ ($6/pt) · Dukascopy proxy ===")
print(f"engine signals in window : {len(sigs)}")
print(f"trades taken (filled)    : {len(trades)}\n")
if trades:
    print(f"{'ENTRY (ET)':17s} {'side':5s} {'entry':>9s} {'stop':>9s} {'exit':>9s} {'Rpts':>6s} {'$P/L':>8s}  reason")
    print("-"*78)
    tot = 0.0
    for t in trades:
        risk = abs(float(t['entry_px'])-float(t['stop_px']))
        R = float(t['pnl_pts'])/risk if risk else 0
        tot += float(t['pnl_usd'])
        print(f"{str(t['ts_entry'])[:16]:17s} {t['direction'][:5]:5s} {float(t['entry_px']):>9.2f} "
              f"{float(t['stop_px']):>9.2f} {float(t['exit_px']):>9.2f} {R:>+6.2f} {float(t['pnl_usd']):>+8,.0f}  {t['reason']}")
    print("-"*78)
    wins = sum(1 for t in trades if float(t['pnl_usd'])>0)
    print(f"net ${tot:+,.0f}  ·  {wins}/{len(trades)} wins ({100*wins/len(trades):.0f}%)  ·  net after ~$6/trade costs")
else:
    print("No trades filled in the window.")
if sigs:
    print("\nsignals (incl. any that didn't fill / were risk-gated):")
    for s in sigs:
        print(f"  {str(s['ts_signal'])[:16]}  {s['side']:5s} entry {s['entry']:.2f} stop {s['stop']:.2f} tgt {s['target']:.2f}")
