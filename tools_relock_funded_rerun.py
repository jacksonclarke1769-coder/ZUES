"""tools_relock_funded_rerun.py — RE-LOCK DEC + FUNDED RE-RUN compute lane.

RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing (no live/config/engine file touched).
Pure execution of pinned formulas over PRIOR-ART machinery — every modeling choice not already
covered by prior art in this repo is called out explicitly below (not hidden).

TASK: (1) reproduce the eval-side headline funnel rows (baseline / balanced / watch) and add a
pass/not-pass economics framing; (2) build a FUNDED simulation grid over A-kept x VPC sizing cells
(+ an A-unfiltered slice + a negative control) using the certified funded lifecycle rules; (3) stress
the top funded cells (slippage / cost / winners-fill / entry-realism) exactly as the eval-side
Wave-2 stress lane (`tools_opt_finalist_stress.py`) already does, just re-pointed at the FUNDED
simulator instead of the eval funnel.

PRIOR ART REUSED (imported, not reimplemented):
  - `tools_sim_parity_check.py` (SPC): `load_rows()` — HONEST A-kept stream (canary n=583, PF=1.361).
  - `tools_1m_truth_recert.py` / `tools_salvage_track_a.py` (TA): `load_streams()['unfiltered']` —
    HONEST A-UNFILTERED stream (canary n=705, PF=1.237; already in the exact (ts,R,mae_r,risk_usd)
    row shape via `truth_a_streams(...)["exit3"]` + `t["filled"]`).
  - `tools_vpc_1m_truth.py` (VT) via `tools_opt_finalist_stress.load_vpc_stream()` (FS): 1m-truth VPC
    re-walk stream (canary n=408, PF(points)=1.318). `FS.load_vpc_stream()` and `FS.load_a_stream()`
    and `FS._localize`/`FS.funnel` are reused VERBATIM — this is the exact tz-normalization +
    eval-funnel primitive the task brief asks to "copy tools_opt_finalist_stress.py's tz handling
    EXACTLY" (naive VPC stamps treated AS ALREADY NY wall-clock via `tz_localize(NY)`, no UTC
    conversion — the same convention `tools_opt_conflict_risk._localize` / `tools_opt_sizing_grid.
    kept_trades()` already use).
  - `tools_salvage_vpc_reeval.py` (VR): `a_rows_2022`/`a_rows_full`, `WINDOW_START`, `ASR`
    (`build_events`/`day_rows`), `STOP_PINNED`/`DLL_PINNED`, `event_pf`, `summarize_cell`,
    `combined_daily_series`, `funded_canary` (the funded-side built-in canary the task brief asks to
    "run it" — reproduces `tools_recert_funded.daily_series`/`run_pa` exactly at cap=3,4,5,6,
    covering the task's "A4" pin), `DPP`.
  - `tools_recert_funded.py` (TF): `monthly_starts`, `run_pa_instrumented` (the certified funded
    lifecycle: PA ladder [1500,1500,2000,2500,2500,3000], CLOSED_MAX, safety net (LOCK_EOD reach),
    DLL/$550 daily-stop, $550 realized cutoff, 30-day payout-sweep cycle, 0.50 consistency rule) —
    used VERBATIM, not reimplemented.
  - `apex_funded_40.py` (FM, via TF): START/TRAIL/LOCK_EOD/DLL/DAILY_STOP/LADDER/MIN_REQ/
    PAYOUT_FLOOR/QUAL_DAY/QUAL_N/CONSISTENCY/PAYOUT_EVERY_D — the certified Apex 4.0 EOD 50K rule
    constants, imported not retyped.
  - `tools_salvage_stress.py` (ST): `FIREWALL_FILES`/`sha_of` (firewall bookkeeping), `dmg_slip`
    (uniform R slippage), `dmg_partial` (winners' fill fraction), `dmg_chase` (entry-realism extra
    points -> R damage via that trade's own stop_pts).

NEW LOGIC (self-verified extension, not prior art — called out, not hidden):
  - `run_pa_instrumented_dd()`: a byte-for-byte copy of `TF.run_pa_instrumented` with ONE addition —
    tracking `maxdd = max(maxdd, peak_eod - bal)` after every day's balance update (a pure read-out
    of state the original function ALREADY computes; no new rule, no new threshold, nothing that can
    change an outcome). Verified in `canary_dd_reproduction()` below to reproduce `TF.run_pa_
    instrumented`'s outcome/months/paid/n_payouts trade-for-trade on every cell run in this file
    before any report is written.
  - Payout-eligibility / first-payout / second-payout / full-ladder rates: extracted mechanically from
    the payout-COUNT distribution over `n_payouts` per start (n_payouts>=1 == "first-payout" ==
    "payout-eligibility" — the ladder's first rung; n_payouts>=2 == "second-payout"; n_payouts==6 (==
    len(LADDER)) == "full-ladder", which is also exactly the CLOSED_MAX outcome). No new rule.
  - "worst start-year split": the single start-year (from `run_pa_instrumented`'s own `start_year`
    field) with the HIGHEST bust_pct among that cell's per-year breakdown. Mechanical, no judgment.
  - "trades/month" / "mean risk/month": built from a per-trade dollar event list (same sizing rule
    `q=min(cap, int(budget//risk_usd))` as `combined_daily_series`, but NOT day-collapsed) — total
    qualifying (sized) events / total qualifying event dollar-risk, divided by the stream's own
    calendar span in months (`(last_ts-first_ts).days/30.4`, the same 30.4 day-month convention
    `run_pa_instrumented`'s own `months` field already uses).
  - "A-vs-VPC funded same-day loss correlation (co-active Pearson)": DELIBERATE, DOCUMENTED CHOICE —
    a NEW term (not "same-day loss correlation", the pre-existing unit-level/union-with-$0 metric
    already defined in `tools_salvage_vpc_reeval.py`'s module docstring for the EVAL side). Here,
    for a given FUNDED cell's own (budget,cap) pair per leg: build each leg's OWN day-level `real`
    series via `combined_daily_series` with only that leg active, restrict to CO-ACTIVE calendar days
    (days on which BOTH legs independently have >=1 sized trade that day — i.e. both day-series
    contain that date, no zero-fill), and Pearson-correlate the two legs' `real` values on exactly
    those days. `None`/N/A if the VPC leg is OFF or fewer than 2 co-active days exist. This is a
    genuinely new metric (the task brief names it "co-active Pearson", distinct from the eval-side
    convention), so the definition is spelled out here rather than silently reusing the union/$0-fill
    convention, which would answer a different question ("what if VPC hadn't traded that day" vs.
    "when both actually traded, how correlated were the outcomes").
  - maxDD reported per cell as the MEDIAN across that cell's monthly-rolling starts (consistent with
    this file's other per-start aggregates, which are medians/means over the same overlapping-start
    population) AND the WORST (max) across starts, both columns present, labelled accordingly.
  - COST 2x/3x stress (04): IDENTICAL convention to `tools_opt_finalist_stress.py`'s own cost-damage
    block (extra_units * lane_base_RT_cost_pt / that_lane's_own_median_stop_pts, A base ~=1.2pt
    task-given, VPC base=0.75pt `nq_vwap_pullback.RT_COST`), applied via `ST.dmg_slip`, just re-run
    through the FUNDED simulator instead of the eval funnel. Copied, not reinvented.
  - Winners-fill on FUNDED: per the task brief, this is explicitly NOT used as a funded-side REJECT
    criterion — the machine-level adjudication already on file (`reports/a_vpc_portfolio_
    optimisation/07_top_cell_stress.md`) is quoted verbatim in the 04 report rather than re-derived.

OVERLAP CAVEAT (verbatim, `tools_recert_funded.py` / `apex_funded_40` funded_40_recert.caveats[0]):
"monthly rolling starts OVERLAP -> effective independent samples ~4-5, bust% has wide CI" — every
percentage below is a point estimate over a small number of effectively-independent overlapping-start
samples, NOT an i.i.d. probability. Treated as WIDE-CI throughout, stated verbatim in every report.

FIREWALL: sha256 of `tools_salvage_stress.FIREWALL_FILES` (config_eval_locked.py,
config_funded_locked.py, config_defaults.py, auto_safety.py) taken before load and again right
before any report is written. Any mismatch -> STOP, no report written.

STOP conditions (per task brief, checked before anything is trusted downstream):
  - Any of the 4 pinned STREAM canaries (A-kept 583/PF1.361, A-unfiltered 705/PF1.237, VPC 408/
    PF(pts)1.318, eval baseline A600/6+VPC600/4 -> 28.7/17.0/54.4 n=684) mismatches.
  - The balanced eval row (A900/6+VPC600/3) misses its expected 37.4/18.0/44.6 by >0.3pp on any of
    pass/bust/exp.
  - `VR.funded_canary` (generalized funded runner vs `apex_funded_40`/`tools_recert_funded`, at
    cap=3,4,5,6 incl. the task-pinned "A4") mismatches.
  - `run_pa_instrumented_dd`'s own reproduction canary vs `TF.run_pa_instrumented` mismatches.
  - Firewall mismatch before writing any report.

Outputs (new, this run only):
  reports/relock_dec_funded_rerun/01_eval_relock_summary.{md,json}
  reports/relock_dec_funded_rerun/03_funded_rerun_matrix.{csv,md}
  reports/relock_dec_funded_rerun/04_funded_stress_tests.{csv,md}

No winner-picking. No commits.
"""
import os
import sys
import json
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tools_sim_parity_check as SPC             # load_rows (A-kept, honest, 583)
import tools_salvage_track_a as TA                # load_streams()['unfiltered'] (A-unfiltered, 705)
import tools_salvage_vpc_reeval as VR             # a_rows_2022, combined_daily_series, funded_canary, ASR
import tools_opt_finalist_stress as FS            # load_a_stream/load_vpc_stream/_localize/funnel (VPC 1m-truth + tz)
import tools_recert_funded as TF                  # monthly_starts, run_pa_instrumented, certified funded rules
import tools_salvage_stress as ST                 # FIREWALL_FILES, sha_of, dmg_slip, dmg_partial, dmg_chase
import apex_funded_40 as FM                       # certified rule constants (read-only)

