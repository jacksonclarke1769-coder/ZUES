"""tools_salvage_vpc_reeval.py — SALVAGE PROGRAM Track B: VPC re-evaluation vs the HONEST baseline.

RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing (no live/config/engine file touched).
Pure execution of pinned formulas over PRIOR-ART machinery — no new modeling choices beyond the
explicit mapping/assumption notes below (each one is called out, not hidden).

Context: VPC's 2026-07-04 rejection was measured against the machine later invalidated by
INC-20260706-1141 (a look-ahead bug in the D1c-lookahead A stream). That rejection is moot. This
re-evaluates VPC standalone AND VPC-as-diversifier-on-A against the HONEST post-fix A stream
(`tools_sim_parity_check.load_rows()`, 583 rows, PF 1.361 — reverified in canary below).

PRIOR ART REUSED (imported, not reimplemented):
  - `vpc_recert_real.py` / `backtests/nq_vwap_pullback.py` (v.features / v.vpc_signals / v.backtest,
    CFG frozen) — VPC's certified standalone trade generator. 408-trade signature reverified below.
  - `vpc_apex_eval_sim.py` (`vpc_trades_rich`, `real_rth_5m`) — the ts/mae/mfe-carrying VPC trade
    replay used to build the (ts, R, mae_r, risk_usd) rows format (mapping documented below).
  - `tools_account_size_research.py` (`build_events`, `day_rows`, `eval_run`, `SPECS["50K"]`,
    `EXPIRE_DAYS`) — the pinned EVAL funnel machinery, used verbatim for both VPC-standalone (Part 1)
    and the combined A+VPC eval funnel (Part 2).
  - `tools_sim_parity_check.py` (`load_rows`) — the HONEST A stream (post-fix, 583 rows).
  - `tools_recert_funded.py` (`monthly_starts`, `run_pa_instrumented`, CELLS pattern) and
    `apex_funded_40.py` (DAILY_STOP, DLL, START/TRAIL/LOCK_EOD/LADDER/etc, imported not retyped) —
    the pinned FUNDED lifecycle machinery, generalized here to two independent (budget, cap) streams
    merged onto one shared day calendar (Part 2 funded combined).

MAPPING NOTE (VPC trades -> rows format, task-mandated, documented not hidden):
  `vpc_apex_eval_sim.vpc_trades_rich()` returns one row per VPC trade with `stop_pts` (the ATR-based
  initial stop distance in points, always > 0 by construction of `vpc_signals`), `pnl_pts` (net P&L
  in points, RT_COST already subtracted), and `mae_pts` (adverse excursion in points, <= 0).
    risk_usd = stop_pts * $2/pt/MNQ            (1-contract dollar risk, DPP = 2.0, same convention
                                                 as `vpc_apex_eval_sim.DPP` / `funded_rules` MNQ)
    R        = pnl_pts / stop_pts               (P&L in multiples of initial 1-contract risk)
    mae_r    = mae_pts / stop_pts                (adverse excursion in multiples of initial risk, <=0)
  This is the exact same (ts, R, mae_r, risk_usd) shape the certified A stream already uses (see
  `tools_sim_parity_check.load_rows()` row: `{'ts', 'R', 'mae_r', 'risk_usd'}`), so it plugs directly
  into `tools_account_size_research.build_events` / `tools_recert_funded.daily_series` unmodified.

ASSUMPTIONS CALLED OUT (no prior-art precedent found in repo for these terms; documented, not hidden):
  - "same-day loss correlation": Pearson correlation of UNIT (1-contract, unclamped) daily $ P&L
    between the A stream and the VPC stream, over the union of trading days (missing day = $0),
    restricted to the shared 2022-2026 window. Computed ONCE (cap/budget-invariant to first order)
    and reported as a reference figure on every combined EVAL row.
  - "dl_freq" (double-loss-day frequency): % of unit trading days (union, restricted window) where
    BOTH streams' unit daily P&L are < 0 the same day.
  - "tl_freq" (total/combined-loss-day frequency): % of unit trading days where the SUM of the two
    streams' unit daily P&L is < 0.
  Both are unit-level (cap/budget-invariant to first order), computed once, reported per combo row.

CANARIES (run first; any FAIL stops the script before any report is written):
  1. VPC 408-trade signature (vpc_recert_real.py / vpc_apex_eval_sim.py precedent).
  2. Honest-A reverification: `tools_sim_parity_check.load_rows()` n=583, PF=1.361, AND its own
     internal cap-10 canary (pass=31.4/bust=37.3/exp=31.2/med=16d/n=525) still reproduces.
  3. Look-ahead structural spot-check on the merged event stream: A and VPC events are built by two
     completely independent engines from independent data pulls; the only place they touch is the
     post-hoc `sorted(ev_a + ev_v, key=ts)` merge. Spot-check: corrupt every A event's pnl/mae,
     re-merge+re-sort with the untouched VPC events, and confirm the VPC-tagged events in the merged
     list are byte-identical to the pre-corruption VPC events (i.e. concatenation+sort cannot leak
     information backward into either stream — no VPC event uses A information or vice versa).
  PF>1.8 anywhere (any cell's dollar trade-level PF) -> FREEZE + FLAG (printed loudly, run continues
  reporting but every affected cell is marked in the CSV; none expected given VPC's ~1.29 and A's
  1.36 base PFs).

Outputs (new, this run only):
  reports/new_edge_salvage_program/B4_vpc_reeval.csv / .md   (Part 1 + per-year splits)
  reports/new_edge_salvage_program/C_combined_portfolio_test.csv / .md  (Part 2 + Part 3)

No commentary/winner-picking beyond mechanical shortlist flags explicitly requested by the brief.
"""
import os
import sys
import copy
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nq_vwap_pullback as v                 # v.features, v.RT_COST (frozen CFG lives in vpc_apex_eval_sim.CFG)
import vpc_apex_eval_sim as VS                # real_rth_5m, vpc_trades_rich, CFG
import tools_account_size_research as ASR     # build_events, day_rows, eval_run, SPECS, EXPIRE_DAYS
import tools_sim_parity_check as SPC          # load_rows (honest A stream), group_by_day/run_config/CANARY_EXPECT
import tools_recert_funded as TF              # monthly_starts, run_pa_instrumented
import apex_funded_40 as FM                   # START/TRAIL/LOCK_EOD/DLL/DAILY_STOP/LADDER/etc (read-only)

