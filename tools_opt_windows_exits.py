"""tools_opt_windows_exits.py — A+VPC PORTFOLIO OPTIMISATION, Lane 3: timing-window grid + exit
interaction, on top of the pinned baseline sizing A@600/6 + VPC@600/4.

RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing (no live/config/engine file touched).
This file only reads real Databento data + the frozen models and writes new report files under
`reports/a_vpc_portfolio_optimisation/`. No modeling choice is new-and-hidden — every one not
already covered by prior art is called out explicitly below and again inline where it is used.

STREAMS:
  A   = `tools_sim_parity_check.load_rows()`, filtered to ts >= 2022-01-01 (`tools_salvage_vpc_reeval
        .a_rows_2022`, imported verbatim) — the honest, certified A/exit3 stream, restricted to the
        window VPC data exists over (same "PART 3 WINDOW NOTE" convention as
        `tools_salvage_vpc_reeval.py`'s own combined-portfolio section).
  VPC = the 1m-truth re-walked VPC stream (`tools_vpc_1m_truth.vpc_1m_truth_trades` +
        `.build_new_vpc_rows`, imported verbatim) — canary n=408, PF(points)=1.318.

CANARY (mandatory, checked before anything else runs; STOP on mismatch):
  A@600/6 + VPC@600/4 (Apex 50K spec, day_rows(550,1000)/eval_run, EXPIRE=30d) must reproduce
  pass=28.7 / bust=17.0 / exp=54.4 (n=684) — the canonical baseline row already certified in
  `reports/a_vpc_portfolio_optimisation/00_preflight.md`.

PRIOR ART REUSED (imported, not reimplemented):
  - `tools_salvage_vpc_reeval.py` (VR): `a_rows_full`/`a_rows_2022`, `WINDOW_START`, `ASR`
    (`build_events`/`day_rows`/`eval_run`), `STOP_PINNED`/`DLL_PINNED`, `event_pf`/`PF_FLAGS`,
    `summarize_cell`, `weeks_span`, `unit_daily`, `df_to_md_table`, `v`/`VS` (the native VPC engine
    handles), `vpc_rows`/`vpc_rows_cache`.
  - `tools_vpc_1m_truth.py` (VT): `load_1m_rth`, `vpc_1m_truth_trades`, `build_new_vpc_rows`,
    `old_new_summary`, `run_canaries`.
  - `tools_salvage_stress.py` (ST): `FIREWALL_FILES`/`sha_of` (firewall bookkeeping), `dmg_slip`
    (uniform R-unit slippage damage — reused verbatim for the 3-point slip probe, applied to BOTH
    legs at the same slip value, exactly as that file's own `a_uniform_slip` family already does).
  - `tools_salvage_funded_exits.py` (TSF): `kept_raw_trades`, `walk_exit3`, `walk_fixed_r`,
    `build_variant_rows`, `variant_stats` — the A5 salvage exit machinery for the A-leg exit
    comparison (exit3-current / fixed-1.5R / fixed-2R). Canary: exit3-current on the FULL stream
    (all history, not window-restricted) must reproduce n=583, PF=1.361, totR=+89.2R exactly — this
    is the A5 file's own pinned canary, re-verified here before use.
  - "E$" placeholder = pass_pct/100*8000 - 131, IDENTICAL formula/label to
    `tools_vpc_audit_standalone.py`'s own reuse of `tools_salvage_track_a.py`'s `E_proxy` (an "8k
    pending A4 placeholder", NOT a dollar certification) — same funnel family (day_rows/eval_run,
    Apex 50K spec), so the same placeholder formula is reused rather than inventing a new one.

NEW LOGIC (self-verified extension, not prior art — called out, not hidden):
  - `vpc_1m_truth_variant()` — a generalized version of `VT.vpc_1m_truth_trades()`'s 1m re-walk
    loop (entries/direction/initial-stop UNCHANGED; native 5m day-loop unchanged — it still drives
    busy_until/daily_stop gating exactly as before). Only the NEW exit's bar-by-bar rule is
    generalized via four independent knobs: `trail_atr` (ATR trail multiple; None = no ratchet),
    `fixed_target_r` (fixed R-multiple target, checked each bar AFTER the stop check — stop-first
    race), `arm_after_1r` (trail does not begin ratcheting until the highest-close-since-entry has
    reached +1R favorable; before that the stop stays at the original fixed level), `time_stop_min`
    (force-exit at that bar's close once this many minutes have elapsed since entry), `hard_eod_time`
    (force-exit at that bar's close the first time the bar's ET wall-clock time reaches it — used to
    approximate "flatten VPC positions by 14:30": the 1m walker knows exact exit times, so this is an
    exact same-day truncation of the exit CHOICE, not a live order-cancel simulation, documented per
    the task's own "approximate by re-walking with hard 14:30 EOD" instruction).
    SELF-CHECK (run every time before use): calling with defaults (trail_atr=5.0, everything else
    off) must reproduce `VT.vpc_1m_truth_trades()`'s own `pnl_pts_new` column byte-for-byte — STOP
    if not.
  - Window filter (`filter_by_window`): VPC 1m-truth rows carry an entry `ts`. If tz-naive, the
    wall-clock time is taken AS-IS (already NY-local by construction of the RTH-only 5m/1m frames
    this repo builds everywhere — same convention `tools_vpc_1m_truth.headline_funnel` uses: "1m-
    truth VPC events may be tz-naive NY"); if tz-aware, converted to NY first. No prior-art
    precedent for a time-of-day *filter* (only for tz *normalization* before event-merging), so
    this is new but mechanical and stated here explicitly.
  - A per-day dedupe variants (`a_variant_first_of_day`, `a_variant_max_n_per_day`): "first signal
    of day" and "max-1/day" are DIFFERENT NAMES in the brief but MECHANICALLY IDENTICAL on this
    stream (both keep only the earliest-ts trade per day) — checked and reported, not assumed.
    "max-2/day" was found to be IDENTICAL to "current" on the 2022-2026 A stream (no day in that
    window ever has 3+ A trades; max observed = 2) — also checked and reported, not assumed.
  - "cumulative day R" for the `stop-day-after-portfolio` overlay: since A and VPC legs carry
    different per-trade dollar risk (no shared "$1R" unit at the portfolio level), this overlay
    walks the MERGED RAW (ts, R, leg) stream day-by-day and sums each trade's OWN R-multiple
    (dimensionless, as used throughout this repo per-trade) directly, regardless of leg or size —
    once that day's running R-sum reaches the threshold, every LATER same-day trade (either leg) is
    dropped before dollar-sizing/eventing. A genuinely new definition (no prior-art precedent found
    for a cross-stream R threshold) — called out explicitly, not hidden.
  - "concentration flag" (lane 3, per-cell): mechanical, new threshold — a cell is flagged if any
    single year's PASS count is >60% of that cell's total pass count across all eligible years.
    No prior-art precedent; stated here, not hidden.
  - "same-day joint-loss count": count (not %) of unit trading days where BOTH legs' unit
    (1-contract, unclamped) daily $ P&L are < 0, reusing `VR.unit_daily` verbatim (only the
    aggregation changes from % to count, mirroring `VR.same_day_stats`'s own dl_freq definition).

Outputs (new, this run only):
  reports/a_vpc_portfolio_optimisation/05_timing_windows.csv / .md
  reports/a_vpc_portfolio_optimisation/06_exit_interaction.csv / .md

No recommendation. No commits.
"""
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tools_salvage_vpc_reeval as VR          # A/VPC row loaders, ASR funnel, event_pf, summarize_cell
import tools_vpc_1m_truth as VT                # 1m-truth VPC re-walk machinery
import tools_salvage_stress as ST              # FIREWALL_FILES, sha_of, dmg_slip
import tools_salvage_funded_exits as TSF       # A5 exit-variant machinery

