"""Trade COUNTS per model over the last 6 months, real Databento. Current model = 1RR for A/B.
A (OTE) and B (ORB) are discrete bracket trades. Continuation (Momentum) is a POSITION strategy, so
its 'trades' = position entries/flips (each time it initiates or reverses direction) + active days.
No individual trades — just the aggregate per lane."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import exit_model_validate as V
import apex_eval_deployed as H
import apex_eval_eod_databento as DB
from profile_momentum_engine import ProfileMomentumEngine as PME
import strategy_engine_profileA as E
import config
T = pd.Timestamp; NY = "America/New_York"


def main():
    print("loading real Databento…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    end = df5.index.max(); lo = end - pd.Timedelta(days=182)          # last 6 months
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5; feats = eng._features(); fi = feats.index

    def inwin(ts):
        return T(ts) >= lo

    # ---- A (OTE) & B (ORB) — discrete bracket trades, 1RR ----
    A = [t for t in V.a_variant(feats, fi, "single1") if inwin(t["ts"])]
    B = [t for t in V.b_sim(df5) if inwin(t["ts"])]
    aR = [float(t["R"]) for t in A]; bR = [float(t["R"]["single1"]) for t in B]

    # ---- Continuation (Momentum) — position entries/flips + active days ----
    d = df5[(df5.index >= lo)].copy()
    mins = d.index.hour * 60 + d.index.minute
    d = d[(mins >= 570) & (mins < 960)].copy()
    d["date"] = d.index.normalize().tz_localize(None)
    d["slot"] = ((d.index.hour * 60 + d.index.minute) - 570) // 5
    dd = d.reset_index().rename(columns={"index": "ts"})
    pos = PME.compute(dd[["date", "slot", "Open", "High", "Low", "Close"]].assign(Volume=0))
    dd["pos"] = pos
    entries = 0; active_days = set(); mpnl = 0.0
    for day, g in dd.groupby("date"):
        g = g.reset_index(drop=True); prev = 0
        for i in range(len(g)):
            p = g.pos.iloc[i]
            if p != 0:
                active_days.add(day)
            if p != 0 and p != prev:                                  # new entry or flip = a trade
                entries += 1
            prev = p
    mpnl = sum(e["pnl"] for e in H.m_events(df5) if inwin(e["ts"]))

    wr = lambda rs: 100 * sum(1 for r in rs if r > 0) / max(1, len(rs))
    print(f"\n  window {lo.date()} -> {end.date()}  (~6 months) · A/B on 1RR\n")
    print(f"  {'model':>26} {'trades':>7} {'win%':>6} {'avg R':>7} {'total R':>8}")
    print("  " + "-" * 60)
    print(f"  {'A  (OTE, bracket)':>26} {len(A):>7} {wr(aR):>5.1f}% {np.mean(aR):>7.3f} {np.sum(aR):>8.1f}")
    print(f"  {'B  (ORB, bracket)':>26} {len(B):>7} {wr(bR):>5.1f}% {np.mean(bR):>7.3f} {np.sum(bR):>8.1f}")
    print(f"  {'Continuation (Momentum)':>26} {entries:>7} {'—':>6} {'—':>7} {'—':>8}")
    print(f"\n  A+B bracket trades : {len(A)+len(B)}")
    print(f"  Momentum           : {entries} entries/flips across {len(active_days)} active days "
          f"(position strategy; P&L ${mpnl:,.0f} @1 MNQ, no per-trade R)")
    print(f"  [~6mo · {len(A)+len(B)+entries} total directional actions across the 3 lanes]")


if __name__ == "__main__":
    main()
