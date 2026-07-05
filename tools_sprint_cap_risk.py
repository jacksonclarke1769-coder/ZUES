"""EVAL-PASSRATE SPRINT — workstreams 1A (baseline reproduction) + 1B (extended cap x risk-budget
matrix). RESEARCH ONLY. Does not touch any live/config/funded file; only writes under
reports/eval_passrate_sprint/.

Reuses (by import, never copied) the certified stream loader and the existing sweep's cell
computation:
  - tools_sim_parity_check.load_rows()      -> the certified exit3+D1c, 1m-truth A stream
  - tools_eval_sizing_sweep.build_events()  -> q = min(cap, budget // risk_usd) sizing
  - tools_eval_sizing_sweep.run_cell()      -> day_rows/eval_run funnel (pass/bust/expire/E$/...)
  - tools_account_size_research.day_rows() / .eval_run()  -> the underlying $550-stop/$1,000-DLL/
    30-day-expiry/$2,500-trail day- and eval-level state machine (imported transitively by
    tools_eval_sizing_sweep, and directly here for the extra stats run_cell doesn't expose:
    worst-day and the trades-used-per-eval instrumentation below).

1A baseline: cap=10, budget=$1,200 (the deployed A10 sizing: A_RISK_BUDGET_USD=1200,
cap10_relock_2026-07-05) must reproduce pass 47.8 / bust 15.9 / expire 36.2 / median 16d / n=395
EXACTLY (this is tools_eval_sizing_sweep.CANARY_A verbatim). If it does not, everything below is
aborted.

1B matrix: caps {10,12,15,18,20,25,30,40} x budgets {600,750,900,1000,1100,1200}. Full funnel per
cell including two stats run_cell does not compute:
  - worst_day_usd: recomputed here via a direct day_rows(build_events(...)) call, min(real) across
    all days in the whole replay window (mirrors tools_account_size_research.main()'s `worst`).
  - n_trades_taken / mean+median trades-per-eval: day_rows/eval_run only return (day, real, trough)
    tuples with no trade count. VERBATIM-COPY-PLUS-ONE-ACCUMULATOR variants
    (day_rows_counted/eval_run_counted below, same pattern tools_eval_sizing_sweep.py used for its
    MFE walk_1m copy) add a per-day trade count and carry a running total through eval_run's day
    loop. Both copies are verified byte-for-byte against the original day_rows/eval_run output
    (status, day-offset) for EVERY cell before the trade-count column is trusted; a mismatch
    anywhere aborts that column with a printed WARNING rather than silently reporting wrong numbers.

Portfolio WR / PF(R) / expectancy-R are computed on the RAW per-trade R values of whichever trades
clear the budget filter (`int(budget // risk_usd) >= 1`) — this set does not depend on cap (cap
only truncates the sizing multiplier upward, never trade eligibility), so these three columns are
identical across every cap row within the same budget column; this is noted in the .md, not hidden.
"""
import os, sys, csv, json, subprocess, time, warnings; warnings.filterwarnings("ignore")
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tools_sim_parity_check as PARITY                       # certified stream loader
import tools_eval_sizing_sweep as SWEEP                        # build_events/run_cell + canaries
import tools_account_size_research as ASR                     # day_rows/eval_run (original)

FRAME = "SIM CONDITIONAL — pending live fill evidence"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "eval_passrate_sprint")

CAPS = [10, 12, 15, 18, 20, 25, 30, 40]
BUDGETS = [600, 750, 900, 1000, 1100, 1200]
KNEE_CAP, KNEE_BUDGET = 15, 1000


# ---------------------------------------------------------------- extra-stat helpers
def worst_day(rows, cap, budget):
    ev = SWEEP.build_events(rows, cap, budget)
    days = ASR.day_rows(ev, SWEEP.STOP, SWEEP.SPEC["dll"])
    if not days:
        return None
    return round(min(d[1] for d in days), 1)


