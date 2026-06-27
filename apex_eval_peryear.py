"""Debunk-check the OLD '~81% worst year' eval claim. Per-year eval pass rate, deployed A10/B5/mm6,
EOD rule + Databento. Shows EOD-real (correct) AND pure-EOD close-only (the lenient model the 81%/86%
likely came from). If no year reaches 81% under the real rule, the old claim is confirmed dead."""
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
    rows = []
    for s in st:
        yr = pd.Timestamp(ev[s]["ts"]).year
        real = EOD.eval_eod(ev, s, SPEC)[0]
        close = EOD.eval_eod_closeonly(ev, s, SPEC)[0]
        rows.append((yr, real, close))

    years = sorted(set(r[0] for r in rows))
    print(f"\n  === PER-YEAR eval pass — deployed A10/B5/mm6 (EOD + Databento) ===")
    print(f"  old auto_safety claim: 'robust EVERY year, worst 2024 ~81%'")
    print(f"  {'year':>6}{'n':>6}{'EOD-real PASS%':>16}{'close-only PASS%':>18}")
    for y in years:
        yr = [r for r in rows if r[0] == y]
        n = len(yr)
        pr = 100*sum(1 for r in yr if r[1] == "PASS")/n
        pc = 100*sum(1 for r in yr if r[2] == "PASS")/n
        flag = "  <-2024" if y == 2024 else ""
        print(f"  {y:>6}{n:>6}{pr:>16.1f}{pc:>18.1f}{flag}")
    allreal = 100*sum(1 for r in rows if r[1] == "PASS")/len(rows)
    allclose = 100*sum(1 for r in rows if r[2] == "PASS")/len(rows)
    best_real = max(100*sum(1 for r in rows if r[0]==y and r[1]=="PASS")/sum(1 for r in rows if r[0]==y) for y in years)
    print(f"  {'ALL':>6}{len(rows):>6}{allreal:>16.1f}{allclose:>18.1f}")
    print(f"\n  best single YEAR under EOD-real: {best_real:.1f}%   "
          f"-> 81% claim {'SURVIVES' if best_real >= 79 else 'DEAD (no year reaches 81%)'}")
    print("  [note] close-only column = the too-lenient model the 81%/86% likely came from.")


if __name__ == "__main__":
    main()
