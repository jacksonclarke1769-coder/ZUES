"""ZEUS passrate_opt — VPC eval PASS-RATE optimization across FIRMS x SIZING (honest sim).

READ-ONLY on bot strategy code (imports only). Writes ONLY under research/passrate_opt +
reports/passrate_opt. Nothing armed. Sim measurement only.

Reuses the CERTIFIED VPC signal/fill + day-collapse machinery BY IMPORT:
  * research/fork_b/honest_eval_engines.py  -> databento_5m_rth, vpc_trades_rich, vpc_events_risk
  * tools_account_size_research (H)         -> day_rows (ARES $550 stop + firm DLL flatten)
The ONLY thing this file re-implements is the per-firm EVAL RULE (EOD-trail vs STATIC dd,
time-limit vs unlimited/censored, min-days, consistency %) so we can sweep the firm option space.
The VPC edge, fills, sizing model, and the $550 ARES self-imposed daily stop are held IDENTICAL to
the fork_b canary (PASS 12.6/BUST 3.6/EXP 83.8 at Apex $600/cap3).

FIRM RULES (2026) ARE UNVERIFIED — sourced from the task brief (reports/cross_firm/00_firm_rules_2026.md
does NOT exist in-repo). Every $ threshold is flagged UNVERIFIED. ETF Static $2,000 especially so.
All 50K evals modeled with a $3,000 profit target (UNVERIFIED per firm).
"""
import os, sys, json, hashlib, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "research", "fork_b"))
sys.path.insert(0, REPO)
import honest_eval_engines as F          # VPC builders + Databento loader (reused by import)
import tools_account_size_research as H  # day_rows (ARES stop + DLL), certified collapse

NY = "America/New_York"
START = 50_000.0
TARGET = 3_000.0            # 50K profit target (UNVERIFIED per firm)
ARES_STOP = 550.0          # self-imposed daily realized stop — held IDENTICAL across firms
NO_DLL = 1e12              # sentinel: no daily-loss-limit flatten
DATA_END = None            # set at runtime = last day in the data

# ---- FIRM SPECS (UNVERIFIED $ from task brief) --------------------------------------------------
# dd_type: 'trail' = EOD-trail ratchet (locks at start+100) ; 'static' = fixed floor, never ratchets
# expire_days: None = UNLIMITED (run to data end -> CENSORED if unresolved)
# consistency: None or fraction (max single-day profit must be <= frac * total profit at pass)
# min_days: minimum number of active trading days before a PASS can be claimed
FIRMS = {
    "Apex50K":       dict(dd_type="trail",  dd=2500.0, dll=1000.0, expire_days=30,   consistency=None, min_days=1),
    "Topstep50K":    dict(dd_type="trail",  dd=2000.0, dll=NO_DLL, expire_days=None, consistency=0.50, min_days=5),
    "MFFU_Builder":  dict(dd_type="trail",  dd=2000.0, dll=NO_DLL, expire_days=None, consistency=None, min_days=2),
    "Bulenox_EOD":   dict(dd_type="trail",  dd=2500.0, dll=1100.0, expire_days=None, consistency=None, min_days=1),
    "ETF_Static":    dict(dd_type="static", dd=2000.0, dll=NO_DLL, expire_days=None, consistency=None, min_days=5),
    "Tradeify_Sel":  dict(dd_type="trail",  dd=2000.0, dll=NO_DLL, expire_days=None, consistency=0.40, min_days=3),
}

# ---- SIZING GRID ---------------------------------------------------------------------------------
BUDGETS = [600, 900, 1200, 1500, 2000]
CAPS = [3, 4, 6, 8, 10]


# =================================================================================================
def all_starts(days):
    """UNLIMITED firms: every trading day is an eligible eval start (rolling 1/day)."""
    return list(range(len(days)))


def bounded_starts(days, expire_days):
    """APEX-style: only starts with > expire_days of room ahead (fair 30-day window)."""
    starts, seen, last = [], set(), days[-1][0]
    for i, (d, _, _) in enumerate(days):
        if d not in seen and (last - d).days > expire_days:
            seen.add(d); starts.append(i)
    return starts


