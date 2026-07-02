"""1m-TRUTH RE-FILL of every A/B trade — kills the entry-bar target look-ahead (2026-07-02 audit F1).

THE BUG: every 5m fill simulator started the exit walk ON the retest-limit fill bar and booked the
target off that bar's full high/low — but for a limit entry the favorable extreme frequently prints
BEFORE the fill. Targets ~= one 5m bar range, so this manufactured a large share of the claimed R
(B@1R: 41.6% of wins booked on the fill bar; A@1R: 24.7%).

THE FIX HERE: signals/entries are unchanged (causally clean). Exits are re-walked on REAL 1m bars:
  * the 1m fill bar = first 1m bar inside the certified 5m fill bar whose range crosses the limit;
  * on that 1m fill bar: STOP check only — no same-bar target/partial (1m cannot prove sequencing);
  * every later 1m bar: adverse-first (stop, then partial, then target);
  * timeouts mirror the 5m conventions (A: MAX_HOLD 48x5m + stop slip 0.5pt; B: 24x5m or RTH end).
Residual optimism: touch==fill at the limit (queue ignored). Residual pessimism: no same-bar target
on the 1m fill bar. Net: a much tighter bracket than the 5m convention.

Outputs old-vs-new PF/netR/WR/expectancy per stream + the EOD eval pass-rate grid on corrected streams.
"""
import os, sys, warnings, json; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import strategy_engine_profileA as E
import model01_sweep_mss_fvg as M1
import config
import run_d1c_real as RD
import apex_eval_eod_databento as DB
import apex_eval_deployed as H
import apex_eval_eod as EOD
import funded_rules as FR

NY = "America/New_York"
DPP = 2.0
B_COST = 0.75
A_SLIP = 2 * 0.25            # model01 SLIP: 0.5pt penalty on stop exits
SPEC = FR.APEX_ACCOUNTS["50K"]
CONFIGS = [(10, 5, 6), (10, 5, 0), (8, 4, 5), (6, 3, 4)]

A_PARAMS = {
    "exit3":   {**E.PROFILE_A, "slip_ticks": 8},                                          # 0.5@1R + 0.5@2R
    "single1": {**E.PROFILE_A, "slip_ticks": 8, "partial": None, "rr": 1.0, "target_mode": "fixed_rr"},
}


# ---------------------------------------------------------------- 1m plumbing
def load_frames():
    d1 = RD.load_1m()
    if d1.index.tz is not None:
        d1 = d1.tz_localize(None)
    df5 = DB.load_databento_5m()                    # NY tz-aware (the validated pipeline)
    return d1, df5


class M1Map:
    """5m-position -> [start,end) slice into the 1m arrays (both naive-NY)."""

    def __init__(self, d1, df5):
        self.H = d1["high"].values; self.L = d1["low"].values; self.C = d1["close"].values
        self.ts1 = d1.index.values
        self.idx5_naive = df5.index.tz_localize(None).values

    def window(self, i5, n_5m_bars):
        t0 = self.idx5_naive[i5]
        t1 = t0 + np.timedelta64(5 * n_5m_bars, "m")
        a = np.searchsorted(self.ts1, t0, "left")
        b = np.searchsorted(self.ts1, t1, "left")
        return a, b


def walk_1m(mp, fill5, d, entry, stop, target, partials, max_5m_bars, end_ts_naive=None):
    """Conservative 1m re-walk. partials = [(level_price, frac)] or []. Returns (realized_R, mae_R, filled, fill_on_bar_win).
    realized in R of risk=|entry-stop|; stop exits pay A_SLIP-style penalty only when slip_pen=True (A)."""
    risk = abs(entry - stop)
    a, b = mp.window(fill5, max_5m_bars)
    if end_ts_naive is not None:
        b = min(b, int(np.searchsorted(mp.ts1, end_ts_naive, "left")) + 1)
    if a >= b:
        return None                                   # no 1m data (shouldn't happen on trade days)
    a5, b5 = mp.window(fill5, 1)                      # the certified 5m fill bar's 1m slice
    fill_i = None
    for x in range(a5, min(b5, b)):
        if (mp.L[x] <= entry) if d > 0 else (mp.H[x] >= entry):
            fill_i = x
            break
    if fill_i is None:
        return None                                   # 1m says the limit never traded -> no fill
    realized, remaining, mae = 0.0, 1.0, 0.0
    scales = sorted(partials or [], key=lambda z: z[0] * d)   # nearest level first in trade direction
    si = 0
    for x in range(fill_i, b):
        hi, lo = mp.H[x], mp.L[x]
        adv = (lo - entry) * d if d > 0 else (hi - entry) * d
        mae = min(mae, adv / risk)
        # 1) stop first — including on the 1m fill bar itself
        if (lo <= stop) if d > 0 else (hi >= stop):
            r_exit = ((stop - A_SLIP - entry) / risk) if d > 0 else ((entry - (stop + A_SLIP)) / risk)
            return realized + remaining * r_exit, mae, True, False
        if x == fill_i:
            continue                                  # NO same-bar target/partial on the fill bar (F1 fix)
        # 2) partial scale-outs
        while si < len(scales):
            lvl, frac = scales[si]
            if (hi >= lvl) if d > 0 else (lo <= lvl):
                realized += frac * (lvl - entry) * d / risk; remaining -= frac; si += 1
            else:
                break
        # 3) final target
        if remaining > 0 and ((hi >= target) if d > 0 else (lo <= target)):
            return realized + remaining * (target - entry) * d / risk, mae, True, False
    x = b - 1                                          # timeout: close at the window's last 1m close
    return realized + remaining * (mp.C[x] - entry) * d / risk, mae, True, False


