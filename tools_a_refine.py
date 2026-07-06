"""PROFILE-A REFINEMENT TESTS (2026-07-02) — pre-registered candidates on EVAL axes.

RESEARCH ONLY. Locked machine unchanged. Extends tools_a_forensics with sequencing / overnight-range
/ drift-margin cuts, then tests PRE-REGISTERED candidates (declared here, before results):
  C1 TILT   : budget x1.30 for grade C/D setups, x0.80 for grade A/B (inverse-confluence finding —
              consistent in BOTH eras in the first forensics pass). Sizing overlay, no trade dropped.
  C2 MARGIN : skip trades whose D1c drift magnitude at fill < 25% of daily ATR (weak-pass skip) —
              tested ONLY if the margin cut shows IS+HO-consistent weakness first.
  C3 FIRST  : first-trade-of-day only — tested ONLY if later trades show IS+HO-consistent weakness.
  C4 ONR    : skip after extreme overnight range (>90th pctile) — same conditionality.
Gates: candidate -> eval sim (50K, $1,600 and $1,200 budgets, DLL-honest) vs baseline; accept only if
pass improves AND bust does not rise >2pp AND both eras agree. Max 2 combined.
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
from tools_account_size_research import day_rows, eval_run, SPECS

NY = "America/New_York"
HO = pd.Timestamp("2025-01-01", tz=NY)


def build(df5, mp, d1_tz, d1):
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    feats = eng._features(); fi = feats.index
    tr = M1.run(feats, "NQ", A_PARAMS["exit3"])
    tr = tr[tr.session == "ny_am"].copy()
    tr = RD.attach_drift(tr, d1_tz, fi)  # INC-20260706-1141: fill_bar + feats.index, not date/time strings
    tr = tr[tr.d1c_keep].copy()
    # daily context off 5m data
    et5 = df5.index.tz_convert(NY)
    day5 = et5.normalize()
    onr, pdr, atr14 = {}, {}, {}
    trng = pd.concat([df5.High - df5.Low, (df5.High - df5.Close.shift(1)).abs(),
                      (df5.Low - df5.Close.shift(1)).abs()], axis=1).max(axis=1)
    datr = trng.groupby(day5).mean()
    for d, g in df5.groupby(day5):
        m = g.index.tz_convert(NY)
        on = g[(m.hour >= 18) | (m.hour < 9) | ((m.hour == 9) & (m.minute < 30))]
        rth = g[(m.hour * 60 + m.minute >= 570) & (m.hour * 60 + m.minute < 960)]
        onr[d] = float(on.High.max() - on.Low.min()) if len(on) else np.nan
        pdr[d] = float(rth.High.max() - rth.Low.min()) if len(rth) else np.nan
        atr14[d] = float(datr.get(d, np.nan))
    onr_s = pd.Series(onr).sort_index(); pdr_s = pd.Series(pdr).sort_index()
    onr_pct = onr_s.rank(pct=True)                      # full-sample pctile (context label)
    c1 = d1["close"]; c1_idx = d1.index

    recs = []
    per_day_count = {}
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
        ts = pd.Timestamp(fi[fb]); dd = ts.tz_convert(NY).normalize()
        k = per_day_count.get(dd, 0) + 1; per_day_count[dd] = k
        tsn = ts.tz_localize(None) if ts.tzinfo else ts
        pos = c1_idx.searchsorted(tsn, "right") - 1
        opn = c1_idx.searchsorted(tsn.normalize() + pd.Timedelta(hours=9, minutes=30), "left")
        drift_abs = abs(float(c1.iloc[pos] - c1.iloc[min(opn, pos)])) if pos >= 0 else np.nan
        a = atr14.get(dd, np.nan)
        recs.append(dict(ts=ts, R=w[0], win=w[0] > 0, mae_r=w[1], risk_usd=risk * 2.0,
                         grade=str(t.grade), dow=str(t.dow), nth=k,
                         onr_pct=float(onr_pct.get(dd, np.nan)),
                         margin=(drift_abs / (a * 12) if a and a == a else np.nan)))  # vs ~daily ATR
    return pd.DataFrame(recs)


def era_cut(df, col, label):
    d = df.dropna(subset=[col])
    g = d.groupby([col, d.ts < HO]).agg(n=("R", "size"), WR=("win", "mean"), expR=("R", "mean"))
    print(f"\n--- {label} ---")
    for (b, is_is), r in g.iterrows():
        print(f"  {str(b):<12} {'IS' if is_is else 'HO'}  n={int(r.n):>4}  WR={100*r.WR:5.1f}%  expR={r.expR:+.3f}")


def eval_axes(df, weights, budget, tag):
    spec = SPECS["50K"]
    ev = []
    for _, t in df.iterrows():
        wmult = weights(t) if weights else 1.0
        if wmult <= 0:
            continue
        q = min(40, int(budget * wmult // t.risk_usd))
        if q < 1:
            continue
        ev.append(dict(ts=t.ts, pnl=t.R * t.risk_usd * q, mae=min(0.0, t.mae_r) * t.risk_usd * q))
    ev.sort(key=lambda e: e["ts"])
    days = day_rows(ev, spec["stop"], spec["dll"])
    starts, seen = [], set()
    for i, (d, _, _) in enumerate(days):
        if d not in seen and (days[-1][0] - d).days > 30:
            seen.add(d); starts.append(i)
    res = [eval_run(days, s, spec) for s in starts]
    n = len(res)
    p = 100 * sum(1 for r in res if r[0] == "PASS") / n
    b = 100 * sum(1 for r in res if r[0] == "BUST") / n
    x = 100 * sum(1 for r in res if r[0] == "EXPIRE") / n
    md = int(np.median([r[1] for r in res if r[0] == "PASS"]) or 0) if p else 0
    early = [r for r, s in zip(res, starts) if days[s][0] < HO]
    late = [r for r, s in zip(res, starts) if days[s][0] >= HO]
    pe = 100 * sum(1 for r in early if r[0] == "PASS") / max(1, len(early))
    pl = 100 * sum(1 for r in late if r[0] == "PASS") / max(1, len(late))
    print(f"  {tag:<34} pass {p:5.1f}%  bust {b:5.1f}%  exp {x:4.1f}%  med {md:>2}d  "
          f"IS {pe:5.1f}% / HO {pl:5.1f}%")
    return p, b


def main():
    d1_tz = RD.load_1m(); d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m(); mp = M1Map(d1, df5)
    df = build(df5, mp, d1_tz, d1)
    print(f"trades: {len(df)} · WR {100*df.win.mean():.1f}% · expR {df.R.mean():+.3f}")

    df["onr_b"] = pd.cut(df.onr_pct, [0, .5, .9, 1.01], labels=["<p50", "p50-90", ">p90"])
    df["mar_b"] = pd.cut(df.margin, [0, .25, .6, 99], labels=["<0.25", "0.25-0.6", ">0.6"])
    df["nth_b"] = np.where(df.nth == 1, "1st", "2nd+")
    era_cut(df, "dow", "day of week")
    era_cut(df, "nth_b", "first vs later trade of day")
    era_cut(df, "onr_b", "overnight range pctile")
    era_cut(df, "mar_b", "D1c drift margin (frac of daily range)")

    print("\n=== EVAL AXES (50K, DLL-honest) ===")
    for budget in (1_600, 1_200):
        print(f"-- budget ${budget:,} --")
        eval_axes(df, None, budget, "BASELINE (locked)")
        eval_axes(df, lambda t: 1.30 if t.grade in ("C", "D") else 0.80, budget,
                  "C1 TILT grade C/D x1.3, A/B x0.8")


if __name__ == "__main__":
    main()
