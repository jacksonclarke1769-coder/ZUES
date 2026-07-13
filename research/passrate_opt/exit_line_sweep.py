"""Investigation B — VPC EXIT-LINE / TARGET tuning for eval-pass SPEED.

RESEARCH / SIM MEASUREMENT ONLY. Read-only toward strategy code (imports only).
Writes confined to reports/passrate_opt/. Nothing armed. No locked/certified config changed.
Changing the live exit is a RE-CERTIFICATION event — this file only MEASURES the research
tradeoff over the honest stream; it deploys nothing.

Method: reuse the fork_b CERTIFIED eval engine BY IMPORT (research/fork_b/honest_eval_engines.py,
which itself imports tools_account_size_research = the certified Apex-50K EOD harness). Only the VPC
EXIT rule changes; signals, sizing ($600/cap-3), costs (RT_COST=0.75pt), daily_stop=120, max_trades=2,
data (Databento 5m RTH 2022+), and the eval funnel are IDENTICAL to fork_b. So the trail_atr=5.0 row
must reproduce fork_b's VPC baseline (12.6 / 3.6 / 83.8, med 19d) as a canary.
"""
import os, sys, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "research", "fork_b"))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))

import honest_eval_engines as FB          # fork_b harness (databento_5m_rth, vpc_events_risk, eval_funnel, CFG)
import nq_vwap_pullback as v              # vpc_signals + RT_COST

DPP = FB.DPP
OUT = os.path.join(REPO, "reports", "passrate_opt")
os.makedirs(OUT, exist_ok=True)


def vpc_trades_exit(feats, exit_mode, trail_atr=5.0, r_mult=2.0):
    """VPC trades with a SWAPPABLE exit. All non-exit machinery is byte-identical to
    fork_b.vpc_trades_rich (same signals/gates/daily_stop/max_trades/RT_COST/adverse-first).

    exit_mode == 'trail' : trailing stop at peak -/+ trail_atr*ATR (fork_b Exit#3 family).
    exit_mode == 'fixedR': hard target at entry +/- r_mult*stopdist; original stop fixed
                           (stop-checked-first intrabar = conservative).
    """
    CFG = FB.CFG
    sig_kw = {k: CFG[k] for k in ("atr_stop", "slot_min", "slot_max", "slope_mult", "trend_mult")}
    max_trades, daily_stop = CFG["max_trades"], CFG["daily_stop"]
    out = []
    for day, g in feats.groupby("date"):
        g = g.sort_values("slot"); idx = g.index
        sigs = v.vpc_signals(g.reset_index(drop=True), **sig_kw)
        O, Hh, L, C, A = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.atr.values
        n = len(g); busy_until = -1; taken = 0; day_pnl = 0.0
        for (ei, d, stopdist) in sigs:
            if ei >= n or ei <= busy_until or taken >= max_trades:
                continue
            if daily_stop and day_pnl <= -daily_stop:
                break
            entry = O[ei]; stop = entry - stopdist if d == 1 else entry + stopdist
            target = entry + d * r_mult * stopdist          # only used in fixedR
            peak = entry; exit_px = None; exit_i = n - 1; mae = 0.0; mfe = 0.0
            for j in range(ei, n):
                mae = min(mae, d * (L[j] - entry) if d == 1 else d * (Hh[j] - entry))
                mfe = max(mfe, d * (Hh[j] - entry) if d == 1 else d * (L[j] - entry))
                if d == 1:
                    if L[j] <= stop: exit_px = stop; exit_i = j; break          # stop-first (adverse)
                    if exit_mode == "fixedR" and Hh[j] >= target: exit_px = target; exit_i = j; break
                    if exit_mode == "trail":
                        peak = max(peak, Hh[j]); ns = peak - trail_atr * A[j]
                        stop = max(stop, ns) if not np.isnan(A[j]) else stop
                else:
                    if Hh[j] >= stop: exit_px = stop; exit_i = j; break
                    if exit_mode == "fixedR" and L[j] <= target: exit_px = target; exit_i = j; break
                    if exit_mode == "trail":
                        peak = min(peak, L[j]); ns = peak + trail_atr * A[j]
                        stop = min(stop, ns) if not np.isnan(A[j]) else stop
            if exit_px is None: exit_px = C[n - 1]; exit_i = n - 1
            pnl = d * (exit_px - entry) - v.RT_COST
            out.append(dict(ts=idx[ei], pnl_pts=pnl, mae_pts=mae, mfe_pts=mfe, stop_pts=stopdist))
            busy_until = exit_i; taken += 1; day_pnl += pnl
    return pd.DataFrame(out).sort_values("ts").reset_index(drop=True)


def pf_of(tr):
    p = tr.pnl_pts.values
    g = p[p > 0].sum(); l = -p[p < 0].sum()
    return (g / l) if l > 0 else float("inf")


def main():
    print("loading Databento 5m RTH (2022+)…", flush=True)
    df5 = FB.databento_5m_rth()
    feats = v.features(df5)
    feats = feats[feats.date >= FB.START_DATE]
    print(f"  bars {df5.index.min().date()}→{df5.index.max().date()} ({len(df5):,})", flush=True)

    variants = [
        ("trail_3.0", dict(exit_mode="trail", trail_atr=3.0)),
        ("trail_4.0", dict(exit_mode="trail", trail_atr=4.0)),
        ("trail_5.0 (BASELINE/canary)", dict(exit_mode="trail", trail_atr=5.0)),
        ("trail_6.0", dict(exit_mode="trail", trail_atr=6.0)),
        ("fixed_1.5R", dict(exit_mode="fixedR", r_mult=1.5)),
        ("fixed_2.0R", dict(exit_mode="fixedR", r_mult=2.0)),
        ("fixed_2.5R", dict(exit_mode="fixedR", r_mult=2.5)),
        ("fixed_3.0R", dict(exit_mode="fixedR", r_mult=3.0)),
    ]

    rows = []
    for label, kw in variants:
        tr = vpc_trades_exit(feats, **kw)
        ev = FB.vpc_events_risk(tr, budget=600, cap=3)   # SAME sizing as fork_b VPC baseline
        r = FB.eval_funnel(ev, label)
        pf = pf_of(tr)
        wr = 100 * (tr.pnl_pts > 0).mean()
        row = dict(variant=label, n_trades=len(tr), PF=round(pf, 3), WR_pct=round(wr, 1),
                   net_pts=round(tr.pnl_pts.sum(), 1),
                   pass_pct=r["pass_pct"], bust_pct=r["bust_pct"], exp_pct=r["exp_pct"],
                   med_days=r["med_days"], tr_wk=r["trades_per_wk"], e_att=r["e_per_att"])
        rows.append(row)
        print(f"  {label:28s} PF {pf:5.3f} WR {wr:4.1f} n{len(tr):4d} | "
              f"pass {r['pass_pct']:4.1f} bust {r['bust_pct']:4.1f} exp {r['exp_pct']:4.1f} "
              f"med {str(r['med_days']):>4}d tr/wk {r['trades_per_wk']}", flush=True)

    with open(os.path.join(OUT, "02_exit_sweep.json"), "w") as f:
        json.dump(rows, f, indent=2, default=str)
    print(f"\n[saved] reports/passrate_opt/02_exit_sweep.json", flush=True)
    return rows


if __name__ == "__main__":
    main()
