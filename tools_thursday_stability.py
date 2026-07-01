"""Is the Thursday edge STRUCTURAL or an artifact? Two digs, real Databento ~5y.
(1) PER-YEAR stability: Thursday avg R vs the rest, every calendar year (single@1R). Is Thu top every year
    or driven by 1-2 monster years?
(2) BREAKOUT QUALITY by weekday: split trades into WINNERS / LOSERS and look at MFE (ran-your-way) + MAE
    (heat). The Thu-vs-Fri puzzle: if Friday's LOSERS have high MFE, its breakouts round-trip (ran right,
    reversed, stopped) — explaining big range but weak edge; if Thursday's losers fail with low MFE, it
    trends cleanly."""
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
NY = "America/New_York"; DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]; DPP = H.DPP


def main():
    print("loading real Databento…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5; feats = eng._features(); fi = feats.index

    # ---- (1) per-year stability, single@1R R ----
    trades = ([(pd.Timestamp(t["ts"]).tz_convert(NY), float(t["R"])) for t in V.a_variant(feats, fi, "single1")]
              + [(pd.Timestamp(t["ts"]).tz_convert(NY), float(t["R"]["single1"])) for t in V.b_sim(df5)])
    print("\n========  (1) PER-YEAR Thursday stability — single@1R avg R  ========")
    print(f"  {'year':>5} | {'Thu avgR':>9} {'Thu n':>6} | {'rest avgR':>10} | {'Thu rank':>9} (1=best of 5 days)")
    yrs = sorted({ts.year for ts, _ in trades})
    for y in yrs:
        yd = {i: [] for i in range(5)}
        for ts, R in trades:
            if ts.year == y and ts.dayofweek < 5:
                yd[ts.dayofweek].append(R)
        means = {i: (np.mean(yd[i]) if yd[i] else np.nan) for i in range(5)}
        thu = means[3]; rest = np.mean([R for i in range(5) if i != 3 for R in yd[i]]) if any(yd[i] for i in range(5) if i!=3) else np.nan
        rank = 1 + sum(1 for i in range(5) if i != 3 and (means[i] > thu)) if not np.isnan(thu) else None
        print(f"  {y:>5} | {thu:>9.3f} {len(yd[3]):>6} | {rest:>10.3f} | {str(rank):>9}")
    print("  [Thu rank 1 = Thursday was the best day that year; consistent #1-2 = structural, jumpy = artifact]")

    # ---- (2) breakout quality: winners vs losers MFE/MAE by weekday (A+B default exit) ----
    ev = H.a_events(df5) + H.b_events(df5)
    q = {i: {"win_mfe": [], "win_mae": [], "los_mfe": [], "los_mae": [], "nw": 0, "nl": 0} for i in range(5)}
    for e in ev:
        w = pd.Timestamp(e["ts"]).tz_convert(NY).dayofweek
        if w >= 5:
            continue
        mfe = e["mfe"] / DPP; mae = -e["mae"] / DPP
        if e["pnl"] > 0:
            q[w]["win_mfe"].append(mfe); q[w]["win_mae"].append(mae); q[w]["nw"] += 1
        else:
            q[w]["los_mfe"].append(mfe); q[w]["los_mae"].append(mae); q[w]["nl"] += 1
    print("\n========  (2) BREAKOUT QUALITY by weekday (A+B, points)  ========")
    print(f"  {'day':>5} | {'WINNERS mae(heat)':>17} | {'LOSERS mfe(round-trip)':>22} | {'win%':>5}")
    for i in range(5):
        d = q[i]; n = d["nw"] + d["nl"]
        wmae = np.mean(d["win_mae"]) if d["win_mae"] else 0
        lmfe = np.mean(d["los_mfe"]) if d["los_mfe"] else 0
        print(f"  {DOW[i]:>5} | {wmae:>17.1f} | {lmfe:>22.1f} | {100*d['nw']/max(1,n):>4.0f}%")
    print("  [WINNERS mae = heat a winner took (lower=cleaner) · LOSERS mfe = how far a loser ran your way")
    print("   BEFORE failing (higher = round-trip/whipsaw: it went right, then reversed and stopped you).]")


if __name__ == "__main__":
    main()