NY = "America/New_York"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "relock_dec_funded_rerun")
FIREWALL_FILES = ST.FIREWALL_FILES

FEE_PER_ATTEMPT = 131.0
FEE_PER_ATTEMPT_PROMO = 30.0

OVERLAP_CAVEAT = ("monthly rolling starts OVERLAP -> effective independent samples ~4-5, "
                  "bust% has wide CI")

# 07_top_cell_stress.csv flip_point_R for the exact (a_bc, v_bc) triples this task pins as
# baseline/balanced/watch (reused, NOT recomputed -- see module docstring; F01/F08/F02 rows).
FLIP_LOOKUP_CSV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "reports", "a_vpc_portfolio_optimisation",
    "07_top_cell_stress.csv")

EVAL_ROWS = [
    dict(name="baseline", a_bc=(600, 6), v_bc=(600, 4),
         expect=dict(pass_pct=28.7, bust_pct=17.0, exp_pct=54.4, n=684, fps=4.22)),
    dict(name="balanced", a_bc=(900, 6), v_bc=(600, 3),
         expect=dict(pass_pct=37.4, bust_pct=18.0, exp_pct=44.6, n=684, fps=5.89)),
    dict(name="watch", a_bc=(900, 6), v_bc=(700, 3),
         expect=dict(pass_pct=39.3, bust_pct=19.6, exp_pct=41.1, n=684, fps=6.37)),
]

# ---- FUNDED grid (task-pinned) ----
A_KEPT_CELLS = [(150, 2), (200, 3), (250, 4), (300, 4), (400, 4), (480, 4)]
VPC_CELLS = [None, (100, 1), (150, 1), (200, 2), (250, 2), (300, 2)]
A_UNF_CELLS = [(250, 4), (300, 4)]
VPC_UNF_CELLS = [None, (200, 2)]
NEG_CONTROL = dict(a_bc=(900, 6), v_bc=(600, 3))

SLIP_LADDER_04 = [0.01, 0.02, 0.03, 0.05, 0.075, 0.10]
WINNERS_FILL_04 = [0.90, 0.85, 0.75]
A_COST_BASE_PT = 1.2
V_COST_BASE_PT = 0.75
A_RETEST_PTS = [0.25, 0.50]     # +1tk, +2tk
V_CHASE_PTS = [0.5, 1.0]

