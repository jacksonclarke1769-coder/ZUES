"""
VPC through the DLL-honest Apex 50K EOD eval sim — the certification gate Profile A passed.

Reuses the REAL eval engine (apex_eval_eod.eval_eod: EOD-drawdown, threshold ratchets on EOD
balance highs, intraday downside liquidation on bal+MAE, $550 daily stop, 30-day clock, rolling
1-eval/trading-day starts). VPC trades come from the locked config on real Databento 1m->5m RTH,
re-walked to capture per-trade ts + MAE + MFE (the recert sim didn't record MAE -> would understate
busts). Sweeps FIXED sizing (1..10 MNQ) and Profile-A-style SIZE-TO-RISK (fixed $ per trade).
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

BT = os.path.expanduser("~/trading-team/backtests")
sys.path.insert(0, BT)
import nq_vwap_pullback as v            # v.features, v.vpc_signals, RT_COST
import apex_eval_eod as AE              # eval_eod, day_starts, summarize
import funded_rules as FR

NY = "America/New_York"
DBNT = os.path.expanduser("~/trading-team/data/real_futures/NQ_databento_1m_5y.parquet")
DPP = 2.0                               # $/pt/MNQ
SPEC = FR.APEX_ACCOUNTS["50K"]
CFG = dict(atr_stop=2.5, trail_atr=5.0, slot_min=6, slot_max=66, max_trades=2,
           slope_mult=0.3, trend_mult=0.5, daily_stop=120)


def real_rth_5m():
    d1 = pd.read_parquet(DBNT)
    d1.index = d1.index.tz_convert(NY) if d1.index.tz else d1.index.tz_localize("UTC").tz_convert(NY)
    d1 = d1.sort_index(); d1 = d1[~d1.index.duplicated(keep="first")]
    g = lambda c, h: getattr(d1[c].resample("5min", label="left", closed="left"), h)()
    df = pd.DataFrame({"Open": g("open", "first"), "High": g("high", "max"), "Low": g("low", "min"),
                       "Close": g("close", "last"), "Volume": g("volume", "sum")}).dropna(subset=["Open"])
    t = df.index
    df = df[((t.hour > 9) | ((t.hour == 9) & (t.minute >= 30))) & (t.hour < 16)]
    df["date"] = df.index.normalize(); df["slot"] = df.groupby("date").cumcount()
    return df


def vpc_trades_rich(feats):
    """Faithful replica of v.simulate_day but records ts(entry), pnl_pts, mae_pts, mfe_pts, stop_pts."""
    sig_kw = {k: CFG[k] for k in ("atr_stop", "slot_min", "slot_max", "slope_mult", "trend_mult") if k in CFG}
    trail_atr = CFG["trail_atr"]; max_trades = CFG["max_trades"]; daily_stop = CFG["daily_stop"]
    out = []
    for day, g in feats.groupby("date"):
        g = g.sort_values("slot")
        idx = g.index                                    # keep timestamps
        sigs = v.vpc_signals(g.reset_index(drop=True), **sig_kw)
        O, H, L, C, A = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.atr.values
        n = len(g); busy_until = -1; taken = 0; day_pnl = 0.0
        for (ei, d, stopdist) in sigs:
            if ei >= n or ei <= busy_until or taken >= max_trades:
                continue
            if daily_stop and day_pnl <= -daily_stop:
                break
            entry = O[ei]; stop = entry - stopdist if d == 1 else entry + stopdist
            peak = entry; exit_px = None; exit_i = n - 1
            mae = 0.0; mfe = 0.0
            for j in range(ei, n):
                mae = min(mae, d * (L[j] - entry) if d == 1 else d * (H[j] - entry))
                mfe = max(mfe, d * (H[j] - entry) if d == 1 else d * (L[j] - entry))
                if d == 1:
                    if L[j] <= stop: exit_px = stop; exit_i = j; break
                    peak = max(peak, H[j]); ns = peak - trail_atr * A[j]
                    stop = max(stop, ns) if not np.isnan(A[j]) else stop
                else:
                    if H[j] >= stop: exit_px = stop; exit_i = j; break
                    peak = min(peak, L[j]); ns = peak + trail_atr * A[j]
                    stop = min(stop, ns) if not np.isnan(A[j]) else stop
            if exit_px is None: exit_px = C[n - 1]; exit_i = n - 1
            pnl = d * (exit_px - entry) - v.RT_COST
            out.append(dict(ts=idx[ei], pnl_pts=pnl, mae_pts=mae, mfe_pts=mfe, stop_pts=stopdist))
            busy_until = exit_i; taken += 1; day_pnl += pnl
    return pd.DataFrame(out).sort_values("ts").reset_index(drop=True)


def events_fixed(tr, contracts):
    return [dict(ts=pd.Timestamp(r.ts), src="A", pnl=r.pnl_pts * DPP * contracts,
                 mfe=max(0.0, r.mfe_pts) * DPP * contracts, mae=min(0.0, r.mae_pts) * DPP * contracts)
            for r in tr.itertuples()]


def events_risk(tr, budget, maxc=10):
    ev = []
    for r in tr.itertuples():
        c = int(np.clip(round(budget / (r.stop_pts * DPP)), 1, maxc)) if r.stop_pts > 0 else 1
        ev.append(dict(ts=pd.Timestamp(r.ts), src="A", pnl=r.pnl_pts * DPP * c,
                       mfe=max(0.0, r.mfe_pts) * DPP * c, mae=min(0.0, r.mae_pts) * DPP * c))
    return ev


def run(ev):
    starts = AE.day_starts(ev)
    p, b, x, md = AE.summarize([AE.eval_eod(ev, s, SPEC) for s in starts])
    return p, b, x, md, len(starts)


def main():
    feats = v.features(real_rth_5m())
    feats = feats[feats.date >= pd.Timestamp("2022-01-01", tz=NY)]
    tr = vpc_trades_rich(feats)
    net_pts = tr.pnl_pts.sum()
    print(f"VPC trades={len(tr)}  net={net_pts:.0f}pt  (recert cross-check: expect ~408 / +net)")
    print(f"Apex 50K: start ${SPEC['start']:,} trail ${SPEC['trailing']:,} target ${SPEC['target']:,} "
          f"max {SPEC['max_contracts']}MNQ | $550 daily stop | 30d clock | EOD-drawdown, rolling starts\n")

    print("=== FIXED SIZING (MNQ) ===")
    print(f"  {'MNQ':>4} {'per-trade risk~$':>16} | {'PASS%':>6} {'BUST%':>6} {'EXP%':>5} {'medDays':>7} {'nStarts':>7}")
    med_stop_pts = tr.stop_pts.median()
    for c in [1, 2, 3, 4, 5, 6]:
        p, b, x, md, ns = run(events_fixed(tr, c))
        print(f"  {c:>4} {med_stop_pts*DPP*c:>16.0f} | {p:>6.1f} {b:>6.1f} {x:>5.1f} {str(md):>7} {ns:>7}")

    print("\n=== SIZE-TO-RISK ($ per trade, Profile-A style, clamp 1..10 MNQ) ===")
    print(f"  {'budget$':>8} {'avgMNQ':>7} | {'PASS%':>6} {'BUST%':>6} {'EXP%':>5} {'medDays':>7}")
    for bud in [200, 300, 400, 500, 700, 1000, 1200]:
        ev = events_risk(tr, bud)
        avgc = np.mean([int(np.clip(round(bud/(r.stop_pts*DPP)),1,10)) if r.stop_pts>0 else 1 for r in tr.itertuples()])
        p, b, x, md, ns = run(ev)
        print(f"  {bud:>8} {avgc:>7.1f} | {p:>6.1f} {b:>6.1f} {x:>5.1f} {str(md):>7}")

    # certified Profile A bar for reference
    print("\n  [ref] Profile A certified (v2026.07.02b): PASS 58.2 / BUST 29.1 / EXPIRE 12.7, median 11d")


if __name__ == "__main__":
    main()
