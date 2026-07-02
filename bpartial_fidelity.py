"""FIDELITY CORRECTION: deployed A10/B5/mm6 Apex-50K eval pass-rate with Profile B modelled
as the REAL live partial (exit3_split @ +1R / +1.5R, shared stop) instead of the eval harness's
single-1.5R-target stand-in.

Incumbent (current dashboard model): B = full size to a single 1.5R target  -> apex_eval_deployed.b_events.
Candidate  (live-faithful): B = exit3_split(5) = 2 MNQ @ +1R + 3 MNQ @ +1.5R, shared stop, position-
weighted MAE (lower drawdown). Same A@10 and Momentum@6 in both arms (paired).

Metric: Apex-50K EOD-drawdown eval PASS% (EOD.eval_eod). Real Databento NQ 1m -> 5m.
Reports: full-history, IS/OOS time splits (x2), and block-bootstrap MC (>=1000 paths) median/p5/p95,
candidate-minus-incumbent paired.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))

import apex_eval_deployed as H
import apex_eval_eod as EOD
import funded_rules as FR
import run_d1c_real as RD
from config_defaults import exit3_split

SPEC = FR.APEX_ACCOUNTS["50K"]
NY = "America/New_York"
DPP = 2.0
B_COST = 0.75
A_SIZE, B_SIZE, M_SIZE = 10, 5, 6


def load_databento_5m():
    d1 = RD.load_1m()
    ag = lambda c, h: getattr(d1[c].resample("5min", label="left", closed="left"), h)()
    df5 = pd.DataFrame({"Open": ag("open", "first"), "High": ag("high", "max"),
                        "Low": ag("low", "min"), "Close": ag("close", "last"),
                        "Volume": ag("volume", "sum")}).dropna(subset=["Open"])
    idx = df5.index
    df5.index = idx.tz_localize(NY) if idx.tz is None else idx.tz_convert(NY)
    df5 = df5[~df5.index.duplicated(keep="last")].sort_index()
    df5.index.name = None
    return df5


def b_events_partial(df5, n1, n2):
    """Profile B with the LIVE partial: n1 contracts exit @ +1R, n2 @ +1.5R, shared 1R stop.
    Identical signal/stop/1.5R geometry to apex_eval_deployed.b_events — only the exit is split.
    Position-weighted MAE/MFE (full size until +1R banked, then n2 size). Stop has intrabar priority
    (matches the single-target convention)."""
    df = df5.copy()
    et = df.index.tz_convert(NY); mins = et.hour * 60 + et.minute
    df["rth"] = (mins >= 570) & (mins < 960)
    df["day"] = et.normalize().tz_localize(None)
    pc = df.Close.shift(1)
    trng = pd.concat([df.High - df.Low, (df.High - pc).abs(), (df.Low - pc).abs()], axis=1).max(axis=1)
    df["atr"] = trng.rolling(14).mean()
    Hh, Ll, Cc = df.High.values, df.Low.values, df.Close.values
    atrv = df["atr"].values; idx = df.index; n = len(Cc); rth = df["rth"].values
    ntot = n1 + n2
    ev = []
    for d0, g in df.groupby("day"):
        r = g[g.rth]
        if len(r) < 20:
            continue
        o_end = r.index[0] + pd.Timedelta(minutes=15)
        orng = r[r.index < o_end]
        if len(orng) < 2:
            continue
        orh, orl = orng.High.max(), orng.Low.min()
        atr0 = atrv[idx.get_loc(orng.index[-1])]
        if not atr0 or np.isnan(atr0):
            continue
        post = r[r.index >= o_end]; broke = False
        for t in post.itertuples():
            if broke:
                break
            gi = idx.get_loc(t.Index)
            for d, lvl in ((1, orh), (-1, orl)):
                br = (t.Close > lvl) if d > 0 else (t.Close < lvl)
                if not br:
                    continue
                broke = True
                fill = None
                for x in range(gi + 1, min(gi + 7, n)):
                    if Ll[x] <= lvl <= Hh[x]:
                        fill = x; break
                if fill is None:
                    break
                entry = lvl
                stop = entry - d * 1.0 * atr0
                t1 = entry + d * 1.0 * atr0
                t15 = entry + d * 1.5 * atr0
                open1, open2 = n1, n2          # contracts still open in each leg
                realized_pts = 0.0             # sum of per-contract point pnl across closed contracts
                mae_w = 0.0; mfe_w = 0.0       # contract-weighted point excursions (worst/best unrealized)
                done = False
                for x in range(fill, min(fill + 24, n)):
                    open_ct = open1 + open2
                    low_exc = (Ll[x] - entry) * d
                    high_exc = (Hh[x] - entry) * d
                    # F3 fix (2026-07-02): for shorts the ADVERSE excursion is the HIGH side
                    mae_w = min(mae_w, (low_exc if d > 0 else high_exc) * open_ct)
                    mfe_w = max(mfe_w, (high_exc if d > 0 else low_exc) * open_ct)
                    # stop first (intrabar priority): close everything open at stop
                    stop_hit = (Ll[x] <= stop) if d > 0 else (Hh[x] >= stop)
                    if stop_hit:
                        realized_pts += open_ct * (stop - entry) * d
                        open1 = open2 = 0; done = True; break
                    # +1R leg
                    t1_hit = (Hh[x] >= t1) if d > 0 else (Ll[x] <= t1)
                    if t1_hit and open1 > 0:
                        realized_pts += open1 * (t1 - entry) * d
                        open1 = 0
                    # +1.5R leg
                    t15_hit = (Hh[x] >= t15) if d > 0 else (Ll[x] <= t15)
                    if t15_hit and open2 > 0:
                        realized_pts += open2 * (t15 - entry) * d
                        open2 = 0
                    if open1 == 0 and open2 == 0:
                        done = True; break
                    if not rth[x] and x > fill:   # EOD flatten remaining
                        realized_pts += (open1 + open2) * (Cc[x] - entry) * d
                        open1 = open2 = 0; done = True; break
                if not done:
                    xlast = min(fill + 24, n) - 1
                    realized_pts += (open1 + open2) * (Cc[xlast] - entry) * d
                realized_pts -= B_COST * ntot       # per-contract cost
                ev.append(dict(ts=idx[fill], src="B",
                               pnl=realized_pts * DPP,
                               mfe=max(0.0, mfe_w) * DPP,
                               mae=min(0.0, mae_w) * DPP))
                break
    return ev


def scale_events(base, sc):
    ev = [dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*sc[e["src"]],
               mfe=e["mfe"]*sc[e["src"]], mae=e["mae"]*sc[e["src"]]) for e in base if sc[e["src"]] > 0]
    return H.apply_daily_stop(ev)


def passrate(ev, lo=None, hi=None):
    """EOD pass-rate over rolling day-starts; optionally restrict eval-START date to [lo,hi)."""
    starts = EOD.day_starts(ev)
    if lo is not None or hi is not None:
        sel = []
        for s in starts:
            d = pd.Timestamp(ev[s]["ts"]).tz_localize(None) if pd.Timestamp(ev[s]["ts"]).tz else pd.Timestamp(ev[s]["ts"])
            if lo is not None and d < lo: continue
            if hi is not None and d >= hi: continue
            sel.append(s)
        starts = sel
    if not starts:
        return None, 0
    out = [EOD.eval_eod(ev, s, SPEC) for s in starts]
    p, b, x, md = EOD.summarize(out)
    return p, len(starts)


# ---------- block bootstrap over trading days (paired single vs partial) ----------
def by_day(ev):
    d = {}
    for e in ev:
        k = pd.Timestamp(e["ts"]).normalize()
        d.setdefault(k, []).append(e)
    return d


def synth_passrate(day_keys, day_map_inc, day_map_cand, rng, block, rule_eval):
    """Build one synthetic history by moving-block resampling trading days; reassign sequential
    business dates; compute EOD pass-rate for incumbent and candidate on the SAME day sequence."""
    Ld = len(day_keys); horizon = Ld
    # moving-block indices with wraparound
    idxs = np.empty(horizon, dtype=int); k = 0
    while k < horizon:
        s = rng.integers(0, Ld); m = min(block, horizon - k)
        idxs[k:k+m] = (s + np.arange(m)) % Ld; k += m
    # synthetic business dates
    base_date = pd.Timestamp("2021-01-04")
    bdates = pd.bdate_range(base_date, periods=horizon)
    inc_ev, cand_ev = [], []
    for j, di in enumerate(idxs):
        key = day_keys[di]; nd = bdates[j]
        for src_map, sink in ((day_map_inc, inc_ev), (day_map_cand, cand_ev)):
            for e in src_map.get(key, []):
                ts = pd.Timestamp(e["ts"])
                newts = pd.Timestamp(nd.year, nd.month, nd.day, ts.hour, ts.minute)
                sink.append(dict(ts=newts, src=e["src"], pnl=e["pnl"], mfe=e["mfe"], mae=e["mae"]))
    inc_ev.sort(key=lambda e: e["ts"]); cand_ev.sort(key=lambda e: e["ts"])
    pi, _ = rule_eval(inc_ev); pc, _ = rule_eval(cand_ev)
    return pi, pc


def main():
    print("loading real Databento NQ 1m -> 5m…", flush=True)
    df5 = load_databento_5m()
    print(f"  bars {df5.index.min().date()} -> {df5.index.max().date()}  ({len(df5):,})", flush=True)

    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    A = H.a_events(df5)                       # unit A
    Bsingle_unit = H.b_events(df5)            # unit B single-1.5R (incumbent stand-in)
    M = H.m_events(df5)                       # unit momentum
    n1, n2 = exit3_split(B_SIZE)
    print(f"  Profile B partial split @ B={B_SIZE}: {n1} @ +1R  +  {n2} @ +1.5R", flush=True)
    Bpartial = b_events_partial(df5, n1, n2)  # ALREADY at size B_SIZE (split is size-dependent)

    sc = {"A": A_SIZE, "B": B_SIZE, "M": M_SIZE}
    # incumbent: scale unit B by B_SIZE (single target). candidate: partial already @ B_SIZE.
    inc_base = [dict(e) for e in A] + [dict(e) for e in Bsingle_unit] + [dict(e) for e in M]
    ev_inc = scale_events(inc_base, sc)
    # candidate: A and M scaled, B = partial (B coefficient already baked in -> scale B by 1)
    cand_base = [dict(e) for e in A] + [dict(e) for e in M]
    ev_cand_AM = scale_events(cand_base, {"A": A_SIZE, "B": 0, "M": M_SIZE})
    ev_cand = H.apply_daily_stop(ev_cand_AM + Bpartial)

    # sanity: single-B totals
    bs = [e for e in ev_inc if e["src"] == "B"]; bp = [e for e in ev_cand if e["src"] == "B"]
    print(f"  B events inc(single@5)={len(bs)}  cand(partial 2+3)={len(bp)}", flush=True)
    print(f"  B net$ inc={sum(e['pnl'] for e in bs):,.0f}  cand={sum(e['pnl'] for e in bp):,.0f}", flush=True)
    print(f"  B sum-MAE$ inc={sum(e['mae'] for e in bs):,.0f}  cand={sum(e['mae'] for e in bp):,.0f}  (less-negative = gentler DD)", flush=True)

    # ---- full history ----
    pi, ni = passrate(ev_inc); pc, nc = passrate(ev_cand)
    print(f"\n  FULL HISTORY EOD pass%:  incumbent(single) {pi:.1f}% (n={ni})   candidate(partial) {pc:.1f}% (n={nc})   Δ {pc-pi:+.1f}pp")

    # ---- IS/OOS splits ----
    def split_report(name, lo_is, hi_is, lo_oos, hi_oos):
        pii, _ = passrate(ev_inc, lo_is, hi_is); pci, _ = passrate(ev_cand, lo_is, hi_is)
        pio, _ = passrate(ev_inc, lo_oos, hi_oos); pco, _ = passrate(ev_cand, lo_oos, hi_oos)
        print(f"\n  {name}")
        print(f"    IS  inc {pii:.1f}%  cand {pci:.1f}%  Δ {pci-pii:+.1f}pp")
        print(f"    OOS inc {pio:.1f}%  cand {pco:.1f}%  Δ {pco-pio:+.1f}pp")
        return (pii, pci, pio, pco)
    T = pd.Timestamp
    s1 = split_report("SPLIT 1  IS 2021-2024 / OOS 2025-2026", None, T("2025-01-01"), T("2025-01-01"), None)
    s2 = split_report("SPLIT 2  IS 2021-2023 / OOS 2024-2026", None, T("2024-01-01"), T("2024-01-01"), None)

    # ---- block-bootstrap MC ----
    day_keys = sorted(by_day(ev_inc).keys())
    dmi = by_day(ev_inc); dmc = by_day(ev_cand)
    rule = lambda ev: passrate(ev)
    NPATH = 1000
    for block in (5, 10, 20):
        rng = np.random.default_rng(20260630 + block)
        di = np.empty(NPATH); dc = np.empty(NPATH); dd = np.empty(NPATH)
        for p in range(NPATH):
            pi_, pc_ = synth_passrate(day_keys, dmi, dmc, rng, block, rule)
            di[p] = pi_; dc[p] = pc_; dd[p] = pc_ - pi_
        q = lambda a, pct: float(np.percentile(a, pct))
        print(f"\n  MC block={block}d  N={NPATH}")
        print(f"    incumbent pass%  median {np.median(di):.1f}  p5 {q(di,5):.1f}  p95 {q(di,95):.1f}")
        print(f"    candidate pass%  median {np.median(dc):.1f}  p5 {q(dc,5):.1f}  p95 {q(dc,95):.1f}")
        print(f"    Δ (cand-inc)     median {np.median(dd):+.1f}  p5 {q(dd,5):+.1f}  p95 {q(dd,95):+.1f}  | frac>0 {100*np.mean(dd>0):.0f}%")


if __name__ == "__main__":
    main()
