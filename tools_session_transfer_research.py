"""SESSION-TRANSFER RESEARCH (2026-07-02) — Profile-A structure in LONDON/ASIA, 1m-truth, holdout.

RESEARCH ONLY. Question: does the validated A structure (sweep -> MSS -> OTE, Exit#3) carry an edge
outside NY-AM, and does adding it improve the ZEUS portfolio (pass/bust at 50K), not just PF?

PRE-REGISTERED (before any result was seen):
  * IS = 2021-06 .. 2024-12-31, HOLDOUT = 2025-01-01 .. end (frozen now).
  * Accept for portfolio testing only if: IS PF > 1.15 AND holdout PF > 1.10 AND holdout n >= 40.
  * Portfolio accept only if 50K@$1,200 eval pass improves AND bust does not rise > 2pp.
  * Drift gate: the validated D1c is NY-open-anchored; here we use a causal 60-min rolling drift
    analog (last 1m close minus close 60min earlier, sign must agree with trade direction) — clearly
    labeled ANALOG, would need its own validation before any live use.
Fills: 1m-truth conventions (walk_1m — no fill-bar target). Costs: model01's slip embedded (A-style).
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
from tools_1m_truth_recert import M1Map, walk_1m, A_PARAMS
from tools_account_size_research import day_rows, eval_run, SPECS

NY = "America/New_York"
HOLDOUT_START = pd.Timestamp("2025-01-01", tz=NY)


def session_rows(feats, mp, d1, session):
    """A-structure trades in `session`, exit3, 1m-truth walked, rolling-drift ANALOG gate."""
    c1 = d1["close"]; c1_idx = d1.index
    tr = M1.run(feats, "NQ", A_PARAMS["exit3"])
    tr = tr[tr.session == session]
    fi = feats.index; n5 = len(fi)
    rows, dropped = [], 0
    for _, t in tr.iterrows():
        risk = abs(float(t.entry) - float(t.stop))
        fb = int(t.fill_bar)
        if risk <= 0 or not (0 <= fb < n5):
            continue
        d = 1 if t.direction == "long" else -1
        ts_naive = fi[fb].tz_localize(None) if fi[fb].tzinfo else fi[fb]
        pos = c1_idx.searchsorted(ts_naive, "right") - 1
        pos0 = c1_idx.searchsorted(ts_naive - pd.Timedelta(minutes=60), "right") - 1
        if pos < 0 or pos0 < 0:
            dropped += 1
            continue
        drift = float(c1.iloc[pos] - c1.iloc[pos0])
        if not ((drift > 0 and d == 1) or (drift < 0 and d == -1)):
            dropped += 1
            continue
        partials = [(float(t.entry) + d * rl * risk, frac) for rl, frac in A_PARAMS["exit3"]["partial"]]
        w = walk_1m(mp, fb, d, float(t.entry), float(t.stop), float(t.target),
                    partials, max_5m_bars=M1.MAX_HOLD)
        if w is None:
            continue
        rows.append(dict(ts=pd.Timestamp(fi[fb]), R=w[0], mae_r=w[1], risk_usd=risk * 2.0))
    return rows, dropped


def stats(rows, label):
    r = np.array([t["R"] for t in rows])
    if not len(r):
        print(f"  {label}: n=0"); return dict(n=0, PF=0.0)
    wins, losses = r[r > 0].sum(), -r[r <= 0].sum()
    pf = wins / losses if losses else np.inf
    print(f"  {label:<28} n={len(r):>4} PF={pf:.3f} netR={r.sum():+7.1f} WR={100*(r>0).mean():.1f}% "
          f"expR={r.mean():+.3f}")
    return dict(n=int(len(r)), PF=round(float(pf), 3), netR=round(float(r.sum()), 1),
                WR=round(float(100 * (r > 0).mean()), 1), expR=round(float(r.mean()), 3))


def portfolio_eval(a_rows, x_rows, budget_a, budget_x):
    """A + candidate at 50K/$1,200-class budgets, shared $550 stop + $1k DLL, EOD eval."""
    spec = SPECS["50K"]
    ev = []
    for rows, budget in ((a_rows, budget_a), (x_rows, budget_x)):
        for t in rows or []:
            risk1 = t["risk_usd"]
            q = min(40, int(budget // risk1))
            if q < 1:
                continue
            ev.append(dict(ts=pd.Timestamp(t["ts"]), pnl=t["R"] * risk1 * q,
                           mae=min(0.0, t["mae_r"]) * risk1 * q))
    ev.sort(key=lambda e: e["ts"])
    days = day_rows(ev, spec["stop"], spec["dll"])
    starts, seen = [], set()
    for i, (d, _, _) in enumerate(days):
        if d not in seen and (days[-1][0] - d).days > 30:
            seen.add(d); starts.append(i)
    res = [eval_run(days, s, spec) for s in starts]
    n = len(res)
    return (100 * sum(1 for r in res if r[0] == "PASS") / n,
            100 * sum(1 for r in res if r[0] == "BUST") / n,
            100 * sum(1 for r in res if r[0] == "EXPIRE") / n,
            int(np.median([r[1] for r in res if r[0] == "PASS"]) or 0))


def daily_corr(a_rows, x_rows):
    da = pd.Series({pd.Timestamp(t["ts"]).normalize(): 0.0 for t in a_rows})
    for t in a_rows:
        da[pd.Timestamp(t["ts"]).normalize()] += t["R"]
    dx = pd.Series(dtype=float)
    for t in x_rows:
        k = pd.Timestamp(t["ts"]).normalize()
        dx[k] = dx.get(k, 0.0) + t["R"]
    j = pd.DataFrame({"a": da, "x": dx}).fillna(0.0)
    j = j[(j.a != 0) | (j.x != 0)]
    return float(j["a"].corr(j["x"])) if len(j) > 10 else float("nan")


def main():
    print("loading frames…", flush=True)
    d1_tz = RD.load_1m(); d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m(); mp = M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    feats = eng._features()

    from tools_phase3_config_sweep import a_streams_d1c
    a_rows = a_streams_d1c(feats, mp, d1_tz)["exit3"][0]      # the locked machine's stream

    out = {}
    for sess in ("london", "asia"):
        rows, dropped = session_rows(feats, mp, d1, sess)
        is_rows = [t for t in rows if t["ts"] < HOLDOUT_START]
        ho_rows = [t for t in rows if t["ts"] >= HOLDOUT_START]
        print(f"\n=== {sess.upper()} (A-structure + 60min-drift ANALOG; drift-dropped {dropped}) ===")
        s_all = stats(rows, "ALL")
        s_is = stats(is_rows, "IS 2021-2024")
        s_ho = stats(ho_rows, "HOLDOUT 2025-26 (frozen)")
        gate = (s_is.get("PF", 0) > 1.15 and s_ho.get("PF", 0) > 1.10 and s_ho.get("n", 0) >= 40)
        corr = daily_corr(a_rows, rows)
        print(f"  pre-registered gate: {'PASS' if gate else 'FAIL'} · daily-R corr vs A: {corr:+.3f}")
        entry = dict(all=s_all, IS=s_is, holdout=s_ho, gate="PASS" if gate else "FAIL",
                     corr_vs_A=round(corr, 3) if corr == corr else None)
        if gate:
            base = portfolio_eval(a_rows, [], 1_200, 0)
            port = portfolio_eval(a_rows, rows, 1_200, 600)      # candidate at half-budget
            print(f"  PORTFOLIO 50K/$1200(+$600 {sess}): base pass {base[0]:.1f}/bust {base[1]:.1f}"
                  f"/exp {base[2]:.1f}/med {base[3]}  ->  A+{sess} {port[0]:.1f}/{port[1]:.1f}"
                  f"/{port[2]:.1f}/med {port[3]}")
            entry["portfolio"] = dict(base=[round(v, 1) for v in base],
                                      with_candidate=[round(v, 1) for v in port])
        out[sess] = entry

    with open("reports/session_transfer_2026-07-02.json", "w") as f:
        json.dump(out, f, indent=1)
    print("\n[saved] reports/session_transfer_2026-07-02.json", flush=True)


if __name__ == "__main__":
    main()
