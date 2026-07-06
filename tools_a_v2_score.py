"""PROFILE-A V2 QUALITY SCORE RESEARCH (2026-07-02). RESEARCH ONLY — locked machine untouched.

Evidence-driven rebuild of the trade-quality score for the certified A stream (435 D1c-kept trades,
1m-truth Exit#3 outcomes). Discipline against n=435 overfitting:
  * every feature judged on IS(≤2024)/HO(2025+) SIGN CONSISTENCY, not magnitude;
  * V2 components are selected on IS ONLY (top era-stable features by |spearman| with sign rule
    frozen from IS medians), then the composed score is evaluated BLIND on HO;
  * max 8 components, integer ±1 votes, no fitted weights;
  * final test = eval axes (rev-b machine, $1,200, DLL-honest) with a sizing tilt, vs baseline and
    vs the old grade tilt.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from scipy.stats import spearmanr

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

    et5 = df5.index.tz_convert(NY); day5 = et5.normalize()
    trng = pd.concat([df5.High - df5.Low, (df5.High - df5.Close.shift(1)).abs(),
                      (df5.Low - df5.Close.shift(1)).abs()], axis=1).max(axis=1)
    datr = trng.groupby(day5).mean()
    atr_pct = datr.rank(pct=True)
    onr, pdr, rth_open, prior_close = {}, {}, {}, {}
    vwap = {}
    for d, g in df5.groupby(day5):
        m = g.index.tz_convert(NY); mins = m.hour * 60 + m.minute
        on = g[(m.hour >= 18) | (mins < 570)]
        rth = g[(mins >= 570) & (mins < 960)]
        onr[d] = float(on.High.max() - on.Low.min()) if len(on) else np.nan
        pdr[d] = float(rth.High.max() - rth.Low.min()) if len(rth) else np.nan
        if len(rth):
            rth_open[d] = float(rth.Open.iloc[0]); prior_close[d] = float(g.Close.iloc[0])
            tp = (rth.High + rth.Low + rth.Close) / 3
            v = rth.Volume.replace(0, 1)
            vwap[d] = (tp * v).cumsum() / v.cumsum()
    onr_pct = pd.Series(onr).rank(pct=True); pdr_pct = pd.Series(pdr).rank(pct=True)
    # HTF trend proxies: EMA slope sign on 15m/1h/4h closes at fill
    c15 = df5.Close.resample("15min").last().dropna(); e15 = c15.ewm(span=20).mean()
    c1h = df5.Close.resample("1h").last().dropna(); e1h = c1h.ewm(span=20).mean()
    c4h = df5.Close.resample("4h").last().dropna(); e4h = c4h.ewm(span=20).mean()
    s15 = np.sign(e15.diff()); s1h = np.sign(e1h.diff()); s4h = np.sign(e4h.diff())
    c1 = d1["close"]; c1_idx = c1.index

    T = {"T1": 1, "T2": 2, "T3": 3}
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
        ts = pd.Timestamp(fi[fb]); tsl = ts.tz_convert(NY); dd = tsl.normalize()
        tsn = ts.tz_localize(None) if ts.tzinfo else ts
        pos = c1_idx.searchsorted(tsn, "right") - 1
        opn = c1_idx.searchsorted(tsn.normalize() + pd.Timedelta(hours=9, minutes=30), "left")
        margin = abs(float(c1.iloc[pos] - c1.iloc[min(opn, pos)])) if pos >= 0 else np.nan
        a = float(datr.get(dd, np.nan))
        vw = vwap.get(dd)
        vwd = np.nan
        if vw is not None:
            vi = vw.index.searchsorted(ts, "right") - 1
            if vi >= 0:
                vwd = (float(t.entry) - float(vw.iloc[vi])) * d / max(a, 1e-9)
        def _sl(series):
            i = series.index.searchsorted(ts, "right") - 1   # tz-aware (resampled from df5)
            return float(series.iloc[i]) * d if i >= 0 else np.nan
        gap = ((rth_open.get(dd, np.nan) - prior_close.get(dd, np.nan)) * d / max(a, 1e-9))
        recs.append(dict(
            ts=ts, R=w[0], win=w[0] > 0, mae_r=w[1], risk_usd=risk * 2.0, grade=str(t.grade),
            # structure
            tier=T.get(str(t.liq_tier), 2), disp=int(t.disp_strength),
            mss_speed=int(t.mss_bar) - int(t.sweep_bar), fill_lag=fb - int(t.mss_bar),
            entry_from_sweep=abs(float(t.entry) - float(t.swept_px)) / risk,
            stop_pts=risk, fvg_size=float(t.fvg_size) / max(risk, 1e-9), rr_avail=float(t.rr),
            # session / context
            t_open=tsl.hour * 60 + tsl.minute - 570, in_sb=int(600 <= tsl.hour * 60 + tsl.minute < 660),
            onr=float(onr_pct.get(dd, np.nan)), pdrng=float(pdr_pct.get(dd, np.nan)),
            atrp=float(atr_pct.get(dd, np.nan)), gap_a=gap, vwap_d=vwd,
            # HTF alignment (signed with trade direction)
            htf15=_sl(s15), htf1h=_sl(s1h), htf4h=_sl(s4h),
            d_draw=int(bool(t.d_draw_aligned)), w_draw=int(bool(t.w_draw_aligned)),
            pd_align=int((d > 0 and str(t.pd_status) == "disc") or (d < 0 and str(t.pd_status) == "prem")),
            # d1c
            d1c_margin=margin / max(a * 12, 1e-9),
            conf=int(t.confluence_score)))
    return pd.DataFrame(recs)


FEATURES = ["tier", "disp", "mss_speed", "fill_lag", "entry_from_sweep", "stop_pts", "fvg_size",
            "rr_avail", "t_open", "in_sb", "onr", "pdrng", "atrp", "gap_a", "vwap_d",
            "htf15", "htf1h", "htf4h", "d_draw", "w_draw", "pd_align", "d1c_margin", "conf"]


def importance(df):
    is_m = df.ts < HO
    rows = []
    for f in FEATURES:
        a = df.loc[is_m, [f, "R"]].dropna(); b = df.loc[~is_m, [f, "R"]].dropna()
        if len(a) < 40 or len(b) < 30 or a[f].nunique() < 2 or b[f].nunique() < 2:
            continue
        ri, _ = spearmanr(a[f], a.R); rh, _ = spearmanr(b[f], b.R)
        rows.append((f, ri, rh, np.sign(ri) == np.sign(rh), min(abs(ri), abs(rh))))
    imp = pd.DataFrame(rows, columns=["feat", "rho_IS", "rho_HO", "sign_ok", "strength"])
    return imp.sort_values("strength", ascending=False)


def main():
    d1_tz = RD.load_1m(); d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m(); mp = M1Map(d1, df5)
    df = build(df5, mp, d1_tz, d1)
    is_m = df.ts < HO
    print(f"trades {len(df)} (IS {is_m.sum()} / HO {(~is_m).sum()}) · WR {100*df.win.mean():.1f}%")

    imp = importance(df)
    print("\n=== FEATURE IMPORTANCE (spearman vs 1m-truth R; sign_ok = IS/HO agree) ===")
    print(imp.to_string(index=False, float_format=lambda x: f"{x:+.3f}"))

    # confluence paradox: correlate each score COMPONENT with R, both eras
    print("\n=== CONFLUENCE PARADOX DECOMPOSITION ===")
    comp = dict(disp_bonus=np.where(df.disp >= 3, 3, np.where(df.disp >= 2, 2, 0)),
                tier_pts=df.tier, sb_bonus=2 * df.in_sb, pd_bonus=2 * df.pd_align)
    for k, v in comp.items():
        a = spearmanr(v[is_m], df.R[is_m])[0]; b = spearmanr(v[~is_m], df.R[~is_m])[0]
        print(f"  {k:<10} rho_IS {a:+.3f}  rho_HO {b:+.3f}")
    # is the paradox just displacement? conf vs R within disp groups
    for g in (1, 2, 3):
        sub = df[df.disp == g]
        if len(sub) > 60:
            a = spearmanr(sub.conf[sub.ts < HO], sub.R[sub.ts < HO])[0]
            b = spearmanr(sub.conf[sub.ts >= HO], sub.R[sub.ts >= HO])[0]
            print(f"  conf|disp={g} rho_IS {a:+.3f} rho_HO {b:+.3f}  (n={len(sub)})")
    # what does high conf correlate with?
    hi = df.conf >= df.conf.median()
    for f in ("stop_pts", "disp", "t_open", "atrp", "entry_from_sweep"):
        print(f"  E[{f}] low-conf {df.loc[~hi, f].mean():.2f} vs high-conf {df.loc[hi, f].mean():.2f}")

    # === V2 SCORE: select on IS ONLY ===
    is_df = df[is_m]
    cand = []
    for f in FEATURES:
        a = is_df[[f, "R"]].dropna()
        if len(a) < 60 or a[f].nunique() < 2:
            continue
        rho = spearmanr(a[f], a.R)[0]
        cand.append((f, rho))
    cand = sorted(cand, key=lambda x: -abs(x[1]))[:8]
    med = {f: float(is_df[f].median()) for f, _ in cand}
    sgn = {f: (1 if rho > 0 else -1) for f, rho in cand}
    print("\n=== V2 COMPONENTS (selected on IS only) ===")
    for f, rho in cand:
        print(f"  {f:<18} IS rho {rho:+.3f} -> vote {'+' if sgn[f]>0 else '-'}1 when {'>' if sgn[f]>0 else '<='} {med[f]:.3g}")

    def v2(row):
        s = 0
        for f, _ in cand:
            v = row[f]
            if v != v:
                continue
            s += sgn[f] * (1 if v > med[f] else -1)
        return s
    df["v2"] = df.apply(v2, axis=1)
    # blind HO check of the composed score
    for era, sub in (("IS", df[is_m]), ("HO(blind)", df[~is_m])):
        rho = spearmanr(sub.v2, sub.R)[0]
        hi3 = sub[sub.v2 >= sub.v2.quantile(2/3)]; lo3 = sub[sub.v2 <= sub.v2.quantile(1/3)]
        print(f"  {era:<10} rho(v2,R) {rho:+.3f} · top-tercile WR {100*hi3.win.mean():.1f}% "
              f"expR {hi3.R.mean():+.3f} · bottom WR {100*lo3.win.mean():.1f}% expR {lo3.R.mean():+.3f}")

    # === EVAL AXES: rev-b machine ($1,200) — baseline vs old-grade tilt vs v2 tilt ===
    spec = SPECS["50K"]
    q23 = df.v2.quantile(2/3); q13 = df.v2.quantile(1/3)
    def axes(wfun, tag):
        ev = []
        for _, t in df.iterrows():
            m = wfun(t)
            q = min(40, int(1200 * m // t.risk_usd))
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
        early = [r for r, s in zip(res, starts) if days[s][0] < HO]
        late = [r for r, s in zip(res, starts) if days[s][0] >= HO]
        pe = 100 * sum(1 for r in early if r[0] == "PASS") / max(1, len(early))
        pl = 100 * sum(1 for r in late if r[0] == "PASS") / max(1, len(late))
        print(f"  {tag:<30} pass {p:5.1f} bust {b:5.1f} exp {x:4.1f} · IS {pe:5.1f} / HO {pl:5.1f}")
    print("\n=== EVAL AXES (rev-b $1,200, DLL-honest) ===")
    axes(lambda t: 1.0, "BASELINE (locked rev b)")
    axes(lambda t: 1.3 if t.grade in ("C", "D") else 0.8, "old-grade tilt (rejected)")
    axes(lambda t: 1.3 if t.v2 >= q23 else (0.8 if t.v2 <= q13 else 1.0), "V2-score tilt 1.3/1.0/0.8")


if __name__ == "__main__":
    main()