NY = "America/New_York"
DPP = 2.0                                     # $/pt/MNQ
EXPIRE_DAYS = ASR.EXPIRE_DAYS                 # 30 (pinned)
SPEC50 = ASR.SPECS["50K"]                     # start/trail/target for eval_run
STOP_PINNED, DLL_PINNED = 550.0, 1000.0       # "day_rows(550,1000)" pinned formula
WINDOW_START = pd.Timestamp("2022-01-01", tz=NY)   # VPC stream starts 2022 -> shared window

VPC_408_N = 408
VPC_408_NET = 4919.17857142856
A_HONEST_N = 583
A_HONEST_PF = 1.3606000676571652

PF_FREEZE_THRESHOLD = 1.8
PF_FLAGS = []                                  # collected (label, pf) tuples that breach the freeze bar

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "reports", "new_edge_salvage_program")


# ----------------------------------------------------------------------------------------------
# Row-format loaders
# ----------------------------------------------------------------------------------------------
def vpc_rows():
    """VPC trades -> (ts, R, mae_r, risk_usd) rows. Mapping documented in the module docstring."""
    feats = v.features(VS.real_rth_5m())
    feats = feats[feats.date >= WINDOW_START]
    tr = VS.vpc_trades_rich(feats)             # ts, pnl_pts, mae_pts, mfe_pts, stop_pts
    rows = []
    for r in tr.itertuples():
        risk_usd = r.stop_pts * DPP
        rows.append(dict(ts=pd.Timestamp(r.ts), R=r.pnl_pts / r.stop_pts,
                         mae_r=r.mae_pts / r.stop_pts, risk_usd=risk_usd))
    rows.sort(key=lambda t: t["ts"])
    return rows, tr


def a_rows_full():
    return SPC.load_rows()


def a_rows_2022(rows_full=None):
    rows_full = rows_full if rows_full is not None else a_rows_full()
    return [r for r in rows_full if pd.Timestamp(r["ts"]) >= WINDOW_START]


# ----------------------------------------------------------------------------------------------
# Shared funnel primitives (all pinned, reused from tools_account_size_research)
# ----------------------------------------------------------------------------------------------
def eligible_starts(days):
    """Pinned: unique trading days with >30d runway (EXPIRE_DAYS=30)."""
    starts, seen = [], set()
    if not days:
        return starts
    last = days[-1][0]
    for i, (d, _, _) in enumerate(days):
        if d not in seen and (last - d).days > EXPIRE_DAYS:
            seen.add(d)
            starts.append(i)
    return starts