REJECT_BUST_PCT = 25.0
REJECT_EPAID = 3000.0
REJECT_SLIP_R = 0.02

ADJUDICATION_QUOTE = (
    "the winners-75% clause is UNSATISFIABLE by construction for any honest thin edge (PF 1.35 x "
    "0.75 ~= 1.01 breakeven -- only PF>=1.8 machines pass it, which our too-good gate would freeze). "
    "It rejected the baseline and discriminates nothing. RULING: winners-fill sensitivity is a "
    "MACHINE-LEVEL operating condition governed by the existing live fill-telemetry kill line (15% "
    "adverse touch-without-fill ~= 85% winner-capture floor), NOT a config selector. Config-level "
    "reject bar = dies-at-0.015R OR flip<0.025R OR dies-at-2x-costs -- under which all 45 survive."
)


# ==================================================================================================
# firewall
# ==================================================================================================
def firewall_snapshot():
    return ST.sha_of(FIREWALL_FILES)


def firewall_check(before, after):
    return all(before[fn] == after[fn] for fn in FIREWALL_FILES)


# ==================================================================================================
# stream loading + canaries
# ==================================================================================================
def load_all_streams():
    print("loading A-kept (SPC.load_rows, 583)...", flush=True)
    a_full = SPC.load_rows()
    a2022 = VR.a_rows_2022(a_full)

    print("loading A-unfiltered (TA.load_streams, 705)...", flush=True)
    ta = TA.load_streams()
    unf_full = FS._loc_rows(ta["unfiltered"])
    unf2022 = [r for r in unf_full if r["ts"] >= VR.WINDOW_START]

    print("loading VPC 1m-truth stream (FS.load_vpc_stream, 408)...", flush=True)
    v_rows, df1m, feats, d1rth, ok_v = FS.load_vpc_stream()

    return dict(a_full=a_full, a2022=a2022, unf_full=unf_full, unf2022=unf2022,
                v_rows=v_rows, ta=ta, ok_v=ok_v)


def check_stream_canaries(S):
    print("\n" + "=" * 100)
    print("STREAM CANARIES")
    print("=" * 100)
    ok = True

    n, pf = len(S["a_full"]), _pf_r(S["a_full"])
    c = (n == 583 and abs(pf - 1.361) < 0.0005)
    print(f"A-kept: n={n} PF={pf:.3f} (expect 583 / 1.361) -> {'PASS' if c else 'FAIL'}")
    ok &= c

    su = TA.stream_stats([t["R"] for t in S["unf_full"]])
    c = (su["n"] == 705 and abs(su["PF"] - 1.237) < 0.0005)
    print(f"A-unfiltered: n={su['n']} PF={su['PF']} (expect 705 / 1.237) -> {'PASS' if c else 'FAIL'}")
    ok &= c

    c = S["ok_v"]
    print(f"VPC 1m-truth: n=408 PF(pts)=1.318 built-in canary -> {'PASS' if c else 'FAIL'}")
    ok &= c

    s0, pf0, ev0, days0 = FS.funnel(S["a2022"], (600, 6), S["v_rows"], (600, 4), "eval baseline canary")
    exp = EVAL_ROWS[0]["expect"]
    c = (s0["pass_pct"] == exp["pass_pct"] and s0["bust_pct"] == exp["bust_pct"]
         and s0["exp_pct"] == exp["exp_pct"] and s0["eligible_starts"] == exp["n"])
    print(f"Eval baseline A600/6+VPC600/4: got pass={s0['pass_pct']} bust={s0['bust_pct']} "
          f"exp={s0['exp_pct']} n={s0['eligible_starts']} (expect {exp['pass_pct']}/{exp['bust_pct']}/"
          f"{exp['exp_pct']}/{exp['n']}) -> {'PASS' if c else 'FAIL'}")
    ok &= c

    print(f"\n-> STREAM CANARIES: {'ALL PASS' if ok else 'FAIL -- STOP'}")
    print("=" * 100)
    return ok


def _pf_r(rows):
    wins = sum(r["R"] for r in rows if r["R"] > 0)
    losses = -sum(r["R"] for r in rows if r["R"] < 0)
    return wins / losses if losses else float("nan")


def check_funded_canary(a2022):
    print("\n" + "=" * 100)
    print("FUNDED CANARY (VR.funded_canary -- generalized funded runner vs tools_recert_funded, "
          "covers task-pinned 'A4')")
    print("=" * 100)
    ok = VR.funded_canary(a2022)
    print(f"-> FUNDED CANARY: {'PASS' if ok else 'FAIL -- STOP'}")
    print("=" * 100)
    return ok


# ==================================================================================================
# 01 -- eval relock summary
# ==================================================================================================
def flip_lookup(a_bc, v_bc):
    if not os.path.exists(FLIP_LOOKUP_CSV):
        return None
    df = pd.read_csv(FLIP_LOOKUP_CSV)
    m = df[(df.a_budget == a_bc[0]) & (df.a_cap == a_bc[1]) &
           (df.v_budget == v_bc[0]) & (df.v_cap == v_bc[1])]
    if len(m) == 0:
        return None
    return float(m.iloc[0]["flip_point_R"])