def eval_one(days, s0, firm):
    """Run ONE eval from start index s0 under a firm's rule set.
    Returns (outcome, days_to_resolve). outcome in {PASS,BUST,EXPIRE,CENSORED}."""
    dd, dd_type = firm["dd"], firm["dd_type"]
    expire, cons, min_days = firm["expire_days"], firm["consistency"], firm["min_days"]
    thr = START - dd
    bal, peak, locked = START, START, False
    t0 = days[s0][0]
    max_day_profit = 0.0
    active = 0
    for i in range(s0, len(days)):
        d, real, trough = days[i]
        # time limit (Apex) ----------------------------------------------------------------------
        if expire is not None and (d - t0).days > expire:
            return "EXPIRE", expire
        # intraday marked-trough liquidation (before applying the day's realized) -----------------
        if bal + min(0.0, trough) <= thr:
            return "BUST", (d - t0).days
        bal += real
        active += 1
        max_day_profit = max(max_day_profit, real)
        # threshold update -------------------------------------------------------------------------
        if dd_type == "trail":
            peak = max(peak, bal)                       # EOD close-set ratchet
            if not locked:
                thr = max(thr, peak - dd)
                if peak - dd >= START + 100.0:
                    thr = START + 100.0; locked = True
        # (static: thr never moves)
        if bal <= thr:
            return "BUST", (d - t0).days
        # PASS test with min-days + consistency filter --------------------------------------------
        if bal >= START + TARGET and active >= min_days:
            total_profit = bal - START
            if cons is None or (total_profit > 0 and max_day_profit <= cons * total_profit):
                return "PASS", (d - t0).days
            # else: consistency not yet met -> keep trading to dilute the big day
    # ran out of data without resolving
    if expire is not None:
        return "EXPIRE", expire          # (won't happen for Apex given bounded starts)
    return "CENSORED", (days[-1][0] - t0).days


def run_cell(vpc, firm, budget, cap):
    ev = F.vpc_events_risk(vpc, budget=budget, cap=cap)
    ev = sorted([dict(ts=e["ts"], pnl=e["pnl"], mae=e["mae"]) for e in ev], key=lambda e: e["ts"])
    days = H.day_rows(ev, ARES_STOP, firm["dll"])
    if len(days) < 2:
        return None
    starts = (bounded_starts(days, firm["expire_days"]) if firm["expire_days"] is not None
              else all_starts(days))
    outs = [eval_one(days, s, firm) for s in starts]
    n = len(outs)
    npass = sum(1 for o in outs if o[0] == "PASS")
    nbust = sum(1 for o in outs if o[0] == "BUST")
    nexp = sum(1 for o in outs if o[0] == "EXPIRE")
    ncen = sum(1 for o in outs if o[0] == "CENSORED")
    pdays = sorted(o[1] for o in outs if o[0] == "PASS")
    resolved = npass + nbust
    # trades/wk from the event stream
    if ev:
        ts = pd.to_datetime([pd.Timestamp(e["ts"]).tz_convert("UTC") if pd.Timestamp(e["ts"]).tzinfo
                             else pd.Timestamp(e["ts"], tz="UTC") for e in ev])
        wk = max(1.0, (ts.max() - ts.min()).days / 7.0)
        trwk = round(len(ev) / wk, 2)
    else:
        trwk = 0.0
    return dict(
        firm=firm.get("_name"), budget=budget, cap=cap, n_starts=n,
        pass_pct=round(100 * npass / n, 1), bust_pct=round(100 * nbust / n, 1),
        exp_pct=round(100 * (nexp + ncen) / n, 1),
        expire_pct=round(100 * nexp / n, 1), censored_pct=round(100 * ncen / n, 1),
        pass_resolved_pct=(round(100 * npass / resolved, 1) if resolved else None),
        med_days=(int(np.median(pdays)) if pdays else None),
        p25_days=(int(np.percentile(pdays, 25)) if pdays else None),
        p75_days=(int(np.percentile(pdays, 75)) if pdays else None),
        trades_per_wk=trwk, n_events=len(ev), n_pass=npass, n_bust=nbust, n_cen=ncen,
    )


def per_year_passes(vpc, firm, budget, cap):
    """Per-year breakdown of PASS count by START year (concentration check)."""
    ev = F.vpc_events_risk(vpc, budget=budget, cap=cap)
    ev = sorted([dict(ts=e["ts"], pnl=e["pnl"], mae=e["mae"]) for e in ev], key=lambda e: e["ts"])
    days = H.day_rows(ev, ARES_STOP, firm["dll"])
    starts = (bounded_starts(days, firm["expire_days"]) if firm["expire_days"] is not None
              else all_starts(days))
    yr_pass, yr_tot = {}, {}
    for s in starts:
        y = days[s][0].year
        yr_tot[y] = yr_tot.get(y, 0) + 1
        if eval_one(days, s, firm)[0] == "PASS":
            yr_pass[y] = yr_pass.get(y, 0) + 1
    return {int(y): dict(passes=yr_pass.get(y, 0), starts=yr_tot.get(y, 0)) for y in sorted(yr_tot)}