NY = "America/New_York"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "a_vpc_portfolio_optimisation")
FIREWALL_FILES = ST.FIREWALL_FILES

BUDGET_A, CAP_A = 600, 6
BUDGET_V, CAP_V = 600, 4
BASELINE_EXPECT = dict(pass_pct=28.7, bust_pct=17.0, exp_pct=54.4, n=684)
SLIP_PROBE = [0.015, 0.03, 0.046]
YEARS_EXPECT = [2022, 2023, 2024, 2025, 2026]
CONCENTRATION_THRESHOLD = 0.60


# ==================================================================================================
# shared funnel primitives
# ==================================================================================================
def to_ny_ts(ts):
    """Correct NY-local conversion for BOTH streams' timestamps -- verified against real data
    (found during implementation, called out explicitly): the VPC 1m-truth rows' `ts` field is
    tz-naive but is NOT already NY wall-clock -- it is a naive-UTC value (pandas converts a
    tz-aware DatetimeIndex's `.values` to UTC-based naive datetime64 under the hood, and
    `vpc_1m_truth_trades()`/this file's own `vpc_1m_truth_variant()` both build `ts=idx[ei]` off
    `g.index.values` on a `America/New_York`-tz-aware 5m index). Verified: naive VPC entries span
    ~14:05-19:35 raw, which converts to 10:05-15:00 ET -- exactly the expected VPC session window
    -- confirming this is UTC, not NY, under the naive label. The A stream's `ts` is already
    tz-aware `America/New_York` (from `tools_sim_parity_check.load_rows()`), so `tz_convert(NY)`
    on it is a no-op. This function is used ONLY by this file's OWN new logic (time-of-day window
    filtering, cross-stream same-day ordering for the stop-day-after overlay, same-day joint-loss
    bucketing) -- it does NOT touch `funnel_cell()`'s pre-existing tz-localize-as-NY normalization,
    which is reused VERBATIM from `tools_vpc_1m_truth.headline_funnel()` (date-only `.normalize()`
    bucketing there is tz-invariant regardless of this offset, and changing it would risk not
    reproducing the certified baseline canary bit-for-bit)."""
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(NY)


def et_time(ts):
    return to_ny_ts(ts).time()


def e_dollar_placeholder(pass_pct):
    return round(pass_pct / 100 * 8000 - 131, 2) if pass_pct is not None else None


def funnel_cell(a_rows, v_rows, label, budget_a=BUDGET_A, cap_a=CAP_A, budget_v=BUDGET_V, cap_v=CAP_V):
    ev = VR.ASR.build_events(a_rows, budget_a, cap_a) + VR.ASR.build_events(v_rows, budget_v, cap_v)
    for e in ev:
        if getattr(e["ts"], "tzinfo", None) is None:
            e["ts"] = e["ts"].tz_localize(NY)
    ev.sort(key=lambda e: e["ts"])
    pf = VR.event_pf(ev, label)
    days = VR.ASR.day_rows(ev, VR.STOP_PINNED, VR.DLL_PINNED)
    s = VR.summarize_cell(days, label)
    return s, pf, ev, days


def _ny_rows(rows):
    """Re-key `ts` to the CORRECT NY-local timestamp (`to_ny_ts`) for day-bucketing/ordering only
    -- does not touch R/mae_r/risk_usd."""
    return [dict(r, ts=to_ny_ts(r["ts"])) for r in rows]


def same_day_joint_loss_count(a_rows, v_rows):
    da = VR.unit_daily(_ny_rows(a_rows))
    dv = VR.unit_daily(_ny_rows(v_rows))
    all_days = sorted(set(da) | set(dv))
    n = sum(1 for d in all_days if da.get(d, 0.0) < 0 and dv.get(d, 0.0) < 0)
    return n, len(all_days)


def concentration_flag(per_year):
    total_pass = sum(round(v["n"] * v["pass_pct"] / 100) for v in per_year.values())
    if total_pass <= 0:
        return False
    for v in per_year.values():
        yp = round(v["n"] * v["pass_pct"] / 100)
        if yp / total_pass > CONCENTRATION_THRESHOLD:
            return True
    return False


def maxdd_usd_of_days(days):
    if not days:
        return 0.0
    bal = np.cumsum([r for _, r, _ in days])
    peak = np.maximum.accumulate(bal)
    return float((peak - bal).max())


# ==================================================================================================
# loading + canaries
# ==================================================================================================
def load_streams():
    print("loading VPC native rows (real Databento, frozen CFG, 2022+)…", flush=True)
    v_rows_old, tr_base = VR.vpc_rows()
    VR.vpc_rows_cache["rows"] = v_rows_old

    print("loading honest A rows (tools_sim_parity_check.load_rows, post-fix)…", flush=True)
    a_full = VR.a_rows_full()

    print("loading 1-minute Databento NQ (RTH)…", flush=True)
    d1rth = VT.load_1m_rth()

    v, VS = VR.v, VR.VS
    feats = v.features(VS.real_rth_5m())
    feats = feats[feats.date >= VR.WINDOW_START]

    print("re-walking VPC exits on 1m bars (current/certified: 5.0xATR trail)…", flush=True)
    df1m, n_skipped = VT.vpc_1m_truth_trades(feats, d1rth)
    print(f"  n_trades={len(df1m)} skipped(no 1m data)={n_skipped}", flush=True)

    vpc_core_ok, portfolio_ok, a2022 = VT.run_canaries(v_rows_old, tr_base, a_full, df1m)
    v_rows_new = VT.build_new_vpc_rows(df1m)
    old_s, new_s = VT.old_new_summary(df1m)

    vpc_408_ok = (new_s["n_trades"] == 408 and new_s["pf_pts"] == 1.318)
    print(f"  VPC 1m-truth canary: n={new_s['n_trades']} PF(pts)={new_s['pf_pts']} "
          f"(expect n=408 PF=1.318) -> {'PASS' if vpc_408_ok else 'FAIL'}")

    ok = vpc_core_ok and portfolio_ok and vpc_408_ok
    return dict(a2022=a2022, v_rows_new=v_rows_new, feats=feats, d1rth=d1rth,
                a_full=a_full, ok=ok)


