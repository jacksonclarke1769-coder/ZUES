"""VALIDATE EXIT MODEL for the DEPLOYED Apex eval (A10/B5/mm6), real Databento, EOD rule.

Compares exit variants by RE-DERIVING each trade's outcome from its per-trade mfe/mae:
  - incumbent 50/50  : A = 0.5@+1R + 0.5@+2R (shared -1R stop); B = 0.5@+1R + 0.5@+1.5R
  - single@1R / 1.5R / 2R : full size to one fixed target, -1R stop.
Re-derivation rule (matches model01's own hit_1r/hit_2r convention, line 315):
  a trade reaches +XR iff its max-favorable-excursion mfe_r >= X (in R); else it stops at -1R.
mfe_r/mae_r are faithful R-excursions from model01._simulate (capped at the 2R original exit, so
variants with target <=2R are exactly re-derivable; >2R is NOT and is excluded).

Momentum (flat-at-EOD intraday position) has no fixed-R target/stop, so its exit is UNCHANGED
across all variants (only A & B exits are swapped).

Outputs per variant: full-history eval PASS%, IS/OOS (2021-24 / 2025-26) + an alt split,
block-bootstrap MC (>=1000 paths, 10-day blocks) median/p5/p95 of eval PASS%, total-R, A maxDD(R).
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))

import apex_eval_deployed as H
import apex_eval_eod as EOD
import apex_eval_eod_databento as DB
import funded_rules as FR
import strategy_engine_profileA as E
import model01_sweep_mss_fvg as M1
import config

SPEC = FR.APEX_ACCOUNTS["50K"]
NY = "America/New_York"
DPP = 2.0
A_SIZE, B_SIZE, M_SIZE = 10, 5, 6
B_COST = 0.75
EXPIRE_DAYS = 30
DAILY_STOP = -550.0
N_PATHS = 1200
BLOCK = 10
np.random.seed(11)


# ---------- A trades: re-simulate the EXACT exit per variant via the validated engine ----------
# incumbent = PROFILE_A (partial 0.5@1R + 0.5@2R, fixed_rr, the locked 57.5%-baseline exit).
# single@X = same setups/stop, partial=None, fixed_rr target at X (engine handles timeouts faithfully).
A_PARAMS = {
    "incumbent": {**E.PROFILE_A, "slip_ticks": 8},
    "single1":   {**E.PROFILE_A, "slip_ticks": 8, "partial": None, "rr": 1.0, "target_mode": "fixed_rr"},
    "single15":  {**E.PROFILE_A, "slip_ticks": 8, "partial": None, "rr": 1.5, "target_mode": "fixed_rr"},
    "single2":   {**E.PROFILE_A, "slip_ticks": 8, "partial": None, "rr": 2.0, "target_mode": "fixed_rr"},
}


def a_variant(feats, fi, variant):
    tr = M1.run(feats, "NQ", A_PARAMS[variant])
    tr = tr[tr.session == "ny_am"].copy()
    out = []
    for _, t in tr.iterrows():
        risk = abs(float(t["entry"]) - float(t["stop"]))
        if risk <= 0:
            continue
        fb = int(t["fill_bar"])
        ts = fi[fb] if 0 <= fb < len(fi) else pd.Timestamp(str(t["date"])).tz_localize(NY)
        out.append(dict(ts=pd.Timestamp(ts), src="A", R=float(t["r_result"]),
                        risk_usd=risk * DPP, mae_r=float(t["mae_r"])))
    return out


# ---------- B trades: simulate ALL exits in one bar-walk (stop-first, timeout at RTH close) ----------
def b_sim(df5):
    """Per B trade return realized-R for every variant + risk + worst adverse excursion (R)."""
    df = df5.copy()
    et = df.index.tz_convert(NY); mins = et.hour * 60 + et.minute
    df["rth"] = (mins >= 570) & (mins < 960)
    df["day"] = et.normalize().tz_localize(None)
    pc = df.Close.shift(1)
    trng = pd.concat([df.High - df.Low, (df.High - pc).abs(), (df.Low - pc).abs()], axis=1).max(axis=1)
    df["atr"] = trng.rolling(14).mean()
    H_, L_, C_ = df.High.values, df.Low.values, df.Close.values
    rthv = df["rth"].values
    atrv = df["atr"].values; idx = df.index; n = len(C_); out = []

    def walk(fill, d, entry, atr0, target_R, partial):
        """Realized R + mae(points) for stop=-1R(atr0), limit target at +target_R, optional partial
        [(1,0.5)] @ +1R; timeout -> close at RTH end. mae tracked ONLY until this variant's exit bar,
        using the validated deployed convention (apex_eval_deployed.py:120) -> single15 reproduces 57.5%."""
        stop = entry - d * atr0
        realized = 0.0; remaining = 1.0; took_partial = False; mae = 0.0
        for x in range(fill, min(fill + 24, n)):
            hi, lo = H_[x], L_[x]
            # adverse extreme is LOW for longs, HIGH for shorts (2026-07-02 audit F3: old short
            # branch (entry-hi)*d = hi-entry, POSITIVE under water -> real short MAE never recorded,
            # phantom MAE on winning shorts).
            mae = min(mae, (lo - entry) * d if d > 0 else (hi - entry) * d)
            # 1) stop first
            if (lo <= stop) if d > 0 else (hi >= stop):
                realized += remaining * (-1.0)
                return realized, mae
            # 2) partial @ +1R
            if partial and not took_partial:
                plvl = entry + d * 1.0 * atr0
                if (hi >= plvl) if d > 0 else (lo <= plvl):
                    realized += 0.5 * 1.0; remaining -= 0.5; took_partial = True
            # 3) final target
            tlvl = entry + d * target_R * atr0
            if (hi >= tlvl) if d > 0 else (lo <= tlvl):
                realized += remaining * target_R
                return realized, mae
            # 4) RTH close timeout
            if not rthv[x] and x > fill:
                realized += remaining * ((C_[x] - entry) * d / atr0)
                return realized, mae
        x = min(fill + 24, n) - 1
        realized += remaining * ((C_[x] - entry) * d / atr0)
        return realized, mae

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
                    if L_[x] <= lvl <= H_[x]:
                        fill = x; break
                if fill is None:
                    break
                entry = lvl
                rw = {
                    "incumbent": walk(fill, d, entry, atr0, 1.5, partial=[(1, 0.5)]),
                    "single1":   walk(fill, d, entry, atr0, 1.0, partial=None),
                    "single15":  walk(fill, d, entry, atr0, 1.5, partial=None),
                    "single2":   walk(fill, d, entry, atr0, 2.0, partial=None),
                }
                out.append(dict(ts=idx[fill], src="B",
                                R={k: v[0] for k, v in rw.items()},
                                mae_pts={k: v[1] for k, v in rw.items()},
                                risk_usd=atr0 * DPP))
                break
    return out


def build_events(A, B, Mm, variant):
    """Per-variant event stream at deployed sizing (A10/B5/mm6), $ pnl + $ mae, daily-stop applied."""
    ev = []
    for t in A[variant]:
        R = t["R"]
        ev.append(dict(ts=t["ts"], src="A", pnl=R * t["risk_usd"] * A_SIZE,
                       mae=min(0.0, t["mae_r"]) * t["risk_usd"] * A_SIZE, R=R))
    for t in B:
        R = t["R"][variant]
        gross_pts = R * (t["risk_usd"] / DPP)              # R -> points
        pnl = (gross_pts - B_COST) * DPP * B_SIZE
        ev.append(dict(ts=t["ts"], src="B", pnl=pnl,
                       mae=min(0.0, t["mae_pts"][variant]) * DPP * B_SIZE, R=R))
    for e in Mm:                                            # momentum unchanged
        ev.append(dict(ts=e["ts"], src="M", pnl=e["pnl"] * M_SIZE,
                       mae=min(0.0, e["mae"]) * M_SIZE, R=np.nan))
    return H.apply_daily_stop(ev)


# ---------- metrics ----------
def pass_pct(ev, starts):
    p = sum(1 for s in starts if EOD.eval_eod(ev, s, SPEC)[0] == "PASS")
    return 100.0 * p / len(starts) if starts else np.nan


def starts_in(ev, lo, hi):
    """day-start indices whose start-date is in [lo,hi) AND have >30d of runway after them."""
    seen, st = set(), []
    last = pd.Timestamp(ev[-1]["ts"])
    for i, e in enumerate(ev):
        d = pd.Timestamp(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - pd.Timestamp(e["ts"])).days <= EXPIRE_DAYS:
            continue
        y = pd.Timestamp(e["ts"])
        if lo <= y < hi:
            st.append(i)
    return st


def total_R(ev):
    return sum(e["R"] for e in ev if not np.isnan(e["R"]))


def a_maxdd_R(A, variant):
    """A-leg cumulative-R drawdown (size 1), chronological."""
    rs = [t["R"] for t in A[variant]]
    cum = 0.0; peak = 0.0; dd = 0.0
    for r in rs:
        cum += r; peak = max(peak, cum); dd = min(dd, cum - peak)
    return dd


# ---------- block-bootstrap MC on eval pass% ----------
def day_blocks(ev):
    """list of (date, [events]) preserving intra-day order."""
    by = {}
    for e in ev:
        d = pd.Timestamp(e["ts"]).normalize()
        by.setdefault(d, []).append(e)
    return [by[d] for d in sorted(by)]


def synth_stream(blocks):
    """resample contiguous 10-day chunks of trading days, re-stamp onto a fresh business calendar."""
    n = len(blocks); out_days = []
    while len(out_days) < n:
        s = np.random.randint(0, max(1, n - BLOCK))
        out_days.extend(blocks[s:s + BLOCK])
    out_days = out_days[:n]
    cal = pd.bdate_range("2000-01-03", periods=n)
    ev = []
    for di, day_evs in enumerate(out_days):
        base = pd.Timestamp(cal[di])
        for k, e in enumerate(day_evs):
            ne = dict(e); ne["ts"] = base + pd.Timedelta(minutes=k)
            ev.append(ne)
    return ev


def mc(ev, n_paths=N_PATHS):
    blocks = day_blocks(ev)
    out = []
    for _ in range(n_paths):
        s = synth_stream(blocks)
        st = EOD.day_starts(s)
        out.append(pass_pct(s, st))
    a = np.array(out)
    return np.median(a), np.percentile(a, 5), np.percentile(a, 95)


def main():
    print("loading real Databento NQ 1m -> 5m…", flush=True)
    df5 = DB.load_databento_5m()
    print(f"  bars {df5.index.min().date()} -> {df5.index.max().date()} ({len(df5):,})", flush=True)

    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    feats = eng._features(); fi = feats.index
    variants = ["incumbent", "single1", "single15", "single2"]
    A = {v: a_variant(feats, fi, v) for v in variants}
    B = b_sim(df5); Mm = H.m_events(df5)
    print(f"  A trades/variant={ {v: len(A[v]) for v in variants} }  B={len(B)} mm-days={len(Mm)}", flush=True)

    # sanity: A-incumbent + B-single15 must reproduce the validated 57.5% deployed baseline
    chk = []
    for t in A["incumbent"]:
        chk.append(dict(ts=t["ts"], src="A", pnl=t["R"] * t["risk_usd"] * A_SIZE,
                        mae=min(0.0, t["mae_r"]) * t["risk_usd"] * A_SIZE, R=t["R"]))
    for t in B:
        R = t["R"]["single15"]; g = R * (t["risk_usd"] / DPP)
        chk.append(dict(ts=t["ts"], src="B", pnl=(g - B_COST) * DPP * B_SIZE,
                        mae=min(0.0, t["mae_pts"]["single15"]) * DPP * B_SIZE, R=R))
    for e in Mm:
        chk.append(dict(ts=e["ts"], src="M", pnl=e["pnl"] * M_SIZE, mae=min(0.0, e["mae"]) * M_SIZE, R=np.nan))
    chk = H.apply_daily_stop(chk)
    print(f"  [sanity] A-incumbent + B-single1.5R (=deployed) pass% = "
          f"{pass_pct(chk, EOD.day_starts(chk)):.1f}  (must ~= validated 57.5)", flush=True)

    lab = {"incumbent": "INCUMBENT 50/50", "single1": "single@1R",
           "single15": "single@1.5R", "single2": "single@2R"}
    T = pd.Timestamp
    splits = {
        "IS 21-24": (T("2021-01-01", tz=NY), T("2025-01-01", tz=NY)),
        "OOS 25-26": (T("2025-01-01", tz=NY), T("2027-01-01", tz=NY)),
        "altIS 21-23": (T("2021-01-01", tz=NY), T("2024-01-01", tz=NY)),
        "altOOS 24-26": (T("2024-01-01", tz=NY), T("2027-01-01", tz=NY)),
    }

    print("\n  ===== EVAL PASS% by exit variant (A10/B5/mm6, EOD rule, real Databento) =====")
    hdr = f"  {'variant':>16} | {'FULL':>6} {'IS 21-24':>9} {'OOS 25-26':>9} {'altIS':>7} {'altOOS':>7} | {'totR':>7} {'A_maxDD':>8} | {'MCmed':>6} {'MCp5':>6} {'MCp95':>6}"
    print(hdr); print("  " + "-" * (len(hdr)))
    res = {}
    for v in variants:
        ev = build_events(A, B, Mm, v)
        allst = EOD.day_starts(ev)
        full = pass_pct(ev, allst)
        sp = {k: pass_pct(ev, starts_in(ev, lo, hi)) for k, (lo, hi) in splits.items()}
        tr = total_R(ev); add = a_maxdd_R(A, v)
        med, p5, p95 = mc(ev)
        res[v] = dict(full=full, **sp, totR=tr, addd=add, med=med, p5=p5, p95=p95,
                      nstart=len(allst))
        print(f"  {lab[v]:>16} | {full:6.1f} {sp['IS 21-24']:9.1f} {sp['OOS 25-26']:9.1f} "
              f"{sp['altIS 21-23']:7.1f} {sp['altOOS 24-26']:7.1f} | {tr:7.0f} {add:8.1f} | "
              f"{med:6.1f} {p5:6.1f} {p95:6.1f}")

    inc = res["incumbent"]
    print(f"\n  rolling eval starts (full history): {inc['nstart']}")
    print(f"  MC: {N_PATHS} block-bootstrap paths, {BLOCK}-day blocks, pass% median/p5/p95")
    for v in ["single1", "single15"]:
        r = res[v]
        print(f"\n  [{lab[v]}] vs incumbent:")
        print(f"     OOS 25-26 : {r['OOS 25-26']:.1f} vs {inc['OOS 25-26']:.1f}  "
              f"-> {'BEATS' if r['OOS 25-26'] > inc['OOS 25-26'] else 'loses'}")
        print(f"     altOOS    : {r['altOOS 24-26']:.1f} vs {inc['altOOS 24-26']:.1f}")
        print(f"     MC p5     : {r['p5']:.1f} vs {inc['p5']:.1f}  "
              f"-> {'BEATS' if r['p5'] > inc['p5'] else 'loses'}")
        print(f"     totR      : {r['totR']:.0f} vs {inc['totR']:.0f}")
    return res


if __name__ == "__main__":
    main()
