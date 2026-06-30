"""ADVERSARIAL stress test of single@1R vs INCUMBENT 50/50, reusing exit_model_validate's
validated re-simulation pipeline. Tries to BREAK the 'deploy' rating:
  (1) per-CALENDAR-YEAR eval PASS% (does single@1R lose vs incumbent in ANY single year?)
  (2) worst rolling-window PASS% (W=80 consecutive eval-starts)
  (3) realistic cost/slippage sensitivity (+1 tick & +2 tick on BOTH legs + commission)
  (4) small-sample fragility: report n in each decisive bucket.
All re-runs use the SAME validated generators; only the exit target / costs change.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))

import exit_model_validate as V
import apex_eval_eod as EOD
import model01_sweep_mss_fvg as M1

NY = "America/New_York"
DPP = V.DPP
A_SIZE, B_SIZE, M_SIZE = V.A_SIZE, V.B_SIZE, V.M_SIZE
T = pd.Timestamp


def a_variant_slip(feats, fi, variant, slip):
    """Re-simulate A with a custom entry slippage (ticks). Mirrors V.a_variant."""
    params = dict(V.A_PARAMS[variant]); params["slip_ticks"] = slip
    tr = M1.run(feats, "NQ", params)
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


def build_cost(A, B, Mm, variant, b_extra_pts=0.0, comm_usd=0.0, a_dict=None):
    """Event stream with extra B slippage (points) + per-contract commission ($ per leg event)."""
    Asrc = a_dict if a_dict is not None else A
    ev = []
    for t in Asrc[variant]:
        R = t["R"]
        ev.append(dict(ts=t["ts"], src="A",
                       pnl=R * t["risk_usd"] * A_SIZE - comm_usd * A_SIZE,
                       mae=min(0.0, t["mae_r"]) * t["risk_usd"] * A_SIZE, R=R))
    for t in B:
        R = t["R"][variant]
        gross_pts = R * (t["risk_usd"] / DPP)
        pnl = (gross_pts - (V.B_COST + b_extra_pts)) * DPP * B_SIZE - comm_usd * B_SIZE
        ev.append(dict(ts=t["ts"], src="B", pnl=pnl,
                       mae=min(0.0, t["mae_pts"][variant]) * DPP * B_SIZE, R=R))
    for e in Mm:
        ev.append(dict(ts=e["ts"], src="M", pnl=e["pnl"] * M_SIZE - comm_usd * M_SIZE,
                       mae=min(0.0, e["mae"]) * M_SIZE, R=np.nan))
    return V.H.apply_daily_stop(ev)


def per_start_pass(ev, starts):
    return [EOD.eval_eod(ev, s, V.SPEC)[0] == "PASS" for s in starts]


def main():
    print("loading real Databento NQ 1m -> 5m…", flush=True)
    df5 = V.DB.load_databento_5m()
    print(f"  bars {df5.index.min().date()} -> {df5.index.max().date()} ({len(df5):,})", flush=True)

    V.H.A_SIZE = V.H.B_SIZE = V.H.M_SIZE = 1
    eng = V.E.ProfileAEngine(V.config.STRAT); eng.buf = df5
    feats = eng._features(); fi = feats.index
    variants = ["incumbent", "single1", "single15"]
    A = {v: V.a_variant(feats, fi, v) for v in variants}
    B = V.b_sim(df5); Mm = V.H.m_events(df5)
    print(f"  A trades/variant={ {v: len(A[v]) for v in variants} }  B={len(B)} mm-days={len(Mm)}", flush=True)

    EV = {v: V.build_events(A, B, Mm, v) for v in variants}
    inc, s1, s15 = EV["incumbent"], EV["single1"], EV["single15"]

    # ---------- (1) PER CALENDAR YEAR ----------
    print("\n  ===== (1) PER-CALENDAR-YEAR eval PASS% (A10/B5/mm6, EOD, real Databento) =====")
    print(f"  {'year':>6} {'n_inc':>6} | {'INCUMBENT':>9} {'single@1R':>9} {'Δ vs inc':>9} | {'single@1.5R':>11}")
    years = list(range(2021, 2027))
    yr_delta = []
    for y in years:
        lo = T(f"{y}-01-01", tz=NY); hi = T(f"{y+1}-01-01", tz=NY)
        st_i = V.starts_in(inc, lo, hi)
        st_1 = V.starts_in(s1, lo, hi)
        st_15 = V.starts_in(s15, lo, hi)
        pi = V.pass_pct(inc, st_i); p1 = V.pass_pct(s1, st_1); p15 = V.pass_pct(s15, st_15)
        d = p1 - pi
        yr_delta.append((y, len(st_i), pi, p1, d))
        mark = "  <-LOSES" if d < 0 else ""
        print(f"  {y:>6} {len(st_i):>6} | {pi:>9.1f} {p1:>9.1f} {d:>+9.1f} | {p15:>11.1f}{mark}")
    loses = [y for (y, n, pi, p1, d) in yr_delta if d < 0]
    print(f"  single@1R loses to incumbent in years: {loses if loses else 'NONE'}")

    # ---------- (2) WORST ROLLING WINDOW ----------
    print("\n  ===== (2) WORST ROLLING-WINDOW eval PASS% (W=80 consecutive starts) =====")
    W = 80
    st_all_i = EOD.day_starts(inc); st_all_1 = EOD.day_starts(s1)
    bi = np.array(per_start_pass(inc, st_all_i), float)
    b1 = np.array(per_start_pass(s1, st_all_1), float)
    # align by index position (both are 1-per-trading-day; counts may differ slightly) -> use min len
    def roll_min(b):
        if len(b) < W: return np.nan, np.nan
        cs = np.convolve(b, np.ones(W), "valid") / W * 100
        return cs.min(), cs.mean()
    wi_min, wi_mean = roll_min(bi); w1_min, w1_mean = roll_min(b1)
    # worst-window date for single1
    cs1 = np.convolve(b1, np.ones(W), "valid") / W * 100
    wpos = int(np.argmin(cs1))
    wdate = pd.Timestamp(inc[st_all_1[wpos]]["ts"]).date()
    print(f"  incumbent : worst {W}-start window {wi_min:.1f}%  (mean {wi_mean:.1f}%)  n={len(bi)}")
    print(f"  single@1R : worst {W}-start window {w1_min:.1f}%  (mean {w1_mean:.1f}%)  n={len(b1)}  worst≈{wdate}")
    print(f"  -> single@1R worst-window {'BEATS' if w1_min >= wi_min else 'LOSES vs'} incumbent worst-window")

    # ---------- (3) COST / SLIPPAGE SENSITIVITY ----------
    print("\n  ===== (3) COST SENSITIVITY (extra slippage + commission on ALL legs) =====")
    # A slip baseline = 8 ticks; +1 tick=9, +2 ticks=10. B baseline cost 0.75pt; +1 tick=+0.25.
    # commission: realistic MNQ round-turn ~$1.5/contract; harsh $4.
    scenarios = [
        ("baseline",      8,  0.00, 0.0),
        ("+1tk +$1.5cm",  9,  0.25, 1.5),
        ("+2tk +$4 cm",   10, 0.50, 4.0),
    ]
    print(f"  {'scenario':>14} | {'INC full':>9} {'INC OOS':>8} | {'s1 full':>9} {'s1 OOS':>8} {'s1 MCp5':>8} | {'Δfull':>6} {'ΔOOS':>6}")
    oos_lo, oos_hi = T("2025-01-01", tz=NY), T("2027-01-01", tz=NY)
    for name, slip, bx, cm in scenarios:
        if slip == 8:
            Ac = A
        else:
            Ac = {v: a_variant_slip(feats, fi, v, slip) for v in variants}
        ev_i = build_cost(A, B, Mm, "incumbent", b_extra_pts=bx, comm_usd=cm, a_dict=Ac)
        ev_1 = build_cost(A, B, Mm, "single1", b_extra_pts=bx, comm_usd=cm, a_dict=Ac)
        fi_full = V.pass_pct(ev_i, EOD.day_starts(ev_i))
        f1_full = V.pass_pct(ev_1, EOD.day_starts(ev_1))
        fi_oos = V.pass_pct(ev_i, V.starts_in(ev_i, oos_lo, oos_hi))
        f1_oos = V.pass_pct(ev_1, V.starts_in(ev_1, oos_lo, oos_hi))
        _, p5_1, _ = V.mc(ev_1, n_paths=400)
        print(f"  {name:>14} | {fi_full:>9.1f} {fi_oos:>8.1f} | {f1_full:>9.1f} {f1_oos:>8.1f} {p5_1:>8.1f} | "
              f"{f1_full-fi_full:>+6.1f} {f1_oos-fi_oos:>+6.1f}")

    # ---------- (4) SMALL-SAMPLE BUCKET SIZES ----------
    print("\n  ===== (4) DECISIVE-BUCKET sample sizes =====")
    for nm, lo, hi in [("OOS 25-26", T("2025-01-01", tz=NY), T("2027-01-01", tz=NY)),
                       ("altOOS 24-26", T("2024-01-01", tz=NY), T("2027-01-01", tz=NY)),
                       ("IS 21-24", T("2021-01-01", tz=NY), T("2025-01-01", tz=NY))]:
        n = len(V.starts_in(inc, lo, hi))
        print(f"  {nm:>12}: n={n} eval-starts  (binomial SE at p~.6 ≈ {100*(0.6*0.4/n)**0.5:.1f}pts)")
    print(f"  full history: n={len(EOD.day_starts(inc))} eval-starts")


if __name__ == "__main__":
    main()