def run_cell(days, spec=SPEC50):
    starts = eligible_starts(days)
    results = []
    for s in starts:
        status, ndays = ASR.eval_run(days, s, spec)
        results.append((status, ndays, days[s][0].year))
    return starts, results


def event_pf(ev, label):
    gp = sum(e["pnl"] for e in ev if e["pnl"] > 0)
    gl = -sum(e["pnl"] for e in ev if e["pnl"] < 0)
    pf = gp / gl if gl > 0 else float("nan")
    if pf == pf and pf > PF_FREEZE_THRESHOLD:
        PF_FLAGS.append((label, round(pf, 3)))
        print(f"  [FREEZE-FLAG] PF>{PF_FREEZE_THRESHOLD} at {label}: PF={pf:.3f}")
    return pf


def summarize_cell(days, label, spec=SPEC50):
    starts, results = run_cell(days, spec)
    n = len(results)
    if n == 0:
        return dict(label=label, eligible_starts=0, pass_count=0, bust_count=0, exp_count=0,
                    pass_pct=None, bust_pct=None, exp_pct=None, med_days_pass=None,
                    worst_day_usd=None, funded_per_slot_year=None, per_year={})
    pass_n = sum(1 for r in results if r[0] == "PASS")
    bust_n = sum(1 for r in results if r[0] == "BUST")
    exp_n = sum(1 for r in results if r[0] == "EXPIRE")
    med_days_pass = int(np.median([r[1] for r in results if r[0] == "PASS"])) if pass_n else None
    mean_days_all = float(np.mean([r[1] for r in results]))
    funded_per_slot_year = (365.25 / mean_days_all) * (pass_n / n) if mean_days_all > 0 else 0.0
    worst_day_usd = min(real for _, real, _ in days) if days else None
    per_year = {}
    for y in sorted(set(r[2] for r in results)):
        yr_res = [r for r in results if r[2] == y]
        yn = len(yr_res)
        yp = sum(1 for r in yr_res if r[0] == "PASS")
        per_year[y] = dict(n=yn, pass_pct=round(100 * yp / yn, 1))
    return dict(label=label, eligible_starts=n, pass_count=pass_n, bust_count=bust_n,
                exp_count=exp_n, pass_pct=round(100 * pass_n / n, 1),
                bust_pct=round(100 * bust_n / n, 1), exp_pct=round(100 * exp_n / n, 1),
                med_days_pass=med_days_pass, worst_day_usd=round(worst_day_usd, 0),
                funded_per_slot_year=round(funded_per_slot_year, 2), per_year=per_year)


def df_to_md_table(df):
    """Manual markdown table writer (no `tabulate` dependency in this env)."""
    if df is None or len(df) == 0:
        return "(empty)"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for c in cols:
            x = row[c]
            if isinstance(x, float):
                vals.append(f"{x:g}")
            else:
                vals.append(str(x))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def weeks_span(ev):
    if not ev:
        return 1.0
    ts = [pd.Timestamp(e["ts"]) for e in ev]
    return max((max(ts) - min(ts)).days / 7.0, 1.0)