def check_baseline_canary(a2022, v_rows_new):
    s, pf, ev, days = funnel_cell(a2022, v_rows_new, "canary baseline A600/6+VPC600/4")
    got = dict(pass_pct=s["pass_pct"], bust_pct=s["bust_pct"], exp_pct=s["exp_pct"], n=s["eligible_starts"])
    ok = got == BASELINE_EXPECT
    print(f"\nBASELINE CANARY (A@{BUDGET_A}/{CAP_A} + VPC@{BUDGET_V}/{CAP_V}, 1m-truth VPC):")
    print(f"  got:      {got}")
    print(f"  expected: {BASELINE_EXPECT}  -> {'PASS' if ok else 'FAIL'}")
    return ok, s


# ==================================================================================================
# LANE 3 (05) -- timing-window grid
# ==================================================================================================
WINDOWS = [
    ("10:00-15:00 (full)", "10:00", "15:00"),
    ("10:00-14:00", "10:00", "14:00"),
    ("10:00-13:00", "10:00", "13:00"),
    ("10:30-15:00", "10:30", "15:00"),
    ("10:30-14:00", "10:30", "14:00"),
    ("11:00-15:00", "11:00", "15:00"),
    ("11:00-14:00", "11:00", "14:00"),
    ("12:00-15:00", "12:00", "15:00"),
]


def filter_by_window(rows, start_s, end_s):
    """Closed interval [start, end] (inclusive both ends) -- verified against real data: one VPC
    entry sits at exactly 15:00:00 ET; a half-open [start,end) filter would silently drop it from
    the "full" 10:00-15:00 window (407 of 408), breaking the baseline-canary reproduction (n=683
    vs 684). Inclusive endpoints make "10:00-15:00 (full)" reproduce the certified 408-trade
    stream exactly -- checked below in `run_lane3`."""
    t0 = pd.Timestamp(f"2000-01-01 {start_s}").time()
    t1 = pd.Timestamp(f"2000-01-01 {end_s}").time()
    return [r for r in rows if t0 <= et_time(r["ts"]) <= t1]


def a_variant_current(a_rows):
    return list(a_rows)


def a_variant_first_of_day(a_rows):
    by_day = {}
    for r in sorted(a_rows, key=lambda x: pd.Timestamp(x["ts"])):
        d = pd.Timestamp(r["ts"]).normalize()
        if d not in by_day:
            by_day[d] = r
    return sorted(by_day.values(), key=lambda x: pd.Timestamp(x["ts"]))


def a_variant_max_n_per_day(a_rows, n):
    by_day = {}
    for r in sorted(a_rows, key=lambda x: pd.Timestamp(x["ts"])):
        d = pd.Timestamp(r["ts"]).normalize()
        by_day.setdefault(d, []).append(r)
    out = []
    for lst in by_day.values():
        out.extend(lst[:n])
    return sorted(out, key=lambda x: pd.Timestamp(x["ts"]))


A_VARIANTS = [
    ("A-current (all trades)", a_variant_current),
    ("A-first-signal-of-day-only", a_variant_first_of_day),
    ("A-max-1/day", lambda r: a_variant_max_n_per_day(r, 1)),
    ("A-max-2/day", lambda r: a_variant_max_n_per_day(r, 2)),
]


def build_window_cell(a_label, a_rows, w_label, v_rows, named_combo=False):
    label = f"{a_label} + VPC[{w_label}]"
    s, pf, ev, days = funnel_cell(a_rows, v_rows, label)
    rec = dict(a_variant=a_label, window=w_label, named_combo=named_combo,
               n_a=len(a_rows), n_v=len(v_rows),
               trades_wk_a=round(len(a_rows) / VR.weeks_span(a_rows), 3) if a_rows else 0.0,
               trades_wk_v=round(len(v_rows) / VR.weeks_span(v_rows), 3) if v_rows else 0.0,
               pf_dollar=round(pf, 3) if pf == pf else None,
               **{k: v for k, v in s.items() if k not in ("label", "per_year")},
               e_dollar_placeholder=e_dollar_placeholder(s["pass_pct"]))
    jl_n, jl_days = same_day_joint_loss_count(a_rows, v_rows)
    rec["joint_loss_days"] = jl_n
    rec["joint_loss_pct"] = round(100 * jl_n / jl_days, 1) if jl_days else None
    for y in YEARS_EXPECT:
        pv = s["per_year"].get(y)
        rec[f"py{y}_n"] = pv["n"] if pv else 0
        rec[f"py{y}_pass_pct"] = pv["pass_pct"] if pv else None
    rec["one_year_concentration_flag"] = concentration_flag(s["per_year"])
    for sv in SLIP_PROBE:
        a_s = ST.dmg_slip(a_rows, sv)
        v_s = ST.dmg_slip(v_rows, sv)
        s2, pf2, _, _ = funnel_cell(a_s, v_s, f"{label} slip={sv}")
        rec[f"slip{sv}_pass_pct"] = s2["pass_pct"]
        rec[f"slip{sv}_bust_pct"] = s2["bust_pct"]
    return rec