def md5_of(obj):
    return hashlib.md5(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def main():
    print("loading Databento 5m + building VPC trades (reused fork_b machinery)…", flush=True)
    df5 = F.databento_5m_rth()
    feats = F.v.features(df5); feats = feats[feats.date >= F.START_DATE]
    vpc = F.vpc_trades_rich(feats)
    global DATA_END
    DATA_END = df5.index.max()
    print(f"  VPC trades={len(vpc)} net={vpc.pnl_pts.sum():.0f}pt  data_end={DATA_END.date()}", flush=True)

    # ---- CANARY: Apex $600/cap3 must reproduce 12.6/3.6/83.8 ----
    fa = dict(FIRMS["Apex50K"]); fa["_name"] = "Apex50K"
    can = run_cell(vpc, fa, 600, 3)
    print(f"[CANARY] Apex50K $600/cap3 -> pass {can['pass_pct']} bust {can['bust_pct']} "
          f"exp {can['exp_pct']} med {can['med_days']}d tr/wk {can['trades_per_wk']} "
          f"(target 12.6/3.6/83.8/19)", flush=True)

    out = {"meta": dict(
        vendor="Databento NQ 1m->5m RTH", window=f"{F.START_DATE.date()}->{DATA_END.date()}",
        engine="fork_b VPC builders (import) + tools_account_size_research.day_rows (import) + "
               "parametrized per-firm eval rule (this file)",
        ares_daily_stop=ARES_STOP, target=TARGET,
        firms_UNVERIFIED={k: {kk: vv for kk, vv in v.items()} for k, v in FIRMS.items()},
        note="ALL firm $ thresholds UNVERIFIED (no reports/cross_firm file in repo). "
             "Unlimited-time firms: every trading day is a start; unresolved-by-data-end = CENSORED "
             "(NOT a fail). pass_resolved_pct = passes/(passes+busts).",
    ), "canary_apex_600_3": can}

    # ---- FULL SWEEP: firm x budget x cap ----
    print("\n=== FULL SWEEP (firm x budget x cap) ===", flush=True)
    grid = {}
    for fname, fspec in FIRMS.items():
        firm = dict(fspec); firm["_name"] = fname
        cells = []
        for b in BUDGETS:
            for c in CAPS:
                r = run_cell(vpc, firm, b, c)
                if r: cells.append(r)
        grid[fname] = cells
        # best by pass metric appropriate to firm (resolved for unlimited, raw for Apex)
        key = (lambda r: r["pass_pct"]) if fspec["expire_days"] is not None else \
              (lambda r: (r["pass_resolved_pct"] or 0))
        best = max(cells, key=key)
        m = "pass" if fspec["expire_days"] is not None else "pass_resolved"
        bv = best["pass_pct"] if fspec["expire_days"] is not None else best["pass_resolved_pct"]
        print(f"  {fname:14s} best {m}={bv}%  @ ${best['budget']}/cap{best['cap']}  "
              f"bust {best['bust_pct']}%  med {best['med_days']}d  cen {best['censored_pct']}%", flush=True)
    out["grid"] = grid

    # ---- per-year concentration for each firm's best cell ----
    print("\n=== PER-YEAR concentration (best cell / firm) ===", flush=True)
    peryear = {}
    for fname, fspec in FIRMS.items():
        firm = dict(fspec); firm["_name"] = fname
        key = (lambda r: r["pass_pct"]) if fspec["expire_days"] is not None else \
              (lambda r: (r["pass_resolved_pct"] or 0))
        best = max(grid[fname], key=key)
        py = per_year_passes(vpc, firm, best["budget"], best["cap"])
        peryear[fname] = dict(cell=f"${best['budget']}/cap{best['cap']}", by_year=py)
        tot = sum(v["passes"] for v in py.values())
        share = {y: (round(100 * v["passes"] / tot, 1) if tot else 0) for y, v in py.items()}
        flag = any(s > 50 for s in share.values())
        print(f"  {fname:14s} {best['budget']}/cap{best['cap']}: "
              f"{ {y: v['passes'] for y,v in py.items()} }  share%={share}  "
              f"{'<<CONCENTRATION>>' if flag else ''}", flush=True)
    out["per_year_best"] = peryear

    payload = {k: v for k, v in out.items() if k != "meta"}
    out["md5"] = md5_of(payload)
    with open(os.path.join(REPO, "reports", "passrate_opt", "01_vpc_firm_sizing.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n[md5] {out['md5']}")
    print("[saved] reports/passrate_opt/01_vpc_firm_sizing.json")
    return out


if __name__ == "__main__":
    main()
