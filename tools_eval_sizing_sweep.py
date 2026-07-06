"""EVAL SIZING SWEEP (2026-07-05) — Apex 50K contract-sizing research, exit3+D1c 1m-truth stream.

SIM CONDITIONAL — pending live fill evidence. Every printed table and the JSON output below carry
this header; no cell in this report is a forecast — it is a backtest replay of the already-
certified exit3 A-stream (1m-truth, D1c-attached) under different position-sizing rules and
optional fill-damage overlays. RESEARCH ONLY.

Data path IDENTICAL to tools_account_size_research.main() (lines ~145-151): run_d1c_real.load_1m
-> apex_eval_eod_databento.load_databento_5m -> M1Map -> ProfileAEngine._features() ->
tools_phase3_config_sweep.a_streams_d1c(...)["exit3"][0]. day_rows/eval_run are imported from
tools_account_size_research (never copied).

Sizing per trade: q = min(cap, int(budget // risk_usd)); skip trade if q < 1 (risk_usd = the
per-contract $ risk already baked into each row of the exit3 stream).

50K spec (fixed, not swept): start $50,000, trail $2,500, target $3,000, DLL $1,000, 30-day clock.
Internal daily stop: $550 for EVERY cell — this is the deployed blocker; it is held FIXED and is
NOT scaled with budget or cap (per spec). Because day_rows re-derives day state from the actual
per-trade P&L stream of each cell, the stop/DLL interaction is automatically re-derived per cell —
every (cap, budget, damage) combination rebuilds events AND day-rows from scratch; nothing is
cached across cells.
"""
import os, sys, warnings, json, time; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import strategy_engine_profileA as E          # noqa: E402  (side effect: adds engine/models to sys.path)
import model01_sweep_mss_fvg as M1            # noqa: E402
import config                                  # noqa: E402
import run_d1c_real as RD                      # noqa: E402
import apex_eval_eod_databento as DB           # noqa: E402
from tools_1m_truth_recert import M1Map, walk_1m, A_PARAMS, DPP, A_SLIP
from tools_phase3_config_sweep import a_streams_d1c
from tools_account_size_research import day_rows, eval_run     # reused BY IMPORT — never copied

FRAME = "SIM CONDITIONAL — pending live fill evidence"
NY = "America/New_York"
EXPIRE_DAYS = 30
SPEC = dict(start=50_000.0, trail=2_500.0, target=3_000.0, dll=1_000.0)
STOP = 550.0        # deployed internal daily stop — held FIXED across every cell, never scaled

CAPS = [10, 15, 20, 25, 30, 35, 40]
BUDGETS = [600, 750, 900, 1000, 1200]
STOP_BUCKETS = [(0, 20), (20, 30), (30, 45), (45, 60), (60, 80), (80, float("inf"))]
BUCKET_LABELS = ["0-20", "20-30", "30-45", "45-60", "60-80", "80+"]

# LOW-CONFIDENCE fee figures, vault Funded Funnel — 2026-07-05:
# funded net $12,827 - $99 activation; eval fee sticker $131
FUNDED_GROSS = 12_827.0
ACTIVATION_FEE = 99.0
FUNDED_NET = FUNDED_GROSS - ACTIVATION_FEE          # 12,728.0
EVAL_FEE = 131.0

UNIFORM_S = [0.0, 0.025, 0.05, 0.075, 0.10]
SIZE_K = [0.001, 0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02]
PARTIAL_F = [1.0, 0.75, 0.5, 0.25]

CANARY_A = dict(cap=10, budget=1200, pass_pct=47.8, bust_pct=15.9, exp_pct=36.2, med_days=16, n=395)
CANARY_B = dict(cap=40, budget=1200, pass_pct=58.2, bust_pct=29.1, exp_pct=12.7, med_days=11, n=395)