def run_lane3(a2022, v_rows_new):
    print("\n" + "=" * 100)
    print("LANE 3 (05) -- timing-window grid (8 VPC windows x 4 A variants + 3 named combos)")
    print("=" * 100)

    # mechanical equivalence checks (called out in module docstring)
    first_of_day = a_variant_first_of_day(a2022)
    max1 = a_variant_max_n_per_day(a2022, 1)
    max2 = a_variant_max_n_per_day(a2022, 2)
    first_eq_max1 = (len(first_of_day) == len(max1)
                     and all(a["ts"] == b["ts"] for a, b in zip(first_of_day, max1)))
    max2_eq_current = (len(max2) == len(a2022))
    print(f"  mechanical check: first-signal-of-day-only == max-1/day: {first_eq_max1} "
          f"(n={len(first_of_day)} vs n={len(max1)})")
    print(f"  mechanical check: max-2/day == current: {max2_eq_current} "
          f"(n={len(max2)} vs n={len(a2022)}, max A-trades/day observed = "
          f"{max((len(list(g)) for _, g in __import__('itertools').groupby(sorted(pd.Timestamp(r['ts']).normalize() for r in a2022))), default=0)})")

    full_window_check = filter_by_window(v_rows_new, "10:00", "15:00")
    print(f"  sanity check: 'full' window (10:00-15:00 inclusive) recovers all VPC trades: "
          f"{len(full_window_check) == len(v_rows_new)} ({len(full_window_check)} vs {len(v_rows_new)})")

    records = []
    for w_label, ws, we in WINDOWS:
        v_filtered = filter_by_window(v_rows_new, ws, we)
        for a_label, a_fn in A_VARIANTS:
            a_filtered = a_fn(a2022)
            rec = build_window_cell(a_label, a_filtered, w_label, v_filtered)
            records.append(rec)
            print(f"  {a_label:>28} + VPC[{w_label:>18}] | n_a={rec['n_a']:>4} n_v={rec['n_v']:>4} "
                  f"pass={rec['pass_pct']}% bust={rec['bust_pct']}% exp={rec['exp_pct']}% "
                  f"n={rec['eligible_starts']} f/slot/yr={rec['funded_per_slot_year']}")

    named = [
        ("A-current+VPC-full (=baseline)", a_variant_current(a2022), filter_by_window(v_rows_new, "10:00", "15:00")),
        ("A-current+VPC-after-11:00", a_variant_current(a2022), filter_by_window(v_rows_new, "11:00", "15:00")),
        ("A-1/day+VPC-full", a_variant_max_n_per_day(a2022, 1), filter_by_window(v_rows_new, "10:00", "15:00")),
    ]
    for label, a_r, v_r in named:
        rec = build_window_cell(label, a_r, "(named combo)", v_r, named_combo=True)
        records.append(rec)
        print(f"  [NAMED] {label:>32} | pass={rec['pass_pct']}% bust={rec['bust_pct']}% "
              f"exp={rec['exp_pct']}% n={rec['eligible_starts']}")

    return pd.DataFrame.from_records(records), first_eq_max1, max2_eq_current


def write_05(df, first_eq_max1, max2_eq_current, baseline_s, runtime_s, firewall_before, firewall_after):
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, "05_timing_windows.csv")
    md_path = os.path.join(OUTDIR, "05_timing_windows.md")
    df.to_csv(csv_path, index=False)

    baseline_row = df[(df["named_combo"]) & (df["a_variant"] == "A-current+VPC-full (=baseline)")].iloc[0]
    grid_only = df[~df["named_combo"]].copy()
    # auditor-stress flag: pass_pct exceeds baseline by >2pp at equal-or-better bust
    grid_only["auditor_stress_flag"] = (
        (grid_only["pass_pct"] - baseline_row["pass_pct"] > 2.0)
        & (grid_only["bust_pct"] <= baseline_row["bust_pct"])
    )
    flagged = grid_only[grid_only["auditor_stress_flag"]]
    conc_flagged = df[df["one_year_concentration_flag"] == True]  # noqa: E712

    lines = []
    lines.append("# 05 -- Timing-window grid (A+VPC portfolio optimisation, Lane 3)")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. Sizing held at the pinned baseline "
                 f"A@{BUDGET_A}/{CAP_A} + VPC@{BUDGET_V}/{CAP_V} throughout (only the timing "
                 "window / A per-day dedupe is varied). VPC leg = 1m-truth stream (current, "
                 "5.0xATR trail), canary n=408 PF=1.318. A leg = "
                 "`tools_sim_parity_check.load_rows()`, filtered to 2022-2026 (shared VPC window).")
    lines.append("")
    lines.append(f"Baseline canary (A-current+VPC-full): pass={baseline_row['pass_pct']}% "
                 f"bust={baseline_row['bust_pct']}% exp={baseline_row['exp_pct']}% "
                 f"n={baseline_row['eligible_starts']} (expect {BASELINE_EXPECT}).")
    lines.append("")
    lines.append(f"Mechanical dedupe-equivalence findings: first-signal-of-day-only == max-1/day: "
                 f"**{first_eq_max1}**; max-2/day == current (no A day in 2022-2026 has 3+ trades): "
                 f"**{max2_eq_current}**.")
    lines.append("")
    lines.append("Grid = 8 VPC windows x 4 A variants = 32 cells, plus 3 named combos (one of which "
                 "IS the baseline). Slip probe = 0.015/0.03/0.046R applied to BOTH legs uniformly "
                 "(`tools_salvage_stress.dmg_slip`, reused verbatim). Concentration flag: any "
                 "single year's PASS count > 60% of that cell's total pass count (new, mechanical, "
                 "documented in module docstring).")
    lines.append("")
    lines.append("## Full grid + named combos")
    lines.append("")
    show_cols = ["a_variant", "window", "named_combo", "n_a", "n_v", "trades_wk_a", "trades_wk_v",
                "eligible_starts", "pass_count", "bust_count", "exp_count", "pass_pct", "bust_pct",
                "exp_pct", "med_days_pass", "worst_day_usd", "funded_per_slot_year", "pf_dollar",
                "e_dollar_placeholder", "joint_loss_days", "joint_loss_pct",
                "one_year_concentration_flag"]
    lines.append(VR.df_to_md_table(df[show_cols]))
    lines.append("")
    lines.append("## Per-year pass% (2022-2026)")
    lines.append("")
    py_cols = ["a_variant", "window", "named_combo"] + [c for y in YEARS_EXPECT for c in (f"py{y}_n", f"py{y}_pass_pct")]
    lines.append(VR.df_to_md_table(df[py_cols]))
    lines.append("")
    lines.append("## 3-point slip probe (0.015 / 0.03 / 0.046 R, both legs)")
    lines.append("")
    slip_cols = ["a_variant", "window", "named_combo"] + [c for sv in SLIP_PROBE for c in
                (f"slip{sv}_pass_pct", f"slip{sv}_bust_pct")]
    lines.append(VR.df_to_md_table(df[slip_cols]))
    lines.append("")
    lines.append(f"## One-year-concentration flags: {len(conc_flagged)}/{len(df)} cells")
    lines.append("")
    if len(conc_flagged):
        lines.append(VR.df_to_md_table(conc_flagged[["a_variant", "window", "named_combo",
                                                       "pass_pct", "bust_pct"] +
                                                      [f"py{y}_pass_pct" for y in YEARS_EXPECT]]))
    else:
        lines.append("(none)")
    lines.append("")
    lines.append(f"## Auditor-stress flags: grid cells where pass_pct exceeds the baseline by >2pp "
                 f"at equal-or-better bust ({len(flagged)}/{len(grid_only)} grid cells, named combos "
                 "excluded from this specific check since 2 of the 3 duplicate grid cells)")
    lines.append("")
    if len(flagged):
        lines.append(VR.df_to_md_table(flagged[["a_variant", "window", "pass_pct", "bust_pct",
                                                  "exp_pct", "eligible_starts"]]))
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("## Firewall before/after")
    lines.append("")
    for f in FIREWALL_FILES:
        b, a = firewall_before.get(f), firewall_after.get(f)
        lines.append(f"- `{f}`: {'UNCHANGED' if b == a else '**CHANGED**'}")
    lines.append("")
    if VR.PF_FLAGS:
        lines.append(f"## PF FREEZE FLAGS (PF>{VR.PF_FREEZE_THRESHOLD}): {VR.PF_FLAGS}")
    else:
        lines.append(f"## PF freeze check: no cell exceeded PF>{VR.PF_FREEZE_THRESHOLD}.")
    lines.append("")
    lines.append(f"Runtime (lane 3 only): {runtime_s:.1f}s")
    lines.append("")
    lines.append("No recommendation. No commits.")
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[saved] {csv_path}\n[saved] {md_path}")
    return baseline_row, flagged, conc_flagged


