"""Full time-to-pass distribution for the eval (deployed A10/B5/mm6, EOD + Databento).
Percentiles, cumulative pass-by-day, and a histogram (calendar days)."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod as EOD
import apex_eval_eod_databento as DB
import funded_rules as FR

SPEC = FR.APEX_ACCOUNTS["50K"]


def main():
    print("loading Databento + streams…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    sc = {"A": 10, "B": 5, "M": 6}
    ev = H.apply_daily_stop([dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*sc[e["src"]],
                                  mfe=e["mfe"]*sc[e["src"]], mae=e["mae"]*sc[e["src"]])
                             for e in H.a_events(df5) + H.b_events(df5) + H.m_events(df5)])
    st = EOD.day_starts(ev)
    res = [EOD.eval_eod(ev, s, SPEC) for s in st]
    n = len(res)
    pdays = sorted(r[1] for r in res if r[0] == "PASS")
    npass = len(pdays)

    print(f"\n  === TIME-TO-PASS distribution — deployed A10/B5/mm6, EOD + Databento ===")
    print(f"  {n} eval starts · {npass} passed ({100*npass/n:.0f}%) · "
          f"{sum(1 for r in res if r[0]=='BUST')} bust · {sum(1 for r in res if r[0]=='EXPIRE')} expire\n")
    pc = lambda p: int(np.percentile(pdays, p))
    print(f"  calendar days to pass (conditional on passing):")
    print(f"    min {pdays[0]}   P10 {pc(10)}   P25 {pc(25)}   MEDIAN {pc(50)}   "
          f"P75 {pc(75)}   P90 {pc(90)}   max {pdays[-1]}   mean {np.mean(pdays):.1f}")

    print(f"\n  cumulative — of the {npass} passers, % that had passed by day:")
    for d in (1, 2, 3, 5, 7, 10, 14, 21, 30):
        k = sum(1 for x in pdays if x <= d)
        print(f"    ≤{d:>2}d  {100*k/npass:>5.1f}%  (of passers)   {100*k/n:>5.1f}%  (of ALL evals bought)")

    print(f"\n  histogram (calendar days to pass):")
    bins = [(0, 2), (3, 4), (5, 6), (7, 9), (10, 13), (14, 20), (21, 30)]
    mx = max(sum(1 for x in pdays if lo <= x <= hi) for lo, hi in bins)
    for lo, hi in bins:
        c = sum(1 for x in pdays if lo <= x <= hi)
        bar = "█" * int(40 * c / mx) if mx else ""
        print(f"    {lo:>2}-{hi:<2}d  {c:>4}  {bar}")
    print("\n  [note] EOD + Databento; ~1.4 cal-days ≈ 1 trading day. days measured from eval start.")


if __name__ == "__main__":
    main()