# ---------------------------------------------------------------- A streams
def a_streams(feats, mp, df5):
    """Per variant: list of dict(ts, R_old, R_new, risk_usd, mae_new, filled)."""
    fi = feats.index
    n5 = len(fi)
    out = {}
    for variant, params in A_PARAMS.items():
        tr = M1.run(feats, "NQ", params)
        tr = tr[tr.session == "ny_am"]
        rows = []
        for _, t in tr.iterrows():
            risk = abs(float(t.entry) - float(t.stop))
            fb = int(t.fill_bar)
            if risk <= 0 or not (0 <= fb < n5):
                continue
            d = 1 if t.direction == "long" else -1
            partials = []
            if params.get("partial"):
                partials = [(float(t.entry) + d * rl * risk, frac) for rl, frac in params["partial"]]
            w = walk_1m(mp, fb, d, float(t.entry), float(t.stop), float(t.target),
                        partials, max_5m_bars=M1.MAX_HOLD)
            rows.append(dict(ts=pd.Timestamp(fi[fb]), R_old=float(t.r_result),
                             R_new=(w[0] if w else None), mae_new=(w[1] if w else 0.0),
                             filled=bool(w), risk_usd=risk * DPP))
        out[variant] = rows
    return out


# ---------------------------------------------------------------- B streams
def b_streams(df5, mp):
    """B trades with old (5m as-coded) and new (1m truth) walks for single1 / single15 / partial."""
    df = df5.copy()
    et = df.index.tz_convert(NY); mins = et.hour * 60 + et.minute
    df["rth"] = (mins >= 570) & (mins < 960)
    df["day"] = et.normalize().tz_localize(None)
    pc = df.Close.shift(1)
    trng = pd.concat([df.High - df.Low, (df.High - pc).abs(), (df.Low - pc).abs()], axis=1).max(axis=1)
    df["atr"] = trng.rolling(14).mean()
    Hh, Ll, Cc = df.High.values, df.Low.values, df.Close.values
    atrv = df["atr"].values; idx = df.index; n = len(Cc)
    rthv = df["rth"].values

    def walk_5m(fill, d, entry, atr0, target_R, partial):
        """The as-coded legacy walk (F3-fixed mae) — kept ONLY as the 'old' baseline."""
        stop = entry - d * atr0
        realized, remaining, took, mae = 0.0, 1.0, False, 0.0
        for x in range(fill, min(fill + 24, n)):
            hi, lo = Hh[x], Ll[x]
            mae = min(mae, ((lo - entry) * d if d > 0 else (hi - entry) * d) / atr0)
            if (lo <= stop) if d > 0 else (hi >= stop):
                return realized + remaining * (-1.0), mae
            if partial and not took:
                plvl = entry + d * atr0
                if (hi >= plvl) if d > 0 else (lo <= plvl):
                    realized += 0.5; remaining -= 0.5; took = True
            tlvl = entry + d * target_R * atr0
            if (hi >= tlvl) if d > 0 else (lo <= tlvl):
                return realized + remaining * target_R, mae
            if not rthv[x] and x > fill:
                return realized + remaining * ((Cc[x] - entry) * d / atr0), mae
        x = min(fill + 24, n) - 1
        return realized + remaining * ((Cc[x] - entry) * d / atr0), mae

    out = []
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
                entry, stop = lvl, lvl - d * atr0
                end_naive = idx[fill].tz_localize(None).normalize() + pd.Timedelta(hours=16)
                variants = {"single1": (1.0, None), "single15": (1.5, None),
                            "partial": (1.5, [(entry + d * atr0, 0.5)])}
                row = dict(ts=idx[fill], atr0=atr0, R_old={}, R_new={}, mae_new={}, filled={})
                for k, (tR, part) in variants.items():
                    row["R_old"][k] = walk_5m(fill, d, entry, atr0, tR, partial=bool(part))[0]
                    w = walk_1m(mp, fill, d, entry, stop, entry + d * tR * atr0, part,
                                max_5m_bars=24, end_ts_naive=np.datetime64(end_naive))
                    row["R_new"][k] = w[0] if w else None
                    row["mae_new"][k] = w[1] if w else 0.0
                    row["filled"][k] = bool(w)
                out.append(row)
                break
    return out