def section01(S):
    rows_out = []
    for spec in EVAL_ROWS:
        s, pf, ev, days = FS.funnel(S["a2022"], spec["a_bc"], S["v_rows"], spec["v_bc"], spec["name"])
        flip = flip_lookup(spec["a_bc"], spec["v_bc"])
        pass_rate = s["pass_pct"] / 100.0
        attempts_per_pass = (1.0 / pass_rate) if pass_rate > 0 else None
        fee_per_pass = (attempts_per_pass * FEE_PER_ATTEMPT) if attempts_per_pass else None
        fee_per_pass_promo = (attempts_per_pass * FEE_PER_ATTEMPT_PROMO) if attempts_per_pass else None
        rows_out.append(dict(
            name=spec["name"], a_bc=f"{spec['a_bc'][0]}/{spec['a_bc'][1]}",
            v_bc=f"{spec['v_bc'][0]}/{spec['v_bc'][1]}",
            pass_pct=s["pass_pct"], bust_pct=s["bust_pct"], exp_pct=s["exp_pct"],
            not_pass_pct=round(s["bust_pct"] + s["exp_pct"], 1),
            n=s["eligible_starts"], funded_per_slot_year=s["funded_per_slot_year"],
            attempts_per_pass=round(attempts_per_pass, 3) if attempts_per_pass else None,
            fee_per_pass=round(fee_per_pass, 0) if fee_per_pass else None,
            fee_per_pass_promo=round(fee_per_pass_promo, 0) if fee_per_pass_promo else None,
            flip_point_R=flip, pf_dollar=pf,
            expect=spec["expect"],
        ))

    baseline = rows_out[0]
    for r in rows_out:
        r["delta_pass_pp"] = round(r["pass_pct"] - baseline["pass_pct"], 1)
        r["delta_bust_pp"] = round(r["bust_pct"] - baseline["bust_pct"], 1)
        r["delta_exp_pp"] = round(r["exp_pct"] - baseline["exp_pct"], 1)
        r["delta_flip_R"] = (round(r["flip_point_R"] - baseline["flip_point_R"], 4)
                              if (r["flip_point_R"] is not None and baseline["flip_point_R"] is not None)
                              else None)

    # miss check on balanced row (>0.3pp any of pass/bust/exp -> STOP, caller handles)
    balanced = rows_out[1]
    exp = balanced["expect"]
    miss = (abs(balanced["pass_pct"] - exp["pass_pct"]) > 0.3 or
            abs(balanced["bust_pct"] - exp["bust_pct"]) > 0.3 or
            abs(balanced["exp_pct"] - exp["exp_pct"]) > 0.3)
    return rows_out, miss


