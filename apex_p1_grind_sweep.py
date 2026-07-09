"""Phase-1 GRIND sizing sweep — reuses validated MT.life (apex_funded_momentum_test) lifecycle:
EOD drawdown rule + REAL Databento, A/B/M unit streams from apex_eval_deployed. We vary ONLY the PRE
(grind/phase-1) sizing and hold POST (phase-2) at deployed A6/B3/mm6. Rank candidate grind sizings by
P(reach lock) [survival to phase 2] and E[payout|funded acct started]. Also report median days-to-lock."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB
import apex_funded_momentum_test as MT

POST = {"A": 6, "B": 3, "M": 6}   # deployed phase-2 (post-lock), held fixed

# candidate phase-1 grind sizings (A, B, grind-mm)
CANDS = [
    ("A1/B1/mm0", {"A": 1, "B": 1, "M": 0}),
    ("A2/B1/mm0", {"A": 2, "B": 1, "M": 0}),
    ("A2/B1/mm2", {"A": 2, "B": 1, "M": 2}),
    ("A2/B2/mm0", {"A": 2, "B": 2, "M": 0}),
    ("A3/B1/mm0", {"A": 3, "B": 1, "M": 0}),
    ("A3/B2/mm0", {"A": 3, "B": 2, "M": 0}),
    ("A3/B2/mm2", {"A": 3, "B": 2, "M": 2}),
    ("A4/B2/mm0", {"A": 4, "B": 2, "M": 0}),
    ("A4/B2/mm2", {"A": 4, "B": 2, "M": 2}),   # DEPLOYED phase-1
    ("A4/B2/mm6", {"A": 4, "B": 2, "M": 6}),
    ("A5/B3/mm0", {"A": 5, "B": 3, "M": 0}),
    ("A6/B3/mm0", {"A": 6, "B": 3, "M": 0}),
]


def metrics(ev, fst, pre):
    out = [MT.life(ev, s, pre, POST) for s in fst]
    n = len(out)
    lk = [o for o in out if o["locked"]]
    p_lock = 100 * len(lk) / n
    pay_all = np.mean([o["payout"] for o in out])
    pay_lk = np.mean([o["payout"] for o in lk]) if lk else 0.0
    mo = np.mean([o["months"] for o in lk]) if lk else 0.0
    inc = pay_lk / mo if mo else 0.0
    return p_lock, inc, pay_all, n


def main():
    print("loading Databento + A/B/Momentum streams…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    ev = sorted(H.a_events(df5) + H.b_events(df5) + H.m_events(df5), key=lambda e: e["ts"])
    last = pd.Timestamp(ev[-1]["ts"]); seen, fst = set(), []
    for i, e in enumerate(ev):
        d = pd.Timestamp(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - pd.Timestamp(e["ts"])).days >= 270:
            fst.append(i)
    print(f"  bars {df5.index.min().date()}..{df5.index.max().date()} · funded starts {len(fst)} · POST fixed A6/B3/mm6\n")

    print(f"  {'phase-1 grind':<14}{'lock%':>8}{'inc/mo':>10}{'E[payout|funded]':>18}")
    rows = []
    for label, pre in CANDS:
        lk, inc, pay, n = metrics(ev, fst, pre)
        rows.append((label, lk, inc, pay))
        star = "  <- DEPLOYED" if label == "A4/B2/mm2" else ""
        print(f"  {label:<14}{lk:>8.1f}{inc:>10,.0f}{pay:>18,.0f}{star}")

    print("\n  ---- ranked by P(reach lock) ----")
    for label, lk, inc, pay in sorted(rows, key=lambda r: -r[1]):
        print(f"    {label:<14} lock {lk:5.1f}%   E[payout|funded] ${pay:>7,.0f}")
    print("\n  ---- ranked by E[payout|funded started] ----")
    for label, lk, inc, pay in sorted(rows, key=lambda r: -r[3]):
        print(f"    {label:<14} E[payout] ${pay:>7,.0f}   lock {lk:5.1f}%")
    print("\n  [note] EOD + Databento; momentum = daily-aggregate proxy; POST held at deployed A6/B3/mm6.")


if __name__ == "__main__":
    main()