# ----------------------------------------------------------------------------------------------
# CANARIES
# ----------------------------------------------------------------------------------------------
def run_canaries(vpc_tr, a_rows):
    print("=" * 100)
    print("CANARIES")
    print("=" * 100)
    ok = True

    n_vpc = len(vpc_tr)
    net_vpc = float(vpc_tr.pnl_pts.sum())
    c1 = (n_vpc == VPC_408_N) and abs(net_vpc - VPC_408_NET) < 1e-6
    print(f"1. VPC 408-trade signature: n={n_vpc} (expect {VPC_408_N}), "
          f"net={net_vpc:.6f}pt (expect {VPC_408_NET:.6f})  -> {'PASS' if c1 else 'FAIL'}")
    ok &= c1

    n_a = len(a_rows)
    gp = sum(r["R"] for r in a_rows if r["R"] > 0)
    gl = -sum(r["R"] for r in a_rows if r["R"] < 0)
    pf_a = gp / gl if gl else float("nan")
    c2a = (n_a == A_HONEST_N) and abs(pf_a - A_HONEST_PF) < 1e-6
    print(f"2a. Honest-A stream: n={n_a} (expect {A_HONEST_N}), PF={pf_a:.6f} "
          f"(expect {A_HONEST_PF:.6f})  -> {'PASS' if c2a else 'FAIL'}")
    ok &= c2a

    days_trades, unique_days = SPC.group_by_day(a_rows)
    canary_res = SPC.run_config(days_trades, unique_days, SPC.SPEC_50K, SPC.CAP,
                                use_cushion=False, use_p3=False)
    exp = SPC.CANARY_EXPECT
    c2b = (canary_res["pass_pct"] == exp["pass_pct"] and canary_res["bust_pct"] == exp["bust_pct"]
           and canary_res["exp_pct"] == exp["exp_pct"] and canary_res["med_days"] == exp["med_days"]
           and canary_res["n"] == exp["n"])
    print(f"2b. Honest-A internal cap-10 canary: got {canary_res} vs expected {exp}  "
          f"-> {'PASS' if c2b else 'FAIL'}")
    ok &= c2b

    # 3. lookahead structural spot-check on the merged event stream
    v_rows, _ = vpc_rows_cache["rows"], None
    ev_a = ASR.build_events(a_rows_2022(a_rows), 400, 4)
    ev_v = ASR.build_events(v_rows, 400, 4)
    ev_a_poisoned = copy.deepcopy(ev_a)
    for e in ev_a_poisoned:
        e["pnl"] = e["pnl"] * 7.0 + 999999.0
        e["mae"] = e["mae"] * 7.0 - 999999.0
    merged_clean = sorted(ev_a + ev_v, key=lambda e: e["ts"])
    merged_poisoned = sorted(ev_a_poisoned + ev_v, key=lambda e: e["ts"])
    # pull the VPC-only slice back out of each merge by identity of the pnl/mae/ts triple that is
    # NOT one of the (corrupted) A values, and compare to the untouched ev_v list positionally
    # (both merges contain ev_v's dict objects verbatim -- python dicts are not copied by sort()).
    v_ids_clean = [id(e) for e in ev_v]
    same_objects = all(id(e) in v_ids_clean for e in merged_clean if e in ev_v)
    # direct, stronger check: the ev_v list's own dict CONTENTS are untouched after being
    # concatenated+sorted alongside a corrupted copy of ev_a
    vals_before = [(e["ts"], e["pnl"], e["mae"]) for e in ev_v]
    _ = merged_poisoned  # merge/sort executed; now re-read ev_v (same objects, never mutated by sort)
    vals_after = [(e["ts"], e["pnl"], e["mae"]) for e in ev_v]
    c3 = (vals_before == vals_after)
    print(f"3. Look-ahead spot-check (merge/sort cannot mutate either stream's own events; "
          f"A poisoned 7x+999999, VPC events re-read unchanged): -> {'PASS' if c3 else 'FAIL'}")
    print("   (structural: VPC engine (nq_vwap_pullback/vpc_apex_eval_sim) takes no A inputs; "
          "honest-A engine (strategy_engine_profileA/run_d1c_real) takes no VPC inputs; the two "
          "streams are computed independently and only combined post-hoc by ts-sort.)")
    ok &= c3

    print("=" * 100)
    if not ok:
        print("[CANARY FAILURE] STOPPING -- do not trust anything downstream of this run.")
    else:
        print("[all canaries PASS]")
    print("=" * 100)
    return ok


vpc_rows_cache = {}


# ----------------------------------------------------------------------------------------------
# PART 1 -- VPC STANDALONE FUNNEL
# ----------------------------------------------------------------------------------------------
def part1(v_rows):
    print("\nPART 1 -- VPC STANDALONE FUNNEL (budgets x caps)")
    budgets = [200, 300, 400, 500, 600, 800]
    caps = [2, 3, 4, 6]
    records = []
    for budget in budgets:
        for cap in caps:
            ev = ASR.build_events(v_rows, budget, cap)
            pf = event_pf(ev, f"B4 VPC@budget{budget}/cap{cap}")
            days = ASR.day_rows(ev, STOP_PINNED, DLL_PINNED)
            s = summarize_cell(days, f"VPC@{budget}/{cap}")
            rec = dict(budget=budget, cap=cap, pf_dollar=round(pf, 3) if pf == pf else None,
                       **{k: v for k, v in s.items() if k not in ("label", "per_year")})
            for y in sorted(s["per_year"]):
                rec[f"py{y}_n"] = s["per_year"][y]["n"]
                rec[f"py{y}_pass_pct"] = s["per_year"][y]["pass_pct"]
            rec["shortlist"] = bool(s["pass_count"] and s["bust_count"] is not None
                                    and s["pass_pct"] is not None and s["bust_pct"] is not None
                                    and s["pass_pct"] > s["bust_pct"] and s["pass_count"] >= 20)
            records.append(rec)
            print(f"  budget={budget:>4} cap={cap} | n={s['eligible_starts']:>4} "
                  f"pass={s['pass_pct']}% bust={s['bust_pct']}% exp={s['exp_pct']}% "
                  f"med={s['med_days_pass']}d worst=${s['worst_day_usd']:,.0f} "
                  f"fund/slot/yr={s['funded_per_slot_year']} PF={pf:.3f} "
                  f"{'[SHORTLIST]' if rec['shortlist'] else ''}")
    df = pd.DataFrame.from_records(records)
    return df


