"""Exit-model optimality test — re-runs the REAL validated Profile-A engine (model01 _simulate,
which is fully parametrized for partial/be_at/rr/trail/floor) with alternative exit configs, then
pushes each variant's event stream through the SAME EOD Databento pass-rate harness used to
validate the deployed stack. B and momentum legs held fixed (B's exit is hardcoded in b_events).

Outputs per Profile-A exit variant:
  * standalone A-leg edge: N, win%, expectancy(R), PF, equity maxDD(R)  -- tests 'early-exits backfire'
  * full deployed-stack (A10/B5/mm6) Apex-50K EOD pass% / bust% / exp% / med-days
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

import apex_eval_eod_databento as DB     # load_databento_5m
import apex_eval_deployed as H           # b_events, m_events, apply_daily_stop, DPP
import apex_eval_eod as EOD              # eval_eod, day_starts, summarize
import funded_rules as FR
import strategy_engine_profileA as E
import config
import model01_sweep_mss_fvg as M1

SPEC = FR.APEX_ACCOUNTS["50K"]
NY = "America/New_York"
DPP = 2.0
A_SIZE, B_SIZE, M_SIZE = 10, 5, 6

# ---- exit variants for Profile A (base = ote entry, fixed_rr) ----
# incumbent EXIT3 = partial 50%@1R + 50%@2R
VARIANTS = [
    ("INCUMBENT 50/50 @1R/2R", dict(partial=[(1, 0.5)], rr=2.0)),
    ("single @2R",             dict(partial=None,       rr=2.0)),
    ("single @1.5R",           dict(partial=None,       rr=1.5)),
    ("single @1R",             dict(partial=None,       rr=1.0)),
    ("split 50/50 @1R/2.5R",   dict(partial=[(1, 0.5)], rr=2.5)),
    ("split 50/50 @1R/3R",     dict(partial=[(1, 0.5)], rr=3.0)),
    ("split 33/67 @1R/2R",     dict(partial=[(1, 1/3)], rr=2.0)),
    ("BE@1R + 50/50 @1R/2R",   dict(partial=[(1, 0.5)], rr=2.0, be_at=1.0)),
    ("BE@1R single @2R",       dict(partial=None,       rr=2.0, be_at=1.0)),
    ("ATR2x trail (no part)",  dict(partial=None,       rr=10.0, trail=True, trail_mode="atr", atr_mult=2.0)),
    ("ATR3x trail (no part)",  dict(partial=None,       rr=10.0, trail=True, trail_mode="atr", atr_mult=3.0)),
    ("swing trail (no part)",  dict(partial=None,       rr=10.0, trail=True, trail_mode="swing")),
    ("50%@1R + ATR2x trail",   dict(partial=[(1, 0.5)], rr=10.0, trail=True, trail_mode="atr", atr_mult=2.0)),
    ("floor@2R + ATR2x trail", dict(partial=[(1, 0.5)], rr=10.0, floor_at=2.0, trail=True, trail_mode="atr", atr_mult=2.0)),
]


def a_trades(feats, exit_params):
    p = {**E.PROFILE_A, "slip_ticks": 8, "target_mode": "fixed_rr"}
    p.update(exit_params)
    tr = M1.run(feats, "NQ", p)
    return tr[tr.session == "ny_am"].copy()


def a_events_from(tr, feats, size):
    fi = feats.index
    ev = []
    for _, t in tr.iterrows():
        risk = abs(float(t["entry"]) - float(t["stop"]))
        if risk <= 0:
            continue
        fb = int(t["fill_bar"])
        ts = fi[fb] if 0 <= fb < len(fi) else pd.Timestamp(str(t["date"])).tz_localize(NY)
        usd = risk * DPP * size
        ev.append(dict(ts=pd.Timestamp(ts), src="A",
                       pnl=float(t["r_result"]) * usd,
                       mfe=max(0.0, float(t["mfe_r"])) * usd,
                       mae=min(0.0, float(t["mae_r"])) * usd))
    return ev


def leg_stats(tr):
    r = tr["r_result"].astype(float).values
    n = len(r)
    wins = r[r > 1e-9]; losses = r[r < -1e-9]
    pf = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else float("inf")
    eq = np.cumsum(r); dd = float((np.maximum.accumulate(eq) - eq).max()) if n else 0.0
    return dict(n=n, win=100*len(wins)/n if n else 0, exp=float(r.mean()) if n else 0,
                pf=pf, totR=float(r.sum()), maxdd=dd)


def main():
    print("loading real Databento NQ 1m -> 5m…", flush=True)
    df5 = DB.load_databento_5m()
    print(f"  bars {df5.index.min().date()} -> {df5.index.max().date()}  ({len(df5):,})", flush=True)

    # Profile A features (once); B + momentum unit streams (fixed across variants)
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    feats = eng._features()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    B_unit = H.b_events(df5)
    M_unit = H.m_events(df5)
    print(f"  fixed legs: B={len(B_unit)}  mm-days={len(M_unit)}", flush=True)

    print("\n  Profile-A exit variants — standalone A-edge + DEPLOYED A10/B5/mm6 Apex-50K EOD pass%")
    print(f"  {'variant':<26}{'N':>5}{'win%':>6}{'expR':>7}{'PF':>6}{'totR':>8}{'ddR':>7}  |  "
          f"{'PASS%':>7}{'BUST%':>7}{'EXP%':>6}{'med':>5}")
    print("  " + "-" * 104)

    rows = []
    for name, ep in VARIANTS:
        tr = a_trades(feats, ep)
        st = leg_stats(tr)
        A_unit = a_events_from(tr, feats, 1)
        # rescale to deployed sizes and merge with fixed B/M
        sc = {"A": A_SIZE, "B": B_SIZE, "M": M_SIZE}
        merged = []
        for src, stream in (("A", A_unit), ("B", B_unit), ("M", M_unit)):
            for e in stream:
                merged.append(dict(ts=e["ts"], src=src, pnl=e["pnl"]*sc[src],
                                   mfe=e["mfe"]*sc[src], mae=e["mae"]*sc[src]))
        merged = H.apply_daily_stop(merged)
        starts = EOD.day_starts(merged)
        pp, bb, xx, md = EOD.summarize([EOD.eval_eod(merged, s, SPEC) for s in starts])
        rows.append((name, st, pp, bb, xx, md))
        pf = "inf" if st["pf"] == float("inf") else f"{st['pf']:.2f}"
        print(f"  {name:<26}{st['n']:>5}{st['win']:>6.1f}{st['exp']:>7.3f}{pf:>6}{st['totR']:>8.1f}"
              f"{st['maxdd']:>7.1f}  |  {pp:>7.1f}{bb:>7.1f}{xx:>6.1f}{md or 0:>5}")

    inc = rows[0]
    print(f"\n  INCUMBENT pass%={inc[2]:.1f}  expR={inc[1]['exp']:.3f}  PF={inc[1]['pf']:.2f}")
    best = max(rows, key=lambda r: r[2])
    print(f"  BEST pass% variant: {best[0]} -> {best[2]:.1f}%  (vs incumbent {inc[2]:.1f}%)")
    bestpf = max(rows, key=lambda r: (r[1]['pf'] if r[1]['pf'] != float('inf') else -1))
    print(f"  BEST A-edge PF: {bestpf[0]} -> PF {bestpf[1]['pf']:.2f}, expR {bestpf[1]['exp']:.3f}")


if __name__ == "__main__":
    main()