# ---------------------------------------------------------------- reporting
def stats(rs):
    r = np.array([x for x in rs if x is not None], float)
    if not len(r):
        return dict(n=0)
    wins = r[r > 0].sum(); losses = -r[r <= 0].sum()
    return dict(n=len(r), netR=r.sum(), PF=(wins / losses if losses else np.inf),
                WR=100.0 * (r > 0).mean(), expR=r.mean())


def line(tag, s_old, s_new):
    print(f"  {tag:<22} OLD: n={s_old['n']:>4} PF={s_old['PF']:.3f} netR={s_old['netR']:+7.1f} "
          f"WR={s_old['WR']:4.1f}% expR={s_old['expR']:+.3f}   ->   "
          f"NEW: n={s_new['n']:>4} PF={s_new['PF']:.3f} netR={s_new['netR']:+7.1f} "
          f"WR={s_new['WR']:4.1f}% expR={s_new['expR']:+.3f}", flush=True)


def eval_grid(A, B, Mev, a_variant, b_variant, use_new):
    """EOD eval pass-rates on old vs new streams at each config. B cost applied per trade."""
    ev = []
    for t in A[a_variant]:
        R = t["R_new"] if use_new else t["R_old"]
        if R is None:
            continue
        mae = (t["mae_new"] if use_new else 0.0) or 0.0
        ev.append(dict(ts=t["ts"], src="A", pnl=R * t["risk_usd"], mae=min(0.0, mae) * t["risk_usd"]))
    for t in B:
        R = (t["R_new"] if use_new else t["R_old"])[b_variant]
        if R is None:
            continue
        mae = (t["mae_new"][b_variant] if use_new else 0.0) or 0.0
        pnl = (R * t["atr0"] - B_COST) * DPP
        ev.append(dict(ts=t["ts"], src="B", pnl=pnl, mae=min(0.0, mae) * t["atr0"] * DPP))
    for e in Mev:
        ev.append(dict(ts=e["ts"], src="M", pnl=e["pnl"], mae=min(0.0, e["mae"])))
    ev.sort(key=lambda e: e["ts"])
    rows = {}
    for (a, b, m) in CONFIGS:
        sc = {"A": a, "B": b, "M": m}
        sev = [dict(ts=e["ts"], src=e["src"], pnl=e["pnl"] * sc[e["src"]], mfe=0.0,
                    mae=e["mae"] * sc[e["src"]]) for e in ev if sc[e["src"]] > 0]
        sev = H.apply_daily_stop(sev)
        starts = EOD.day_starts(sev)
        p, bu, x, md = EOD.summarize([EOD.eval_eod(sev, s, SPEC) for s in starts])
        rows[(a, b, m)] = (p, bu, x, md)
    return rows


def main():
    print("loading 1m + 5m Databento…", flush=True)
    d1, df5 = load_frames()
    mp = M1Map(d1, df5)
    print(f"  1m bars {len(d1):,} · 5m bars {len(df5):,}", flush=True)

    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    feats = eng._features()
    print("building A streams (model01 x2 variants)…", flush=True)
    A = a_streams(feats, mp, df5)
    print("building B streams…", flush=True)
    B = b_streams(df5, mp)
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    Mev = H.m_events(df5)

    print("\n=== 1m-TRUTH RE-FILL — old (5m as-coded, F3-fixed) vs new (1m truth) ===", flush=True)
    for v in ("single1", "exit3"):
        rows = A[v]
        unf = sum(1 for t in rows if not t["filled"])
        line(f"A {v}", stats([t["R_old"] for t in rows]), stats([t["R_new"] for t in rows]))
        if unf:
            print(f"    ({unf} certified fills never traded at 1m -> dropped)", flush=True)
    for v in ("single1", "single15", "partial"):
        line(f"B {v}", stats([t["R_old"][v] for t in B]), stats([t["R_new"][v] for t in B]))

    print("\n=== EOD EVAL PASS-RATE (Apex 50K · $550 stop · 30d clock) — corrected streams ===", flush=True)
    for a_v, b_v, tag in (("single1", "single1", "SINGLE_1R (live)"), ("exit3", "partial", "EXIT3/B-partial")):
        old = eval_grid(A, B, Mev, a_v, b_v, use_new=False)
        new = eval_grid(A, B, Mev, a_v, b_v, use_new=True)
        print(f"  -- {tag} --")
        for cfg in CONFIGS:
            po = old[cfg]; pn = new[cfg]
            print(f"    A{cfg[0]}/B{cfg[1]}/mm{cfg[2]:<2}  OLD pass {po[0]:5.1f}% bust {po[1]:5.1f}%   ->   "
                  f"NEW pass {pn[0]:5.1f}% bust {pn[1]:5.1f}% exp {pn[2]:4.1f}% med {pn[3] or 0:>2}d", flush=True)

    out = dict(generated="2026-07-02", note="1m-truth re-fill (audit F1) + F3 sign fix; "
               "old 5m-convention numbers INVALID for certification")
    with open("reports/recert_1m_truth_2026-07-02.json", "w") as f:
        json.dump(out, f)
    print("\n[done] old 5m-fill numbers are INVALID for certification; use the NEW columns.", flush=True)


if __name__ == "__main__":
    main()