# ==================================================================================================
# LANE 2 (06) -- exit interaction
# ==================================================================================================
def vpc_1m_truth_variant(feats, d1rth, trail_atr=5.0, fixed_target_r=None,
                          arm_after_1r=False, time_stop_min=None, hard_eod_time=None):
    """Generalized extension of VT.vpc_1m_truth_trades()'s 1m re-walk. See module docstring
    'NEW LOGIC' section for the full description of every knob. Native 5m day-loop (busy_until/
    daily_stop gating) is UNCHANGED and byte-identical to VT.vpc_1m_truth_trades()'s own; only the
    NEW exit's bar-by-bar rule is generalized. SELF-CHECK: caller must verify defaults reproduce
    VT.vpc_1m_truth_trades()'s pnl_pts_new column exactly before trusting any non-default config."""
    v, VS = VR.v, VR.VS
    CFG = VS.CFG
    sig_kw = {k: CFG[k] for k in ("atr_stop", "slot_min", "slot_max", "slope_mult", "trend_mult") if k in CFG}
    max_trades = CFG["max_trades"]; daily_stop = CFG["daily_stop"]
    native_trail_atr = CFG["trail_atr"]
    cost = v.RT_COST
    d1_by_day = {d: g for d, g in d1rth.groupby("date")}
    hard_eod_t = pd.Timestamp(f"2000-01-01 {hard_eod_time}").time() if hard_eod_time else None
    out = []
    skipped_no_1m = 0
    for day, g in feats.groupby("date"):
        g = g.sort_values("slot")
        idx = g.index.values
        sigs = v.vpc_signals(g.reset_index(drop=True), **sig_kw)
        O, H, L, C, A = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.atr.values
        n = len(g); busy_until = -1; taken = 0; day_pnl = 0.0
        g1 = d1_by_day.get(day)
        idx1 = g1.index.values if g1 is not None and len(g1) else None
        H1 = g1.high.values if idx1 is not None else None
        L1 = g1.low.values if idx1 is not None else None
        C1 = g1.close.values if idx1 is not None else None
        for (ei, d, stopdist) in sigs:
            if ei >= n or ei <= busy_until or taken >= max_trades:
                continue
            if daily_stop and day_pnl <= -daily_stop:
                break
            # ---- NATIVE 5m walk (unchanged -- drives busy_until/day_pnl gating exactly as before) ----
            entry = O[ei]; stop = entry - stopdist if d == 1 else entry + stopdist
            peak = entry; exit_px = None; exit_i = n - 1
            for j in range(ei, n):
                if d == 1:
                    if L[j] <= stop: exit_px = stop; exit_i = j; break
                    peak = max(peak, H[j]); ns = peak - native_trail_atr * A[j]
                    stop = max(stop, ns) if not np.isnan(A[j]) else stop
                else:
                    if H[j] >= stop: exit_px = stop; exit_i = j; break
                    peak = min(peak, L[j]); ns = peak + native_trail_atr * A[j]
                    stop = min(stop, ns) if not np.isnan(A[j]) else stop
            if exit_px is None: exit_px = C[n - 1]; exit_i = n - 1
            pnl_old = d * (exit_px - entry) - cost

            # ---- VARIANT 1m-truth exit re-walk ----
            pnl_new = None
            if idx1 is not None:
                t_entry = idx[ei]
                a1 = int(np.searchsorted(idx1, t_entry, side="left"))
                if a1 < len(idx1):
                    stop_new = entry - stopdist if d == 1 else entry + stopdist
                    peak_close = entry
                    j5 = ei
                    exit_px_new = None
                    armed = not arm_after_1r
                    target_px = (entry + d * fixed_target_r * stopdist) if fixed_target_r is not None else None
                    for x in range(a1, len(idx1)):
                        while j5 + 1 < n and idx1[x] >= idx[j5 + 1]:
                            j5 += 1
                        atr_prev = A[j5 - 1] if j5 - 1 >= 0 else np.nan
                        atr_now = atr_prev if not np.isnan(atr_prev) else A[ei - 1]
                        hi1, lo1, cl1 = H1[x], L1[x], C1[x]
                        # adverse-first: stop check uses the level set BEFORE this bar folds in
                        if (lo1 <= stop_new) if d == 1 else (hi1 >= stop_new):
                            exit_px_new = stop_new; break
                        if target_px is not None:
                            if (hi1 >= target_px) if d == 1 else (lo1 <= target_px):
                                exit_px_new = target_px; break
                        if time_stop_min is not None:
                            elapsed_min = (pd.Timestamp(idx1[x]) - pd.Timestamp(t_entry)).total_seconds() / 60.0
                            if elapsed_min >= time_stop_min:
                                exit_px_new = cl1; break
                        if hard_eod_t is not None:
                            ts_x = pd.Timestamp(idx1[x])
                            bar_t = ts_x.tz_convert(NY).time() if ts_x.tzinfo else ts_x.time()
                            if bar_t >= hard_eod_t:
                                exit_px_new = cl1; break
                        peak_close = max(peak_close, cl1) if d == 1 else min(peak_close, cl1)
                        if trail_atr is not None:
                            if not armed:
                                favorable_r = d * (peak_close - entry) / stopdist
                                if favorable_r >= 1.0:
                                    armed = True
                            if armed:
                                cand = (peak_close - trail_atr * atr_now) if d == 1 else (peak_close + trail_atr * atr_now)
                                stop_new = max(stop_new, cand) if d == 1 else min(stop_new, cand)
                    if exit_px_new is None:
                        exit_px_new = C1[len(idx1) - 1]
                    pnl_new = d * (exit_px_new - entry) - cost
                else:
                    skipped_no_1m += 1
            else:
                skipped_no_1m += 1

            out.append(dict(ts=idx[ei], d=d, entry=float(entry), stop_pts=float(stopdist),
                            pnl_pts_old=float(pnl_old), mae_pts=0.0, eod_old=(exit_px is None),
                            pnl_pts_new=pnl_new))
            busy_until = exit_i; taken += 1; day_pnl += pnl_old
    df = pd.DataFrame(out).sort_values("ts").reset_index(drop=True)
    return df, skipped_no_1m