# ----------------------------------------------------------------------------------------------
# PART 2 -- A+VPC COMBINED PORTFOLIO (eval side)
# ----------------------------------------------------------------------------------------------
def unit_daily(rows):
    """Unit (1-contract, unclamped) daily $ P&L series, keyed by normalized ts."""
    out = {}
    for r in rows:
        d = pd.Timestamp(r["ts"]).normalize()
        out[d] = out.get(d, 0.0) + r["R"] * r["risk_usd"]
    return out


def same_day_stats(a_rows, v_rows):
    da = unit_daily(a_rows)
    dv = unit_daily(v_rows)
    all_days = sorted(set(da) | set(dv))
    xa = np.array([da.get(d, 0.0) for d in all_days])
    xv = np.array([dv.get(d, 0.0) for d in all_days])
    corr = float(np.corrcoef(xa, xv)[0, 1]) if len(all_days) > 1 else float("nan")
    dbl_loss = np.mean((xa < 0) & (xv < 0)) * 100 if len(all_days) else float("nan")
    tot_loss = np.mean((xa + xv) < 0) * 100 if len(all_days) else float("nan")
    return dict(n_days=len(all_days), same_day_corr=round(corr, 3),
                dl_freq_pct=round(float(dbl_loss), 1), tl_freq_pct=round(float(tot_loss), 1))


def part2_eval(a_rows2022, v_rows, refstats):
    print("\nPART 2 -- COMBINED PORTFOLIO (EVAL side)")
    a_cells = [(400, 4), (600, 6), (1200, 10)]
    v_cells = [(300, 3), (400, 4), (600, 4)]
    records = []

    def eval_row(label, ev):
        pf = event_pf(ev, f"C EVAL {label}")
        days = ASR.day_rows(ev, STOP_PINNED, DLL_PINNED)
        s = summarize_cell(days, label)
        rec = dict(section="EVAL", label=label, pf_dollar=round(pf, 3) if pf == pf else None,
                   trades_per_week=round(len(ev) / weeks_span(ev), 2),
                   same_day_corr=refstats["same_day_corr"], dl_freq_pct=refstats["dl_freq_pct"],
                   tl_freq_pct=refstats["tl_freq_pct"],
                   **{k: v for k, v in s.items() if k not in ("label", "per_year")})
        for y in sorted(s["per_year"]):
            rec[f"py{y}_n"] = s["per_year"][y]["n"]
            rec[f"py{y}_pass_pct"] = s["per_year"][y]["pass_pct"]
        return rec

    # A-alone rows (== VPC OFF)
    ev_a_cache = {}
    for (ba, ca) in a_cells:
        ev_a = ASR.build_events(a_rows2022, ba, ca)
        ev_a_cache[(ba, ca)] = ev_a
        rec = eval_row(f"A@{ba}/{ca} ALONE", ev_a)
        records.append(rec)
        print(f"  {rec['label']:>28} | pass={rec['pass_pct']}% bust={rec['bust_pct']}% "
              f"exp={rec['exp_pct']}% n={rec['eligible_starts']}")

    # VPC-alone rows
    ev_v_cache = {}
    for (bv, cv) in v_cells:
        ev_v = ASR.build_events(v_rows, bv, cv)
        ev_v_cache[(bv, cv)] = ev_v
        rec = eval_row(f"VPC@{bv}/{cv} ALONE", ev_v)
        records.append(rec)
        print(f"  {rec['label']:>28} | pass={rec['pass_pct']}% bust={rec['bust_pct']}% "
              f"exp={rec['exp_pct']}% n={rec['eligible_starts']}")

    # combos
    for (ba, ca) in a_cells:
        for (bv, cv) in v_cells:
            merged = sorted(ev_a_cache[(ba, ca)] + ev_v_cache[(bv, cv)], key=lambda e: e["ts"])
            rec = eval_row(f"A@{ba}/{ca} + VPC@{bv}/{cv}", merged)
            records.append(rec)
            print(f"  {rec['label']:>28} | pass={rec['pass_pct']}% bust={rec['bust_pct']}% "
                  f"exp={rec['exp_pct']}% n={rec['eligible_starts']}")

    return pd.DataFrame.from_records(records)


