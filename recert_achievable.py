"""INC-20260707 RE-CERTIFICATION — STEP 1->2: achievable-subset strategy + eval funnel + funded.

CONSUME-ONLY. Reads `reports/inc_20260707_recert/achievable_keys.csv` (built by the FULL-HISTORY
run of `databento_emission_replay.py`, auditor-triggered) and subsets the CERTIFIED Databento
streams to those keys:
  * UNFILTERED (eval-relevant, phase-split): `tools_1m_truth_recert.a_streams` exit3 variant --
    every ny_am trade, 1m-truth walked, no D1c attach.
  * D1c-KEPT (phase-split): `tools_phase3_config_sweep.a_streams_d1c` exit3 variant -- the
    certified D1c-attached, 1m-truth-walked A stream (same construction as
    `tools_account_size_research.main` / `tools_sim_parity_check.load_rows`).

Every downstream number (day_rows / eval_run / funded_paid) is REUSED BY IMPORT from
`tools_account_size_research` -- never copied -- so the day-level bookkeeping (trough
construction, $550 realized daily stop, $1,000 DLL clamp, EOD ratchet/lock, bust/pass/expire,
funded ladder) is byte-identical to the certified harness.

MEASUREMENT ONLY: frozen strategy untouched (no entry/exit/session/filter/sizing change), not
armed, no hold-lift, VPC unwired (N>=30-gated -- NOT applied here; the cap-6/$900 row below is the
arm-able defensible-minimum on its own, not "A+VPC").

Fee/funded-value figures are LOW-CONFIDENCE / PLACEHOLDER per the Apex-terms canary
(test_apex_terms_canary.py) -- never launder these as certified funded numbers.

Do NOT run until `reports/inc_20260707_recert/achievable_keys.csv` exists (the auditor triggers
this after the full-history `databento_emission_replay.py` background run completes). This script
refuses to guess and exits loudly if the file is missing.
"""
import argparse, json, os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import strategy_engine_profileA as E                                   # noqa: E402
import config                                                            # noqa: E402
import run_d1c_real as RD                                                # noqa: E402
import apex_eval_eod_databento as DB                                     # noqa: E402  CERTIFIED Databento 5m loader
from tools_1m_truth_recert import M1Map, a_streams as a_streams_unfiltered   # noqa: E402
from tools_phase3_config_sweep import a_streams_d1c                      # noqa: E402
from tools_account_size_research import day_rows, eval_run, funded_paid  # noqa: E402  reused BY IMPORT

NY = "America/New_York"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "reports", "inc_20260707_recert")
DEFAULT_KEYS = os.path.join(OUT_DIR, "achievable_keys.csv")

# 50K spec -- matches the deployed machine / tools_account_size_research.SPECS["50K"] exactly
# (stop=550 == ARES 50K daily stop, dll=1000 == Apex 50K DLL).
SPEC_50K = dict(start=50_000.0, trail=2_500.0, target=3_000.0, dll=1_000.0, stop=550.0,
                fee_mo=45.0, max_qty=60, ladder=[1_500, 1_500, 2_000, 2_500, 2_500, 3_000])
A_CAP = 6                    # arm-able defensible-minimum cap -- its OWN explicit row, not A+VPC
A_BUDGET = 900.0
FUNDED_BUDGET_FRAC = 0.4     # certified 50K funded fraction of eval budget (research convention)
EXPIRE_DAYS = 30


def load_achievable_keys(path):
    if not os.path.exists(path):
        raise SystemExit(
            f"[BLOCKED] achievable_keys.csv not found at {path}. This script is consume-only and "
            f"will not guess -- run the FULL-HISTORY databento_emission_replay.py first (the "
            f"auditor triggers this after reviewing the Step-0 feasibility slice)."
        )
    df = pd.read_csv(path)
    return set(df["key"].astype(str))


def build_frames():
    d1_tz = RD.load_1m(); d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m()
    mp = M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    feats = eng._features()
    return d1_tz, df5, mp, feats


def subset_unfiltered(feats, mp, df5, keys):
    """Phase-split UNFILTERED (eval-relevant): every ny_am exit3 trade, 1m-truth walked, no D1c
    filter, subset to the achievable keys."""
    streams = a_streams_unfiltered(feats, mp, df5)["exit3"]
    out = []
    for t in streams:
        if t["R_new"] is None:
            continue
        k = pd.Timestamp(t["ts"]).isoformat()
        if k not in keys:
            continue
        out.append(dict(ts=pd.Timestamp(t["ts"]), R=t["R_new"], mae_r=t["mae_new"],
                        risk_usd=t["risk_usd"]))
    out.sort(key=lambda r: r["ts"])
    return out