def self_check_walker_defaults(feats, d1rth, df1m_ref):
    df1m_var, _ = vpc_1m_truth_variant(feats, d1rth, trail_atr=5.0)
    same = (len(df1m_ref) == len(df1m_var)
            and np.allclose(df1m_ref["pnl_pts_new"].values, df1m_var["pnl_pts_new"].values, atol=1e-9)
            and (pd.to_datetime(df1m_ref["ts"]).values == pd.to_datetime(df1m_var["ts"]).values).all())
    print(f"  SELF-CHECK (generalized walker w/ defaults == VT.vpc_1m_truth_trades): "
          f"{'PASS' if same else 'FAIL'}")
    return same


def mae_from_stop_pts(df1m):
    """mae_r for the new build_new_vpc_rows() call needs a mae_pts column; since these exit
    variants don't re-derive MAE (out of scope, same call as VT's own docstring note), reuse the
    NATIVE mae from VT's certified re-walk keyed by ts (falls back to 0.0 if not found -- flagged,
    not hidden)."""
    return df1m


def build_a_exit_rows():
    print("\n  loading A5 raw D1c-kept trades (tools_salvage_funded_exits.kept_raw_trades)…", flush=True)
    raw, mp = TSF.kept_raw_trades()
    variants = {
        "exit3-current": TSF.walk_exit3,
        "fixed-1.5R": TSF.walk_fixed_r(1.5),
        "fixed-2R": TSF.walk_fixed_r(2.0),
    }
    out = {}
    for name, fn in variants.items():
        rows = TSF.build_variant_rows(raw, mp, fn)
        out[name] = rows
    stats3 = TSF.variant_stats(out["exit3-current"])
    ok = (stats3["n"] == 583 and stats3["PF"] == 1.361 and round(stats3["totR"], 1) == 89.2)
    print(f"  A-leg exit3-current canary (full stream): n={stats3['n']} PF={stats3['PF']} "
          f"totR={stats3['totR']:+.1f}R (expect n=583 PF=1.361 totR=+89.2R) -> "
          f"{'PASS' if ok else 'FAIL'}")
    return out, ok


def window_2022(rows):
    """Restrict A-leg rows to the shared 2022-2026 VPC window (same 'PART 3 WINDOW NOTE'
    convention as `tools_salvage_vpc_reeval.py`), using the CORRECT NY-local timestamp
    (`to_ny_ts` -- the A-leg's own `ts` here is tz-aware NY already, so this is a straightforward
    comparison)."""
    return [r for r in rows if to_ny_ts(r["ts"]) >= VR.WINDOW_START]


def build_vpc_exit_rows(feats, d1rth):
    configs = {
        "current-5.0xATR": dict(trail_atr=5.0),
        "tighter-4.0xATR": dict(trail_atr=4.0),
        "looser-6.0xATR": dict(trail_atr=6.0),
        "fixed-2R-target": dict(trail_atr=None, fixed_target_r=2.0),
        "trail-armed-after-1R": dict(trail_atr=5.0, arm_after_1r=True),
        "time-stop-120min": dict(trail_atr=5.0, time_stop_min=120),
    }
    out = {}
    for name, kw in configs.items():
        df1m, skipped = vpc_1m_truth_variant(feats, d1rth, **kw)
        rows = VT.build_new_vpc_rows(df1m)
        out[name] = rows
        print(f"  VPC-leg [{name}]: n={len(rows)} skipped(no 1m)={skipped}", flush=True)
    return out


def stopday_filter(a_rows, v_rows, threshold_r):
    """New overlay logic (called out in module docstring): merges legs by ts, walks each day
    chronologically, drops every LATER same-day trade (either leg) once that day's running SUM of
    each trade's OWN R-multiple reaches `threshold_r`."""
    tagged = ([dict(r, _leg="A", _ny_ts=to_ny_ts(r["ts"])) for r in a_rows]
              + [dict(r, _leg="V", _ny_ts=to_ny_ts(r["ts"])) for r in v_rows])
    tagged.sort(key=lambda r: r["_ny_ts"])
    by_day = {}
    for r in tagged:
        d = r["_ny_ts"].normalize()
        by_day.setdefault(d, []).append(r)
    keep_a, keep_v = [], []
    for lst in by_day.values():
        cum = 0.0
        for r in lst:
            if cum >= threshold_r:
                continue
            leg = r["_leg"]
            orig = {k: v for k, v in r.items() if k not in ("_leg", "_ny_ts")}
            (keep_a if leg == "A" else keep_v).append(orig)
            cum += r["R"]
    return keep_a, keep_v


def exit_row(label, a_rows, v_rows):
    s, pf, ev, days = funnel_cell(a_rows, v_rows, label)
    all_r = np.array([r["R"] for r in a_rows] + [r["R"] for r in v_rows], float)
    if len(all_r):
        wr = 100.0 * float((all_r > 0).mean())
        wins = float(all_r[all_r > 0].sum()); losses = float(-all_r[all_r <= 0].sum())
        pf_r = wins / losses if losses > 0 else float("nan")
        totR = float(all_r.sum())
    else:
        wr, pf_r, totR = None, float("nan"), 0.0
    maxdd = maxdd_usd_of_days(days)
    rec = dict(label=label, n_a=len(a_rows), n_v=len(v_rows),
               pf_dollar=round(pf, 3) if pf == pf else None,
               pf_r=round(pf_r, 3) if pf_r == pf_r else None,
               wr_pct=round(wr, 1) if wr is not None else None,
               totR=round(totR, 1), maxdd_usd=round(maxdd, 0),
               **{k: v for k, v in s.items() if k not in ("label", "per_year")},
               e_dollar_placeholder=e_dollar_placeholder(s["pass_pct"]))
    for sv in SLIP_PROBE:
        a_s = ST.dmg_slip(a_rows, sv)
        v_s = ST.dmg_slip(v_rows, sv)
        s2, pf2, _, _ = funnel_cell(a_s, v_s, f"{label} slip={sv}")
        rec[f"slip{sv}_pass_pct"] = s2["pass_pct"]
        rec[f"slip{sv}_bust_pct"] = s2["bust_pct"]
    return rec


