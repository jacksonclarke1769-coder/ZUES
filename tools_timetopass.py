"""Time-to-pass the eval (-> time to a funded account): live partial vs single@1R / @1.5R.
Reuses exit_model_validate's validated per-variant streams; EOD.eval_eod returns days-to-pass.
Reports pass%, EXPIRE% (the 30-day-clock cost), and the days-to-pass distribution for passers."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import exit_model_validate as V
import apex_eval_eod as EOD
import apex_eval_deployed as H
import apex_eval_eod_databento as DB
import funded_rules as FR
import strategy_engine_profileA as E
import config

SPEC = FR.APEX_ACCOUNTS["50K"]
print("loading real Databento NQ 1m -> 5m…", flush=True)
df5 = DB.load_databento_5m()
print(f"  {df5.index.min().date()} -> {df5.index.max().date()} ({len(df5):,})", flush=True)
H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
feats = eng._features(); fi = feats.index
variants = ["incumbent", "single1", "single15"]
lab = {"incumbent": "LIVE BOT partial", "single1": "single@1R", "single15": "single@1.5R"}
A = {v: V.a_variant(feats, fi, v) for v in variants}
B = V.b_sim(df5); Mm = H.m_events(df5)

print("\n  TIME-TO-PASS the Apex eval (A10/B5/mm6, EOD rule, 30-day clock, real Databento)")
print(f"  {'exit':>16} | {'pass%':>6} {'exp%':>5} | {'med d':>6} {'mean d':>7} {'p25':>4} {'p75':>4} {'p90':>4} | passers")
print("  " + "-" * 78)
for v in variants:
    ev = V.build_events(A, B, Mm, v)
    starts = EOD.day_starts(ev)
    res = [EOD.eval_eod(ev, s, SPEC) for s in starts]
    n = len(res)
    pd_days = [d for (o, d) in res if o == "PASS"]
    exps = sum(1 for (o, d) in res if o == "EXPIRE")
    pr = 100 * len(pd_days) / n
    ep = 100 * exps / n
    md = int(np.median(pd_days)); mn = np.mean(pd_days)
    p25, p75, p90 = (int(np.percentile(pd_days, q)) for q in (25, 75, 90))
    print(f"  {lab[v]:>16} | {pr:6.1f} {ep:5.1f} | {md:6} {mn:7.1f} {p25:4} {p75:4} {p90:4} | n={len(pd_days)}")
print("\n  exp% = evals that hit the 30-day clock without passing (faster passers -> fewer expiries).")
