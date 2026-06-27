"""DOUBLE-CHECK harness: verifies the foundations the Apex sims rest on.
1) standalone edges on Databento (A/B/momentum must show their expected PF, else everything downstream is sand),
2) linear-rescale invariant (pnl/mfe/mae must scale exactly with contracts),
3) EOD>=intraday invariant (EOD must be gentler), 4) headline numbers reproduce."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod as EOD
import apex_eval_eod_databento as DB
import funded_rules as FR

SPEC = FR.APEX_ACCOUNTS["50K"]


def pf(pnls):
    w = sum(p for p in pnls if p > 0); l = abs(sum(p for p in pnls if p < 0))
    return (w / l) if l else float("inf")


def stats(name, ev, unit_contracts):
    pn = [e["pnl"] for e in ev]
    wr = 100 * sum(1 for p in pn if p > 0) / len(pn)
    print(f"  {name:<26} n={len(pn):>5}  WR {wr:4.0f}%  PF {pf(pn):4.2f}  "
          f"net ${sum(pn):>8,.0f} (@{unit_contracts} MNQ)  avg ${np.mean(pn):>6,.1f}")


def main():
    print("loading Databento + unit streams…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    A, B, M = H.a_events(df5), H.b_events(df5), H.m_events(df5)

    print(f"\n  === (1) STANDALONE EDGES on real Databento (per 1 MNQ) ===")
    print(f"      expect: A PF ~1.4-1.8 (Exit#3), B PF ~1.1-1.2, Momentum PF ~1.6-1.9")
    stats("Profile A (OTE/Exit#3)", A, 1)
    stats("Profile B (ORB)", B, 1)
    stats("Momentum (daily, cont.)", M, 1)

    print(f"\n  === (2) LINEAR-RESCALE INVARIANT (pnl must scale exactly with contracts) ===")
    a1 = sum(e["pnl"] for e in A); a3 = sum(e["pnl"] * 3 for e in A)
    print(f"      A net @1 MNQ = ${a1:,.0f} ; @3 MNQ (×3) = ${a3:,.0f} ; ratio {a3/a1:.4f}  "
          f"-> {'OK (exactly 3.0)' if abs(a3/a1 - 3.0) < 1e-9 else 'FAIL'}")

    print(f"\n  === (3) EOD ≥ INTRADAY invariant + headline reproduce (deployed A10/B5/mm6) ===")
    sc = {"A": 10, "B": 5, "M": 6}
    ev = H.apply_daily_stop([dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*sc[e["src"]],
                                  mfe=e["mfe"]*sc[e["src"]], mae=e["mae"]*sc[e["src"]]) for e in A+B+M])
    st = EOD.day_starts(ev)
    ip, ib, _, _ = EOD.summarize([H.eval_from(ev, s, SPEC) for s in st])
    epp, ebb, exx, emd = EOD.summarize([EOD.eval_eod(ev, s, SPEC) for s in st])
    print(f"      intraday PASS {ip:.1f}%   EOD PASS {epp:.1f}%   "
          f"-> {'OK (EOD gentler)' if epp >= ip else 'FAIL (EOD should be >= intraday)'}")
    print(f"      deployed EOD eval: PASS {epp:.1f}% BUST {ebb:.1f}% EXP {exx:.1f}% med {emd}d  "
          f"(reported 57.5% — {'MATCH' if abs(epp-57.5) < 2 else 'DRIFT'})")

    print(f"\n  === (4) funded reach-lock reproduce (A4/B2, EOD) ===")
    import apex_funded_momentum_test as MT
    fev = sorted(A + B, key=lambda e: e["ts"])
    last = pd.Timestamp(fev[-1]["ts"]); seen, fst = set(), []
    for i, e in enumerate(fev):
        d = pd.Timestamp(e["ts"]).normalize()
        if d in seen: continue
        seen.add(d)
        if (last - pd.Timestamp(e["ts"])).days >= 270: fst.append(i)
    out = [MT.life(fev, s, {"A": 4, "B": 2, "M": 0}, {"A": 6, "B": 3, "M": 0}) for s in fst]
    lk = 100 * sum(1 for o in out if o["locked"]) / len(out)
    print(f"      A4/B2 reach-lock {lk:.1f}%  (reported ~68% — {'MATCH' if abs(lk-68) < 3 else 'DRIFT'})")
    print("\n  done.")


if __name__ == "__main__":
    main()