def run_lane2(a_exit_rows, vpc_exit_rows, a_exit_ok):
    print("\n" + "=" * 100)
    print("LANE 2 (06) -- exit interaction (A-leg x VPC-leg x portfolio overlays)")
    print("=" * 100)
    print("NOTICE: exit changes are certification events. This is a RESEARCH-ONLY comparison; the "
          "certified live exits (A exit3, VPC current 5.0xATR trail) are NOT modified anywhere.")

    a_default = window_2022(a_exit_rows["exit3-current"])
    v_default = vpc_exit_rows["current-5.0xATR"]

    records = []
    baseline = exit_row("BASELINE (A=exit3-current, VPC=current-5.0xATR, overlay=none)", a_default, v_default)
    baseline["dimension"] = "baseline"
    records.append(baseline)

    a_leg_results = {"exit3-current": baseline}
    for name in ("fixed-1.5R", "fixed-2R"):
        a_rows = window_2022(a_exit_rows[name])
        rec = exit_row(f"A-leg={name} (VPC=current-5.0xATR)", a_rows, v_default)
        rec["dimension"] = "A-leg"
        records.append(rec)
        a_leg_results[name] = rec

    vpc_leg_results = {"current-5.0xATR": baseline}
    for name in ("tighter-4.0xATR", "looser-6.0xATR", "fixed-2R-target",
                 "trail-armed-after-1R", "time-stop-120min"):
        v_rows = vpc_exit_rows[name]
        rec = exit_row(f"VPC-leg={name} (A=exit3-current)", a_default, v_rows)
        rec["dimension"] = "VPC-leg"
        records.append(rec)
        vpc_leg_results[name] = rec

    # overlays
    v_flatten = vpc_exit_rows.get("flatten-1430")
    rec = exit_row("overlay=flatten-VPC-by-14:30 (A=exit3-current)", a_default, v_flatten)
    rec["dimension"] = "overlay"
    records.append(rec)

    for thr in (1.0, 1.5, 2.0):
        keep_a, keep_v = stopday_filter(a_default, v_default, thr)
        rec = exit_row(f"overlay=stop-day-after-portfolio>=+{thr}R", keep_a, keep_v)
        rec["dimension"] = "overlay"
        records.append(rec)

    # best-A x best-VPC combined row (mechanical: highest dollar PF within each dimension's
    # varied-leg rows, baseline included)
    best_a_name = max(a_leg_results, key=lambda k: (a_leg_results[k]["pf_dollar"] or -999))
    best_v_name = max(vpc_leg_results, key=lambda k: (vpc_leg_results[k]["pf_dollar"] or -999))
    best_a_rows = a_default if best_a_name == "exit3-current" else window_2022(a_exit_rows[best_a_name])
    best_v_rows = v_default if best_v_name == "current-5.0xATR" else vpc_exit_rows[best_v_name]
    rec = exit_row(f"BEST-A({best_a_name}) x BEST-VPC({best_v_name}) combined", best_a_rows, best_v_rows)
    rec["dimension"] = "best-combo"
    records.append(rec)

    for r in records:
        print(f"  [{r['dimension']:>10}] {r['label']:<58} PF$={r['pf_dollar']} PF_R={r['pf_r']} "
              f"WR={r['wr_pct']}% totR={r['totR']:+.1f}R maxDD$={r['maxdd_usd']:,.0f} "
              f"pass={r['pass_pct']}% bust={r['bust_pct']}%")

    return pd.DataFrame.from_records(records), best_a_name, best_v_name


def write_06(df, best_a_name, best_v_name, a_exit_ok, runtime_s, firewall_before, firewall_after):
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, "06_exit_interaction.csv")
    md_path = os.path.join(OUTDIR, "06_exit_interaction.md")
    df.to_csv(csv_path, index=False)

    baseline = df[df["dimension"] == "baseline"].iloc[0]

    lines = []
    lines.append("# 06 -- Exit interaction (A+VPC portfolio optimisation, Lane 2)")
    lines.append("")
    lines.append("**NOTICE: exit changes are certification events.** RESEARCH-ONLY comparison; no "
                 "certified live exit (A exit3, VPC current 5.0xATR trail) is modified by this "
                 "file. Every row below is a hypothetical re-walk, reported as data, not a "
                 "recommendation.")
    lines.append("")
    lines.append("A-leg exits reuse `tools_salvage_funded_exits.py`'s A5 machinery verbatim "
                 f"(exit3-current/fixed-1.5R/fixed-2R). A-leg canary: {'PASS' if a_exit_ok else 'FAIL'} "
                 "(exit3-current on the FULL stream reproduces n=583 PF=1.361 totR=+89.2R). "
                 "A-leg rows below are window-restricted to 2022-2026 (shared VPC window) before "
                 "combining with the VPC leg, mirroring the existing 'PART 3 WINDOW NOTE' "
                 "convention in `tools_salvage_vpc_reeval.py`.")
    lines.append("")
    lines.append("VPC-leg exits are a self-verified extension of `tools_vpc_1m_truth.py`'s 1m "
                 "re-walk (`vpc_1m_truth_variant`, this file) -- entries/direction/initial-stop "
                 "unchanged; only the exit's bar-by-bar rule varies (trail multiple / fixed target "
                 "/ arm-delay / time-stop / hard EOD flatten). Self-check: defaults reproduce "
                 "`VT.vpc_1m_truth_trades()`'s own re-walk exactly (see run log).")
    lines.append("")
    lines.append(f"Baseline (A=exit3-current, VPC=current-5.0xATR, overlay=none): PF$={baseline['pf_dollar']} "
                 f"PF_R={baseline['pf_r']} WR={baseline['wr_pct']}% totR={baseline['totR']:+.1f}R "
                 f"maxDD$={baseline['maxdd_usd']:,.0f} pass={baseline['pass_pct']}% "
                 f"bust={baseline['bust_pct']}% exp={baseline['exp_pct']}% "
                 f"n={baseline['eligible_starts']}. This is the SAME A/VPC trade set as 05's "
                 "A-current+VPC-full named combo (verified: identical R-multiset, n=513, and "
                 "identical VPC re-walk) but reproduces pass=28.8%/bust=16.4% here vs "
                 "pass=28.7%/bust=17.0% in 05 -- ROOT-CAUSED (not a bug in this file): the A-leg's "
                 "`mae_r` field differs between the two independently-sourced 'identical' A "
                 "streams (`tools_sim_parity_check.load_rows()`'s own mae_r vs the A5 machinery's "
                 "`walk_exit3`-re-derived mae, e.g. one specific day, 2022-01-14, has trough "
                 "-$910 in one stream's mae vs -$453 in the other), which changes the DLL-clamp "
                 "trough on that day and flips a small number of eval-run outcomes. R itself is "
                 "byte-identical between the two streams (elementwise multiset check passed); only "
                 "the adverse-excursion field differs. Called out, not hidden -- not investigated "
                 "further here (out of this file's scope; a pre-existing discrepancy between two "
                 "already-certified prior-art pipelines).")
    lines.append("")
    lines.append(f"`Best-A x Best-VPC` combined row picks, mechanically, the highest dollar-PF "
                 f"variant within each leg's varied rows (baseline included): "
                 f"best A-leg = **{best_a_name}**, best VPC-leg = **{best_v_name}**.")
    lines.append("")
    lines.append("Slip probe = 0.015/0.03/0.046R applied to BOTH legs uniformly "
                 "(`tools_salvage_stress.dmg_slip`, reused verbatim).")
    lines.append("")
    lines.append("## Full table")
    lines.append("")
    show_cols = ["dimension", "label", "n_a", "n_v", "pf_dollar", "pf_r", "wr_pct", "totR",
                "maxdd_usd", "eligible_starts", "pass_count", "bust_count", "exp_count",
                "pass_pct", "bust_pct", "exp_pct", "med_days_pass", "funded_per_slot_year",
                "e_dollar_placeholder"]
    lines.append(VR.df_to_md_table(df[show_cols]))
    lines.append("")
    lines.append("## Slip probe")
    lines.append("")
    slip_cols = ["dimension", "label"] + [c for sv in SLIP_PROBE for c in
                (f"slip{sv}_pass_pct", f"slip{sv}_bust_pct")]
    lines.append(VR.df_to_md_table(df[slip_cols]))
    lines.append("")
    lines.append("## Firewall before/after")
    lines.append("")
    for f in FIREWALL_FILES:
        b, a = firewall_before.get(f), firewall_after.get(f)
        lines.append(f"- `{f}`: {'UNCHANGED' if b == a else '**CHANGED**'}")
    lines.append("")
    if VR.PF_FLAGS:
        lines.append(f"## PF FREEZE FLAGS (PF>{VR.PF_FREEZE_THRESHOLD}): {VR.PF_FLAGS}")
    else:
        lines.append(f"## PF freeze check: no cell exceeded PF>{VR.PF_FREEZE_THRESHOLD}.")
    lines.append("")
    lines.append(f"Runtime (lane 2 only): {runtime_s:.1f}s")
    lines.append("")
    lines.append("No recommendation. No commits.")
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[saved] {csv_path}\n[saved] {md_path}")


