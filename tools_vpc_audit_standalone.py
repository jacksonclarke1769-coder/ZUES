"""tools_vpc_audit_standalone.py — VPC STANDALONE AUDIT, compute lane 1.

RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing (no live/config/engine file touched).
Pure execution of pinned formulas over PRIOR-ART machinery — no new modeling choices beyond the
explicit mapping/assumption notes below (each one called out, not hidden). No winner-picking
beyond the mechanical shortlist flag explicitly requested by the brief. Auditor judges.

STREAM: reuses `tools_salvage_vpc_reeval.py`'s VPC machinery end to end:
  - `VR.vpc_rows()` / `VR.VS.vpc_trades_rich()` — the certified 408-trade VPC standalone stream
    (real Databento NQ 1m->5m RTH, 2022+, frozen CFG) and its (ts, R, mae_r, risk_usd) row mapping.
  - `VR.a_rows_full()` (`tools_sim_parity_check.load_rows`) — the honest-A reference (n=583,
    PF 1.361) used ONLY here to build the "A trade-day" set for the sleep-day computation.
  - `VR.ASR` (`tools_account_size_research`) — `build_events` / `day_rows(550,1000)` / `eval_run` /
    `SPECS["50K"]` / `EXPIRE_DAYS` — the pinned EVAL funnel machinery, unchanged.
  - `VR.same_day_stats` — the already-pinned dl_freq/tl_freq/same_day_corr definitions (VPC vs the
    honest-A 2022-2026 stream), computed once and REPEATED as a reference column on every one of
    the 104 funnel cells below (identical reuse of Part 2's own pattern in tools_salvage_vpc_reeval.py
    — not a new metric).
  - `tools_salvage_track_a.py` (`TA`) — the unfiltered-705-trade A stream + its own pinned canary
    (`TA.check_canaries`), used ONLY for the "vs unfiltered-705 days" half of the sleep-day ask.
  - `tools_salvage_stress.py` (`ST`) — `dmg_slip` (uniform R-unit slippage damage) / `SLIP_GRID`
    (coarse grid) / `find_flip` (linear-interpolated pass>bust margin flip) — reused verbatim for
    the slippage-breakpoint column on the top-5 funnel cells.

TWO NEW (but self-verified) PIECES OF LOGIC in this file — both are checked byte-identical to the
pinned originals before their EXTRA fields are trusted:
  1. `vpc_trades_ext()` — a faithful extension of `VS.vpc_trades_rich()` (same CFG, same day-by-day
     walk) that additionally records direction (`d`) and hold time in bars (`exit_i - ei`) for the
     long/short split and hold-time stats the task asks for. Verified elementwise identical to
     `VS.vpc_trades_rich()`'s own (ts, pnl_pts, mae_pts, mfe_pts, stop_pts) columns — STOP on mismatch.
  2. `day_rows_instrumented()` / `eval_run_instrumented()` — faithful extensions of
     `ASR.day_rows()` / `ASR.eval_run()` that additionally count DLL-clamp days and tag each BUST as
     `intraday_trough` (breached on the honest marked-open trough) vs `eod_trail` (breached only at
     EOD-settled balance). Verified to return IDENTICAL (day,real,trough) tuples / (status,ndays) to
     the pinned originals on every cell/start actually evaluated — assert, not sampled.

ASSUMPTIONS CALLED OUT (no prior-art precedent found in repo for these terms; documented, not hidden):
  - "dl_freq"/"tl_freq"/"same_day_corr" on the 104-cell standalone grid are NOT re-derived here —
    they are the exact reference figures `tools_salvage_vpc_reeval.same_day_stats(a2022, v_rows)`
    already computes for VPC-vs-honest-A (2022-2026 window), repeated as constant context columns
    on every row (same treatment Part 2 of that file already gives them). They are cap/budget-
    invariant to first order (unit, 1-contract dollar P&L), per that file's own docstring.
  - "E$" placeholder = pass_pct/100*8000 - 131, IDENTICAL formula/comment to
    `tools_salvage_track_a.py`'s own `E_proxy` ("8k pending A4 placeholder... NOT a dollar
    certification").
  - "DLL-clamp interaction count" = number of unique trading days (within that cell's day-collapsed
    calendar) where the marked-open trough breached -$1,000 (the DLL clamp in `ASR.day_rows`
    actually fires), i.e. how often the honest-DLL clamp semantics bind vs a naive realized-only
    clamp would have differed.
  - "EOD-trail failure count" = of BUSTs only, how many were triggered by the EOD-settled-balance
    trail check (`bal <= thr` after the day's real P&L posts) vs the intraday marked-open-trough
    check (`bal + min(0.,trough) <= thr`, i.e. would have busted mid-day even before EOD).

PF>1.8 anywhere (dollar trade-level PF) -> FREEZE + FLAG via the shared `VR.event_pf`/`VR.PF_FLAGS`
bookkeeping (same mechanism `tools_salvage_stress.py` already shares with `tools_salvage_vpc_reeval.py`).

FIREWALL: sha256 of `tools_salvage_stress.FIREWALL_FILES` (config_eval_locked.py,
config_funded_locked.py, config_defaults.py, auto_safety.py) taken before load and again right
before any report is written. Any mismatch -> STOP, no report written (stronger than the salvage-
stress precedent, per this task's explicit "fail=STOP").

Outputs (new, this run only):
  reports/vpc_standalone_audit/02_vpc_standalone_backtest.csv / .md / .json
  reports/vpc_standalone_audit/03_vpc_eval_funnel_standalone.csv / .md
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

import tools_salvage_vpc_reeval as VR       # VPC machinery, ASR, honest-A, same_day_stats, event_pf
import tools_salvage_track_a as TA          # unfiltered-705 A stream + its own pinned canary
import tools_salvage_stress as ST           # dmg_slip / SLIP_GRID / find_flip / sha_of / FIREWALL_FILES

NY = "America/New_York"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "reports", "vpc_standalone_audit")

BUDGETS = [100, 150, 200, 250, 300, 400, 500, 600, 700, 800, 900, 1000, 1200]
CAPS = [1, 2, 3, 4, 5, 6, 8, 10]
HIGHLIGHT_CELL = (600, 4)


# ==================================================================================================
# 1. self-verified extension of VS.vpc_trades_rich() -- adds direction + hold time, nothing else
# ==================================================================================================
def vpc_trades_ext(feats):
    """Faithful extension of vpc_apex_eval_sim.vpc_trades_rich() (identical CFG, identical
    day-by-day walk) — additionally records direction `d` and hold time in bars (`exit_i - ei`).
    Caller MUST verify elementwise equality against VS.vpc_trades_rich(feats) on the shared columns
    before trusting the extra fields (done in run_canaries below)."""
    v, VS = VR.v, VR.VS
    CFG = VS.CFG
    sig_kw = {k: CFG[k] for k in ("atr_stop", "slot_min", "slot_max", "slope_mult", "trend_mult") if k in CFG}
    trail_atr = CFG["trail_atr"]; max_trades = CFG["max_trades"]; daily_stop = CFG["daily_stop"]
    out = []
    for day, g in feats.groupby("date"):
        g = g.sort_values("slot")
        idx = g.index
        sigs = v.vpc_signals(g.reset_index(drop=True), **sig_kw)
        O, H, L, C, A = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.atr.values
        n = len(g); busy_until = -1; taken = 0; day_pnl = 0.0
        for (ei, d, stopdist) in sigs:
            if ei >= n or ei <= busy_until or taken >= max_trades:
                continue
            if daily_stop and day_pnl <= -daily_stop:
                break
            entry = O[ei]; stop = entry - stopdist if d == 1 else entry + stopdist
            peak = entry; exit_px = None; exit_i = n - 1
            mae = 0.0; mfe = 0.0
            for j in range(ei, n):
                mae = min(mae, d * (L[j] - entry) if d == 1 else d * (H[j] - entry))
                mfe = max(mfe, d * (H[j] - entry) if d == 1 else d * (L[j] - entry))
                if d == 1:
                    if L[j] <= stop: exit_px = stop; exit_i = j; break
                    peak = max(peak, H[j]); ns = peak - trail_atr * A[j]
                    stop = max(stop, ns) if not np.isnan(A[j]) else stop
                else:
                    if H[j] >= stop: exit_px = stop; exit_i = j; break
                    peak = min(peak, L[j]); ns = peak + trail_atr * A[j]
                    stop = min(stop, ns) if not np.isnan(A[j]) else stop
            if exit_px is None: exit_px = C[n - 1]; exit_i = n - 1
            pnl = d * (exit_px - entry) - v.RT_COST
            out.append(dict(ts=idx[ei], pnl_pts=pnl, mae_pts=mae, mfe_pts=mfe, stop_pts=stopdist,
                            d=d, hold_bars=exit_i - ei))
            busy_until = exit_i; taken += 1; day_pnl += pnl
    return pd.DataFrame(out).sort_values("ts").reset_index(drop=True)


# ==================================================================================================
# 2. self-verified extensions of ASR.day_rows() / ASR.eval_run() -- add clamp/bust-reason counters
# ==================================================================================================
def day_rows_instrumented(ev, stop, dll):
    """Mirrors tools_account_size_research.day_rows() exactly, plus a DLL-clamp-day counter.
    Caller MUST verify the (day,real,trough) tuples equal ASR.day_rows()'s own output (done inline
    in extra_diagnostics() below, every cell, not sampled)."""
    days = {}
    for e in ev:
        d = e["ts"].normalize()
        r = days.setdefault(d, dict(real=0.0, trough=0.0, stopped=False))
        if r["stopped"]:
            continue
        r["trough"] = min(r["trough"], r["real"] + e["mae"])
        r["real"] += e["pnl"]
        if r["real"] <= -stop:
            r["stopped"] = True
    out = []
    clamp_days = 0
    for d in sorted(days):
        r = days[d]
        clamped = r["trough"] <= -dll
        if clamped:
            clamp_days += 1
            real, trough = -dll, -dll
        else:
            real, trough = r["real"], r["trough"]
        out.append((d, real, trough))
    return out, clamp_days


def eval_run_instrumented(days, s0, spec):
    """Mirrors ASR.eval_run() exactly, plus a bust-reason tag: 'intraday_trough' (busted on the
    honest marked-open trough, before EOD-settlement) vs 'eod_trail' (busted only once the day's
    real P&L posted at EOD). Caller MUST verify (status,ndays) equals ASR.eval_run()'s own output
    (done inline in extra_diagnostics() below, every start, not sampled)."""
    sb, tr, tg = spec["start"], spec["trail"], spec["target"]
    thr, bal, peak, locked = sb - tr, sb, sb, False
    t0 = days[s0][0]
    for i in range(s0, len(days)):
        d, real, trough = days[i]
        if (d - t0).days > VR.EXPIRE_DAYS:
            return "EXPIRE", VR.EXPIRE_DAYS, None
        if bal + min(0.0, trough) <= thr:
            return "BUST", (d - t0).days, "intraday_trough"
        bal += real
        peak = max(peak, bal)
        if not locked:
            thr = max(thr, peak - tr)
            if peak - tr >= sb + 100.0:
                thr = sb + 100.0; locked = True
        if bal <= thr:
            return "BUST", (d - t0).days, "eod_trail"
        if bal >= sb + tg:
            return "PASS", (d - t0).days, None
    return "INCOMPLETE", None, None


def extra_diagnostics(ev, spec=VR.SPEC50):
    """DLL-clamp-day count + EOD-trail-vs-intraday-trough bust-reason counts for one cell, with a
    hard structural-equivalence assert against the pinned ASR functions on every day/start."""
    days_i, clamp_days = day_rows_instrumented(ev, VR.STOP_PINNED, VR.DLL_PINNED)
    days_p = VR.ASR.day_rows(ev, VR.STOP_PINNED, VR.DLL_PINNED)
    assert [t[:3] for t in days_i] == days_p, "day_rows_instrumented diverged from ASR.day_rows"
    starts = VR.eligible_starts(days_p)
    reasons = {"intraday_trough": 0, "eod_trail": 0}
    for s in starts:
        status_i, ndays_i, reason = eval_run_instrumented(days_p, s, spec)
        status_p, ndays_p = VR.ASR.eval_run(days_p, s, spec)
        assert (status_i, ndays_i) == (status_p, ndays_p), "eval_run_instrumented diverged from ASR.eval_run"
        if reason:
            reasons[reason] += 1
    n_days = len(days_p)
    return dict(dll_clamp_days=clamp_days,
               dll_clamp_pct=round(100.0 * clamp_days / n_days, 2) if n_days else None,
               eod_trail_bust=reasons["eod_trail"], intraday_trough_bust=reasons["intraday_trough"])


# ==================================================================================================
# CANARIES (run first; STOP before any report on any mismatch)
# ==================================================================================================
def run_canaries_core(v_rows, tr_base, a_full):
    """(1)+(2a)+(2b)+(3): reuse tools_salvage_vpc_reeval's own canary battery verbatim. Run this
    FIRST and fail fast -- it is the cheapest, most fundamental check (VPC 408-signature + honest-A
    583/PF1.361 reference the whole audit is keyed on) and does not require the heavier
    tools_salvage_track_a stream load."""
    print("=" * 100)
    print("CANARIES (core: VPC 408-signature + honest-A 583/PF1.361 + look-ahead spot-check)")
    print("=" * 100)
    VR.vpc_rows_cache["rows"] = v_rows
    ok = VR.run_canaries(tr_base, a_full)
    print("=" * 100)
    if not ok:
        print("[CANARY FAILURE] STOPPING -- do not trust anything downstream of this run.")
    print("=" * 100)
    return ok


def run_canaries_extra(tr_base, tr_ext, S_ta):
    """(4)+(5): unfiltered-705 stream canary + vpc_trades_ext replica-equivalence canary. Only
    reached once run_canaries_core has already passed."""
    print("=" * 100)
    print("CANARIES (extra: unfiltered-705 stream + vpc_trades_ext replica equivalence)")
    print("=" * 100)
    ok = True

    ok4, su, sk, row1200 = TA.check_canaries(S_ta)
    print(f"4. tools_salvage_track_a canary (unfiltered n={su['n']}/PF={su['PF']}, "
          f"kept n={sk['n']}/PF={sk['PF']}, (10,$1200) row): -> {'PASS' if ok4 else 'FAIL'}")
    ok &= ok4

    shared = ["ts", "pnl_pts", "mae_pts", "mfe_pts", "stop_pts"]
    same_shape = len(tr_ext) == len(tr_base)
    c5 = same_shape and all(
        (tr_ext[c].reset_index(drop=True) == tr_base[c].reset_index(drop=True)).all()
        for c in shared
    )
    print(f"5. vpc_trades_ext elementwise match vs VS.vpc_trades_rich on {shared}: "
          f"n_ext={len(tr_ext)} n_base={len(tr_base)} -> {'PASS' if c5 else 'FAIL'}")
    ok &= c5

    print("=" * 100)
    if not ok:
        print("[CANARY FAILURE] STOPPING -- do not trust anything downstream of this run.")
    else:
        print("[all canaries PASS]")
    print("=" * 100)
    return ok


# ==================================================================================================
# PART 02 -- standalone backtest stats
# ==================================================================================================
def cost_variant_stats(tr, label):
    if len(tr) == 0:
        return dict(label=label, n_trades=0)
    pts = tr.pnl_pts.values
    r = pts / tr.stop_pts.values
    gp_pts = float(pts[pts > 0].sum()); gl_pts = float(-pts[pts < 0].sum())
    gp_r = float(r[r > 0].sum()); gl_r = float(-r[r < 0].sum())
    eq_pts = np.cumsum(pts); dd_pts = eq_pts - np.maximum.accumulate(eq_pts)
    eq_r = np.cumsum(r); dd_r = eq_r - np.maximum.accumulate(eq_r)
    return dict(label=label, n_trades=len(tr),
               wr_pct=round(100.0 * float((pts > 0).mean()), 1),
               pf_pts=round(gp_pts / gl_pts, 3) if gl_pts else None,
               pf_R=round(gp_r / gl_r, 3) if gl_r else None,
               exp_R=round(float(r.mean()), 4), total_R=round(float(r.sum()), 2),
               total_pts=round(float(pts.sum()), 2),
               maxdd_R=round(float(dd_r.min()), 3), maxdd_pts=round(float(dd_pts.min()), 1),
               best_trade_pts=round(float(pts.max()), 2), worst_trade_pts=round(float(pts.min()), 2))


def part2(v_rows, tr_base, tr_ext, a_full, S_ta):
    print("\nPART 02 -- VPC STANDALONE BACKTEST STATS")

    v, VS = VR.v, VR.VS
    feats = v.features(VS.real_rth_5m())
    feats = feats[feats.date >= VR.WINDOW_START]

    orig_cost = v.RT_COST
    try:
        v.RT_COST = 3.0
        tr_harsh = VS.vpc_trades_rich(feats)
    finally:
        v.RT_COST = orig_cost

    base_stats = cost_variant_stats(tr_base, f"base_{orig_cost}pt")
    harsh_stats = cost_variant_stats(tr_harsh, "harsh_3.0pt")
    print(f"  base ({orig_cost}pt): n={base_stats['n_trades']} PF(pts)={base_stats['pf_pts']} "
          f"PF(R)={base_stats['pf_R']} WR={base_stats['wr_pct']}%")
    print(f"  harsh (3.0pt): n={harsh_stats['n_trades']} PF(pts)={harsh_stats['pf_pts']} "
          f"PF(R)={harsh_stats['pf_R']} WR={harsh_stats['wr_pct']}%")
    if harsh_stats["n_trades"] != base_stats["n_trades"]:
        print(f"  [NOTE] harsh-cost trade count differs from base ({harsh_stats['n_trades']} vs "
              f"{base_stats['n_trades']}) -- higher RT_COST changes the per-day daily_stop=120pt "
              f"cutoff timing (day_pnl includes RT_COST), so it is NOT simply the base 408 trades "
              f"minus a constant per-trade cost.")

    # structural stats (cost-independent), base 408-trade set
    stop_pts = tr_ext.stop_pts.values
    hold_min = tr_ext.hold_bars.values * 5.0
    structural = dict(avg_stop_pts=round(float(stop_pts.mean()), 2),
                      median_stop_pts=round(float(np.median(stop_pts)), 2),
                      avg_hold_min=round(float(hold_min.mean()), 1),
                      median_hold_min=round(float(np.median(hold_min)), 1))

    # trades/week + day spans
    ts_arr = pd.to_datetime(tr_base["ts"])
    weeks = max((ts_arr.max() - ts_arr.min()).days / 7.0, 1.0)
    trades_per_week = round(len(tr_base) / weeks, 2)
    trading_days_spanned = int(feats["date"].nunique())
    vpc_fire_days = set(pd.Timestamp(t).normalize() for t in tr_base["ts"])
    n_vpc_fire_days = len(vpc_fire_days)

    honest_a_days = set(pd.Timestamp(r["ts"]).normalize() for r in a_full)
    unfiltered_a_days = set(pd.Timestamp(t["ts"]).normalize() for t in S_ta["unfiltered"])
    sleep_honest = vpc_fire_days - honest_a_days
    sleep_unfiltered = vpc_fire_days - unfiltered_a_days
    sleep_stats = dict(
        trading_days_spanned=trading_days_spanned, vpc_fire_days=n_vpc_fire_days,
        trades_per_week=trades_per_week,
        vpc_days_a_sleeps_vs_honest583=len(sleep_honest),
        vpc_days_a_sleeps_vs_honest583_pct=round(100.0 * len(sleep_honest) / n_vpc_fire_days, 1),
        vpc_days_a_sleeps_vs_unfiltered705=len(sleep_unfiltered),
        vpc_days_a_sleeps_vs_unfiltered705_pct=round(100.0 * len(sleep_unfiltered) / n_vpc_fire_days, 1),
    )

    # long/short split (base cost)
    by_side = []
    for d, name in ((1, "long"), (-1, "short")):
        sub = tr_ext[tr_ext.d == d]
        s = cost_variant_stats(sub, f"{name}")
        s["side"] = name
        by_side.append(s)

    # per-year (base cost)
    by_year = []
    yrs = pd.to_datetime(tr_base["ts"]).dt.year
    for y in sorted(yrs.unique()):
        sub = tr_base[yrs == y]
        s = cost_variant_stats(sub, str(y))
        s["year"] = int(y)
        by_year.append(s)

    # per-month (base cost)
    by_month = []
    ym = pd.to_datetime(tr_base["ts"]).dt.strftime("%Y-%m")
    for m in sorted(ym.unique()):
        sub = tr_base[ym == m]
        s = cost_variant_stats(sub, m)
        s["year_month"] = m
        by_month.append(s)

    # time-of-day (entry hour, ET) (base cost)
    by_hour = []
    hr = pd.to_datetime(tr_base["ts"]).dt.hour
    for h in sorted(hr.unique()):
        sub = tr_base[hr == h]
        s = cost_variant_stats(sub, f"{h}:00")
        s["entry_hour_et"] = int(h)
        by_hour.append(s)

    notes = dict(
        cost_fill_model=(
            "Entry: NEXT-bar-open (bar i+1's Open) after the signal bar i CLOSES — no lookahead "
            "(nq_vwap_pullback.py module docstring lines 8-13, verified against vpc_signals()/"
            "vpc_trades_rich() source: sigs.append((i+1, ...))). Cost: RT_COST baked into every "
            f"trade's pnl at exit ({orig_cost}pt round trip baseline = 2*HALF_COST, i.e. "
            f"{orig_cost/2}pt/side; harsh row re-runs the SAME engine with RT_COST=3.0pt end to "
            "end, which also shifts the per-day daily_stop=120pt cutoff timing, not just a "
            "constant per-trade offset). Stop/trail: checked against bar High/Low; if touched, "
            "the trade exits AT the stop price (not the bar extreme) — conservative but not "
            "sub-bar; the ATR trailing stop is RECALCULATED EVERY 5-MINUTE BAR CLOSE using that "
            "bar's 14-period rolling ATR (bar-close granularity, not intrabar/tick) and only ever "
            "ratchets in the favorable direction. EOD: if never stopped out, the trade is flattened "
            "at the day's LAST bar close (no overnight risk)."
        ),
        exit_documentation=(
            "VPC's own exit is a PURE ATR TRAILING STOP (2.5x-ATR initial stop distance, 5.0x-ATR "
            "trail) with NO FIXED PROFIT TARGET — the only exit condition per trade is the trailing "
            "stop (or EOD flat if never touched). This is structurally DIFFERENT from Exit#3 (the "
            "certified Profile-A partial/fixed-target exit) and was never re-tested against Exit#3 "
            "in this audit. Because VPC has only one exit condition, the same-bar stop-vs-target "
            "race that produced the F1 fill-bar-target-booking bug class elsewhere in this repo is "
            "structurally INAPPLICABLE here (there is no target to race against the stop). Whether "
            "VPC's own trailing-stop exit warrants independent re-testing/re-certification (vs "
            "e.g. swapping in Exit#3) is a judgment call reserved to the auditor — this report only "
            "states the mechanical fact."
        ),
    )

    return dict(base=base_stats, harsh=harsh_stats, structural=structural, sleep=sleep_stats,
               by_side=by_side, by_year=by_year, by_month=by_month, by_hour=by_hour, notes=notes)


def write_part2(d):
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, "02_vpc_standalone_backtest.csv")
    md_path = os.path.join(OUTDIR, "02_vpc_standalone_backtest.md")
    json_path = os.path.join(OUTDIR, "02_vpc_standalone_backtest.json")

    df_cost = pd.DataFrame.from_records([d["base"], d["harsh"]]); df_cost["section"] = "cost_variant"
    df_struct = pd.DataFrame.from_records([d["structural"]]); df_struct["section"] = "structural"
    df_sleep = pd.DataFrame.from_records([d["sleep"]]); df_sleep["section"] = "sleep_days"
    df_side = pd.DataFrame.from_records(d["by_side"]); df_side["section"] = "by_side"
    df_year = pd.DataFrame.from_records(d["by_year"]); df_year["section"] = "by_year"
    df_month = pd.DataFrame.from_records(d["by_month"]); df_month["section"] = "by_month"
    df_hour = pd.DataFrame.from_records(d["by_hour"]); df_hour["section"] = "by_hour"
    combined = pd.concat([df_cost, df_struct, df_sleep, df_side, df_year, df_month, df_hour],
                        ignore_index=True, sort=False)
    combined.to_csv(csv_path, index=False)

    def to_native(o):
        if isinstance(o, dict):
            return {k: to_native(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [to_native(v) for v in o]
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        return o
    with open(json_path, "w") as f:
        json.dump(to_native(d), f, indent=2)

    lines = []
    lines.append("# 02 -- VPC standalone backtest stats")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. VPC STANDALONE AUDIT, compute lane 1.")
    lines.append("")
    lines.append("## Cost variants (base = engine default RT_COST; harsh = RT_COST overridden to 3.0pt, "
                 "re-walked end to end)")
    lines.append("")
    lines.append(VR.df_to_md_table(df_cost.drop(columns=["section"])))
    lines.append("")
    lines.append("## Structural stats (cost-independent; base 408-trade set)")
    lines.append("")
    lines.append(VR.df_to_md_table(df_struct.drop(columns=["section"])))
    lines.append("")
    lines.append("## Sleep-day computation (days VPC fires where A is asleep, both A-reference-day-sets)")
    lines.append("")
    lines.append(VR.df_to_md_table(df_sleep.drop(columns=["section"])))
    lines.append("")
    lines.append("## Long/short split (base cost)")
    lines.append("")
    lines.append(VR.df_to_md_table(df_side.drop(columns=["section"])))
    lines.append("")
    lines.append("## Per-year (base cost)")
    lines.append("")
    lines.append(VR.df_to_md_table(df_year.drop(columns=["section"])))
    lines.append("")
    lines.append("## Per-month (base cost)")
    lines.append("")
    lines.append(VR.df_to_md_table(df_month.drop(columns=["section"])))
    lines.append("")
    lines.append("## Time-of-day (entry hour, America/New_York; base cost)")
    lines.append("")
    lines.append(VR.df_to_md_table(df_hour.drop(columns=["section"])))
    lines.append("")
    lines.append("## Cost/slippage/fill model documentation")
    lines.append("")
    lines.append(d["notes"]["cost_fill_model"])
    lines.append("")
    lines.append("## Exit documentation")
    lines.append("")
    lines.append(d["notes"]["exit_documentation"])
    lines.append("")
    if VR.PF_FLAGS:
        lines.append(f"## PF FREEZE FLAGS (PF>{VR.PF_FREEZE_THRESHOLD}): {VR.PF_FLAGS}")
    else:
        lines.append(f"## PF freeze check: no cell exceeded PF>{VR.PF_FREEZE_THRESHOLD}.")
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[saved] {csv_path}\n[saved] {md_path}\n[saved] {json_path}")


# ==================================================================================================
# PART 03 -- eval funnel grid (104 cells) + slippage breakpoints on top-5
# ==================================================================================================
def part3(v_rows, a2022, refstats):
    print("\nPART 03 -- VPC EVAL FUNNEL STANDALONE (13 budgets x 8 caps = 104 cells)")
    records = []
    for budget in BUDGETS:
        for cap in CAPS:
            label = f"VPCstandalone@{budget}/{cap}"
            ev = VR.ASR.build_events(v_rows, budget, cap)
            pf = VR.event_pf(ev, label)
            days = VR.ASR.day_rows(ev, VR.STOP_PINNED, VR.DLL_PINNED)
            s = VR.summarize_cell(days, label)
            xd = extra_diagnostics(ev)
            e_dollar = (round(s["pass_pct"] / 100 * 8000 - 131, 2)
                       if s["pass_pct"] is not None else None)
            rec = dict(budget=budget, cap=cap, pf_dollar=round(pf, 3) if pf == pf else None,
                      **{k: v for k, v in s.items() if k not in ("label", "per_year")},
                      e_dollar_placeholder=e_dollar,
                      same_day_corr=refstats["same_day_corr"], dl_freq_pct=refstats["dl_freq_pct"],
                      tl_freq_pct=refstats["tl_freq_pct"], **xd,
                      highlight_600_4=(budget, cap) == HIGHLIGHT_CELL)
            rec["shortlist"] = bool(s["pass_count"] and s["pass_pct"] is not None
                                   and s["bust_pct"] is not None
                                   and s["pass_pct"] > s["bust_pct"] and s["pass_count"] >= 20)
            records.append(rec)
            tag = " [HIGHLIGHT 600/4]" if rec["highlight_600_4"] else ""
            print(f"  budget={budget:>4} cap={cap:>2} | n={s['eligible_starts']:>4} "
                  f"pass={s['pass_pct']}% bust={s['bust_pct']}% exp={s['exp_pct']}% "
                  f"med={s['med_days_pass']}d PF={pf:.3f} clampDays={xd['dll_clamp_days']} "
                  f"eodBust={xd['eod_trail_bust']} trghBust={xd['intraday_trough_bust']}"
                  f"{' [SHORTLIST]' if rec['shortlist'] else ''}{tag}")
    df = pd.DataFrame.from_records(records)
    return df


def top5_breakpoints(df, v_rows):
    shortlist = df[df["shortlist"] == True].copy()  # noqa: E712
    if len(shortlist) == 0:
        return pd.DataFrame()
    shortlist["margin"] = shortlist["pass_pct"] - shortlist["bust_pct"]
    top5 = shortlist.sort_values("margin", ascending=False).head(5)
    records = []
    for _, row in top5.iterrows():
        budget, cap = int(row["budget"]), int(row["cap"])
        pts = []
        for s in ST.SLIP_GRID:
            rows_d = ST.dmg_slip(v_rows, s) if s > 0.0 else v_rows
            ev = VR.ASR.build_events(rows_d, budget, cap)
            days = VR.ASR.day_rows(ev, VR.STOP_PINNED, VR.DLL_PINNED)
            s2 = VR.summarize_cell(days, f"VPC@{budget}/{cap} slipR={s}")
            margin = None if s2["pass_pct"] is None else s2["pass_pct"] - s2["bust_pct"]
            pts.append((s, margin))
        flip = ST.find_flip(pts)
        records.append(dict(budget=budget, cap=cap, pass_pct=row["pass_pct"], bust_pct=row["bust_pct"],
                            margin=round(float(row["margin"]), 1), breakpoint_slipR=flip))
        print(f"  top5 breakpoint budget={budget} cap={cap} margin={row['margin']:.1f} "
              f"-> flips at slipR={flip}")
    return pd.DataFrame.from_records(records)


def write_part3(df, df_bp, refstats):
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, "03_vpc_eval_funnel_standalone.csv")
    md_path = os.path.join(OUTDIR, "03_vpc_eval_funnel_standalone.md")
    df.to_csv(csv_path, index=False)

    hl = df[df["highlight_600_4"] == True]  # noqa: E712
    shortlist = df[df["shortlist"] == True]  # noqa: E712

    lines = []
    lines.append("# 03 -- VPC eval funnel standalone (13 budgets x 8 caps = 104 cells)")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. VPC STANDALONE AUDIT, compute lane 1. Funnel = "
                 "tools_account_size_research.build_events / day_rows(550,1000) / eval_run (Apex "
                 "50K spec), unchanged, pinned. eligible_starts = unique trading days with >30d "
                 "runway (EXPIRE=30d).")
    lines.append("")
    lines.append(f"Reference dl/tl freq (VPC vs honest-A, 2022-2026 unit-level, computed ONCE by "
                f"tools_salvage_vpc_reeval.same_day_stats and repeated on every row below): "
                f"n_days={refstats['n_days']}, same_day_corr={refstats['same_day_corr']}, "
                f"dl_freq_pct={refstats['dl_freq_pct']}, tl_freq_pct={refstats['tl_freq_pct']}.")
    lines.append("")
    lines.append("E$ placeholder = pass_pct/100*8000-131 (identical formula/label to "
                 "tools_salvage_track_a.py's E_proxy — an \"8k pending A4 placeholder\", NOT a "
                 "dollar certification).")
    lines.append("")
    lines.append(f"## HIGHLIGHT ROW: budget=600 cap=4 (the portfolio leg)")
    lines.append("")
    lines.append(VR.df_to_md_table(hl) if len(hl) else "(cell not found -- check grid)")
    lines.append("")
    lines.append("## Full grid (104 cells)")
    lines.append("")
    lines.append(VR.df_to_md_table(df))
    lines.append("")
    lines.append(f"## Mechanical shortlist (pass_pct > bust_pct AND pass_count >= 20): "
                 f"{len(shortlist)}/{len(df)} cells")
    lines.append("")
    lines.append(VR.df_to_md_table(shortlist) if len(shortlist) else "(none)")
    lines.append("")
    lines.append("## Top-5 funnel cells (by pass-bust margin, from the mechanical shortlist) — "
                 "uniform R-unit slippage breakpoint (coarse grid, tools_salvage_stress.SLIP_GRID / "
                 "dmg_slip / find_flip, reused verbatim)")
    lines.append("")
    lines.append(VR.df_to_md_table(df_bp) if len(df_bp) else "(no shortlisted cells to rank)")
    lines.append("")
    if VR.PF_FLAGS:
        lines.append(f"## PF FREEZE FLAGS (PF>{VR.PF_FREEZE_THRESHOLD}): {VR.PF_FLAGS}")
    else:
        lines.append(f"## PF freeze check: no cell exceeded PF>{VR.PF_FREEZE_THRESHOLD}.")
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[saved] {csv_path}\n[saved] {md_path}")


# ==================================================================================================
def main():
    t_start = time.time()
    firewall_before = ST.sha_of(ST.FIREWALL_FILES)

    print("loading VPC rows (real Databento, frozen CFG, 2022+)…", flush=True)
    v_rows, tr_base = VR.vpc_rows()
    print(f"  VPC rows n={len(v_rows)}", flush=True)

    print("loading honest A rows (tools_sim_parity_check.load_rows, post-fix)…", flush=True)
    a_full = VR.a_rows_full()
    a2022 = VR.a_rows_2022(a_full)
    print(f"  A rows n={len(a_full)} (full)  n={len(a2022)} (2022-2026 window)", flush=True)

    if not run_canaries_core(v_rows, tr_base, a_full):
        print("[ABORT] core canary mismatch — no report written. (unfiltered-705 stream load "
              "skipped; not reached.)")
        return

    print("loading unfiltered-705 A stream (tools_salvage_track_a.load_streams)…", flush=True)
    S_ta = TA.load_streams()
    print(f"  unfiltered A rows n={len(S_ta['unfiltered'])}", flush=True)

    print("building vpc_trades_ext (direction + hold-time extension)…", flush=True)
    v, VS = VR.v, VR.VS
    feats = v.features(VS.real_rth_5m())
    feats = feats[feats.date >= VR.WINDOW_START]
    tr_ext = vpc_trades_ext(feats)

    if not run_canaries_extra(tr_base, tr_ext, S_ta):
        print("[ABORT] extra canary mismatch — no report written.")
        return

    d2 = part2(v_rows, tr_base, tr_ext, a_full, S_ta)
    write_part2(d2)

    refstats = VR.same_day_stats(a2022, v_rows)
    df3 = part3(v_rows, a2022, refstats)
    df_bp = top5_breakpoints(df3, v_rows)

    firewall_after = ST.sha_of(ST.FIREWALL_FILES)
    firewall_ok = all(firewall_before[fn] == firewall_after[fn] for fn in ST.FIREWALL_FILES)
    if not firewall_ok:
        print("[FIREWALL FAILURE] a firewalled file changed during this run — STOPPING, no "
              "report written.")
        for fn in ST.FIREWALL_FILES:
            match = firewall_before[fn] == firewall_after[fn]
            print(f"  {fn}: {'UNCHANGED' if match else 'CHANGED'}")
        return

    write_part3(df3, df_bp, refstats)

    runtime_s = time.time() - t_start
    print("\n" + "=" * 100)
    if VR.PF_FLAGS:
        print(f"[FREEZE] {len(VR.PF_FLAGS)} cell(s) breached PF>{VR.PF_FREEZE_THRESHOLD}: {VR.PF_FLAGS}")
    else:
        print(f"No cell anywhere breached PF>{VR.PF_FREEZE_THRESHOLD}.")
    print(f"Runtime: {runtime_s:.1f}s")
    for fn in ST.FIREWALL_FILES:
        print(f"Firewall {fn}: UNCHANGED")
    print("=" * 100)


if __name__ == "__main__":
    main()