def subset_d1c(feats, mp, d1_tz, keys):
    """Phase-split D1c-KEPT: the certified a_streams_d1c exit3 stream, subset to achievable keys."""
    rows, dropped = a_streams_d1c(feats, mp, d1_tz)["exit3"]
    out = [r for r in rows if pd.Timestamp(r["ts"]).isoformat() in keys]
    out.sort(key=lambda r: r["ts"])
    return out, dropped


def strategy_stats(rows):
    if not rows:
        return dict(n=0)
    r = np.array([x["R"] for x in rows], float)
    wins = r[r > 0].sum(); losses = -r[r <= 0].sum()
    ts = pd.DatetimeIndex([x["ts"] for x in rows])
    span_wk = max(1.0, (ts.max() - ts.min()).days / 7.0)
    return dict(n=len(r), PF=(float(wins / losses) if losses else float("inf")),
               WR=round(100.0 * (r > 0).mean(), 1), totR=round(float(r.sum()), 2),
               expR=round(float(r.mean()), 3), trades_per_wk=round(len(r) / span_wk, 2))


def per_year_stats(rows):
    out = {}
    if not rows:
        return out
    df = pd.DataFrame([(pd.Timestamp(x["ts"]).year, x["R"]) for x in rows], columns=["yr", "R"])
    for yr, g in df.groupby("yr"):
        r = g["R"].values
        wins = r[r > 0].sum(); losses = -r[r <= 0].sum()
        out[int(yr)] = dict(n=len(r), PF=(round(float(wins / losses), 3) if losses else float("inf")),
                            WR=round(100.0 * (r > 0).mean(), 1))
    return out


