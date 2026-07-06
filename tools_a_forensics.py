"""PROFILE-A FORENSICS (2026-07-02) — what separates winners from losers in the LOCKED stream.

RESEARCH ONLY. Locked machine untouched. Joins model01's per-trade features with the 1m-truth
Exit#3 outcomes for the D1c-kept trades, then cuts WR/expR by feature — IS (…2024) vs HOLDOUT
(2025+) side by side so nothing gets believed off one half. n<25 buckets are noise; ignore.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import strategy_engine_profileA as E
import model01_sweep_mss_fvg as M1
import config
import run_d1c_real as RD
import apex_eval_eod_databento as DB
from tools_1m_truth_recert import M1Map, walk_1m, A_PARAMS

NY = "America/New_York"


def main():
    d1_tz = RD.load_1m(); d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m(); mp = M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    feats = eng._features(); fi = feats.index
    tr = M1.run(feats, "NQ", A_PARAMS["exit3"])
    tr = tr[tr.session == "ny_am"].copy()
    tr = RD.attach_drift(tr, d1_tz, fi)  # INC-20260706-1141: fill_bar + feats.index, not date/time strings
    tr = tr[tr.d1c_keep].copy()

    recs = []
    for _, t in tr.iterrows():
        risk = abs(float(t.entry) - float(t.stop)); fb = int(t.fill_bar)
        if risk <= 0 or not (0 <= fb < len(fi)):
            continue
        d = 1 if t.direction == "long" else -1
        partials = [(float(t.entry) + d * rl * risk, frac) for rl, frac in A_PARAMS["exit3"]["partial"]]
        w = walk_1m(mp, fb, d, float(t.entry), float(t.stop), float(t.target), partials,
                    max_5m_bars=M1.MAX_HOLD)
        if w is None:
            continue
        ts = pd.Timestamp(fi[fb])
        hh = ts.tz_convert(NY).hour * 60 + ts.tz_convert(NY).minute
        recs.append(dict(ts=ts, R=w[0], win=w[0] > 0, dir=t.direction, dow=t.dow,
                         t_open=(hh - 570) // 30 * 30,               # minutes after 09:30, 30m buckets
                         level=str(t.liq_swept), tier=t.liq_tier,
                         disp=int(t.disp_strength), conf=int(t.confluence_score),
                         grade=str(t.grade), pd_status=str(t.pd_status),
                         risk_pts=round(risk), drift=int(t.drift_sign),
                         fvg=float(t.fvg_size)))
    df = pd.DataFrame(recs)
    df["era"] = np.where(df.ts < pd.Timestamp("2025-01-01", tz=NY), "IS", "HO")
    df["risk_b"] = pd.cut(df.risk_pts, [0, 25, 40, 60, 90, 999],
                          labels=["<25pt", "25-40", "40-60", "60-90", ">90"])
    df["fvg_b"] = pd.cut(df.fvg, [0, 5, 10, 20, 999], labels=["<5", "5-10", "10-20", ">20"])
    print(f"kept trades joined: {len(df)} · overall WR {100*df.win.mean():.1f}% expR {df.R.mean():+.3f}")

    def cut(col):
        g = df.groupby([col, "era"]).agg(n=("R", "size"), WR=("win", "mean"), expR=("R", "mean"))
        g["WR"] = (100 * g["WR"]).round(1); g["expR"] = g["expR"].round(3)
        p = g.unstack("era")
        p.columns = [f"{a}_{b}" for a, b in p.columns]
        cols = [c for c in ["n_IS", "WR_IS", "expR_IS", "n_HO", "WR_HO", "expR_HO"] if c in p.columns]
        print(f"\n--- by {col} ---"); print(p[cols].to_string())

    for col in ["dow", "t_open", "level", "tier", "disp", "conf", "grade",
                "pd_status", "dir", "risk_b", "fvg_b"]:
        cut(col)


if __name__ == "__main__":
    main()