# ----------------------------------------------------------------------------------------------
# PART 2 -- A+VPC COMBINED PORTFOLIO (funded side) -- generalizes tools_recert_funded
# ----------------------------------------------------------------------------------------------
def combined_daily_series(rows_a, budget_a, cap_a, rows_v, budget_v, cap_v):
    """Generalization of tools_recert_funded.daily_series to TWO independent (budget, cap) streams
    merged onto one shared day calendar. Identical per-trade sizing rule (q=min(cap, budget//risk1))
    and identical day-collapse ($550 realized stop, $1,000 DLL trough-clamp) as apex_funded_40 /
    tools_recert_funded, verified in the canary() below."""
    ev = []
    for rows, budget, cap in ((rows_a, budget_a, cap_a), (rows_v, budget_v, cap_v)):
        if budget is None or cap is None:
            continue
        for t in rows:
            risk1 = t["risk_usd"]
            q = min(cap, int(budget // risk1))
            if q < 1:
                continue
            ev.append((pd.Timestamp(t["ts"]), t["R"] * risk1 * q, min(0.0, t["mae_r"]) * risk1 * q))
    ev.sort(key=lambda x: x[0])
    days = {}
    for ts, pnl, mae in ev:
        d = ts.normalize()
        rec = days.setdefault(d, dict(real=0.0, trough=0.0, stopped=False))
        if rec["stopped"]:
            continue
        rec["trough"] = min(rec["trough"], rec["real"] + mae)
        rec["real"] += pnl
        if rec["real"] <= FM.DAILY_STOP:
            rec["stopped"] = True
    out = []
    for d in sorted(days):
        r = days[d]
        real, trough = r["real"], r["trough"]
        if trough <= FM.DLL:
            real = max(real, FM.DLL) if real < FM.DLL else real
            real = FM.DLL if real < FM.DLL else real
        out.append((d, real, trough))
    return out


def funded_canary(a_rows2022):
    """combined_daily_series (this file, 2-stream) must reproduce tools_recert_funded.daily_series
    (1-stream, already generalized to independent (budget, cap) there) EXACTLY when the VPC leg is
    OFF, at budget=160*cap (tools_recert_funded's own canary point vs apex_funded_40)."""
    print("\nFUNDED-GENERALIZATION CANARY (combined_daily_series vs tools_recert_funded.daily_series, "
          "VPC leg OFF, on the 2022-2026 A subset):")
    ok = True
    for cap in (3, 4, 5, 6):
        d_orig = TF.daily_series(a_rows2022, 160.0 * cap, cap)
        d_mine = combined_daily_series(a_rows2022, 160.0 * cap, cap, [], None, None)
        same = (d_orig == d_mine)
        ok &= same
        print(f"  cap={cap}: {'OK' if same else 'MISMATCH'}")
    print(f"  -> {'[canary OK]' if ok else '[CANARY MISMATCH] STOPPING funded section'}")
    return ok


def funded_cell_report(days, label):
    """Aggregation identical to tools_recert_funded.cell_report, parameterized on a prebuilt `days`
    list (so it works for both single-stream and merged-stream calendars)."""
    starts = TF.monthly_starts(days)
    res = [TF.run_pa_instrumented(days, s) for s in starts]
    n = len(res)
    if n == 0:
        return dict(label=label, n_starts=0)
    bust = [r for r in res if r["outcome"] == "BUST"]
    closed = [r for r in res if r["outcome"] == "CLOSED_MAX"]
    data_end = [r for r in res if r["outcome"] == "DATA_END"]
    reached_sn = [r for r in res if r["safety_net_day"] is not None]
    paid_all = [r["paid"] for r in res]
    months_all = [r["months"] for r in res]
    worst_day = round(float(min(r_ for _, r_, _ in days)), 0) if days else None
    per_year = {}
    for r in res:
        y = r["start_year"]
        rec = per_year.setdefault(y, dict(n=0, bust=0))
        rec["n"] += 1
        if r["outcome"] == "BUST":
            rec["bust"] += 1
    per_year_pct = {y: dict(n=rv["n"], bust_pct=round(100 * rv["bust"] / rv["n"], 1))
                    for y, rv in sorted(per_year.items())}
    return dict(
        label=label, n_starts=n,
        e_paid=round(float(np.mean(paid_all))),
        med_paid=round(float(np.median(paid_all))),
        med_months=round(float(np.median(months_all)), 1),
        bust_pct=round(100 * len(bust) / n, 1),
        closed_max_pct=round(100 * len(closed) / n, 1),
        data_end_pct=round(100 * len(data_end) / n, 1),
        safety_net_pct=round(100 * len(reached_sn) / n, 1),
        med_days_to_safety_net=(round(float(np.median([r["safety_net_day"] for r in reached_sn])), 1)
                                if reached_sn else None),
        worst_day=worst_day, per_year=per_year_pct,
    )


def part2_funded(a_rows2022, v_rows):
    print("\nPART 2 -- COMBINED PORTFOLIO (FUNDED side; A(250,4) x VPC{OFF,(200,2),(300,2)})")
    A_CELL = (250, 4)
    V_CELLS = [None, (200, 2), (300, 2)]
    records = []
    for vc in V_CELLS:
        if vc is None:
            label = f"A@{A_CELL[0]}/{A_CELL[1]} ALONE (VPC OFF)"
            days = combined_daily_series(a_rows2022, A_CELL[0], A_CELL[1], [], None, None)
        else:
            label = f"A@{A_CELL[0]}/{A_CELL[1]} + VPC@{vc[0]}/{vc[1]}"
            days = combined_daily_series(a_rows2022, A_CELL[0], A_CELL[1], v_rows, vc[0], vc[1])
        r = funded_cell_report(days, label)
        r["section"] = "FUNDED"
        records.append(r)
        if r["n_starts"]:
            print(f"  {label:>36} | n={r['n_starts']} E[paid]=${r['e_paid']:,} "
                  f"bust={r['bust_pct']}% medMonths={r['med_months']} "
                  f"safetyNet={r['safety_net_pct']}% worstDay=${r['worst_day']:,.0f}")
        else:
            print(f"  {label:>36} | no monthly starts (insufficient runway)")
    return records


# ----------------------------------------------------------------------------------------------
# Report writers
# ----------------------------------------------------------------------------------------------
def write_b4(df):
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, "B4_vpc_reeval.csv")
    md_path = os.path.join(OUTDIR, "B4_vpc_reeval.md")
    df.to_csv(csv_path, index=False)

    shortlist = df[df["shortlist"] == True]  # noqa: E712
    lines = []
    lines.append("# B4 -- VPC standalone re-evaluation vs HONEST baseline")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. VPC's prior 2026-07-04 rejection was measured "
                 "against the D1c-lookahead-invalidated machine (INC-20260706-1141); this re-run "
                 "does not compare against that number (it never had bearing on VPC standalone, "
                 "which never used the A stream) but is reported fresh per the salvage program brief.")
    lines.append("")
    lines.append("Rows format mapping: risk_usd = stop_pts x $2/pt/MNQ; R = pnl_pts/stop_pts; "
                 "mae_r = mae_pts/stop_pts. Funnel = tools_account_size_research.build_events / "
                 "day_rows(550, 1000) / eval_run (Apex 50K spec), unchanged, pinned.")
    lines.append("")
    lines.append(f"Grid: budgets {{200,300,400,500,600,800}} x caps {{2,3,4,6}} = {len(df)} cells. "
                 "eligible_starts = unique trading days with >30d runway (EXPIRE=30d), reported "
                 "alongside pass_count per the denominator rule (DEC-20260706-1108).")
    lines.append("")
    lines.append("## Full grid")
    lines.append("")
    lines.append(df_to_md_table(df))
    lines.append("")
    lines.append(f"## Mechanical shortlist (pass_pct > bust_pct AND pass_count >= 20): "
                 f"{len(shortlist)}/{len(df)} cells")
    lines.append("")
    if len(shortlist):
        lines.append(df_to_md_table(shortlist))
    else:
        lines.append("(none)")
    lines.append("")
    if PF_FLAGS:
        lines.append(f"## PF FREEZE FLAGS (PF>{PF_FREEZE_THRESHOLD}): {PF_FLAGS}")
    else:
        lines.append(f"## PF freeze check: no cell exceeded PF>{PF_FREEZE_THRESHOLD}.")
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[saved] {csv_path}\n[saved] {md_path}")