def write_01(rows_out):
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "01_eval_relock_summary.json"), "w") as f:
        json.dump(rows_out, f, indent=1, default=str)

    lines = []
    lines.append("# 01 -- Eval Re-Lock Summary (RE-LOCK DEC + Funded Re-Run)")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. Reproduced via the pinned funnel "
                 "(`tools_opt_finalist_stress.funnel` / `tools_salvage_vpc_reeval.ASR`), unmodified.")
    lines.append("")
    lines.append(f"OVERLAP CAVEAT (verbatim): {OVERLAP_CAVEAT}")
    lines.append("")
    hdr = ("| row | A(budget/cap) | VPC(budget/cap) | pass% | bust% | exp% | not-pass% | n | "
           "f/slot/yr | attempts/pass | fee/pass ($131) | fee/pass ($30 promo) | flip_R | "
           "Δpass | Δbust | Δexp | Δflip |")
    sep = "|" + "---|" * 17
    lines.append(hdr)
    lines.append(sep)
    for r in rows_out:
        lines.append(
            f"| {r['name']} | {r['a_bc']} | {r['v_bc']} | {r['pass_pct']} | {r['bust_pct']} | "
            f"{r['exp_pct']} | {r['not_pass_pct']} | {r['n']} | {r['funded_per_slot_year']} | "
            f"{r['attempts_per_pass']} | {r['fee_per_pass']} | {r['fee_per_pass_promo']} | "
            f"{r['flip_point_R']} | {r['delta_pass_pp']} | {r['delta_bust_pp']} | "
            f"{r['delta_exp_pp']} | {r['delta_flip_R']} |")
    lines.append("")
    lines.append("`flip_point_R` reused verbatim from the already-certified "
                 "`reports/a_vpc_portfolio_optimisation/07_top_cell_stress.csv` (F01/F08/F02 rows), "
                 "NOT recomputed here (avoids duplicating the full slip-ladder engine for 3 rows "
                 "already on file at the exact pinned (budget,cap) tuples).")
    lines.append("")
    lines.append("No winner-picking.")
    with open(os.path.join(OUTDIR, "01_eval_relock_summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


# ==================================================================================================
# funded core engine (TF.run_pa_instrumented reused; run_pa_instrumented_dd adds maxDD readout only)
# ==================================================================================================
def run_pa_instrumented_dd(days, start_i):
    """Byte-for-byte copy of TF.run_pa_instrumented + a pure readout: maxdd = max(peak_eod - bal)
    after every day's balance update. No new rule; verified against TF.run_pa_instrumented in
    canary_dd_reproduction() before use."""
    bal, peak_eod, locked = FM.START, FM.START, False
    thr = FM.START - FM.TRAIL
    paid, ladder_i = 0.0, 0
    since = dict(profit=0.0, maxday=0.0, qual=0)
    t0 = days[start_i][0]
    last_sweep = t0
    safety_net_day = None
    payouts = []
    maxdd = 0.0

    def result(outcome, d_last):
        return dict(outcome=outcome, day_offset=(d_last - t0).days,
                    months=(d_last - t0).days / 30.4, paid=paid, n_payouts=ladder_i,
                    safety_net_day=safety_net_day, payouts=list(payouts), start_year=t0.year,
                    maxdd=maxdd)

    for i in range(start_i, len(days)):
        d, real, trough = days[i]
        if bal + min(0.0, trough) <= thr:
            return result("BUST", d)
        bal += real
        since["profit"] += real
        since["maxday"] = max(since["maxday"], real)
        if real >= FM.QUAL_DAY:
            since["qual"] += 1
        peak_eod = max(peak_eod, bal)
        maxdd = max(maxdd, peak_eod - bal)
        if safety_net_day is None and peak_eod >= FM.LOCK_EOD:
            safety_net_day = (d - t0).days
        if not locked:
            thr = max(thr, peak_eod - FM.TRAIL)
            if peak_eod >= FM.LOCK_EOD:
                thr = FM.START + 100.0
                locked = True
        if bal <= thr:
            return result("BUST", d)
        if (d - last_sweep).days >= FM.PAYOUT_EVERY_D:
            last_sweep = d
            eligible = (bal >= FM.MIN_REQ and since["qual"] >= FM.QUAL_N
                        and (since["profit"] > 0 and since["maxday"] < FM.CONSISTENCY * since["profit"]))
            if eligible:
                amt = min(FM.LADDER[ladder_i], bal - FM.PAYOUT_FLOOR)
                if amt > 0:
                    bal -= amt
                    paid += amt
                    ladder_i += 1
                    payouts.append(dict(index=ladder_i, day_offset=(d - t0).days, amount=amt))
                    since = dict(profit=0.0, maxday=0.0, qual=0)
                    if ladder_i >= len(FM.LADDER):
                        return result("CLOSED_MAX", d)
    return result("DATA_END", days[-1][0])


def canary_dd_reproduction(a2022):
    print("\n" + "=" * 100)
    print("run_pa_instrumented_dd CANARY (must reproduce TF.run_pa_instrumented outcome-for-outcome)")
    print("=" * 100)
    ok = True
    for cap in (3, 4, 5, 6):
        days = VR.combined_daily_series(a2022, 160.0 * cap, cap, [], None, None)
        starts = TF.monthly_starts(days)
        r1 = [TF.run_pa_instrumented(days, s) for s in starts]
        r2 = [run_pa_instrumented_dd(days, s) for s in starts]
        n_mismatch = 0
        for o1, o2 in zip(r1, r2):
            same = (o1["outcome"] == o2["outcome"] and abs(o1["months"] - o2["months"]) < 1e-9
                    and abs(o1["paid"] - o2["paid"]) < 1e-9 and o1["n_payouts"] == o2["n_payouts"])
            if not same:
                n_mismatch += 1
        status = "OK" if n_mismatch == 0 else f"MISMATCH ({n_mismatch}/{len(starts)})"
        print(f"  cap={cap}: {status} (n={len(starts)} starts)")
        ok &= (n_mismatch == 0)
    print(f"-> {'[canary OK]' if ok else '[CANARY MISMATCH] STOPPING'}")
    print("=" * 100)
    return ok


# ==================================================================================================
# per-cell full metrics (funded)
# ==================================================================================================
def _events_dollar(rows, budget, cap):
    ev = []
    for t in rows:
        risk1 = t["risk_usd"]
        q = min(cap, int(budget // risk1))
        if q < 1:
            continue
        ev.append((pd.Timestamp(t["ts"]), t["R"] * risk1 * q, risk1 * q))
    ev.sort(key=lambda x: x[0])
    return ev


def _trades_and_risk_per_month(a_rows, a_bc, v_rows, v_bc):
    ev = []
    if a_rows is not None and a_bc is not None:
        ev += _events_dollar(a_rows, a_bc[0], a_bc[1])
    if v_rows is not None and v_bc is not None:
        ev += _events_dollar(v_rows, v_bc[0], v_bc[1])
    if not ev:
        return None, None
    ev.sort(key=lambda x: x[0])
    span_days = (ev[-1][0] - ev[0][0]).days
    months = max(span_days / 30.4, 1e-9)
    trades_per_month = len(ev) / months
    risk_per_month = sum(r for _, _, r in ev) / months
    return round(trades_per_month, 2), round(risk_per_month, 0)


def _coactive_pearson(a_rows, a_bc, v_rows, v_bc):
    if v_rows is None or v_bc is None or a_rows is None or a_bc is None:
        return None
    days_a = VR.combined_daily_series(a_rows, a_bc[0], a_bc[1], [], None, None)
    days_v = VR.combined_daily_series([], None, None, v_rows, v_bc[0], v_bc[1])
    map_a = {d: real for d, real, _ in days_a}
    map_v = {d: real for d, real, _ in days_v}
    co_dates = sorted(set(map_a) & set(map_v))
    if len(co_dates) < 2:
        return None
    xa = np.array([map_a[d] for d in co_dates], float)
    xv = np.array([map_v[d] for d in co_dates], float)
    if xa.std() == 0 or xv.std() == 0:
        return None
    return round(float(np.corrcoef(xa, xv)[0, 1]), 3), len(co_dates)


def cell_full_report(a_rows, a_bc, v_rows, v_bc, label):
    rv = v_rows if v_rows is not None else []
    bv, cv = (v_bc[0], v_bc[1]) if v_bc is not None else (None, None)
    av, ac = (a_bc[0], a_bc[1]) if a_bc is not None else (None, None)
    days = VR.combined_daily_series(a_rows if a_rows is not None else [], av, ac, rv, bv, cv)
    starts = TF.monthly_starts(days)
    res = [run_pa_instrumented_dd(days, s) for s in starts]
    n = len(res)
    if n == 0:
        return dict(label=label, a_bc=a_bc, v_bc=v_bc, n_starts=0)

    bust = [r for r in res if r["outcome"] == "BUST"]
    closed = [r for r in res if r["outcome"] == "CLOSED_MAX"]
    data_end = [r for r in res if r["outcome"] == "DATA_END"]
    reached_sn = [r for r in res if r["safety_net_day"] is not None]

    paid_all = [r["paid"] for r in res]
    months_all = [r["months"] for r in res]
    n_payouts_all = [r["n_payouts"] for r in res]
    maxdd_all = [r["maxdd"] for r in res]

    n_ladder = len(FM.LADDER)
    payout_eligibility_pct = round(100 * sum(1 for x in n_payouts_all if x >= 1) / n, 1)
    first_payout_pct = payout_eligibility_pct
    second_payout_pct = round(100 * sum(1 for x in n_payouts_all if x >= 2) / n, 1)
    full_ladder_pct = round(100 * sum(1 for x in n_payouts_all if x >= n_ladder) / n, 1)

    per_year = {}
    for r in res:
        y = r["start_year"]
        rec = per_year.setdefault(y, dict(n=0, bust=0))
        rec["n"] += 1
        if r["outcome"] == "BUST":
            rec["bust"] += 1
    per_year_pct = {y: dict(n=v_["n"], bust_pct=round(100 * v_["bust"] / v_["n"], 1))
                    for y, v_ in sorted(per_year.items())}
    worst_year = max(per_year_pct.items(), key=lambda kv: kv[1]["bust_pct"]) if per_year_pct else (None, {})

    worst_day = round(float(min(r_ for _, r_, _ in days)), 0) if days else None

    tpm, rpm = _trades_and_risk_per_month(a_rows, a_bc, v_rows, v_bc)
    corr = _coactive_pearson(a_rows, a_bc, v_rows, v_bc)
    corr_val, corr_n = (corr if corr else (None, None))

    return dict(
        label=label, a_budget=av, a_cap=ac, v_budget=bv, v_cap=cv,
        n_starts=n,
        e_paid=round(float(np.mean(paid_all))),
        med_paid=round(float(np.median(paid_all))),
        mean_paid=round(float(np.mean(paid_all))),
        med_months=round(float(np.median(months_all)), 1),
        mean_months=round(float(np.mean(months_all)), 1),
        bust_pct=round(100 * len(bust) / n, 1),
        closed_max_pct=round(100 * len(closed) / n, 1),
        data_end_pct=round(100 * len(data_end) / n, 1),
        safety_net_pct=round(100 * len(reached_sn) / n, 1),
        med_days_to_safety_net=(round(float(np.median([r["safety_net_day"] for r in reached_sn])), 1)
                                 if reached_sn else None),
        payout_eligibility_pct=payout_eligibility_pct,
        first_payout_pct=first_payout_pct,
        second_payout_pct=second_payout_pct,
        full_ladder_pct=full_ladder_pct,
        maxdd_median=round(float(np.median(maxdd_all)), 0),
        maxdd_worst=round(float(np.max(maxdd_all)), 0),
        worst_day=worst_day,
        worst_start_year=worst_year[0],
        worst_start_year_bust_pct=worst_year[1].get("bust_pct"),
        trades_per_month=tpm,
        mean_risk_per_month=rpm,
        a_vpc_coactive_pearson=corr_val,
        a_vpc_coactive_n=corr_n,
        per_start_year=per_year_pct,
    )


# ==================================================================================================
# 03 -- funded rerun matrix
# ==================================================================================================
def section03(S):
    cells = []

    for a_bc in A_KEPT_CELLS:
        for v_bc in VPC_CELLS:
            label = f"A@{a_bc[0]}/{a_bc[1]}" + (f"+VPC@{v_bc[0]}/{v_bc[1]}" if v_bc else " (VPC OFF)")
            r = cell_full_report(S["a2022"], a_bc, S["v_rows"], v_bc, label)
            r["family"] = "A-kept"
            cells.append(r)

    for a_bc in A_UNF_CELLS:
        for v_bc in VPC_UNF_CELLS:
            label = f"A-unf@{a_bc[0]}/{a_bc[1]}" + (f"+VPC@{v_bc[0]}/{v_bc[1]}" if v_bc else " (VPC OFF)")
            r = cell_full_report(S["unf2022"], a_bc, S["v_rows"], v_bc, label)
            r["family"] = "A-unfiltered"
            cells.append(r)

    neg_label = f"NEGATIVE CONTROL A@{NEG_CONTROL['a_bc'][0]}/{NEG_CONTROL['a_bc'][1]}" \
                f"+VPC@{NEG_CONTROL['v_bc'][0]}/{NEG_CONTROL['v_bc'][1]} (eval-style thru funded sim)"
    neg = cell_full_report(S["a2022"], NEG_CONTROL["a_bc"], S["v_rows"], NEG_CONTROL["v_bc"], neg_label)
    neg["family"] = "negative-control"

    return cells, neg


def write_03(cells, neg):
    os.makedirs(OUTDIR, exist_ok=True)
    df = pd.DataFrame.from_records(cells + [neg])
    df.to_csv(os.path.join(OUTDIR, "03_funded_rerun_matrix.csv"), index=False)

    top10 = sorted([c for c in cells], key=lambda c: c.get("e_paid", -1), reverse=True)[:10]

    lines = []
    lines.append("# 03 -- Funded Re-Run Matrix (RE-LOCK DEC + Funded Re-Run)")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. Uses ONLY the repo's implemented funded/payout "
                 "rules (`apex_funded_40.py` / `tools_recert_funded.py`, imported not retyped): PA "
                 "ladder [1500,1500,2000,2500,2500,3000], CLOSED_MAX, safety net (LOCK_EOD reach), "
                 "$1,000 DLL, $550 daily stop, 0.50 consistency, 30-day payout-sweep cycle.")
    lines.append("")
    lines.append(f"OVERLAP CAVEAT (verbatim): {OVERLAP_CAVEAT}")
    lines.append("")
    lines.append(f"Grid: A-kept {A_KEPT_CELLS} x VPC {['OFF' if v is None else v for v in VPC_CELLS]} "
                 f"= {len(A_KEPT_CELLS) * len(VPC_CELLS)} cells; "
                 f"A-unfiltered {A_UNF_CELLS} x VPC {['OFF' if v is None else v for v in VPC_UNF_CELLS]} "
                 f"= {len(A_UNF_CELLS) * len(VPC_UNF_CELLS)} cells; "
                 f"+1 negative control (eval-style A900/6+VPC600/3 run through the funded simulator).")
    lines.append("")
    lines.append("## Top-10 by E[paid]")
    hdr = ("| label | n | E[paid] | med paid | mean paid | med mo | mean mo | bust% | SN% | med SN day | "
           "1st-payout% | 2nd-payout% | full-ladder% | maxDD med | maxDD worst | worst yr (bust%) | "
           "trades/mo | risk/mo | A-vs-VPC coactive r (n) |")
    sep = "|" + "---|" * 18
    lines.append(hdr)
    lines.append(sep)
    for c in top10:
        wy = f"{c['worst_start_year']} ({c['worst_start_year_bust_pct']}%)" if c["worst_start_year"] else "-"
        cr = f"{c['a_vpc_coactive_pearson']} (n={c['a_vpc_coactive_n']})" if c["a_vpc_coactive_pearson"] is not None else "N/A"
        lines.append(
            f"| {c['label']} | {c['n_starts']} | ${c['e_paid']:,} | ${c['med_paid']:,} | "
            f"${c['mean_paid']:,} | {c['med_months']} | {c['mean_months']} | {c['bust_pct']} | "
            f"{c['safety_net_pct']} | {c['med_days_to_safety_net']} | {c['first_payout_pct']} | "
            f"{c['second_payout_pct']} | {c['full_ladder_pct']} | ${c['maxdd_median']:,.0f} | "
            f"${c['maxdd_worst']:,.0f} | {wy} | {c['trades_per_month']} | ${c['mean_risk_per_month']:,.0f} | {cr} |")
    lines.append("")
    lines.append("## Negative control (eval-style A900/6+VPC600/3 through the FUNDED simulator)")
    wy = f"{neg['worst_start_year']} ({neg['worst_start_year_bust_pct']}%)" if neg["worst_start_year"] else "-"
    cr = f"{neg['a_vpc_coactive_pearson']} (n={neg['a_vpc_coactive_n']})" if neg["a_vpc_coactive_pearson"] is not None else "N/A"
    lines.append(hdr)
    lines.append(sep)
    lines.append(
        f"| {neg['label']} | {neg['n_starts']} | ${neg['e_paid']:,} | ${neg['med_paid']:,} | "
        f"${neg['mean_paid']:,} | {neg['med_months']} | {neg['mean_months']} | {neg['bust_pct']} | "
        f"{neg['safety_net_pct']} | {neg['med_days_to_safety_net']} | {neg['first_payout_pct']} | "
        f"{neg['second_payout_pct']} | {neg['full_ladder_pct']} | ${neg['maxdd_median']:,.0f} | "
        f"${neg['maxdd_worst']:,.0f} | {wy} | {neg['trades_per_month']} | ${neg['mean_risk_per_month']:,.0f} | {cr} |")
    lines.append("")
    lines.append("No winner-picking.")
    with open(os.path.join(OUTDIR, "03_funded_rerun_matrix.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return top10


# ==================================================================================================
# 04 -- funded stress tests
# ==================================================================================================
def median_stop_pts(rows):
    if not rows:
        return None
    return float(np.median([r["risk_usd"] / VR.DPP for r in rows]))


def _rows_for_family(S, family):
    return S["a2022"] if family != "A-unfiltered" else S["unf2022"]


def select_stress_cells(cells):
    elig = [c for c in cells if c.get("n_starts", 0) and c["bust_pct"] <= 15.0]
    top5 = sorted(elig, key=lambda c: c["e_paid"], reverse=True)[:5]
    vpc_incl = [c for c in cells if c.get("v_cap") is not None]
    best_vpc = max(vpc_incl, key=lambda c: c["e_paid"]) if vpc_incl else None
    chosen = list(top5)
    labels = {c["label"] for c in chosen}
    if best_vpc is not None and best_vpc["label"] not in labels:
        chosen.append(best_vpc)
    return chosen, best_vpc


def stress_one_cell(S, cell):
    a_bc = (cell["a_budget"], cell["a_cap"])
    v_bc = (cell["v_budget"], cell["v_cap"]) if cell["v_cap"] is not None else None
    a_rows = _rows_for_family(S, cell["family"])
    v_rows = S["v_rows"]

    out = dict(label=cell["label"], family=cell["family"], a_bc=f"{a_bc[0]}/{a_bc[1]}",
               v_bc=(f"{v_bc[0]}/{v_bc[1]}" if v_bc else "OFF"))
    out["base_e_paid"] = cell["e_paid"]
    out["base_bust_pct"] = cell["bust_pct"]
    out["base_safety_net_pct"] = cell["safety_net_pct"]

    # (1) uniform slippage, both lanes
    for sv in SLIP_LADDER_04:
        a_s = ST.dmg_slip(a_rows, sv)
        v_s = ST.dmg_slip(v_rows, sv) if v_bc else None
        r = cell_full_report(a_s, a_bc, v_s, v_bc, f"{cell['label']}-slip{sv}")
        out[f"slip{sv}_e_paid"] = r.get("e_paid")
        out[f"slip{sv}_bust_pct"] = r.get("bust_pct")
        out[f"slip{sv}_safety_net_pct"] = r.get("safety_net_pct")

    # (2) costs 2x/3x (per-lane R-damage via median stop pts -- identical convention to
    # tools_opt_finalist_stress.py's own cost-damage block, copied not reinvented)
    a_med_stop = median_stop_pts(a_rows)
    v_med_stop = median_stop_pts(v_rows) if v_bc else None
    for mult, tag in ((2, "cost2x"), (3, "cost3x")):
        extra_units = mult - 1
        dmg_r_a = (extra_units * A_COST_BASE_PT) / a_med_stop if a_med_stop else 0.0
        dmg_r_v = (extra_units * V_COST_BASE_PT) / v_med_stop if (v_bc and v_med_stop) else 0.0
        a_c = ST.dmg_slip(a_rows, dmg_r_a)
        v_c = ST.dmg_slip(v_rows, dmg_r_v) if v_bc else None
        r = cell_full_report(a_c, a_bc, v_c, v_bc, f"{cell['label']}-{tag}")
        out[f"{tag}_e_paid"] = r.get("e_paid")
        out[f"{tag}_bust_pct"] = r.get("bust_pct")
        out[f"{tag}_safety_net_pct"] = r.get("safety_net_pct")

    # (3) winners-fill (informational only -- machine-level universal, see ADJUDICATION_QUOTE;
    # NOT used in the REJECT column below)
    for f in WINNERS_FILL_04:
        a_p = ST.dmg_partial(a_rows, f)
        v_p = ST.dmg_partial(v_rows, f) if v_bc else None
        r = cell_full_report(a_p, a_bc, v_p, v_bc, f"{cell['label']}-wf{int(f*100)}")
        tag = f"wf{int(f * 100)}"
        out[f"{tag}_e_paid"] = r.get("e_paid")
        out[f"{tag}_bust_pct"] = r.get("bust_pct")
        out[f"{tag}_safety_net_pct"] = r.get("safety_net_pct")

    # (4) entry realism -- A-leg retest-fill (VPC undamaged), VPC-leg chase (A undamaged)
    for pts in A_RETEST_PTS:
        a_r = ST.dmg_chase(a_rows, pts)
        r = cell_full_report(a_r, a_bc, v_rows if v_bc else None, v_bc, f"{cell['label']}-aretest{pts}")
        tag = f"a_retest{pts}pt"
        out[f"{tag}_e_paid"] = r.get("e_paid")
        out[f"{tag}_bust_pct"] = r.get("bust_pct")
        out[f"{tag}_safety_net_pct"] = r.get("safety_net_pct")

    if v_bc:
        for pts in V_CHASE_PTS:
            v_c = ST.dmg_chase(v_rows, pts)
            r = cell_full_report(a_rows, a_bc, v_c, v_bc, f"{cell['label']}-vchase{pts}")
            tag = f"v_chase{pts}pt"
            out[f"{tag}_e_paid"] = r.get("e_paid")
            out[f"{tag}_bust_pct"] = r.get("bust_pct")
            out[f"{tag}_safety_net_pct"] = r.get("safety_net_pct")
    else:
        for pts in V_CHASE_PTS:
            tag = f"v_chase{pts}pt"
            out[f"{tag}_e_paid"] = None
            out[f"{tag}_bust_pct"] = None
            out[f"{tag}_safety_net_pct"] = None

    slip_bust = out.get(f"slip{REJECT_SLIP_R}_bust_pct")
    slip_epaid = out.get(f"slip{REJECT_SLIP_R}_e_paid")
    reject = bool((slip_bust is not None and slip_bust > REJECT_BUST_PCT) or
                  (slip_epaid is not None and slip_epaid < REJECT_EPAID))
    out["REJECT"] = reject
    return out


def section04(S, cells):
    chosen, best_vpc = select_stress_cells(cells)
    out = [stress_one_cell(S, c) for c in chosen]
    return out, best_vpc


def write_04(rows_out, best_vpc):
    os.makedirs(OUTDIR, exist_ok=True)
    df = pd.DataFrame.from_records(rows_out)
    df.to_csv(os.path.join(OUTDIR, "04_funded_stress_tests.csv"), index=False)

    lines = []
    lines.append("# 04 -- Funded Stress Tests (RE-LOCK DEC + Funded Re-Run)")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. Top-5 cells by E[paid] among bust<=15% "
                 "(from 03_funded_rerun_matrix), plus the best VPC-inclusive cell "
                 f"({best_vpc['label'] if best_vpc else 'N/A'}) if not already in that set.")
    lines.append("")
    lines.append(f"OVERLAP CAVEAT (verbatim): {OVERLAP_CAVEAT}")
    lines.append("")
    lines.append("## Winners-fill adjudication (quoted verbatim, `reports/a_vpc_portfolio_"
                 "optimisation/07_top_cell_stress.md`) -- NOT used as a funded-side REJECT criterion:")
    lines.append(f"> {ADJUDICATION_QUOTE}")
    lines.append("")
    lines.append(f"REJECT column: bust% > {REJECT_BUST_PCT} at {REJECT_SLIP_R}R slip OR "
                 f"E[paid] < ${REJECT_EPAID:,.0f} at {REJECT_SLIP_R}R slip.")
    lines.append("")
    hdr = "| label | base E[paid] | base bust% | base SN% |"
    for sv in SLIP_LADDER_04:
        hdr += f" slip{sv} E[paid] | slip{sv} bust% |"
    hdr += " cost2x E[paid] | cost2x bust% | cost3x E[paid] | cost3x bust% | REJECT |"
    lines.append(hdr)
    sep_n = hdr.count("|") - 1
    lines.append("|" + "---|" * sep_n)
    for r in rows_out:
        row = (f"| {r['label']} | ${r['base_e_paid']:,} | {r['base_bust_pct']} | "
               f"{r['base_safety_net_pct']} |")
        for sv in SLIP_LADDER_04:
            ep = r.get(f"slip{sv}_e_paid")
            bp = r.get(f"slip{sv}_bust_pct")
            row += f" {'$' + format(ep, ',') if ep is not None else 'N/A'} | {bp} |"
        row += (f" ${r['cost2x_e_paid']:,} | {r['cost2x_bust_pct']} | "
                f"${r['cost3x_e_paid']:,} | {r['cost3x_bust_pct']} | {r['REJECT']} |")
        lines.append(row)
    lines.append("")
    lines.append("Winners-fill (90/85/75%) and entry-realism (A +1/+2tk, VPC +0.5/+1pt) points are "
                 "in the CSV (all columns) for completeness; per the adjudication above, winners-fill "
                 "is informational only, not a reject criterion here.")
    lines.append("")
    lines.append("No winner-picking.")
    with open(os.path.join(OUTDIR, "04_funded_stress_tests.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


# ==================================================================================================
# main
# ==================================================================================================
def main():
    t0 = time.time()
    fw_before = firewall_snapshot()

    S = load_all_streams()

    if not check_stream_canaries(S):
        print("[STOP] stream canary mismatch.")
        return

    rows_01, miss = section01(S)
    if miss:
        print("[STOP] balanced eval row missed pinned expectation by >0.3pp.")
        return
    write_01(rows_01)
    print("\n[01 written] 01_eval_relock_summary.{md,json}")

    if not check_funded_canary(S["a2022"]):
        print("[STOP] funded canary mismatch.")
        return
    if not canary_dd_reproduction(S["a2022"]):
        print("[STOP] run_pa_instrumented_dd canary mismatch.")
        return

    print("\nrunning 03 funded grid (40 cells)...", flush=True)
    cells, neg = section03(S)
    top10 = write_03(cells, neg)
    print("[03 written] 03_funded_rerun_matrix.{csv,md}")

    print("\nrunning 04 funded stress (top-5 + best-VPC cell)...", flush=True)
    rows_04, best_vpc = section04(S, cells)
    write_04(rows_04, best_vpc)
    print("[04 written] 04_funded_stress_tests.{csv,md}")

    fw_after = firewall_snapshot()
    if not firewall_check(fw_before, fw_after):
        print("[FIREWALL FAILURE] a firewalled file changed during this run -- reports already "
              "written above should be treated as UNTRUSTED.")
        for fn in FIREWALL_FILES:
            print(f"  {fn}: {'UNCHANGED' if fw_before[fn] == fw_after[fn] else 'CHANGED'}")
        return

    runtime_s = time.time() - t0
    print(f"\nRuntime: {runtime_s:.1f}s")
    for fn in FIREWALL_FILES:
        print(f"Firewall {fn}: UNCHANGED")
    print("=" * 100)
    return dict(rows_01=rows_01, cells=cells, neg=neg, top10=top10, rows_04=rows_04, runtime_s=runtime_s)


if __name__ == "__main__":
    main()
