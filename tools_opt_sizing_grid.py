"""tools_opt_sizing_grid.py — A+VPC OPTIMISATION Lane 1: baseline reproduction + full two-lane
sizing grid.

RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing (no live/config/engine file touched).
Pure execution of pinned formulas over PRIOR-ART machinery imported unmodified from
`tools_salvage_vpc_reeval.py` (VR), `tools_vpc_1m_truth.py` (VT), `tools_account_size_research.py`
(VR.ASR), and `tools_salvage_stress.py` (ST, for `dmg_slip`/`FIREWALL_FILES`/`sha_of`). No new
funnel logic — only new grid-orchestration + reporting code.

CANONICAL STREAMS (pinned exactly, per task spec):
  A   = the honest kept stream via `tools_sim_parity_check.load_rows()` (imported here as
        `VR.a_rows_full()`), restricted to 2022+ via `VR.a_rows_2022()` (the combined window).
        Full-stream canary: n=583, PF=1.3606000676571652.
  VPC = the 1M-TRUTH stream from `tools_vpc_1m_truth.py`: `VT.build_new_vpc_rows(df1m)` where
        `df1m = VT.vpc_1m_truth_trades(feats, d1rth)` (feats/d1rth built exactly as
        `tools_vpc_1m_truth.main()` does). Canary: n=408, PF(points)=1.318, net=+5319.67pt.

COMBINED MACHINERY (pinned): `VR.ASR.build_events` (budget/cap sizing, MAX_A_QTY=40 ceiling
unchanged) + `VR.ASR.day_rows(ev, 550, 1000)` (STOP_PINNED=550, DLL_PINNED=1000) + `VR.ASR.eval_run`
(via `VR.run_cell`, which returns (starts, results)). `eligible_starts` = unique trading days with
>30d runway (EXPIRE_DAYS=30), exactly as `VR.eligible_starts`/`VR.run_cell` already implement.
`funded_per_slot_year = (365.25/mean_days_all) * (pass_count/eligible_starts)` (same formula as
`VR.summarize_cell`, recomputed locally here so `mean_days_all` — not exposed by
`VR.summarize_cell` — is available for the fee-drag/attempts-per-slot-yr columns below).
`E$ = pass% * 8000 - 131` (PLACEHOLDER, pinned verbatim from the task spec).
`attempts_per_slot_yr = 365.25/mean_days_all`; `fee_drag_$ = 131 * attempts_per_slot_yr`.

TZ NOTE: VPC 1m-truth row timestamps come back tz-naive (America/New_York wall-clock, no tzinfo
attached by `VT.build_new_vpc_rows`); the honest-A stream's timestamps are tz-aware
(America/New_York). Localized once, at `kept_trades()` construction time (mirrors the
tz-normalization `VT.headline_funnel()` already performs at merge time) rather than per-cell in the
hot loop.

PERFORMANCE / PRECOMPUTE: sizing (contract count `q`) depends only on `(risk_usd, budget, cap)` —
never on `R`/`mae_r` — so the KEPT-TRADE SET and each trade's `q` are damage-invariant. Per the task
spec, both lanes' "build_events" are precomputed ONCE per (budget, cap) pair (9x8=72 A variants +
9x6=54 VPC variants: `kept_trades()` below), storing `(ts, R, mae_r, risk_usd, q)` for every kept
trade. Every grid cell (a 72x54=3,888-cell cross of those two precomputed lists) and every damage
probe (`dmg_slip`-style: `R -> R-s`, `mae_r -> mae_r-s`, applied at read time, not re-filtered) is
then just a cheap merge+sort+day_rows+run_cell call over pre-filtered lists — no repeated
build_events() scanning of the full 583/408-row streams per cell.

DAMAGE (slippage probe): reuses `tools_salvage_stress.dmg_slip(rows, s)` verbatim (uniform R-unit
slippage subtracted from `R` and `mae_r` before day-aggregation) — the same "family (a)
uniform-slippage" measure already used across the salvage-program stress lanes. `s` in {0.015,
0.030, 0.046} per the task spec. Because `q`/kept-set are damage-invariant (see above), applying
damage to the precomputed `(R, mae_r)` values and rebuilding day-level events is exactly equivalent
to calling `dmg_slip()` on the raw rows before `build_events()` (verified structurally, not by new
modeling choice).

CLASSIFICATION (mechanical, per task spec, applied in this priority order — RED overrides GREEN
overrides YELLOW; any cell matching none of the three explicit rules is RED by exhaustive
default, since GREEN/YELLOW are both "this cell is good" claims and RED is the residual "not good
enough" bucket — a plain three-way partition, not a new modeling judgment):
  1. RED    if bust_pct >= pass_pct, OR bust_pct > 25, OR fails the 0.015R probe (pass<=bust there).
  2. GREEN  elif pass_pct >= 30 AND bust_pct <= 20 AND survives the 0.046R probe.
  3. YELLOW elif pass_pct > 28.7 (baseline) AND (bust_pct in (20,25] OR survives 0.030R but not
            0.046R ("only" as far as 0.030R)).
  4. RED    otherwise (residual/default).
HARD-REJECT flag (separate boolean column, additive to the above): pass_pct > 28.7 (baseline) AND
pass_count < 196 (baseline pass_count) AND funded_per_slot_year < 4.0 — the denominator-artifact
signature flagged per DEC-20260706-1108 (pass% rises while the underlying pass COUNT falls, i.e. a
shrinking-eligible-starts artifact, not a real edge improvement).

FIREWALL: sha256 of `tools_salvage_stress.FIREWALL_FILES` (config_eval_locked.py,
config_funded_locked.py, config_defaults.py, auto_safety.py) taken before load and again right
before the grid report is written. Any mismatch -> STOP, no 02_ report written (01_ baseline report
is still written with the mismatch noted, since it captures the firewall state at that point).

BASELINE-REPRODUCTION STOP RULE (task-mandated): if computed (a)/(b)/(c) pass/bust/exp/n miss the
pinned reference by more than 0.3pp (percentages) or at all (n, an exact integer), the script
STOPS before running the 3,888-cell grid (02_sizing_grid.* is not written) — trust nothing
downstream of an unreproduced baseline.

Outputs (new, this run only):
  reports/a_vpc_portfolio_optimisation/01_baseline_reproduction.md / .json
  reports/a_vpc_portfolio_optimisation/02_sizing_grid.csv / .md

No commentary/winner-picking beyond the mechanical classification flags explicitly requested by
the task spec.
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

import tools_salvage_vpc_reeval as VR      # VPC/A machinery, ASR, event_pf/PF_FLAGS, run_cell
import tools_vpc_1m_truth as VT            # 1m-truth VPC re-walk (load_1m_rth, vpc_1m_truth_trades,
                                            # build_new_vpc_rows)
import tools_salvage_stress as ST          # FIREWALL_FILES, sha_of, dmg_slip

NY = "America/New_York"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "reports", "a_vpc_portfolio_optimisation")
FIREWALL_FILES = ST.FIREWALL_FILES

# ---- pinned reference figures (STOP-gated, tolerance 0.3pp on percentages / exact on n) ----
A_FULL_N, A_FULL_PF = 583, 1.3606000676571652
VPC_1MT_N, VPC_1MT_PF_PTS, VPC_1MT_NET_PTS = 408, 1.318, 5319.67

REF_A_SOLO = dict(pass_pct=9.1, bust_pct=3.5, exp_pct=87.5, n=463, funded_per_slot_year=1.14)
REF_VPC_SOLO = dict(pass_pct=10.8, bust_pct=3.1, exp_pct=86.1, n=388, funded_per_slot_year=1.39)
REF_COMBINED = dict(pass_pct=28.7, bust_pct=17.0, exp_pct=54.4, n=684, funded_per_slot_year=4.22)
BASELINE_PASS_COUNT = 196          # combined baseline's pass_count (28.7% of n=684, rounds to 196)
TOL_PP = 0.3

DAMAGE_GRID = [0.015, 0.030, 0.046]
STOP_PINNED, DLL_PINNED = VR.STOP_PINNED, VR.DLL_PINNED
SPEC50 = VR.SPEC50
MAX_A_QTY = VR.ASR.MAX_A_QTY               # 40, unchanged research ceiling

A_BUDGETS = [250, 300, 400, 500, 600, 700, 800, 900, 1000]
A_CAPS = [2, 3, 4, 5, 6, 7, 8, 10]
V_BUDGETS = [150, 200, 250, 300, 400, 500, 600, 700, 800]
V_CAPS = [1, 2, 3, 4, 5, 6]

FEE_PER_ATTEMPT = 131.0                     # pinned ($131 x attempts-per-slot-yr fee drag)


# ==================================================================================================
# stream loading
# ==================================================================================================
def load_streams():
    print("loading honest-A stream (VR.a_rows_full/a_rows_2022)…", flush=True)
    a_full = VR.a_rows_full()
    a2022 = VR.a_rows_2022(a_full)
    print(f"  A rows n={len(a_full)} full / n={len(a2022)} 2022-2026 window", flush=True)

    print("loading VPC 1m-truth stream (VT.load_1m_rth + vpc_1m_truth_trades + build_new_vpc_rows)…",
          flush=True)
    v, VS = VR.v, VR.VS
    d1rth = VT.load_1m_rth()
    feats = v.features(VS.real_rth_5m())
    feats = feats[feats.date >= VR.WINDOW_START]
    df1m, n_skipped = VT.vpc_1m_truth_trades(feats, d1rth)
    v_rows_new = VT.build_new_vpc_rows(df1m)
    print(f"  VPC 1m-truth rows n={len(v_rows_new)} skipped(no 1m data)={n_skipped}", flush=True)

    return a_full, a2022, v_rows_new, df1m


def stream_canaries(a_full, v_rows_new):
    """Verify the two canonical streams before trusting anything downstream. Returns bool."""
    print("=" * 100)
    print("STREAM CANARIES")
    print("=" * 100)
    ok = True

    gp = sum(r["R"] for r in a_full if r["R"] > 0)
    gl = -sum(r["R"] for r in a_full if r["R"] < 0)
    pf_a = gp / gl if gl else float("nan")
    c1 = (len(a_full) == A_FULL_N) and abs(pf_a - A_FULL_PF) < 1e-6
    print(f"1. A full-stream: n={len(a_full)} (expect {A_FULL_N}), PF={pf_a:.10f} "
          f"(expect {A_FULL_PF:.10f})  -> {'PASS' if c1 else 'FAIL'}")
    ok &= c1

    gpv = sum(1 for _ in v_rows_new)
    pts = [r["R"] * (r["risk_usd"] / VR.DPP) for r in v_rows_new]     # R * stop_pts = pnl_pts
    gp2 = sum(p for p in pts if p > 0)
    gl2 = -sum(p for p in pts if p < 0)
    pf_v_pts = gp2 / gl2 if gl2 else float("nan")
    net_pts = sum(pts)
    c2 = (gpv == VPC_1MT_N and abs(pf_v_pts - VPC_1MT_PF_PTS) < 5e-4 and abs(net_pts - VPC_1MT_NET_PTS) < 0.5)
    print(f"2. VPC 1m-truth stream: n={gpv} (expect {VPC_1MT_N}), PF(pts)={pf_v_pts:.4f} "
          f"(expect {VPC_1MT_PF_PTS}), net={net_pts:.2f}pt (expect {VPC_1MT_NET_PTS})  "
          f"-> {'PASS' if c2 else 'FAIL'}")
    ok &= c2

    print("=" * 100)
    print(f"STREAM CANARY GATE: {'PASS' if ok else 'FAIL — STOP, do not trust anything downstream'}")
    print("=" * 100)
    return ok


# ==================================================================================================
# baseline reproduction (a)/(b)/(c)/(d)
# ==================================================================================================
def _combo_events(ev_a, ev_v):
    """Merge two prebuilt event lists (dicts with ts/pnl/mae), normalizing tz (A aware, VPC may be
    naive) exactly as `VT.headline_funnel()` already does at merge time."""
    ev = list(ev_a) + list(ev_v)
    for e in ev:
        if getattr(e["ts"], "tzinfo", None) is None:
            e["ts"] = e["ts"].tz_localize(NY)
    ev.sort(key=lambda e: e["ts"])
    return ev


def _cell_stats(days, spec=SPEC50):
    """Full per-cell stats, including `mean_days_all` (needed for fee-drag/attempts-per-slot-yr,
    not exposed by `VR.summarize_cell`). Same formulas as `VR.summarize_cell`, recomputed locally
    so the extra field is available without touching `tools_salvage_vpc_reeval.py`."""
    starts, results = VR.run_cell(days, spec)
    n = len(results)
    if n == 0:
        return dict(eligible_starts=0, pass_count=0, bust_count=0, exp_count=0, pass_pct=None,
                    bust_pct=None, exp_pct=None, med_days_pass=None, mean_days_all=None,
                    funded_per_slot_year=None, worst_day_usd=None)
    pass_n = sum(1 for r in results if r[0] == "PASS")
    bust_n = sum(1 for r in results if r[0] == "BUST")
    exp_n = sum(1 for r in results if r[0] == "EXPIRE")
    med_days_pass = int(np.median([r[1] for r in results if r[0] == "PASS"])) if pass_n else None
    mean_days_all = float(np.mean([r[1] for r in results]))
    funded_per_slot_year = (365.25 / mean_days_all) * (pass_n / n) if mean_days_all > 0 else 0.0
    worst_day_usd = min(real for _, real, _ in days) if days else None
    return dict(eligible_starts=n, pass_count=pass_n, bust_count=bust_n, exp_count=exp_n,
                pass_pct=round(100 * pass_n / n, 1), bust_pct=round(100 * bust_n / n, 1),
                exp_pct=round(100 * exp_n / n, 1), med_days_pass=med_days_pass,
                mean_days_all=round(mean_days_all, 3),
                funded_per_slot_year=round(funded_per_slot_year, 2),
                worst_day_usd=round(worst_day_usd, 0) if worst_day_usd is not None else None)


def _within_tol(got, ref, tol=TOL_PP):
    return all(abs(got[k] - ref[k]) <= tol for k in ("pass_pct", "bust_pct", "exp_pct")) and got["eligible_starts"] == ref["n"]


def baseline_reproduction(a2022, v_rows_new):
    print("\n" + "=" * 100)
    print("01 -- BASELINE REPRODUCTION")
    print("=" * 100)

    # (a) A solo 600/6, 2022+ window
    ev_a = VR.ASR.build_events(a2022, 600, 6)
    days_a = VR.ASR.day_rows(ev_a, STOP_PINNED, DLL_PINNED)
    s_a = _cell_stats(days_a)
    print(f"(a) A solo 600/6 (2022+): {s_a}")

    # (b) VPC solo 600/4, 1m-truth stream
    ev_v = VR.ASR.build_events(v_rows_new, 600, 4)
    days_v = VR.ASR.day_rows(ev_v, STOP_PINNED, DLL_PINNED)
    s_v = _cell_stats(days_v)
    print(f"(b) VPC solo 600/4 (1m truth): {s_v}")

    # (c) A600/6 + VPC600/4 combined
    ev_p = _combo_events(ev_a, ev_v)
    days_p = VR.ASR.day_rows(ev_p, STOP_PINNED, DLL_PINNED)
    s_c = _cell_stats(days_p)
    print(f"(c) A600/6 + VPC600/4 combined: {s_c}")

    match_a = _within_tol(s_a, REF_A_SOLO)
    match_v = _within_tol(s_v, REF_VPC_SOLO)
    match_c = _within_tol(s_c, REF_COMBINED)
    print(f"\n(a) match={match_a} (ref {REF_A_SOLO})")
    print(f"(b) match={match_v} (ref {REF_VPC_SOLO})")
    print(f"(c) match={match_c} (ref {REF_COMBINED})")

    # (d) 3-point slippage probe of the (c) baseline
    probe_rows = []
    for s in DAMAGE_GRID:
        a_d = ST.dmg_slip(a2022, s)
        v_d = ST.dmg_slip(v_rows_new, s)
        ev_ad = VR.ASR.build_events(a_d, 600, 6)
        ev_vd = VR.ASR.build_events(v_d, 600, 4)
        ev_pd = _combo_events(ev_ad, ev_vd)
        days_pd = VR.ASR.day_rows(ev_pd, STOP_PINNED, DLL_PINNED)
        s_pd = _cell_stats(days_pd)
        pass_gt_bust = (s_pd["pass_pct"] is not None and s_pd["bust_pct"] is not None
                        and s_pd["pass_pct"] > s_pd["bust_pct"])
        probe_rows.append(dict(damage=s, pass_pct=s_pd["pass_pct"], bust_pct=s_pd["bust_pct"],
                               exp_pct=s_pd["exp_pct"], pass_gt_bust=pass_gt_bust))
        print(f"(d) damage={s}R: pass={s_pd['pass_pct']} bust={s_pd['bust_pct']} "
              f"exp={s_pd['exp_pct']} pass>bust={pass_gt_bust}")
    d_ok = all(r["pass_gt_bust"] for r in probe_rows)

    overall_ok = match_a and match_v and match_c and d_ok
    print(f"\nBASELINE REPRODUCTION VERDICT: {'MATCH — proceeding to grid' if overall_ok else 'MISMATCH — STOP'}")
    return dict(a=s_a, b=s_v, c=s_c, match_a=match_a, match_v=match_v, match_c=match_c,
               d_probes=probe_rows, d_ok=d_ok, overall_ok=overall_ok)


def write_01(baseline, firewall_before, firewall_after, runtime_s):
    os.makedirs(OUTDIR, exist_ok=True)
    json_path = os.path.join(OUTDIR, "01_baseline_reproduction.json")
    md_path = os.path.join(OUTDIR, "01_baseline_reproduction.md")

    with open(json_path, "w") as f:
        json.dump(dict(baseline=baseline, firewall_before=firewall_before,
                       firewall_after=firewall_after, runtime_s=round(runtime_s, 1)), f, indent=1,
                 default=str)

    lines = ["# 01 -- Baseline Reproduction (A+VPC Optimisation, Lane 1)", "",
             "RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing.", "",
             "## (a) A solo 600/6 (2022+ window)",
             f"- computed: {baseline['a']}",
             f"- reference: {REF_A_SOLO}",
             f"- match (tolerance {TOL_PP}pp): **{baseline['match_a']}**", "",
             "## (b) VPC solo 600/4 (1m-truth stream)",
             f"- computed: {baseline['b']}",
             f"- reference: {REF_VPC_SOLO}",
             f"- match (tolerance {TOL_PP}pp): **{baseline['match_v']}**", "",
             "## (c) A600/6 + VPC600/4 combined",
             f"- computed: {baseline['c']}",
             f"- reference: {REF_COMBINED}",
             f"- match (tolerance {TOL_PP}pp): **{baseline['match_c']}**", "",
             "## (d) 3-point slippage probe of the (c) baseline (0.015/0.030/0.046R)", "",
             "| damage(R) | pass% | bust% | exp% | pass>bust |",
             "| --- | --- | --- | --- | --- |"]
    for r in baseline["d_probes"]:
        lines.append(f"| {r['damage']} | {r['pass_pct']} | {r['bust_pct']} | {r['exp_pct']} | {r['pass_gt_bust']} |")
    lines += ["", f"pass>bust at all three probe points: **{baseline['d_ok']}**", "",
             "## Overall verdict",
             f"**{'MATCH — proceeding to 02_sizing_grid' if baseline['overall_ok'] else 'MISMATCH — STOPPED, 02_sizing_grid NOT run'}**",
             "", "## Firewall before/after",
             f"- before: `{firewall_before}`", f"- after: `{firewall_after}`",
             f"- match: **{firewall_before == firewall_after}**", "",
             f"Runtime: {runtime_s:.1f}s"]
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[saved] {json_path}\n[saved] {md_path}")


# ==================================================================================================
# 02 -- full two-lane sizing grid
# ==================================================================================================
def kept_trades(rows, budget, cap, max_qty=MAX_A_QTY):
    """Precompute, ONCE per (budget, cap), the kept-trade set with each trade's contract count `q`
    (damage-invariant: q depends only on risk_usd/budget/cap, never R/mae_r). tz-localized to NY
    here (once), matching `VT.headline_funnel()`'s merge-time tz-normalization."""
    out = []
    for t in rows:
        risk1 = t["risk_usd"]
        q = min(cap, max_qty, int(budget // risk1))
        if q < 1:
            continue
        ts = pd.Timestamp(t["ts"])
        if ts.tzinfo is None:
            ts = ts.tz_localize(NY)
        out.append(dict(ts=ts, R=t["R"], mae_r=t["mae_r"], risk_usd=risk1, q=q))
    out.sort(key=lambda r: r["ts"])
    return out


def damaged_events(kept, damage):
    """kept -> event dicts (ts, pnl, mae) at a given uniform R-unit slippage damage level.
    damage=0.0 == undamaged."""
    ev = []
    for r in kept:
        R = r["R"] - damage
        mae_r = min(0.0, r["mae_r"] - damage)
        risk1, q = r["risk_usd"], r["q"]
        ev.append(dict(ts=r["ts"], pnl=R * risk1 * q, mae=mae_r * risk1 * q))
    return ev


def precompute_lane(rows, budgets, caps, tag):
    lane = {}
    for b in budgets:
        for c in caps:
            lane[(b, c)] = kept_trades(rows, b, c)
    n_kept = [len(v) for v in lane.values()]
    print(f"  {tag} lane precomputed: {len(lane)} (budget,cap) variants, "
          f"kept-trade count range {min(n_kept)}-{max(n_kept)}", flush=True)
    return lane


def build_grid(a2022, v_rows_new):
    print("\n" + "=" * 100)
    print("02 -- FULL TWO-LANE SIZING GRID")
    print("=" * 100)
    t0 = time.time()

    a_lane = precompute_lane(a2022, A_BUDGETS, A_CAPS, "A")
    v_lane = precompute_lane(v_rows_new, V_BUDGETS, V_CAPS, "VPC")

    records = []
    n_cells = len(A_BUDGETS) * len(A_CAPS) * len(V_BUDGETS) * len(V_CAPS)
    done = 0
    log_every = max(1, n_cells // 20)

    for ab in A_BUDGETS:
        for ac in A_CAPS:
            a_kept = a_lane[(ab, ac)]
            n_a = len(a_kept)
            sum_qa = sum(r["q"] for r in a_kept)
            sum_riska = sum(r["risk_usd"] for r in a_kept)
            ev_a0 = damaged_events(a_kept, 0.0)
            ts_a = [r["ts"] for r in a_kept]
            wk_a = max((max(ts_a) - min(ts_a)).days / 7.0, 1.0) if ts_a else 1.0

            for vb in V_BUDGETS:
                for vc in V_CAPS:
                    v_kept = v_lane[(vb, vc)]
                    n_v = len(v_kept)
                    sum_qv = sum(r["q"] for r in v_kept)
                    sum_riskv = sum(r["risk_usd"] for r in v_kept)
                    ev_v0 = damaged_events(v_kept, 0.0)
                    ts_v = [r["ts"] for r in v_kept]
                    wk_v = max((max(ts_v) - min(ts_v)).days / 7.0, 1.0) if ts_v else 1.0

                    # ---- undamaged (base) cell: full stats ----
                    ev0 = list(ev_a0) + list(ev_v0)
                    ev0.sort(key=lambda e: e["ts"])
                    pf0 = VR.event_pf(ev0, f"grid A@{ab}/{ac}+VPC@{vb}/{vc}")
                    days0 = VR.ASR.day_rows(ev0, STOP_PINNED, DLL_PINNED)
                    s0 = _cell_stats(days0)

                    n_tot = n_a + n_v
                    all_ts = ts_a + ts_v
                    wk_tot = max((max(all_ts) - min(all_ts)).days / 7.0, 1.0) if all_ts else 1.0
                    trades_wk_total = round(n_tot / wk_tot, 2)
                    trades_wk_a = round(n_a / wk_a, 2)
                    trades_wk_v = round(n_v / wk_v, 2)
                    mean_days_all = s0["mean_days_all"]
                    trades_per_eval = (round(trades_wk_total * mean_days_all / 7.0, 2)
                                      if mean_days_all else None)
                    attempts_per_slot_yr = (round(365.25 / mean_days_all, 3) if mean_days_all else None)
                    fee_drag = (round(FEE_PER_ATTEMPT * attempts_per_slot_yr, 1)
                               if attempts_per_slot_yr else None)
                    e_dollar = (round((s0["pass_pct"] / 100.0) * 8000.0 - FEE_PER_ATTEMPT, 1)
                               if s0["pass_pct"] is not None else None)
                    mean_contracts = round((sum_qa + sum_qv) / n_tot, 3) if n_tot else None
                    mean_risk_usd = round((sum_riska + sum_riskv) / n_tot, 2) if n_tot else None

                    # ---- coarse slippage probe (pass>bust boolean at 3 damage points) ----
                    probes = {}
                    for s in DAMAGE_GRID:
                        evs = damaged_events(a_kept, s) + damaged_events(v_kept, s)
                        evs.sort(key=lambda e: e["ts"])
                        days_s = VR.ASR.day_rows(evs, STOP_PINNED, DLL_PINNED)
                        stats_s = _cell_stats(days_s)
                        probes[s] = (stats_s["pass_pct"] is not None and stats_s["bust_pct"] is not None
                                    and stats_s["pass_pct"] > stats_s["bust_pct"])

                    survives_015 = probes[0.015]
                    survives_030 = probes[0.030]
                    survives_046 = probes[0.046]

                    # ---- classification (mechanical, priority RED > GREEN > YELLOW > RED-default;
                    # see module docstring) ----
                    pass_pct, bust_pct = s0["pass_pct"], s0["bust_pct"]
                    if pass_pct is None or bust_pct is None:
                        classification = "RED"
                    elif bust_pct >= pass_pct or bust_pct > 25.0 or not survives_015:
                        classification = "RED"
                    elif pass_pct >= 30.0 and bust_pct <= 20.0 and survives_046:
                        classification = "GREEN"
                    elif pass_pct > 28.7 and (20.0 < bust_pct <= 25.0 or (survives_030 and not survives_046)):
                        classification = "YELLOW"
                    else:
                        classification = "RED"

                    hard_reject = bool(pass_pct is not None and pass_pct > 28.7
                                      and s0["pass_count"] < BASELINE_PASS_COUNT
                                      and s0["funded_per_slot_year"] is not None
                                      and s0["funded_per_slot_year"] < 4.0)

                    rec = dict(a_budget=ab, a_cap=ac, v_budget=vb, v_cap=vc,
                              pf_dollar=round(pf0, 3) if pf0 == pf0 else None,
                              eligible_starts=s0["eligible_starts"], pass_count=s0["pass_count"],
                              bust_count=s0["bust_count"], exp_count=s0["exp_count"],
                              pass_pct=pass_pct, bust_pct=bust_pct, exp_pct=s0["exp_pct"],
                              med_days_pass=s0["med_days_pass"], mean_days_all=mean_days_all,
                              worst_day_usd=s0["worst_day_usd"],
                              funded_per_slot_year=s0["funded_per_slot_year"],
                              trades_wk_total=trades_wk_total, trades_wk_a=trades_wk_a,
                              trades_wk_v=trades_wk_v, trades_per_eval=trades_per_eval,
                              e_dollar=e_dollar, attempts_per_slot_yr=attempts_per_slot_yr,
                              fee_drag_usd=fee_drag, mean_risk_usd=mean_risk_usd,
                              mean_contracts=mean_contracts,
                              probe_015_pass_gt_bust=survives_015, probe_030_pass_gt_bust=survives_030,
                              probe_046_pass_gt_bust=survives_046,
                              classification=classification, hard_reject_flag=hard_reject,
                              is_baseline=(ab == 600 and ac == 6 and vb == 600 and vc == 4))
                    records.append(rec)
                    done += 1
                    if done % log_every == 0:
                        print(f"  {done}/{n_cells} cells done ({100*done/n_cells:.0f}%), "
                              f"elapsed {time.time()-t0:.1f}s", flush=True)

    # dl/tl freq + same-day joint-loss count: unit-level, computed ONCE (cap/budget-invariant to
    # first order per `VR.same_day_stats`'s own docstring), attached to every row as a constant.
    # v_rows_new's ts are tz-naive (VT.build_new_vpc_rows does not attach tzinfo) while a2022's are
    # tz-aware NY; localize a throwaway copy here (same normalization `_combo_events`/`kept_trades`
    # already apply elsewhere) so VR.same_day_stats/VR.unit_daily's own day-key set/sort don't choke
    # on mixed tz-aware/naive Timestamps.
    v_rows_ny = [dict(r, ts=(pd.Timestamp(r["ts"]).tz_localize(NY) if pd.Timestamp(r["ts"]).tzinfo is None
                            else pd.Timestamp(r["ts"]))) for r in v_rows_new]
    refstats = VR.same_day_stats(a2022, v_rows_ny)
    da = VR.unit_daily(a2022); dv = VR.unit_daily(v_rows_ny)
    all_days = sorted(set(da) | set(dv))
    xa = np.array([da.get(d, 0.0) for d in all_days])
    xv = np.array([dv.get(d, 0.0) for d in all_days])
    joint_loss_count = int(np.sum((xa < 0) & (xv < 0)))
    for rec in records:
        rec["same_day_corr"] = refstats["same_day_corr"]
        rec["dl_freq_pct"] = refstats["dl_freq_pct"]
        rec["tl_freq_pct"] = refstats["tl_freq_pct"]
        rec["same_day_joint_loss_count"] = joint_loss_count

    runtime_s = time.time() - t0
    print(f"\nGrid runtime: {runtime_s:.1f}s ({n_cells} cells)")
    return pd.DataFrame.from_records(records), runtime_s


def write_02(df, runtime_s):
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, "02_sizing_grid.csv")
    md_path = os.path.join(OUTDIR, "02_sizing_grid.md")
    df.to_csv(csv_path, index=False)

    green = df[df["classification"] == "GREEN"]
    yellow = df[df["classification"] == "YELLOW"]
    red = df[df["classification"] == "RED"]
    mirage = df[df["hard_reject_flag"]]

    top30_green_pass = green.sort_values("pass_pct", ascending=False).head(30)
    gy = pd.concat([green, yellow])
    top30_gy_funded = gy.sort_values("funded_per_slot_year", ascending=False).head(30)

    baseline_row = df[df["is_baseline"]]
    baseline_rank_pass = None
    if len(baseline_row):
        sorted_by_pass = df.sort_values("pass_pct", ascending=False).reset_index(drop=True)
        baseline_rank_pass = int(sorted_by_pass[sorted_by_pass["is_baseline"]].index[0]) + 1

    lines = ["# 02 -- Full Two-Lane Sizing Grid (A+VPC Optimisation, Lane 1)", "",
             "RESEARCH ONLY. LIVE HOLD ACTIVE. No commentary beyond mechanical classification.", "",
             f"Grid: {df.shape[0]} cells. Runtime: {runtime_s:.1f}s.", "",
             f"GREEN={len(green)}  YELLOW={len(yellow)}  RED={len(red)}  HARD-REJECT-flagged={len(mirage)}",
             "", f"Baseline row (A@600/6+VPC@600/4) rank by pass_pct: **{baseline_rank_pass}** of {len(df)}",
             "", "## Baseline row", VR.df_to_md_table(baseline_row), "",
             "## Top-30 GREEN by pass_pct", VR.df_to_md_table(top30_green_pass), "",
             "## Top-30 GREEN+YELLOW by funded_per_slot_year", VR.df_to_md_table(top30_gy_funded), "",
             f"## Counts: RED={len(red)}  HARD-REJECT-flagged={len(mirage)}"]
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[saved] {csv_path}\n[saved] {md_path}")
    return dict(green=len(green), yellow=len(yellow), red=len(red), mirage=len(mirage),
               baseline_rank_pass=baseline_rank_pass, top10_green_pass=top30_green_pass.head(10))


# ==================================================================================================
def main():
    t_start = time.time()
    firewall_before = ST.sha_of(FIREWALL_FILES)
    print(f"firewall before: {firewall_before}")

    a_full, a2022, v_rows_new, df1m = load_streams()

    if not stream_canaries(a_full, v_rows_new):
        print("[ABORT] stream canary mismatch -- no report written.")
        return

    baseline = baseline_reproduction(a2022, v_rows_new)
    firewall_mid = ST.sha_of(FIREWALL_FILES)
    write_01(baseline, firewall_before, firewall_mid, time.time() - t_start)

    if not baseline["overall_ok"]:
        print("\n[STOP] baseline reproduction MISMATCH -- 02_sizing_grid NOT run per task spec.")
        return

    df, grid_runtime_s = build_grid(a2022, v_rows_new)

    firewall_after = ST.sha_of(FIREWALL_FILES)
    if firewall_after != firewall_before:
        print("\n[STOP] FIREWALL MISMATCH after grid computation -- 02_sizing_grid NOT written.")
        print(f"  before: {firewall_before}")
        print(f"  after:  {firewall_after}")
        return

    summary = write_02(df, grid_runtime_s)
    total_runtime = time.time() - t_start
    print(f"\nTOTAL RUNTIME: {total_runtime:.1f}s")
    print(f"GREEN={summary['green']} YELLOW={summary['yellow']} RED={summary['red']} "
          f"HARD-REJECT-flagged={summary['mirage']}")
    print(f"baseline rank by pass_pct: {summary['baseline_rank_pass']} of {len(df)}")
    print("\ntop-10 GREEN by pass_pct:")
    cols = ["a_budget", "a_cap", "v_budget", "v_cap", "pass_pct", "bust_pct", "exp_pct",
           "funded_per_slot_year", "eligible_starts", "pass_count"]
    print(summary["top10_green_pass"][cols].to_string(index=False))
    print(f"\nfirewall before: {firewall_before}")
    print(f"firewall after:  {firewall_after}")
    print(f"firewall match: {firewall_before == firewall_after}")


if __name__ == "__main__":
    main()
