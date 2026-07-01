"""Day-of-week edge breakdown — deployed strategy (Profile A OTE + B ORB), real Databento ~5y.
Per weekday: trade count, win-rate, average realized R (RR), and total R. A uses the EXIT3 partial R;
B uses its partial R (both = the deployed 'incumbent' exit). Momentum excluded (position, no clean R).
Goal: is any weekday a real edge or a drag we could filter?"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import exit_model_validate as V
import apex_eval_deployed as H
import apex_eval_eod_databento as DB
import strategy_engine_profileA as E
import config
NY = "America/New_York"
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def collect(exitv):
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5; feats = eng._features(); fi = feats.index
    A = [(pd.Timestamp(t["ts"]).tz_convert(NY), float(t["R"])) for t in V.a_variant(feats, fi, exitv)]
    B = [(pd.Timestamp(t["ts"]).tz_convert(NY), float(t["R"][exitv])) for t in V.b_sim(df5)]
    return A, B, (df5.index.min(), df5.index.max())


def by_dow(trades):
    d = {i: [] for i in range(5)}
    for ts, R in trades:
        w = ts.dayofweek
        if w < 5:
            d[w].append(R)
    return d


def line(name, d):
    print(f"  {name}")
    print(f"  {'day':>6} {'trades':>7} {'win%':>6} {'avg R':>7} {'total R':>8}")
    tot_n = tot_r = 0.0; wins = 0
    for i in range(5):
        rs = d[i]; n = len(rs)
        if n == 0:
            print(f"  {DOW[i]:>6} {0:>7} {'—':>6} {'—':>7} {'—':>8}"); continue
        wr = 100 * sum(1 for r in rs if r > 0) / n
        print(f"  {DOW[i]:>6} {n:>7} {wr:>5.1f}% {np.mean(rs):>7.3f} {np.sum(rs):>8.1f}")
        tot_n += n; tot_r += np.sum(rs); wins += sum(1 for r in rs if r > 0)
    print(f"  {'ALL':>6} {int(tot_n):>7} {100*wins/max(1,tot_n):>5.1f}% {tot_r/max(1,tot_n):>7.3f} {tot_r:>8.1f}\n")


def main():
    exitv = sys.argv[1] if len(sys.argv) > 1 else "single1"   # default: 1RR
    label = {"single1": "single@1R (1RR)", "incumbent": "EXIT3 partial (current)",
             "single15": "single@1.5R", "single2": "single@2R"}.get(exitv, exitv)
    print(f"loading real Databento… exit model = {label}", flush=True)
    A, B, (lo, hi) = collect(exitv)
    print(f"  window {lo.date()} -> {hi.date()} · A trades {len(A)} · B trades {len(B)}\n")
    print(f"========  DAY-OF-WEEK EDGE — {label} (realized R per trade)  ========\n")
    line("PROFILE A (OTE)", by_dow(A))
    line("PROFILE B (ORB)", by_dow(B))
    line("COMBINED A+B", by_dow(A + B))
    print(f"  [exit = {label} · avg R = realized R-multiple per trade · win% = R>0 · momentum excluded]")


if __name__ == "__main__":
    main()
