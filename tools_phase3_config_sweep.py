"""PHASE-3 CONFIG SWEEP on 1m-truth streams (2026-07-02) — pick the live machine on corrected numbers.

Sweeps: A exit {Exit#3, single@1R} x B {full, reduced 2, off} x sizes A{10,8,6} x mm0, with the
D1c drift gate ATTACHED to A (live runs ACTIVE_EVAL_FILTER; certified streams never included it — audit K).
All fills are 1m-truth (tools_1m_truth_recert conventions). Momentum excluded per operator decision
(live-dead until properly warmed + re-certified — audit D1/H).

Ranked on pass%, bust%, expectancy, worst-day $, trades/day, and era-split robustness — not raw PF.
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
from tools_1m_truth_recert import M1Map, walk_1m, b_streams, A_PARAMS, DPP, B_COST

NY = "America/New_York"
SPEC = FR.APEX_ACCOUNTS["50K"]

A_SIZES = (10, 8, 6)
B_MODES = {"full": lambda a: a // 2, "b2": lambda a: 2, "off": lambda a: 0}
PAIRINGS = [("exit3", "partial"), ("exit3", "single1"), ("single1", "single1")]


def a_streams_d1c(feats, mp, d1_tz):
    """A trades per exit variant, D1c-attached, 1m-truth walked. Returns kept + dropped counts."""
    out = {}
    for variant, params in A_PARAMS.items():
        tr = M1.run(feats, "NQ", params)
        tr = tr[tr.session == "ny_am"].copy()
        # INC-20260706-1141: fill_bar + feats.index, not date/time strings (avoids the
        # UTC-relocalized-as-NY lookahead defect).
        tr = RD.attach_drift(tr, d1_tz, feats.index)          # the validated live gate (fail-closed)
        rows, dropped = [], 0
        fi = feats.index; n5 = len(fi)
        for _, t in tr.iterrows():
            risk = abs(float(t.entry) - float(t.stop))
            fb = int(t.fill_bar)
            if risk <= 0 or not (0 <= fb < n5):
                continue
            if not bool(t["d1c_keep"]):
                dropped += 1
                continue
            d = 1 if t.direction == "long" else -1
            partials = []
            if params.get("partial"):
                partials = [(float(t.entry) + d * rl * risk, frac) for rl, frac in params["partial"]]
            w = walk_1m(mp, fb, d, float(t.entry), float(t.stop), float(t.target),
                        partials, max_5m_bars=M1.MAX_HOLD)
            if w is None:
                continue
            rows.append(dict(ts=pd.Timestamp(fi[fb]), R=w[0], mae_r=w[1], risk_usd=risk * DPP))
        out[variant] = (rows, dropped)
    return out


def build_stream(A_rows, B, b_variant, a_size, b_size):
    ev = []
    for t in A_rows:
        ev.append(dict(ts=t["ts"], src="A", pnl=t["R"] * t["risk_usd"] * a_size, mfe=0.0,
                       mae=min(0.0, t["mae_r"]) * t["risk_usd"] * a_size))
    if b_size > 0:
        for t in B:
            R = t["R_new"][b_variant]
            if R is None:
                continue
            ev.append(dict(ts=t["ts"], src="B", pnl=(R * t["atr0"] - B_COST) * DPP * b_size, mfe=0.0,
                           mae=min(0.0, t["mae_new"][b_variant]) * t["atr0"] * DPP * b_size))
    ev.sort(key=lambda e: e["ts"])
    return H.apply_daily_stop(ev)


def metrics(ev):
    starts = EOD.day_starts(ev)
    res = [EOD.eval_eod(ev, s, SPEC) for s in starts]
    p, b, x, md = EOD.summarize(res)
    # era-split robustness (starts before/after 2024-01-01)
    cut = pd.Timestamp("2024-01-01", tz=NY)
    early = [r for r, s in zip(res, starts) if pd.Timestamp(ev[s]["ts"]) < cut]
    late = [r for r, s in zip(res, starts) if pd.Timestamp(ev[s]["ts"]) >= cut]
    pe = 100 * sum(1 for r in early if r[0] == "PASS") / max(1, len(early))
    pl = 100 * sum(1 for r in late if r[0] == "PASS") / max(1, len(late))
    # daily aggregates
    df = pd.DataFrame([(pd.Timestamp(e["ts"]).normalize(), e["pnl"], e["mae"]) for e in ev],
                      columns=["d", "pnl", "mae"])
    day = df.groupby("d")["pnl"].sum()
    worst_real = day.min()
    worst_marked = (df.groupby("d").apply(lambda g: g["pnl"].sum() + g["mae"].min())).min()
    ndays = day.index.nunique()
    return dict(pass_pct=p, bust_pct=b, exp_pct=x, med=md, pass_early=pe, pass_late=pl,
                net=day.sum(), per_day=day.sum() / ndays, tpd=len(ev) / ndays,
                worst_day=worst_real, worst_marked=worst_marked)


def main():
    print("loading frames…", flush=True)
    d1_tz = RD.load_1m()                                   # tz-aware NY (attach_drift needs this)
    d1 = d1_tz.tz_localize(None) if d1_tz.index.tz is not None else d1_tz
    d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m()
    mp = M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    feats = eng._features()
    print("A streams (model01 x2 + D1c attach + 1m walk)…", flush=True)
    A = a_streams_d1c(feats, mp, d1_tz)
    for v, (rows, dropped) in A.items():
        r = np.array([t["R"] for t in rows])
        wins = r[r > 0].sum(); losses = -r[r <= 0].sum()
        print(f"  A {v}+D1c: kept {len(rows)} dropped {dropped} · PF {wins/losses:.3f} netR {r.sum():+.1f} "
              f"WR {100*(r>0).mean():.1f}%", flush=True)
    print("B streams…", flush=True)
    B = b_streams(df5, mp)

    print(f"\n{'config':<26}{'pass':>6}{'bust':>6}{'exp':>5}{'med':>4}{'p<24':>6}{'p>=24':>6}"
          f"{'net$':>9}{'$/day':>7}{'tr/d':>5}{'worst-day$':>11}{'w-marked$':>10}", flush=True)
    results = {}
    for a_exit, b_exit in PAIRINGS:
        for a_size in A_SIZES:
            for bm, bf in B_MODES.items():
                b_size = bf(a_size)
                if bm == "b2" and b_size >= a_size // 2:
                    continue                                # reduced == full at small A -> skip dup
                ev = build_stream(A[a_exit][0], B, b_exit, a_size, b_size)
                m = metrics(ev)
                tag = f"A{a_size}{a_exit[-2:]}/B{b_size}{'' if b_size==0 else b_exit[:4]}"
                key = f"{a_exit}+{b_exit} A{a_size}/B{b_size}"
                results[key] = m
                print(f"{key:<26}{m['pass_pct']:>5.1f}%{m['bust_pct']:>5.1f}%{m['exp_pct']:>4.0f}%"
                      f"{m['med'] or 0:>4}{m['pass_early']:>5.1f}%{m['pass_late']:>5.1f}%"
                      f"{m['net']:>9,.0f}{m['per_day']:>7,.0f}{m['tpd']:>5.2f}"
                      f"{m['worst_day']:>11,.0f}{m['worst_marked']:>10,.0f}", flush=True)
        print("", flush=True)

    with open("reports/phase3_sweep_2026-07-02.json", "w") as f:
        json.dump({k: {kk: (None if vv is None or (isinstance(vv, float) and np.isnan(vv)) else
                            round(float(vv), 2) if isinstance(vv, (int, float, np.floating)) else vv)
                       for kk, vv in m.items()} for k, m in results.items()}, f, indent=1)
    print("[saved] reports/phase3_sweep_2026-07-02.json", flush=True)


if __name__ == "__main__":
    main()