def portfolio_stats(rows, budget):
    """WR% / PF(R) / expectancy-R over the raw per-trade R of budget-eligible trades. Independent
    of cap (see module docstring)."""
    elig = [t for t in rows if int(budget // t["risk_usd"]) >= 1]
    n = len(elig)
    if n == 0:
        return dict(n_trades_taken=0, wr_pct=None, pf_r=None, expectancy_r=None)
    R = np.array([t["R"] for t in elig], float)
    wr = 100.0 * float((R > 0).mean())
    wins, losses = float(R[R > 0].sum()), float(-R[R <= 0].sum())
    pf = (wins / losses) if losses > 0 else float("inf")
    return dict(n_trades_taken=n, wr_pct=round(wr, 1),
                pf_r=(round(pf, 3) if pf != float("inf") else "inf"),
                expectancy_r=round(float(R.mean()), 3))


def day_rows_counted(ev, stop, dll):
    """VERBATIM copy of tools_account_size_research.day_rows with ONE added accumulator: n (trade
    count actually processed for that day, i.e. before any same-day stop truncation). Every other
    line is unchanged."""
    days = {}
    for e in ev:
        d = e["ts"].normalize()
        r = days.setdefault(d, dict(real=0.0, trough=0.0, stopped=False, n=0))
        if r["stopped"]:
            continue
        r["trough"] = min(r["trough"], r["real"] + e["mae"])
        r["real"] += e["pnl"]
        r["n"] += 1                                            # <-- ADDED
        if r["real"] <= -stop:
            r["stopped"] = True
    out = []
    for d in sorted(days):
        r = days[d]
        if r["trough"] <= -dll:
            real, trough = -dll, -dll
        else:
            real, trough = r["real"], r["trough"]
        out.append((d, real, trough, r["n"]))                   # <-- ADDED r["n"]
    return out


def eval_run_counted(days4, s0, spec):
    """VERBATIM copy of tools_account_size_research.eval_run operating on the 4-tuple
    (day, real, trough, n) rows from day_rows_counted, with ONE added accumulator: trades_used
    (cumulative trade count from s0 through the terminal day, inclusive — the trades on the
    terminal day did occur even if that day is where BUST/PASS triggers). Control flow (bust/pass/
    expire order of checks) is otherwise byte-identical to the original."""
    sb, tr, tg = spec["start"], spec["trail"], spec["target"]
    thr, bal, peak, locked = sb - tr, sb, sb, False
    t0 = days4[s0][0]
    trades_used = 0
    for i in range(s0, len(days4)):
        d, real, trough, n = days4[i]
        if (d - t0).days > SWEEP.EXPIRE_DAYS:
            return "EXPIRE", SWEEP.EXPIRE_DAYS, trades_used
        trades_used += n                                        # <-- ADDED
        if bal + min(0.0, trough) <= thr:
            return "BUST", (d - t0).days, trades_used
        bal += real
        peak = max(peak, bal)
        if not locked:
            thr = max(thr, peak - tr)
            if peak - tr >= sb + 100.0:
                thr = sb + 100.0; locked = True
        if bal <= thr:
            return "BUST", (d - t0).days, trades_used
        if bal >= sb + tg:
            return "PASS", (d - t0).days, trades_used
    return "INCOMPLETE", None, trades_used


def trades_per_eval_stats(rows, cap, budget):
    """Returns (mean_trades, median_trades, verified) where verified is False if the counted copy
    ever disagrees with the original day_rows/eval_run on status or day-offset for this cell."""
    ev = SWEEP.build_events(rows, cap, budget)
    days_orig = ASR.day_rows(ev, SWEEP.STOP, SWEEP.SPEC["dll"])
    days_cnt = day_rows_counted(ev, SWEEP.STOP, SWEEP.SPEC["dll"])
    if not days_orig:
        return None, None, True
    starts = [i for i, (d, _, _) in enumerate(days_orig) if (days_orig[-1][0] - d).days > SWEEP.EXPIRE_DAYS]
    used = []
    verified = True
    for s in starts:
        st_o, off_o = ASR.eval_run(days_orig, s, SWEEP.SPEC)
        st_c, off_c, tu = eval_run_counted(days_cnt, s, SWEEP.SPEC)
        if st_o != st_c or off_o != off_c:
            verified = False
            continue
        if st_c == "PASS" or st_c == "BUST":                    # trades-per-eval only meaningful
            used.append(tu)                                     # for a resolved attempt
    if not used:
        return None, None, verified
    return (round(float(np.mean(used)), 2), round(float(np.median(used)), 1), verified)


# ---------------------------------------------------------------- 1A
def run_1a(rows):
    print(f"{FRAME}\n1A — BASELINE REPRODUCTION\n")
    c = SWEEP.CANARY_A
    got = SWEEP.run_cell(rows, c["cap"], c["budget"])
    ok = (got["n"] == c["n"] and got["pass_pct"] == c["pass_pct"] and got["bust_pct"] == c["bust_pct"]
          and got["exp_pct"] == c["exp_pct"] and got["med_days"] == c["med_days"])
    verdict = "REPRODUCED" if ok else "MISMATCH"
    print(f"  reproduced: n={got['n']} pass={got['pass_pct']} bust={got['bust_pct']} "
          f"exp={got['exp_pct']} med={got['med_days']}d")
    print(f"  certified:  n={c['n']} pass={c['pass_pct']} bust={c['bust_pct']} "
          f"exp={c['exp_pct']} med={c['med_days']}d")
    print(f"  -> {verdict}\n")

    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                        cwd=os.path.dirname(os.path.abspath(__file__)),
                                        stderr=subprocess.DEVNULL).decode().strip()
    except Exception as e:
        head = f"unavailable ({e})"

    apex_val_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "apex_validation.json")
    with open(apex_val_path) as f:
        current_machine = json.load(f).get("current_machine")

    os.makedirs(OUT_DIR, exist_ok=True)
    report = dict(
        framing=FRAME,
        generated="2026-07-05",
        harness_path="tools_sprint_cap_risk.py (1A: calls tools_eval_sizing_sweep.run_cell via "
                     "the certified tools_sim_parity_check.load_rows() stream)",
        data_source="Databento 5m (apex_eval_eod_databento.load_databento_5m) + 1m truth "
                    "(run_d1c_real.load_1m, via tools_1m_truth_recert.M1Map) — loaded transitively "
                    "inside tools_sim_parity_check.load_rows()",
        provenance_pointer=dict(file="reports/apex_validation.json", current_machine=current_machine),
        repo_head_commit=head,
        reproduced_row=got,
        certified_row=c,
        verdict=verdict,
    )
    with open(os.path.join(OUT_DIR, "baseline_reproduction.json"), "w") as f:
        json.dump(report, f, indent=1, default=str)

    md = [
        "# 1A — Baseline Reproduction", "",
        f"**{FRAME}**", "",
        f"- Harness path: `tools_sprint_cap_risk.py` (1A section), calling "
        f"`tools_eval_sizing_sweep.run_cell(cap=10, budget=1200)` on the stream returned by "
        f"`tools_sim_parity_check.load_rows()`",
        f"- Data source: Databento 5m (`apex_eval_eod_databento.load_databento_5m`) + 1m truth "
        f"(`run_d1c_real.load_1m` via `tools_1m_truth_recert.M1Map`) — loaded transitively inside "
        f"`load_rows()`",
        f"- Provenance pointer: `reports/apex_validation.json` -> `current_machine` = "
        f"`{current_machine}`",
        f"- Repo HEAD commit: `{head}`",
        "",
        "| | n | pass% | bust% | expire% | median days |",
        "|---|---|---|---|---|---|",
        f"| Reproduced | {got['n']} | {got['pass_pct']} | {got['bust_pct']} | {got['exp_pct']} | {got['med_days']} |",
        f"| Certified  | {c['n']} | {c['pass_pct']} | {c['bust_pct']} | {c['exp_pct']} | {c['med_days']} |",
        "",
        f"## Verdict: **{verdict}**", "",
    ]
    with open(os.path.join(OUT_DIR, "baseline_reproduction.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"[saved] reports/eval_passrate_sprint/baseline_reproduction.{{md,json}}\n")
    return ok


# ---------------------------------------------------------------- 1B
def run_1b(rows):
    print(f"{FRAME}\n1B — EXTENDED CAP x RISK-BUDGET MATRIX\n")
    portfolio_cache = {b: portfolio_stats(rows, b) for b in BUDGETS}

    cells = []
    trade_count_verified = True
    for cap in CAPS:
        for budget in BUDGETS:
            m = SWEEP.run_cell(rows, cap, budget)
            wd = worst_day(rows, cap, budget)
            mean_tpe, med_tpe, ver = trades_per_eval_stats(rows, cap, budget)
            trade_count_verified = trade_count_verified and ver
            ps = portfolio_cache[budget]
            cells.append(dict(
                cap=cap, budget=budget, n=m["n"], pass_pct=m["pass_pct"], bust_pct=m["bust_pct"],
                exp_pct=m["exp_pct"], median_days=m["med_days"], mean_days=m["mean_days"],
                e_per_attempt=m["e_attempt"], evals_per_funded=m["evals_per_funded"],
                n_trades_taken=ps["n_trades_taken"], mean_trades_per_eval=mean_tpe,
                median_trades_per_eval=med_tpe, portfolio_wr_pct=ps["wr_pct"], pf_r=ps["pf_r"],
                expectancy_r=ps["expectancy_r"], mean_risk_usd_per_trade=m["mean_risk_per_trade"],
                mean_contracts=m["mean_contracts"], pct_cap_clipped=m["clipped_pct"],
                worst_day_usd=wd,
            ))
    print(f"  trade-count instrumentation verified against original day_rows/eval_run on every "
          f"cell: {'OK' if trade_count_verified else 'MISMATCH — see WARNING'}")
    if not trade_count_verified:
        print("  [WARNING] trades-per-eval column disagreed with the certified day_rows/eval_run "
              "on at least one cell — treat mean/median_trades_per_eval as UNVERIFIED.")

    by_key = {(c["cap"], c["budget"]): c for c in cells}

    # ---- (a) knee: marginal E$ per cap step, per budget column ----
    knee_lines = []
    for budget in BUDGETS:
        col = [by_key[(cap, budget)] for cap in CAPS]
        deltas = [(col[i + 1]["cap"], col[i + 1]["e_per_attempt"] - col[i]["e_per_attempt"])
                  for i in range(len(col) - 1)]
        knee_lines.append((budget, [c["e_per_attempt"] for c in col], deltas))
    ref = by_key[(KNEE_CAP, KNEE_BUDGET)]
    # is (15,1000)'s own step (12->15) positive and the NEXT step (15->18) smaller/negative?
    col1000 = [by_key[(cap, KNEE_BUDGET)] for cap in CAPS]
    idx15 = CAPS.index(KNEE_CAP)
    step_into_15 = col1000[idx15]["e_per_attempt"] - col1000[idx15 - 1]["e_per_attempt"]
    step_out_of_15 = col1000[idx15 + 1]["e_per_attempt"] - col1000[idx15]["e_per_attempt"]
    knee_holds = (step_into_15 > 0) and (step_out_of_15 <= step_into_15)

    # ---- (b) dominance check vs (15,1000) ----
    dominators = []
    for c in cells:
        if (c["cap"], c["budget"]) == (KNEE_CAP, KNEE_BUDGET):
            continue
        if (c["pass_pct"] >= ref["pass_pct"] and c["bust_pct"] <= ref["bust_pct"]
                and c["e_per_attempt"] >= ref["e_per_attempt"]
                and (c["pass_pct"] > ref["pass_pct"] or c["bust_pct"] < ref["bust_pct"]
                     or c["e_per_attempt"] > ref["e_per_attempt"])):
            dominators.append(c)

    # ---- (c) decompose each cap step's pass-rate gain into expiry-delta vs bust-delta ----
    decomposition = {}
    for budget in BUDGETS:
        col = [by_key[(cap, budget)] for cap in CAPS]
        steps = []
        for i in range(len(col) - 1):
            a, b = col[i], col[i + 1]
            steps.append(dict(from_cap=a["cap"], to_cap=b["cap"],
                              d_pass=round(b["pass_pct"] - a["pass_pct"], 1),
                              d_bust=round(b["bust_pct"] - a["bust_pct"], 1),
                              d_expire=round(b["exp_pct"] - a["exp_pct"], 1)))
        decomposition[budget] = steps

    # ---- (d) $1,000 vs $1,200 at each cap ----
    thousand_vs_1200 = {}
    for cap in CAPS:
        c1000, c1200 = by_key[(cap, 1000)], by_key[(cap, 1200)]
        thousand_vs_1200[cap] = dict(
            pass_1000=c1000["pass_pct"], pass_1200=c1200["pass_pct"],
            bust_1000=c1000["bust_pct"], bust_1200=c1200["bust_pct"],
            e_1000=c1000["e_per_attempt"], e_1200=c1200["e_per_attempt"],
            e1000_beats_e1200=c1000["e_per_attempt"] > c1200["e_per_attempt"],
            pass1000_beats_pass1200=c1000["pass_pct"] > c1200["pass_pct"],
        )
    all_caps_e1000_wins = all(v["e1000_beats_e1200"] for v in thousand_vs_1200.values())
    all_caps_pass1000_wins = all(v["pass1000_beats_pass1200"] for v in thousand_vs_1200.values())

    # ---- top-5 cells by E$ ----
    top5 = sorted(cells, key=lambda c: c["e_per_attempt"], reverse=True)[:5]

    # ---- save CSV ----
    os.makedirs(OUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUT_DIR, "cap_risk_matrix.csv")
    fieldnames = list(cells[0].keys())
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for c in cells:
            w.writerow(c)
    print(f"[saved] reports/eval_passrate_sprint/cap_risk_matrix.csv  ({len(cells)} rows)")

    # ---- save MD ----
    md = ["# 1B — Extended Cap x Risk-Budget Matrix", "", f"**{FRAME}**", "",
          "Spec: caps {10,12,15,18,20,25,30,40} x budgets {600,750,900,1000,1100,1200}. "
          "$550 daily stop, $1,000 DLL, $2,500 trail, $3,000 target, 30-day expiry clock — all "
          "fixed (never swept), identical to the certified A10 machine. Sizing: "
          "q = min(cap, budget // risk_usd), skip if q < 1.", "",
          "NOTE: `n_trades_taken`, `portfolio_wr_pct`, `pf_r`, `expectancy_r` are budget-only "
          "(cap does not change trade eligibility, only the size multiplier) and are therefore "
          "IDENTICAL across every cap row within the same budget column — this is expected, not a bug.",
          "",
          f"Trade-count instrumentation (`mean/median_trades_per_eval`) cross-check against the "
          f"certified `day_rows`/`eval_run`: **{'VERIFIED on every cell' if trade_count_verified else 'MISMATCH — UNVERIFIED, do not trust'}**.",
          ""]

    md.append("## Full funnel table")
    md.append("")
    hdr = ("| cap | budget | n | pass% | bust% | exp% | med_d | mean_d | E$/att | evals/fund | "
           "n_trades | mean_tr/eval | med_tr/eval | WR% | PF(R) | expR | mean_risk$ | mean_q | "
           "clip% | worst_day$ |")
    sep = "|" + "---|" * 19
    md.append(hdr); md.append(sep)
    for cap in CAPS:
        for budget in BUDGETS:
            c = by_key[(cap, budget)]
            md.append(f"| {c['cap']} | {c['budget']} | {c['n']} | {c['pass_pct']} | {c['bust_pct']} | "
                      f"{c['exp_pct']} | {c['median_days']} | {c['mean_days']} | {c['e_per_attempt']:,.0f} | "
                      f"{c['evals_per_funded']} | {c['n_trades_taken']} | {c['mean_trades_per_eval']} | "
                      f"{c['median_trades_per_eval']} | {c['portfolio_wr_pct']} | {c['pf_r']} | "
                      f"{c['expectancy_r']} | {c['mean_risk_usd_per_trade']:,.0f} | {c['mean_contracts']} | "
                      f"{c['pct_cap_clipped']} | {c['worst_day_usd']:,.0f} |")
        md.append("")

    md.append("## (a) Is (15, $1000) still the knee?")
    md.append("")
    md.append("Marginal E$/attempt per cap step, per budget column:")
    md.append("")
    md.append("| budget | " + " | ".join(f"cap{cap}" for cap in CAPS) + " |")
    md.append("|" + "---|" * (len(CAPS) + 1))
    for budget, e_vals, deltas in knee_lines:
        md.append(f"| {budget} | " + " | ".join(f"{v:,.0f}" for v in e_vals) + " |")
    md.append("")
    md.append("Step-by-step marginal E$ deltas (E$[cap_i+1] - E$[cap_i]) at budget=$1000 (the "
              "reference column):")
    md.append("")
    md.append("| step | delta E$ |")
    md.append("|---|---|")
    for cap_to, delta in knee_lines[BUDGETS.index(KNEE_BUDGET)][2]:
        md.append(f"| ->cap{cap_to} | {delta:,.0f} |")
    md.append("")
    md.append(f"Step into cap15 (12->15) delta E$ = {step_into_15:,.0f}; step out of cap15 "
              f"(15->18) delta E$ = {step_out_of_15:,.0f}.")
    md.append("")
    md.append(f"**Answer: {'YES' if knee_holds else 'NO'}** — (15, $1000) "
              f"{'remains' if knee_holds else 'no longer looks like'} the knee under this "
              f"extended grid (the marginal-E$ gain into cap15 is "
              f"{'positive and the next step is flat/negative' if knee_holds else 'not the local peak by this test'}).")
    md.append("")

    md.append("## (b) Does any cell dominate (15, $1000) on pass AND bust AND E$?")
    md.append("")
    md.append(f"Reference (cap=15, budget=$1000): pass={ref['pass_pct']}% bust={ref['bust_pct']}% "
              f"E$={ref['e_per_attempt']:,.0f}")
    md.append("")
    if dominators:
        md.append("| cap | budget | pass% | bust% | E$/att |")
        md.append("|---|---|---|---|---|")
        for c in dominators:
            md.append(f"| {c['cap']} | {c['budget']} | {c['pass_pct']} | {c['bust_pct']} | {c['e_per_attempt']:,.0f} |")
        md.append("")
        md.append("**Answer: YES** — at least one cell weakly dominates on all three axes (see table above).")
    else:
        md.append("**Answer: NO** — no cell in the grid is simultaneously >= pass%, <= bust%, and "
                  ">= E$/attempt vs (15, $1000) with at least one strict improvement.")
    md.append("")

    md.append("## (c) Decompose each cap step's pass-rate gain: reduced-expiry vs changed-bust")
    md.append("")
    for budget in BUDGETS:
        md.append(f"### budget = ${budget}")
        md.append("")
        md.append("| step | d_pass | d_bust | d_expire |")
        md.append("|---|---|---|---|")
        for s in decomposition[budget]:
            md.append(f"| cap{s['from_cap']}->cap{s['to_cap']} | {s['d_pass']} | {s['d_bust']} | {s['d_expire']} |")
        md.append("")

    md.append("## (d) Does $1,000 beat $1,200 at each cap? (DLL-alignment effect)")
    md.append("")
    md.append("| cap | pass@1000 | pass@1200 | bust@1000 | bust@1200 | E$@1000 | E$@1200 | E$ 1000>1200 | pass 1000>1200 |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for cap in CAPS:
        v = thousand_vs_1200[cap]
        md.append(f"| {cap} | {v['pass_1000']} | {v['pass_1200']} | {v['bust_1000']} | {v['bust_1200']} | "
                  f"{v['e_1000']:,.0f} | {v['e_1200']:,.0f} | {v['e1000_beats_e1200']} | {v['pass1000_beats_pass1200']} |")
    md.append("")
    md.append(f"**Answer:** $1,000 beats $1,200 on E$/attempt at **{'every' if all_caps_e1000_wins else 'not every'}** "
              f"cap in the grid; $1,000 beats $1,200 on pass% at "
              f"**{'every' if all_caps_pass1000_wins else 'not every'}** cap.")
    md.append("")

    md.append("## Top-5 cells by E$/attempt")
    md.append("")
    md.append("| rank | cap | budget | pass% | bust% | E$/att |")
    md.append("|---|---|---|---|---|---|")
    for i, c in enumerate(top5, 1):
        md.append(f"| {i} | {c['cap']} | {c['budget']} | {c['pass_pct']} | {c['bust_pct']} | {c['e_per_attempt']:,.0f} |")
    md.append("")

    with open(os.path.join(OUT_DIR, "cap_risk_matrix.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"[saved] reports/eval_passrate_sprint/cap_risk_matrix.md\n")

    return dict(knee_holds=knee_holds, dominators=dominators, top5=top5,
               trade_count_verified=trade_count_verified)


def main():
    t0 = time.time()
    print(FRAME)
    print("loading certified stream via tools_sim_parity_check.load_rows()…", flush=True)
    rows = PARITY.load_rows()
    print(f"  loaded {len(rows)} trades  ({time.time()-t0:.1f}s)\n", flush=True)

    ok_1a = run_1a(rows)
    if not ok_1a:
        print("\n[STOP] 1A MISMATCH — aborting 1B. Do not trust anything below.", flush=True)
        sys.exit(1)

    result_1b = run_1b(rows)

    print(f"total runtime {time.time()-t0:.1f}s")
    return result_1b


if __name__ == "__main__":
    main()