def eval_funnel(rows, cap, budget):
    """A-ONLY eval funnel at (cap, budget) on the achievable-subset D1c-kept stream. VPC unwired
    (N>=30-gated) -- NOT applied here; this is the cap-6/$900 arm-able defensible-minimum on its
    own, reported as its own explicit row (not "A+VPC")."""
    ev = []
    for t in rows:
        risk1 = t["risk_usd"]
        q = min(cap, int(budget // risk1))
        if q < 1:
            continue
        ev.append(dict(ts=pd.Timestamp(t["ts"]), pnl=t["R"] * risk1 * q,
                       mae=min(0.0, t["mae_r"]) * risk1 * q))
    ev.sort(key=lambda e: e["ts"])
    if not ev:
        return dict(n=0)
    days = day_rows(ev, SPEC_50K["stop"], SPEC_50K["dll"])
    starts, seen = [], set()
    for i, (d, _, _) in enumerate(days):
        if d not in seen and (days[-1][0] - d).days > EXPIRE_DAYS:
            seen.add(d); starts.append(i)
    if not starts:
        return dict(n=0)
    res = [eval_run(days, s, SPEC_50K) for s in starts]
    n = len(res)
    p = 100 * sum(1 for r in res if r[0] == "PASS") / n
    b = 100 * sum(1 for r in res if r[0] == "BUST") / n
    x = 100 * sum(1 for r in res if r[0] == "EXPIRE") / n
    pass_days = [r[1] for r in res if r[0] == "PASS"]
    med = float(np.median(pass_days)) if pass_days else None
    mean = float(np.mean(pass_days)) if pass_days else None
    # funded at FUNDED_BUDGET_FRAC of eval budget (certified 50K funded fraction convention) --
    # LOW-CONFIDENCE / PLACEHOLDER, see module docstring.
    fdays = day_rows([dict(ts=e["ts"], pnl=e["pnl"] * FUNDED_BUDGET_FRAC,
                           mae=e["mae"] * FUNDED_BUDGET_FRAC) for e in ev],
                     SPEC_50K["stop"], SPEC_50K["dll"])
    fp = funded_paid(fdays, SPEC_50K)
    e_attempt = (p / 100) * fp - SPEC_50K["fee_mo"] * 1.5
    return dict(cap=cap, budget=budget, n_starts=n, pass_pct=round(p, 1), bust_pct=round(b, 1),
               exp_pct=round(x, 1), med_days_to_pass=med, mean_days_to_pass=mean,
               e_funded_LOW_CONFIDENCE=round(fp), e_per_attempt_LOW_CONFIDENCE=round(e_attempt))


def funded_survival(rows, cap, budget):
    """FUNDED survival + E[paid] on the achievable stream at FUNDED_BUDGET_FRAC of the eval
    budget. WIDE-CI CAVEAT: the achievable subset is far smaller than the full certified stream
    (only ~1 trade every few days survives to begin with) -- expect on the order of ~4-5
    EFFECTIVE INDEPENDENT quarterly funded starts here, so every number below is directional,
    not a precise point estimate."""
    ev = []
    for t in rows:
        risk1 = t["risk_usd"]
        q = min(cap, int((FUNDED_BUDGET_FRAC * budget) // risk1))
        if q < 1:
            continue
        ev.append(dict(ts=pd.Timestamp(t["ts"]), pnl=t["R"] * risk1 * q,
                       mae=min(0.0, t["mae_r"]) * risk1 * q))
    ev.sort(key=lambda e: e["ts"])
    if not ev:
        return dict(n_quarterly_starts=0)
    days = day_rows(ev, SPEC_50K["stop"], SPEC_50K["dll"])
    fp = funded_paid(days, SPEC_50K)
    n_quarterly_starts = len([d for d, _, _ in days if (days[-1][0] - d).days >= 365][::63]) if days else 0
    return dict(e_paid_mean_LOW_CONFIDENCE=round(fp), n_quarterly_starts=n_quarterly_starts,
               caveat="WIDE-CI: ~4-5 effective independent samples on the achievable subset -- "
                      "treat as directional, not a precise point estimate")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", default=DEFAULT_KEYS)
    args = ap.parse_args()

    print("[reminder] test_funded_config_firewall.py must be green before AND after this script -- "
          "run it separately (this script does not touch funded config).", flush=True)

    keys = load_achievable_keys(args.keys)
    print(f"[load] {len(keys)} achievable keys from {args.keys}", flush=True)

    print("[build] loading certified Databento frames + feats ...", flush=True)
    d1_tz, df5, mp, feats = build_frames()

    print("[subset] UNFILTERED (eval-relevant) achievable-subset stream ...", flush=True)
    unf_rows = subset_unfiltered(feats, mp, df5, keys)
    print("[subset] D1c-KEPT achievable-subset stream ...", flush=True)
    d1c_rows, dropped = subset_d1c(feats, mp, d1_tz, keys)

    out = dict(inc="INC-20260707", frame="MEASUREMENT ONLY -- frozen strategy untouched; "
               "no arming, no hold-lift, no VPC wiring")

    out["strategy_unfiltered"] = strategy_stats(unf_rows)
    out["strategy_unfiltered"]["per_year"] = per_year_stats(unf_rows)
    out["strategy_d1c_kept"] = strategy_stats(d1c_rows)
    out["strategy_d1c_kept"]["per_year"] = per_year_stats(d1c_rows)
    out["strategy_d1c_kept"]["dropped_by_d1c"] = dropped

    print("\n=== STRATEGY (achievable subset) ===", flush=True)
    print(f"  UNFILTERED (eval-relevant): {out['strategy_unfiltered']}", flush=True)
    print(f"  D1c-KEPT:                   {out['strategy_d1c_kept']}", flush=True)

    print("\n[eval] A-ONLY cap-6/$900 (arm-able defensible-minimum, VPC unwired, own row) ...",
          flush=True)
    row_cap6 = eval_funnel(d1c_rows, A_CAP, A_BUDGET)
    out["eval_A_only_cap6_budget900_LOW_CONFIDENCE_fees"] = row_cap6
    print(f"  {row_cap6}", flush=True)

    print("\n[funded] survival + E[paid] on achievable subset (WIDE-CI) ...", flush=True)
    fund_row = funded_survival(d1c_rows, A_CAP, A_BUDGET)
    out["funded_cap6_budget900_LOW_CONFIDENCE"] = fund_row
    print(f"  {fund_row}", flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "recert_achievable_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n[saved] {out_path}", flush=True)
    print("[note] fee/funded-value figures are LOW-CONFIDENCE/PLACEHOLDER per the Apex-terms "
          "canary -- never launder as certified funded numbers.", flush=True)


if __name__ == "__main__":
    main()