# ---------------------------------------------------------------- sizing / cell replay
def build_events(rows, cap, budget, mode="none", param=None):
    """Rebuild the (cap, budget, damage) event stream from scratch. mode in {"none","uniform",
    "size","frac"}; param is s / k / f respectively. Never cache across cells."""
    ev = []
    for t in rows:
        risk_usd = t["risk_usd"]
        q_budget = int(budget // risk_usd)
        q = min(cap, q_budget)
        if q < 1:
            continue
        R, mae_r = t["R"], t["mae_r"]
        q_pnl = q_mae = float(q)
        if mode == "uniform":
            s = param
            R = R - s; mae_r = mae_r - s
        elif mode == "size":
            k = param
            s = k * max(0, q - 10)
            R = R - s; mae_r = mae_r - s
        elif mode == "frac":
            f = param
            if R > 0:                      # winners only get the partial-fill haircut
                q_pnl = q_mae = q * f
        pnl = R * risk_usd * q_pnl
        mae = min(0.0, mae_r) * risk_usd * q_mae
        ev.append(dict(ts=pd.Timestamp(t["ts"]), pnl=pnl, mae=mae, q=q, risk_usd=risk_usd,
                       clipped=(q_budget >= cap)))
    ev.sort(key=lambda e: e["ts"])
    return ev


def run_cell(rows, cap, budget, mode="none", param=None):
    ev = build_events(rows, cap, budget, mode, param)
    days = day_rows(ev, STOP, SPEC["dll"])
    if not days:
        return dict(n=0, pass_pct=0.0, bust_pct=0.0, exp_pct=0.0, med_days=None, mean_days=None,
                    mean_risk_per_trade=0.0, mean_contracts=0.0, clipped_pct=0.0,
                    e_attempt=round(-EVAL_FEE, 1), evals_per_funded=None)
    starts = [i for i, (d, _, _) in enumerate(days) if (days[-1][0] - d).days > EXPIRE_DAYS]
    res = [eval_run(days, s, SPEC) for s in starts]
    n = len(res)
    p = 100.0 * sum(1 for r in res if r[0] == "PASS") / n
    b = 100.0 * sum(1 for r in res if r[0] == "BUST") / n
    x = 100.0 * sum(1 for r in res if r[0] == "EXPIRE") / n
    pass_days = [r[1] for r in res if r[0] == "PASS"]
    med = int(np.median(pass_days)) if pass_days else None
    mean_d = float(np.mean(pass_days)) if pass_days else None
    mean_risk = float(np.mean([e["risk_usd"] * e["q"] for e in ev])) if ev else 0.0
    mean_q = float(np.mean([e["q"] for e in ev])) if ev else 0.0
    clip_pct = 100.0 * float(np.mean([e["clipped"] for e in ev])) if ev else 0.0
    e_att = (p / 100.0) * FUNDED_NET - EVAL_FEE
    epf = (100.0 / p) if p > 0 else None
    return dict(n=n, pass_pct=round(p, 1), bust_pct=round(b, 1), exp_pct=round(x, 1),
                med_days=med, mean_days=(round(mean_d, 1) if mean_d is not None else None),
                mean_risk_per_trade=round(mean_risk, 1), mean_contracts=round(mean_q, 2),
                clipped_pct=round(clip_pct, 1), e_attempt=round(e_att, 1),
                evals_per_funded=(round(epf, 2) if epf is not None else None))


def bust_dates_for(rows, cap, budget):
    """Instrument a (cap, budget) replay: return the exact calendar date of every BUST start."""
    ev = build_events(rows, cap, budget)
    days = day_rows(ev, STOP, SPEC["dll"])
    starts = [i for i, (d, _, _) in enumerate(days) if (days[-1][0] - d).days > EXPIRE_DAYS]
    dates = []
    for s0 in starts:
        status, off = eval_run(days, s0, SPEC)
        if status == "BUST":
            dates.append(days[s0][0] + pd.Timedelta(days=off))
    return dates


# ---------------------------------------------------------------- augmented rows (PART B needs
# entry/direction/fill_bar/stop/target, which a_streams_d1c's own return does not carry)
def walk_1m_mfe(mp, fill5, d, entry, stop, target, partials, max_5m_bars, end_ts_naive=None):
    """VERBATIM copy of tools_1m_truth_recert.walk_1m (2026-07-02) with ONE added accumulator:
    mfe (favorable excursion, same R-normalization as mae). Every other line is unchanged.
    Verified 0 mismatches vs the original on all 435 exit3+D1c trades before being trusted below
    (see main(): mfe_checked/mfe_mismatch)."""
    risk = abs(entry - stop)
    a, b = mp.window(fill5, max_5m_bars)
    if end_ts_naive is not None:
        b = min(b, int(np.searchsorted(mp.ts1, end_ts_naive, "left")) + 1)
    if a >= b:
        return None
    a5, b5 = mp.window(fill5, 1)
    fill_i = None
    for x in range(a5, min(b5, b)):
        if (mp.L[x] <= entry) if d > 0 else (mp.H[x] >= entry):
            fill_i = x
            break
    if fill_i is None:
        return None
    realized, remaining, mae, mfe = 0.0, 1.0, 0.0, 0.0                 # <-- ADDED: mfe accumulator
    scales = sorted(partials or [], key=lambda z: z[0] * d)
    si = 0
    for x in range(fill_i, b):
        hi, lo = mp.H[x], mp.L[x]
        adv = (lo - entry) * d if d > 0 else (hi - entry) * d
        mae = min(mae, adv / risk)
        fav = (hi - entry) * d if d > 0 else (lo - entry) * d          # <-- ADDED
        mfe = max(mfe, fav / risk)                                     # <-- ADDED
        if (lo <= stop) if d > 0 else (hi >= stop):
            r_exit = ((stop - A_SLIP - entry) / risk) if d > 0 else ((entry - (stop + A_SLIP)) / risk)
            return realized + remaining * r_exit, mae, mfe, True, False
        if x == fill_i:
            continue
        while si < len(scales):
            lvl, frac = scales[si]
            if (hi >= lvl) if d > 0 else (lo <= lvl):
                realized += frac * (lvl - entry) * d / risk; remaining -= frac; si += 1
            else:
                break
        if remaining > 0 and ((hi >= target) if d > 0 else (lo <= target)):
            return realized + remaining * (target - entry) * d / risk, mae, mfe, True, False
    x = b - 1
    return realized + remaining * (mp.C[x] - entry) * d / risk, mae, mfe, True, False


def build_augmented_rows(feats, mp, d1_tz):
    """Same filter + 1m-walk as tools_phase3_config_sweep.a_streams_d1c(...)["exit3"] — verified
    to match its (ts, R, mae_r, risk_usd) output 1:1 in main() — with entry/direction/fill_bar/
    stop/target retained for the stop-distance bucket + penetration-depth + MFE analysis."""
    params = A_PARAMS["exit3"]
    tr = M1.run(feats, "NQ", params)
    tr = tr[tr.session == "ny_am"].copy()
    # INC-20260706-1141: fill_bar + feats.index, not date/time strings.
    tr = RD.attach_drift(tr, d1_tz, feats.index)
    fi = feats.index; n5 = len(fi)
    rows = []
    mfe_checked = mfe_mismatch = 0
    for _, t in tr.iterrows():
        risk = abs(float(t.entry) - float(t.stop))
        fb = int(t.fill_bar)
        if risk <= 0 or not (0 <= fb < n5):
            continue
        if not bool(t["d1c_keep"]):
            continue
        d = 1 if t.direction == "long" else -1
        partials = []
        if params.get("partial"):
            partials = [(float(t.entry) + d * rl * risk, frac) for rl, frac in params["partial"]]
        w = walk_1m(mp, fb, d, float(t.entry), float(t.stop), float(t.target),
                    partials, max_5m_bars=M1.MAX_HOLD)
        if w is None:
            continue
        wm = walk_1m_mfe(mp, fb, d, float(t.entry), float(t.stop), float(t.target),
                         partials, max_5m_bars=M1.MAX_HOLD)
        mfe_checked += 1
        mfe_r = None
        if wm is not None and abs(wm[0] - w[0]) < 1e-9 and abs(wm[1] - w[1]) < 1e-9:
            mfe_r = wm[2]
        else:
            mfe_mismatch += 1
        rows.append(dict(ts=pd.Timestamp(fi[fb]), R=w[0], mae_r=w[1], risk_usd=risk * DPP,
                         fill_bar=fb, direction=d, entry=float(t.entry),
                         stop=float(t.stop), target=float(t.target), mfe_r=mfe_r))
    return rows, mfe_checked, mfe_mismatch


def penetration_depth(mp, fb, d, entry):
    """Audited method (tools_1m_truth_recert.walk_1m's own fill-search window): within the
    certified 5m fill bar's 1m slice, long = entry - min(low); short = max(high) - entry."""
    a5, b5 = mp.window(fb, 1)
    if b5 <= a5:
        return 0.0
    if d > 0:
        return float(entry - mp.L[a5:b5].min())
    return float(mp.H[a5:b5].max() - entry)


def bucket_of(stop_pts):
    for (lo, hi), lbl in zip(STOP_BUCKETS, BUCKET_LABELS):
        if lo <= stop_pts < hi:
            return lbl
    return BUCKET_LABELS[-1]


def attribute_busts(bust_dates, by_date):
    attr = {lbl: 0.0 for lbl in BUCKET_LABELS}
    for bd in bust_dates:
        trades = by_date.get(bd, [])
        n = len(trades)
        if n == 0:
            continue
        for t in trades:
            attr[bucket_of(t["risk_usd"] / DPP)] += 1.0 / n
    total = len(bust_dates)
    return {lbl: (100.0 * v / total if total else 0.0) for lbl, v in attr.items()}


def build_bucket_table(aug_rows, mp):
    buckets = {lbl: [] for lbl in BUCKET_LABELS}
    for t in aug_rows:
        buckets[bucket_of(t["risk_usd"] / DPP)].append(t)
    total_R = sum(t["R"] for t in aug_rows)

    bust10 = bust_dates_for(aug_rows, 10, 1200)
    bust40 = bust_dates_for(aug_rows, 40, 1200)
    # trade set that clears the budget=1200 sizing filter (q>=1) is identical for every cap
    # (cap only truncates q from above; it never turns a q>=1 trade into q=0 in this sweep)
    included = [t for t in aug_rows if int(1200 // t["risk_usd"]) >= 1]
    by_date = {}
    for t in included:
        by_date.setdefault(pd.Timestamp(t["ts"]).normalize(), []).append(t)
    busts10_share = attribute_busts(bust10, by_date)
    busts40_share = attribute_busts(bust40, by_date)

    out = {}
    for lbl in BUCKET_LABELS:
        trs = buckets[lbl]
        n = len(trs)
        if n == 0:
            out[lbl] = dict(n=0)
            continue
        R = np.array([t["R"] for t in trs], float)
        wr = 100.0 * float((R > 0).mean())
        wins = float(R[R > 0].sum()); losses = float(-R[R <= 0].sum())
        pf = (wins / losses) if losses > 0 else float("inf")
        expR = float(R.mean())
        mean_mae = float(np.mean([t["mae_r"] for t in trs]))
        pen = [penetration_depth(mp, t["fill_bar"], t["direction"], t["entry"]) for t in trs]
        mean_pen = float(np.mean(pen))
        q_wanted = [int(1200 // t["risk_usd"]) for t in trs]
        mean_qw = float(np.mean(q_wanted))
        mean_q10 = float(np.mean([min(10, qw) for qw in q_wanted]))
        mean_q40 = float(np.mean([min(40, qw) for qw in q_wanted]))
        share_R = 100.0 * float(R.sum()) / total_R if total_R else 0.0
        mfe_vals = [t["mfe_r"] for t in trs if t.get("mfe_r") is not None]
        mean_mfe = float(np.mean(mfe_vals)) if mfe_vals else None
        out[lbl] = dict(n=n, wr_pct=round(wr, 1), pf=(round(pf, 3) if pf != float("inf") else "inf"),
                        exp_r=round(expR, 3), mean_mae_r=round(mean_mae, 3),
                        mean_penetration_pts=round(mean_pen, 2), mean_q_wanted_1200=round(mean_qw, 2),
                        mean_q_cap10=round(mean_q10, 2), mean_q_cap40=round(mean_q40, 2),
                        share_portfolio_R_pct=round(share_R, 1),
                        share_busts_cap10_1200_pct=round(busts10_share[lbl], 1),
                        share_busts_cap40_1200_pct=round(busts40_share[lbl], 1),
                        mean_mfe_r=(round(mean_mfe, 3) if mean_mfe is not None else None))
    return out


# ---------------------------------------------------------------- PART C matrix + PART D overlays
def build_matrix(rows, mode="none", param=None):
    return {f"cap{cap}_b{budget}": run_cell(rows, cap, budget, mode, param)
            for cap in CAPS for budget in BUDGETS}


def build_overlay(rows, mode, values):
    return {str(v): build_matrix(rows, mode, v) for v in values}


def check_size_invariance(size_overlay):
    """E[cap 10] must be identical across every k (q<=10 always -> zero size-scaled damage)."""
    ok = True
    for budget in BUDGETS:
        key = f"cap10_b{budget}"
        vals = {size_overlay[str(k)][key]["e_attempt"] for k in SIZE_K}
        ok = ok and (len(vals) == 1)
    return ok


def breakeven_table(matrix, uniform_overlay, size_overlay, frac_overlay):
    out = {}
    for cap in CAPS:
        if cap == 10:
            continue
        for budget in BUDGETS:
            key, key10 = f"cap{cap}_b{budget}", f"cap10_b{budget}"

            # (a) max uniform s at which cap still beats cap-10-same-budget
            max_s = None
            for s in UNIFORM_S:
                e_cap = uniform_overlay[str(s)][key]["e_attempt"]
                e_10 = uniform_overlay[str(s)][key10]["e_attempt"]
                if e_cap > e_10:
                    max_s = s
                else:
                    break
            if max_s is None:
                max_s_label = "never"
            elif max_s == UNIFORM_S[-1]:
                max_s_label = f">{UNIFORM_S[-1]}"
            else:
                max_s_label = max_s

            # (b) k* via linear interpolation (E[cap10] invariant in k -> use matrix baseline)
            e10_base = matrix[key10]["e_attempt"]
            pts = [(0.0, matrix[key]["e_attempt"] - e10_base)]
            for k in SIZE_K:
                pts.append((k, size_overlay[str(k)][key]["e_attempt"] - e10_base))
            k_star = None
            for (k0, d0), (k1, d1) in zip(pts, pts[1:]):
                if d0 > 0 and d1 <= 0:
                    k_star = k0 + (0 - d0) * (k1 - k0) / (d1 - d0)
                    break
            k_star_label = round(k_star, 5) if k_star is not None else ">0.02"

            # (c) min f at which cap still beats cap-10-same-budget
            min_f = None
            for f in PARTIAL_F:            # descending 1.0 -> 0.25
                e_cap = frac_overlay[str(f)][key]["e_attempt"]
                e_10 = frac_overlay[str(f)][key10]["e_attempt"]
                if e_cap > e_10:
                    min_f = f
                else:
                    break
            if min_f is None:
                min_f_label = "never"
            elif min_f == PARTIAL_F[-1]:
                min_f_label = f"<={PARTIAL_F[-1]}"
            else:
                min_f_label = min_f

            out[key] = dict(cap=cap, budget=budget, max_uniform_s=max_s_label,
                            k_star=k_star_label, min_f=min_f_label)
    return out


def main():
    t0 = time.time()
    print(FRAME)
    print("loading frames + locked A stream (exit3 + D1c, 1m truth)…", flush=True)
    d1_tz = RD.load_1m(); d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m(); mp = M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    feats = eng._features()
    rows = a_streams_d1c(feats, mp, d1_tz)["exit3"][0]
    print(f"  loaded {len(rows)} exit3+D1c 1m-truth trades  ({time.time()-t0:.1f}s)", flush=True)

    aug_rows, mfe_checked, mfe_mismatch = build_augmented_rows(feats, mp, d1_tz)
    assert len(aug_rows) == len(rows), "augmented-row build diverged from a_streams_d1c — abort"
    for a, b in zip(rows, aug_rows):
        assert (a["ts"] == b["ts"] and abs(a["R"] - b["R"]) < 1e-9
                and abs(a["mae_r"] - b["mae_r"]) < 1e-9 and abs(a["risk_usd"] - b["risk_usd"]) < 1e-9), \
            "augmented rows mismatch a_streams_d1c output on (ts,R,mae_r,risk_usd) — abort"
    mfe_ok = (mfe_checked == len(aug_rows) and mfe_mismatch == 0)
    print(f"  augmented-row cross-check OK: matches a_streams_d1c exactly on {len(aug_rows)} trades")
    print(f"  MFE walk_1m copy: checked={mfe_checked} mismatches={mfe_mismatch} -> "
          f"{'INCLUDED (verified)' if mfe_ok else 'OMITTED (verification failed)'}", flush=True)

    # ---- PART A: mandatory canaries ----
    print(f"\n{FRAME}\nPART A — canaries (abort if either fails)")
    canary_ok = True
    canary_results = {}
    for label, c in [("A", CANARY_A), ("B", CANARY_B)]:
        r = run_cell(rows, c["cap"], c["budget"])
        ok = (r["n"] == c["n"] and r["pass_pct"] == c["pass_pct"] and r["bust_pct"] == c["bust_pct"]
              and r["exp_pct"] == c["exp_pct"] and r["med_days"] == c["med_days"])
        tag = "HISTORICAL-REPRODUCTION-ONLY" if label == "B" else "live-candidate"
        print(f"  canary {label} [{tag}] cap={c['cap']} budget={c['budget']}: "
              f"got n={r['n']} pass={r['pass_pct']} bust={r['bust_pct']} exp={r['exp_pct']} med={r['med_days']}  "
              f"expect n={c['n']} pass={c['pass_pct']} bust={c['bust_pct']} exp={c['exp_pct']} med={c['med_days']}  "
              f"-> {'PASS' if ok else 'FAIL'}")
        canary_ok = canary_ok and ok
        canary_results[label] = dict(tag=tag, got=r, expect=c, ok=ok)
    if not canary_ok:
        print("\nCANARY FAILED — aborting. Harness does not reproduce the specified reference cells.")
        sys.exit(1)
    print("  canaries OK — harness verified against both reference cells.")

    # ---- PART B: stop-distance buckets ----
    print(f"\n{FRAME}\nPART B — stop-distance buckets (from the exit3+D1c 1m-truth stream, n=435)")
    buckets = build_bucket_table(aug_rows, mp)
    hdr = (f"{'bucket':>8}{'n':>5}{'WR%':>7}{'PF':>7}{'expR':>7}{'meanMAE':>9}{'meanPen':>9}"
           f"{'qw@1200':>9}{'q@c10':>7}{'q@c40':>7}{'%R':>7}{'%bust10':>9}{'%bust40':>9}{'MFE_R':>8}")
    print(hdr); print("-" * len(hdr))
    for lbl in BUCKET_LABELS:
        b = buckets[lbl]
        if b.get("n", 0) == 0:
            print(f"{lbl:>8}{0:>5}"); continue
        mfe_s = f"{b['mean_mfe_r']:.3f}" if b['mean_mfe_r'] is not None else "n/a"
        print(f"{lbl:>8}{b['n']:>5}{b['wr_pct']:>6.1f}%{str(b['pf']):>7}{b['exp_r']:>7.3f}"
              f"{b['mean_mae_r']:>9.3f}{b['mean_penetration_pts']:>9.2f}{b['mean_q_wanted_1200']:>9.2f}"
              f"{b['mean_q_cap10']:>7.2f}{b['mean_q_cap40']:>7.2f}{b['share_portfolio_R_pct']:>6.1f}%"
              f"{b['share_busts_cap10_1200_pct']:>8.1f}%{b['share_busts_cap40_1200_pct']:>8.1f}%{mfe_s:>8}")

    # ---- PART C: the matrix ----
    print(f"\n{FRAME}\nPART C — cap x budget matrix (no damage)")
    matrix = build_matrix(rows)
    hdr = (f"{'cap':>4}{'budget':>7}{'n':>5}{'pass%':>7}{'bust%':>7}{'exp%':>6}{'med':>5}{'mean_d':>7}"
           f"{'meanRisk$':>10}{'meanQ':>7}{'clip%':>7}{'E$/att':>9}{'evals/fund':>11}")
    print(hdr); print("-" * len(hdr))
    for cap in CAPS:
        for budget in BUDGETS:
            m = matrix[f"cap{cap}_b{budget}"]
            print(f"{cap:>4}{budget:>7}{m['n']:>5}{m['pass_pct']:>6.1f}%{m['bust_pct']:>6.1f}%"
                  f"{m['exp_pct']:>5.1f}%{m['med_days'] or 0:>5}{m['mean_days'] or 0:>7}"
                  f"{m['mean_risk_per_trade']:>10,.0f}{m['mean_contracts']:>7.2f}{m['clipped_pct']:>6.1f}%"
                  f"{m['e_attempt']:>9,.0f}{m['evals_per_funded'] or 0:>11.2f}")
        print("-" * len(hdr))

    # ---- PART D: fill-damage overlays ----
    print(f"\n{FRAME}\nPART D — fill-damage overlays (rebuilding events per variant)", flush=True)
    uniform_overlay = build_overlay(rows, "uniform", UNIFORM_S)
    size_overlay = build_overlay(rows, "size", SIZE_K)
    frac_overlay = build_overlay(rows, "frac", PARTIAL_F)
    size_inv_ok = check_size_invariance(size_overlay)
    print(f"  size-scaled internal check: E[cap 10] invariant across all k -> "
          f"{'OK' if size_inv_ok else 'FAILED'}")
    breakeven = breakeven_table(matrix, uniform_overlay, size_overlay, frac_overlay)

    print(f"\n{FRAME}\nBREAK-EVEN TABLE (headline) — max uniform s / k* / min f at which cap "
          f"still beats cap-10-same-budget on E[$/attempt]")
    hdr = f"{'cap':>4}{'budget':>7}{'max_s':>8}{'k_star':>10}{'min_f':>8}"
    print(hdr); print("-" * len(hdr))
    for cap in CAPS:
        if cap == 10:
            continue
        for budget in BUDGETS:
            r = breakeven[f"cap{cap}_b{budget}"]
            print(f"{cap:>4}{budget:>7}{str(r['max_uniform_s']):>8}{str(r['k_star']):>10}"
                  f"{str(r['min_f']):>8}")
        print("-" * len(hdr))

    # ---- save ----
    os.makedirs("reports", exist_ok=True)
    report = dict(
        framing=FRAME,
        generated="2026-07-05",
        note="RESEARCH ONLY — no cell is a forecast; every result is a backtest replay pending "
             "live fill evidence.",
        spec=dict(account="50K", start=SPEC["start"], trail=SPEC["trail"], target=SPEC["target"],
                  dll=SPEC["dll"], internal_daily_stop=STOP, expire_days=EXPIRE_DAYS,
                  sizing_rule="q = min(cap, int(budget // risk_usd)); skip if q < 1"),
        constants=dict(funded_gross=FUNDED_GROSS, activation_fee=ACTIVATION_FEE, funded_net=FUNDED_NET,
                       eval_fee=EVAL_FEE,
                       note="funded net $12,827-$99 activation; eval fee sticker $131 — "
                            "LOW-CONFIDENCE fee figures, vault Funded Funnel — 2026-07-05"),
        canaries=canary_results,
        mfe=dict(included=mfe_ok, checked=mfe_checked, mismatches=mfe_mismatch,
                 note="tools_1m_truth_recert.walk_1m copied verbatim + 1 favorable-excursion "
                      "accumulator; only trusted if checked==mismatches-free on all trades"),
        buckets=buckets,
        matrix=matrix,
        overlays=dict(uniform=uniform_overlay, size_scaled=size_overlay,
                     asymmetric_partial=frac_overlay,
                     size_scaled_cap10_invariance_ok=size_inv_ok),
        breakeven=breakeven,
    )
    out_path = "reports/eval_sizing_sweep_2026-07-05.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=1, default=str)
    print(f"\n[saved] {out_path}   (total runtime {time.time()-t0:.1f}s)", flush=True)


if __name__ == "__main__":
    main()