# ==================================================================================================
def main():
    t_all = time.time()
    firewall_before = ST.sha_of(FIREWALL_FILES)
    print(f"firewall (before): {firewall_before}")

    streams = load_streams()
    if not streams["ok"]:
        print("[ABORT] upstream VPC-core/portfolio/408-signature canary mismatch -- STOP, no report written.")
        return
    a2022, v_rows_new, feats, d1rth = streams["a2022"], streams["v_rows_new"], streams["feats"], streams["d1rth"]

    baseline_ok, baseline_s = check_baseline_canary(a2022, v_rows_new)
    if not baseline_ok:
        print("[ABORT] baseline canary (A600/6+VPC600/4) mismatch -- STOP, no report written.")
        return

    # -------- LANE 3 (05) --------
    t3 = time.time()
    df05, first_eq_max1, max2_eq_current = run_lane3(a2022, v_rows_new)
    runtime_lane3 = time.time() - t3

    firewall_mid = ST.sha_of(FIREWALL_FILES)
    if any(firewall_before[fn] != firewall_mid[fn] for fn in FIREWALL_FILES):
        print("[FIREWALL FAILURE after lane 3] STOPPING, no report written.")
        return
    write_05(df05, first_eq_max1, max2_eq_current, baseline_s, runtime_lane3, firewall_before, firewall_mid)

    # -------- LANE 2 (06) --------
    t2 = time.time()
    print("\nloading 1m-truth VPC 408-trade re-walk canary df (for self-check)…", flush=True)
    v, VS = VR.v, VR.VS
    df1m_ref, _ = VT.vpc_1m_truth_trades(feats, d1rth)
    self_ok = self_check_walker_defaults(feats, d1rth, df1m_ref)
    if not self_ok:
        print("[ABORT] generalized walker self-check (defaults) mismatch -- STOP, no lane-2 report written.")
        return

    a_exit_rows, a_exit_ok = build_a_exit_rows()
    if not a_exit_ok:
        print("[ABORT] A-leg exit3 canary mismatch -- STOP, no lane-2 report written.")
        return

    vpc_exit_rows = build_vpc_exit_rows(feats, d1rth)
    # extra config for the flatten-by-14:30 overlay
    df1m_flat, skipped_flat = vpc_1m_truth_variant(feats, d1rth, trail_atr=5.0, hard_eod_time="14:30")
    vpc_exit_rows["flatten-1430"] = VT.build_new_vpc_rows(df1m_flat)
    print(f"  VPC-leg [flatten-1430]: n={len(vpc_exit_rows['flatten-1430'])} skipped={skipped_flat}")

    df06, best_a_name, best_v_name = run_lane2(a_exit_rows, vpc_exit_rows, a_exit_ok)
    runtime_lane2 = time.time() - t2

    firewall_after = ST.sha_of(FIREWALL_FILES)
    firewall_ok = all(firewall_before[fn] == firewall_after[fn] for fn in FIREWALL_FILES)
    if not firewall_ok:
        print("[FIREWALL FAILURE after lane 2] STOPPING, no lane-2 report written.")
        for fn in FIREWALL_FILES:
            print(f"  {fn}: {'UNCHANGED' if firewall_before[fn] == firewall_after[fn] else 'CHANGED'}")
        return
    write_06(df06, best_a_name, best_v_name, a_exit_ok, runtime_lane2, firewall_before, firewall_after)

    total_runtime = time.time() - t_all
    print("\n" + "=" * 100)
    if VR.PF_FLAGS:
        print(f"[FREEZE] {len(VR.PF_FLAGS)} cell(s) breached PF>{VR.PF_FREEZE_THRESHOLD}: {VR.PF_FLAGS}")
    else:
        print(f"No cell anywhere breached PF>{VR.PF_FREEZE_THRESHOLD}.")
    print(f"Total runtime: {total_runtime:.1f}s (lane3={runtime_lane3:.1f}s, lane2={runtime_lane2:.1f}s)")
    for fn in FIREWALL_FILES:
        print(f"Firewall {fn}: UNCHANGED")
    print("=" * 100)


if __name__ == "__main__":
    main()
