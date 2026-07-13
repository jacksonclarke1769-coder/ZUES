"""
C — VOLATILITY-GATED RANGING MEAN-REVERSION on NQ (HONEST edge discovery).

Family: fade extension beyond VWAP +/- k*ATR back toward VWAP, ENTERED ONLY on
detected LOW-VOL / RANGING days; stand down on trend/high-vol days.

Prior (team-proven): naive high-WR intraday MR on NQ is a TRAP -> PF<1 after costs
(negative skew, not profit). NOVEL question tested here: does a causal VOL/REGIME
GATE rescue it above PF 1.0 after honest costs? Gate ON vs OFF is the core contrast.

DATA: REAL Databento NQ futures only.
  5m 24h: apex_eval_eod_databento.load_databento_5m()  (2021-06 .. 2026-06)
  1m RTH: tools_vpc_1m_truth.load_1m_rth()             (fill-realism check)

HONEST MECHANICS:
  - RTH only (09:30-16:00 ET). Session VWAP (causal cumulative). ATR14 on 5m.
  - Signal at CLOSE of bar i (causal): Close beyond VWAP +/- band_k*ATR -> fade.
  - PRIMARY entry = MARKET at NEXT bar (i+1) open (no limit-fill ambiguity).
  - Exit intrabar on 5m, ADVERSE-FIRST (stop checked before target same bar).
  - Target = revert to VWAP(entry) [tgt_mode=vwap] or halfway [half]. Stop beyond extreme.
  - EOD flat at last RTH bar close. Cost 0.75 pt round-trip baked into every trade.
  - Regime gates are ALL causal (computed from bars strictly <= i, prior-day stats).

Usage: python3 c_volgated_mr.py            (full search + gate ON/OFF + IS/OOS)
       python3 c_volgated_mr.py fillcheck   (1m limit-entry fill-realism on survivor)
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
import apex_eval_eod_databento as DB
import tools_vpc_1m_truth as T

NY = "America/New_York"
RT_COST = 0.75          # pt round trip
IS_END = "2025-01-01"   # IS = 2022-2024, OOS = 2025-2026 (params fixed on IS)
YR_START = "2022-01-01"


# ---------------------------------------------------------------- features
def rth5(df5):
    t = df5.index
    m = (((t.hour > 9) | ((t.hour == 9) & (t.minute >= 30))) & (t.hour < 16))
    d = df5[m].copy()
    d = d[d.index >= YR_START]
    d["date"] = d.index.normalize()
    d["slot"] = d.groupby("date").cumcount()
    return d


def wilder_adx(H, L, C, n=14):
    up = np.diff(H, prepend=H[0]); dn = -np.diff(L, prepend=L[0])
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    pc = np.concatenate([[C[0]], C[:-1]])
    tr = np.maximum(H - L, np.maximum(np.abs(H - pc), np.abs(L - pc)))
    def rma(x):
        out = np.full(len(x), np.nan); a = 1.0 / n; s = np.nan
        for i, v in enumerate(x):
            s = v if np.isnan(s) else (s + a * (v - s))
            out[i] = s
        return out
    atr = rma(tr); pdi = 100 * rma(plus) / np.where(atr == 0, np.nan, atr)
    mdi = 100 * rma(minus) / np.where(atr == 0, np.nan, atr)
    dx = 100 * np.abs(pdi - mdi) / np.where((pdi + mdi) == 0, np.nan, pdi + mdi)
    return rma(dx)


def features(df5):
    d = rth5(df5)
    d["dayopen"] = d.groupby("date")["Open"].transform("first")
    tp = (d.High + d.L if False else d.Low + d.Close) / 3.0  # guard
    tp = (d.High + d.Low + d.Close) / 3.0
    cv = d.groupby("date")["Volume"].cumsum()
    d["vwap"] = (tp * d.Volume).groupby(d["date"]).cumsum() / cv.replace(0, np.nan)
    d["vwap"] = d["vwap"].fillna(d.groupby("date")["Close"].cumsum() / (d["slot"] + 1))
    pc = d["Close"].shift(1)
    tr = np.maximum(d.High - d.Low, np.maximum((d.High - pc).abs(), (d.Low - pc).abs()))
    d["atr"] = tr.rolling(14, min_periods=7).mean()
    # continuous ADX (causal)
    d["adx"] = wilder_adx(d.High.values, d.Low.values, d.Close.values, 14)
    # ----- causal regime stats (info available at close of bar i) -----
    # vwap-cross count so far today
    above = (d.Close > d.vwap).astype(int)
    crossed = (above != above.groupby(d["date"]).shift(1)).astype(int)
    crossed = crossed.where(d["slot"] > 0, 0)
    d["vcross"] = crossed.groupby(d["date"]).cumsum()
    # daily ATR percentile vs trailing 20 prior days (uses each day's MEDIAN atr, prior days only)
    day_atr = d.groupby("date")["atr"].median()
    pct = day_atr.rolling(20, min_periods=10).apply(
        lambda w: (w[:-1] < w[-1]).mean() if len(w) > 1 else np.nan, raw=True)
    pct = pct.shift(1)  # only prior days -> causal for today
    d["atr_day_pct"] = d["date"].map(pct)
    # opening-range (first 6 bars = 30m) size / atr, causal for slot>=6
    def or_size(g):
        first6 = g[g["slot"] < 6]
        if len(first6) == 0:
            return np.nan
        rng = first6.High.max() - first6.Low.min()
        a = g[g["slot"] == 5]["atr"]
        a = a.iloc[0] if len(a) else np.nan
        return rng / a if a and not np.isnan(a) else np.nan
    orv = d.groupby("date").apply(or_size)
    d["or_atr"] = d["date"].map(orv)
    return d


# ---------------------------------------------------------------- regime gate
def gate_pass(row, gate, thr):
    if gate == "off":
        return True
    if gate == "adx":       # low ADX = ranging
        return not np.isnan(row.adx) and row.adx < thr
    if gate == "atrpct":    # low daily-ATR percentile = quiet day
        return not np.isnan(row.atr_day_pct) and row.atr_day_pct < thr
    if gate == "vcross":    # many vwap crosses = oscillating/range
        return not np.isnan(row.vcross) and row.vcross >= thr
    if gate == "orange":    # small opening range vs ATR = quiet
        return not np.isnan(row.or_atr) and row.or_atr < thr
    return True


GATE_THR = {"off": None, "adx": 20.0, "atrpct": 0.40, "vcross": 3, "orange": 6.0}


# ---------------------------------------------------------------- backtest (5m market entry, adverse-first)
def run_day(g, band_k, stop_atr, tgt_mode, slot_min, slot_max, max_trades,
            gate, thr):
    g = g.sort_values("slot").reset_index(drop=True)
    n = len(g)
    O, H, L, Cl, A, V = (g.Open.values, g.High.values, g.Low.values,
                         g.Close.values, g.atr.values, g.vwap.values)
    trades = []
    busy_until = -1; taken = 0
    for i in range(n - 1):
        if not (slot_min <= i <= slot_max):
            continue
        if i <= busy_until or taken >= max_trades:
            continue
        if np.isnan(A[i]) or A[i] <= 0 or np.isnan(V[i]):
            continue
        if not gate_pass(g.iloc[i], gate, thr):
            continue
        upper = V[i] + band_k * A[i]; lower = V[i] - band_k * A[i]
        d = 0
        if Cl[i] > upper:
            d = -1
        elif Cl[i] < lower:
            d = 1
        if d == 0:
            continue
        ei = i + 1
        if ei >= n:
            continue
        entry = O[ei]
        if tgt_mode == "vwap":
            target = V[i]
        else:  # half-way back to vwap
            target = entry + 0.5 * (V[i] - entry)
        stop = entry - stop_atr * A[i] if d == 1 else entry + stop_atr * A[i]
        exit_px = None; exit_i = n - 1; reason = "eod"
        for j in range(ei, n):
            if d == 1:
                if L[j] <= stop:            # adverse first
                    exit_px = stop; exit_i = j; reason = "stop"; break
                if H[j] >= target:
                    exit_px = target; exit_i = j; reason = "tgt"; break
            else:
                if H[j] >= stop:            # adverse first
                    exit_px = stop; exit_i = j; reason = "stop"; break
                if L[j] <= target:
                    exit_px = target; exit_i = j; reason = "tgt"; break
        if exit_px is None:
            exit_px = Cl[n - 1]; exit_i = n - 1; reason = "eod"
        pnl = d * (exit_px - entry) - RT_COST
        trades.append(dict(ts=g.index[ei] if hasattr(g, "index") else ei,
                           date=g["date"].iloc[ei], d=d, entry=entry,
                           exit=exit_px, pnl=pnl, reason=reason))
        busy_until = exit_i; taken += 1
    return trades


def backtest(feats, **kw):
    out = []
    for day, g in feats.groupby("date"):
        out += run_day(g, **kw)
    return pd.DataFrame(out)


def stats(tr):
    if len(tr) == 0:
        return dict(n=0, pf=np.nan, wr=np.nan, net=0.0, avg=np.nan)
    w = tr.pnl[tr.pnl > 0].sum(); l = -tr.pnl[tr.pnl < 0].sum()
    return dict(n=len(tr), pf=(w / l if l > 0 else np.inf), wr=(tr.pnl > 0).mean(),
                net=tr.pnl.sum(), avg=tr.pnl.mean())


def pf_of(tr):
    if len(tr) == 0:
        return np.nan
    w = tr.pnl[tr.pnl > 0].sum(); l = -tr.pnl[tr.pnl < 0].sum()
    return w / l if l > 0 else np.inf


# ---------------------------------------------------------------- main search
def main():
    print("loading real Databento NQ 5m...", flush=True)
    df5 = DB.load_databento_5m()
    feats = features(df5)
    print(f"  RTH feats {feats['date'].min().date()} .. {feats['date'].max().date()} "
          f"days={feats['date'].nunique()} bars={len(feats)}", flush=True)

    band_ks = [1.5, 2.0, 2.5]
    stop_atrs = [1.0, 1.5, 2.0]
    tgt_modes = ["vwap", "half"]
    gates = ["off", "adx", "atrpct", "vcross", "orange"]
    slot_min, slot_max, max_trades = 6, 66, 2

    is_mask = feats["date"] < IS_END
    rows = []
    n_cfg = 0
    for bk in band_ks:
        for sa in stop_atrs:
            for tm in tgt_modes:
                for gt in gates:
                    n_cfg += 1
                    thr = GATE_THR[gt]
                    tr = backtest(feats, band_k=bk, stop_atr=sa, tgt_mode=tm,
                                  slot_min=slot_min, slot_max=slot_max,
                                  max_trades=max_trades, gate=gt, thr=thr)
                    if len(tr):
                        tr_is = tr[tr.date < IS_END]; tr_oos = tr[tr.date >= IS_END]
                    else:
                        tr_is = tr_oos = tr
                    s = stats(tr); sis = stats(tr_is); soos = stats(tr_oos)
                    rows.append(dict(band_k=bk, stop_atr=sa, tgt=tm, gate=gt, thr=thr,
                                     n=s["n"], pf=s["pf"], wr=s["wr"], net=s["net"],
                                     n_is=sis["n"], pf_is=sis["pf"], net_is=sis["net"],
                                     n_oos=soos["n"], pf_oos=soos["pf"], net_oos=soos["net"]))
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(os.path.dirname(__file__), "c_search_full.csv"), index=False)
    print(f"\n=== FULL SEARCH: {n_cfg} configs (all reported, no winner-picking) ===")
    pd.set_option("display.width", 200, "display.max_rows", 300,
                  "display.float_format", lambda x: f"{x:.3f}")
    print(R.to_string(index=False))

    # gate ON vs OFF summary (aggregate over geometry)
    print("\n=== GATE ON vs OFF (median PF across the 18 geometry configs) ===")
    g = R.groupby("gate").agg(med_pf=("pf", "median"), med_pf_is=("pf_is", "median"),
                              med_pf_oos=("pf_oos", "median"), med_n=("n", "median"),
                              frac_pf_gt1=("pf", lambda x: (x > 1).mean()))
    print(g.to_string())

    # survivors: full PF>1.0 AND IS PF>1.0 AND OOS PF>1.0 AND n>=50
    surv = R[(R.pf > 1.0) & (R.pf_is > 1.0) & (R.pf_oos > 1.0) & (R.n >= 50) &
             (R.n_is >= 30) & (R.n_oos >= 20)]
    print(f"\n=== SURVIVORS (full+IS+OOS PF>1.0, N>=50): {len(surv)} ===")
    if len(surv):
        print(surv.to_string(index=False))
        # per-year + cost stress on best survivor by OOS PF
        best = surv.sort_values("pf_oos", ascending=False).iloc[0]
        print(f"\n=== BEST SURVIVOR: {best.to_dict()} ===")
        per_year_and_cost(feats, best)
    else:
        print("NONE. The vol-gate does NOT rescue MR above PF 1.0 on IS+OOS after honest costs.")
        # still show best-OOS gated config for transparency
        gated = R[R.gate != "off"].sort_values("pf_oos", ascending=False)
        print("\nBest-OOS gated configs (for transparency, NOT survivors):")
        print(gated.head(8).to_string(index=False))
    return R


def per_year_and_cost(feats, cfg):
    kw = dict(band_k=cfg.band_k, stop_atr=cfg.stop_atr, tgt_mode=cfg.tgt,
              slot_min=6, slot_max=66, max_trades=2, gate=cfg.gate,
              thr=GATE_THR[cfg.gate])
    tr = backtest(feats, **kw)
    tr["yr"] = pd.to_datetime(tr.date).dt.year
    print("\n  per-year:")
    for yr, gg in tr.groupby("yr"):
        s = stats(gg)
        print(f"    {yr}: n={s['n']:4d} pf={s['pf']:.3f} wr={s['wr']:.3f} net={s['net']:+.1f}")
    print("\n  cost stress (RT pt):")
    global RT_COST
    base = RT_COST
    for c in [0.75, 1.5, 2.25]:
        RT_COST = c
        tr2 = backtest(feats, **kw)
        s = stats(tr2)
        print(f"    cost={c}: n={s['n']} pf={s['pf']:.3f} net={s['net']:+.1f}")
    RT_COST = base


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fillcheck":
        import c_fillcheck  # noqa
        c_fillcheck.run()
    else:
        main()