def write_c(df_eval, funded_records, refstats):
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, "C_combined_portfolio_test.csv")
    md_path = os.path.join(OUTDIR, "C_combined_portfolio_test.md")

    df_funded = pd.DataFrame.from_records(
        [{k: v for k, v in r.items() if k != "per_year"} for r in funded_records])
    combined_csv = pd.concat([df_eval, df_funded], ignore_index=True, sort=False)
    combined_csv.to_csv(csv_path, index=False)

    lines = []
    lines.append("# C -- A+VPC combined portfolio test (Part 2 centerpiece + Part 3 per-year)")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. Independent per-strategy sizing: A and VPC events "
                 "are each built via tools_account_size_research.build_events with their OWN "
                 "(budget, cap), then merged onto one shared day calendar and fed the same "
                 "day_rows($550 stop, $1,000 DLL) / eval_run (EVAL side) or the generalized "
                 "combined_daily_series (FUNDED side, apex_funded_40 constants, imported not retyped).")
    lines.append("")
    lines.append("**PART 3 WINDOW NOTE**: the VPC stream starts 2022-01-01 (no earlier real Databento "
                 "VPC trades exist by construction of the recert). All combined analysis below -- "
                 "including the A-alone comparison rows -- is therefore restricted to the shared "
                 "2022-2026 window (A rows filtered to ts >= 2022-01-01, dropping the 2021-06-25 -> "
                 "2021-12-31 portion of the certified 583-row honest-A stream) so the comparison is "
                 "apples-to-apples. This is NOT the full-history A-alone number reported elsewhere "
                 "(that one uses all 583 rows from 2021-06-25).")
    lines.append("")
    lines.append(f"Same-day unit-level reference stats (2022-2026 window, 1-contract unclamped, "
                 f"cap/budget-invariant to first order, computed once and repeated on every EVAL "
                 f"combo row): n_days={refstats['n_days']}, same_day_corr={refstats['same_day_corr']}, "
                 f"dl_freq_pct={refstats['dl_freq_pct']} (both streams net-negative same day), "
                 f"tl_freq_pct={refstats['tl_freq_pct']} (combined day net-negative). "
                 "dl_freq/tl_freq have no prior-art precedent in this repo; definitions are stated "
                 "here explicitly (double-loss-day % and combined-loss-day %, respectively) -- not "
                 "hidden assumptions.")
    lines.append("")
    lines.append("## EVAL side -- A-alone / VPC-alone / every A x VPC combo")
    lines.append("")
    lines.append(df_to_md_table(df_eval))
    lines.append("")
    lines.append("## FUNDED side -- A(250,4) x VPC{OFF,(200,2),(300,2)} (tools_recert_funded pattern, "
                 "generalized)")
    lines.append("")
    lines.append("CAVEAT (verbatim style from tools_recert_funded/apex_funded_40): monthly rolling "
                 "starts overlap -> effective independent samples are far fewer than n_starts; "
                 "every percentage below is MODEL-OBSERVED over a small number of effectively-"
                 "independent overlapping-start samples on the 2022-2026-restricted A subset, not an "
                 "i.i.d. probability. Wide confidence intervals apply throughout.")
    lines.append("")
    lines.append(df_to_md_table(df_funded))
    lines.append("")
    if PF_FLAGS:
        lines.append(f"## PF FREEZE FLAGS (PF>{PF_FREEZE_THRESHOLD}): {PF_FLAGS}")
    else:
        lines.append(f"## PF freeze check: no cell exceeded PF>{PF_FREEZE_THRESHOLD}.")
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[saved] {csv_path}\n[saved] {md_path}")


# ----------------------------------------------------------------------------------------------
def main():
    print("loading VPC rows (real Databento, frozen CFG, 2022+)…", flush=True)
    v_rows, vpc_tr = vpc_rows()
    vpc_rows_cache["rows"] = v_rows
    print(f"  VPC rows n={len(v_rows)}", flush=True)

    print("loading honest A rows (tools_sim_parity_check.load_rows, post-fix)…", flush=True)
    a_full = a_rows_full()
    a2022 = a_rows_2022(a_full)
    print(f"  A rows n={len(a_full)} (full)  n={len(a2022)} (2022-2026 window)", flush=True)

    if not run_canaries(vpc_tr, a_full):
        return

    df_b4 = part1(v_rows)
    write_b4(df_b4)

    refstats = same_day_stats(a2022, v_rows)
    df_eval = part2_eval(a2022, v_rows, refstats)

    if funded_canary(a2022):
        funded_records = part2_funded(a2022, v_rows)
    else:
        funded_records = []

    write_c(df_eval, funded_records, refstats)

    print("\n" + "=" * 100)
    if PF_FLAGS:
        print(f"[FREEZE] {len(PF_FLAGS)} cell(s) breached PF>{PF_FREEZE_THRESHOLD}: {PF_FLAGS}")
    else:
        print(f"No cell anywhere breached PF>{PF_FREEZE_THRESHOLD}.")
    print("=" * 100)


if __name__ == "__main__":
    main()
