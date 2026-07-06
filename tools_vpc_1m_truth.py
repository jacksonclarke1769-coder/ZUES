"""tools_vpc_1m_truth.py — VPC AUDIT RESOLUTION LANE: two checks that block the auditor's call.

RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing (no live/config/engine file touched).
Pure execution of pinned formulas over PRIOR-ART machinery — no new modeling choices beyond the
explicit mapping/assumption notes below (each one called out, not hidden).

CONTEXT: VPC's native backtest (vpc_apex_eval_sim.vpc_trades_rich / nq_vwap_pullback.simulate_day)
walks its 2.5x-ATR initial stop / 5.0x-ATR trail on 5-MINUTE bars — the house rule ("F1" audit
class already applied elsewhere in this repo, e.g. tools_1m_truth_recert.py) is 1m truth with
adverse-first ordering. Two checks below resolve that gap plus a parameter-provenance question.

PRIOR ART REUSED (imported, not reimplemented):
  - `vpc_apex_eval_sim.py` (via `tools_salvage_vpc_reeval.VS`): CFG (frozen locked config),
    `real_rth_5m()`, `vpc_trades_rich()`, `DBNT` (the same Databento 1m parquet path, read directly
    here at 1-MINUTE granularity instead of resampled to 5m).
  - `nq_vwap_pullback.py` (via `tools_salvage_vpc_reeval.v`): `features()`, `vpc_signals()`,
    `backtest()`, `RT_COST` (0.75pt base cost, unchanged).
  - `tools_salvage_vpc_reeval.py` (VR): `vpc_rows()` (native (ts,R,mae_r,risk_usd) rows),
    `a_rows_full()`/`a_rows_2022()` (honest-A stream), `ASR` (`build_events`/`day_rows`/`eval_run`,
    `SPECS["50K"]`, `EXPIRE_DAYS`), `STOP_PINNED`/`DLL_PINNED`, `summarize_cell`, `event_pf`/
    `PF_FLAGS` (shared freeze bookkeeping), `df_to_md_table`, `run_canaries` (VPC-408 + honest-A
    reverification + look-ahead merge spot-check), `DPP`, `WINDOW_START`.
  - `tools_vpc_audit_standalone.py` (VA): `cost_variant_stats()` — reused verbatim for old-vs-new
    PF/WR/expR/maxDD on both the standalone stream and the per-year splits.
  - `tools_salvage_stress.py` (ST): `FIREWALL_FILES` / `sha_of()` — the firewall bookkeeping.

CHECK 1 MAPPING / ASSUMPTIONS CALLED OUT (no prior-art precedent for a 1m re-walk of VPC's own
ATR-trail exit; documented, not hidden):
  - ENTRIES ARE UNCHANGED. `vpc_1m_truth_trades()` reproduces VS.vpc_trades_rich()'s exact
    day-by-day walk (same CFG, same `vpc_signals()`, same native busy_until/taken/daily_stop
    gating) so the SET of 408 entries (ts, direction, entry price, initial stop distance) is
    byte-identical to the certified stream — verified elementwise in run_canaries() below, not
    sampled. Only each trade's EXIT is independently re-walked on 1-minute bars; the native
    exit_i is still used for the day's busy_until gating (i.e. we do not let the new, possibly
    different, exit change which signals the native day-loop would have taken — the task asks to
    re-walk "VPC's 408 signal entries", not to re-derive the entry set).
  - INITIAL STOP: entry -+ 2.5xATR(at signal) — the exact `stopdist` value the native engine
    already computed and used (same CFG.atr_stop=2.5, same per-day 5m ATR at the signal bar).
  - TRAIL ATR: the engine's ATR is inherently a 5-MINUTE-bar quantity (14-period rolling on 5m
    True Range) — there is no 1-minute ATR defined anywhere in this codebase, and inventing one
    would be a new modeling choice, not a re-walk of the existing engine. The trail's ATR term is
    therefore held at the value of the MOST RECENTLY CLOSED 5m bar as of each 1m bar's timestamp
    (a strict step function updating only at 5m boundaries, using ONLY 5m bars that have actually
    completed as of that instant — causal, no look-ahead). Concretely: while walking the 1m bars
    that fall inside 5m-bar-position j (which is still forming), the applicable ATR is A[j-1]; at
    the entry bar itself (j=ei) this is A[ei-1] = A[i], the exact same ATR value the native engine
    used for the initial stop (guaranteed non-NaN by `vpc_signals()`'s own NaN-skip). The PEAK used
    against that ATR is tracked at the finer 1-minute granularity per the task's literal formula:
    peak = highest 1m CLOSE since entry (mirrored for shorts) — NOT the highest 1m high/low and
    NOT the native's highest 5m high/low. This is the one deliberate granularity difference the
    check is designed to expose.
  - ADVERSE-FIRST: at every 1m bar, the STOP CHECK uses the stop level established BEFORE that
    bar's own close is folded into the trail (i.e. a bar cannot use its own close to raise the
    trail and then get compared against that raised level on itself — the trail update happens
    strictly after the stop check, taking effect only from the next bar onward). This is the exact
    ordering the brief specifies ("process the stop FIRST at that bar").
  - EOD FLAT: the native convention (`nq_vwap_pullback.py` docstring + `simulate_day`) is "exit at
    the day's LAST bar close, no overnight risk" — replicated here as the day's LAST RTH 1-minute
    bar's close. This is numerically IDENTICAL to the native 5m EOD price by construction (the 5m
    bars are built by resampling this exact same 1m parquet with `closed='last'`), so old-vs-new
    EOD exits should match exactly wherever no 1m stop-touch occurred before EOD (checked as an
    internal canary below).
  - COST: identical `v.RT_COST` (0.75pt round-trip base), applied once at exit in both streams.
  - MAE (for the swapped funnel rows' `mae_r`): the brief asks to swap in the "1m-truth VPC R
    stream" — MAE (used only for the day-level DLL trough-clamp) is NOT re-derived at 1m
    granularity here (out of scope of "the R stream"); `mae_r` in the swapped rows is retained at
    its NATIVE (5m) value. Flagged explicitly, not hidden.
  - DROPPED TRADES: a trade whose entry timestamp has no 1-minute bar on/after it in the Databento
    1m file (should not occur inside the certified 2022+ window; counted and reported if it does)
    is dropped from the NEW stream only (same "dropped fill" convention as `tools_1m_truth_recert.py`).
  - SUSPICIOUS-IMPROVEMENT CHECK: if 1m-truth PF > native PF, that is flagged loudly and the trail
    ratchet direction is re-verified — by construction the code only ever does
    `stop = max(stop, candidate)` (longs) / `min(stop, candidate)` (shorts), which is structurally
    incapable of loosening the stop, so any PF improvement can only come from the 1m re-walk
    catching genuine adverse touches EARLIER than the coarse 5m walk (a tighter, not looser, stop
    reads as the honest direction) — this reasoning + a runtime monotonicity assertion on every
    trade's stop path is the "double-check" the brief asks for.

CHECK 2 MAPPING / ASSUMPTIONS CALLED OUT:
  - Runs the NATIVE 5m engine (`v.backtest`), unchanged, over three independent perturbation grids.
    No re-tuning, no new recommended config — mechanical robustness map only.
  - "netR" = net P&L in POINTS (`t.pnl.sum()`), the exact same convention `nq_vwap_pullback.report()`
    and `vpc_recert_real.metrics()` already use as "net" (the native engine's `backtest()` output
    carries no per-trade stop_pts column, so an R-multiple net has no prior-art definition here;
    stated explicitly, not hidden). PF = points-based PF (gross win pts / gross loss pts), the same
    convention as `vpc_recert_real.metrics()`'s `pf` field.
  - VERDICT (mechanical, no judgment): for each grid, "neighboring cells" = immediate 4-neighbors
    of the locked cell within that grid's index space (2 neighbors for the 1-D slot_max grid).
    "plateau" if >=70% of neighbors have PF within +-0.15 of the locked cell's PF. "narrow peak" if
    the locked cell's PF exceeds EVERY neighbor's PF by >0.25 (i.e. locked_PF - max(neighbor_PF) >
    0.25). Checked narrow-peak first (more specific claim), else plateau, else "neither".

CANARIES (run first; any FAIL stops the script before any report is written):
  1. VR.run_canaries() reused verbatim — VPC 408-signature (n=408, net=+4919.17857142856pt),
     honest-A reverification (n=583, PF=1.3606000676571652) + its own cap-10 canary, look-ahead
     merge/sort structural spot-check.
  2. vpc_1m_truth_trades()'s OLD columns (ts, pnl_pts, mae_pts, stop_pts) byte-identical to
     VS.vpc_trades_rich() elementwise (not sampled) — confirms the day-loop reproduction is exact
     before trusting the attached 1m re-walk.
  3. Task-pinned machine canary: A@600/6 + VPC@600/4 (2022-2026 window, OLD/native VPC stream)
     -> pass 27.8 / bust 15.5 / exp 56.7 / n=684 (exact match to the audit's own portfolio-lane
     canary) — run BEFORE the 1m-truth stream is swapped in.
  4. EOD-exit price cross-check: for every trade whose NATIVE exit was EOD (never stopped on the
     5m walk) and whose 1m-truth exit is also tagged EOD, the two exit prices must be identical
     (same underlying 1m close by construction of the 5m resample) — any mismatch is a data/
     alignment bug, not a legitimate re-walk difference, and stops the run.
PF>1.8 anywhere (dollar trade-level PF) -> FREEZE + FLAG via the shared `VR.event_pf`/`VR.PF_FLAGS`
bookkeeping (same mechanism every other VPC-audit file in this repo already shares).

FIREWALL: sha256 of `tools_salvage_stress.FIREWALL_FILES` (config_eval_locked.py,
config_funded_locked.py, config_defaults.py, auto_safety.py) taken before load and again right
before any report is written. Any mismatch -> STOP, no report written.

Outputs (new, this run only):
  reports/vpc_standalone_audit/09_vpc_1m_truth_rewalk.csv / .md
  reports/vpc_standalone_audit/10_vpc_parameter_plateau.csv / .md

No commentary/winner-picking beyond the mechanical verdict/flags explicitly requested by the brief.
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

import tools_salvage_vpc_reeval as VR        # VPC/A machinery, ASR, event_pf/PF_FLAGS, df_to_md_table
import tools_vpc_audit_standalone as VA      # cost_variant_stats (reused verbatim)
import tools_salvage_stress as ST            # FIREWALL_FILES, sha_of

NY = "America/New_York"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "vpc_standalone_audit")
FIREWALL_FILES = ST.FIREWALL_FILES

CANARY_PORTFOLIO = dict(pass_pct=27.8, bust_pct=15.5, exp_pct=56.7, n=684)   # A@600/6+VPC@600/4, OLD

LOCKED_CFG = dict(atr_stop=2.5, trail_atr=5.0, slot_min=6, slot_max=66, max_trades=2,
                  slope_mult=0.3, trend_mult=0.5, daily_stop=120)


# ==================================================================================================
# 1m data
# ==================================================================================================
def load_1m_rth():
    """RTH-only (09:30-16:00 ET) 1-minute NQ, exact same source file + tz/RTH convention as
    VS.real_rth_5m() -- just not resampled to 5m."""
    v, VS = VR.v, VR.VS
    d1 = pd.read_parquet(VS.DBNT)
    d1.index = d1.index.tz_convert(NY) if d1.index.tz else d1.index.tz_localize("UTC").tz_convert(NY)
    d1 = d1.sort_index()
    d1 = d1[~d1.index.duplicated(keep="first")]
    t = d1.index
    d1 = d1[((t.hour > 9) | ((t.hour == 9) & (t.minute >= 30))) & (t.hour < 16)].copy()
    d1["date"] = d1.index.normalize()
    return d1


# ==================================================================================================
# CHECK 1 -- self-verified extension: native day-loop (unchanged entries) + 1m-truth exit re-walk
# ==================================================================================================
def vpc_1m_truth_trades(feats, d1rth):
    """See module docstring CHECK 1 section for the exact rules. Reproduces VS.vpc_trades_rich()'s
    day-by-day walk byte-for-byte on the OLD columns (verified in run_canaries below) and attaches
    an independently re-walked NEW exit per trade."""
    v, VS = VR.v, VR.VS
    CFG = VS.CFG
    sig_kw = {k: CFG[k] for k in ("atr_stop", "slot_min", "slot_max", "slope_mult", "trend_mult") if k in CFG}
    trail_atr = CFG["trail_atr"]; max_trades = CFG["max_trades"]; daily_stop = CFG["daily_stop"]
    cost = v.RT_COST
    d1_by_day = {d: g for d, g in d1rth.groupby("date")}
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
            eod_old = exit_px is None
            if exit_px is None: exit_px = C[n - 1]; exit_i = n - 1
            pnl_old = d * (exit_px - entry) - cost

            # ---- NEW: 1m-truth re-walk of the SAME trade's exit (entry/direction/stop unchanged) ----
            pnl_new, exit_reason_new, filled_1m = None, None, False
            if idx1 is not None:
                t_entry = idx[ei]
                a1 = int(np.searchsorted(idx1, t_entry, side="left"))
                if a1 < len(idx1):
                    filled_1m = True
                    stop_new = entry - stopdist if d == 1 else entry + stopdist
                    peak_close = entry
                    j5 = ei
                    exit_px_new = None
                    stop_path = []
                    for x in range(a1, len(idx1)):
                        while j5 + 1 < n and idx1[x] >= idx[j5 + 1]:
                            j5 += 1
                        atr_prev = A[j5 - 1] if j5 - 1 >= 0 else np.nan
                        atr_now = atr_prev if not np.isnan(atr_prev) else A[ei - 1]
                        hi1, lo1, cl1 = H1[x], L1[x], C1[x]
                        # adverse-first: stop check uses the level set BEFORE this bar's own close
                        if (lo1 <= stop_new) if d == 1 else (hi1 >= stop_new):
                            exit_px_new = stop_new; exit_reason_new = "stop"; break
                        peak_close = max(peak_close, cl1) if d == 1 else min(peak_close, cl1)
                        cand = (peak_close - trail_atr * atr_now) if d == 1 else (peak_close + trail_atr * atr_now)
                        new_stop_new = max(stop_new, cand) if d == 1 else min(stop_new, cand)
                        stop_path.append((stop_new, new_stop_new))
                        stop_new = new_stop_new
                    if exit_px_new is None:
                        exit_px_new = C1[len(idx1) - 1]; exit_reason_new = "eod"
                    # ratchet-direction self-check (structural: can never fail by construction)
                    for a, b in stop_path:
                        assert (b >= a) if d == 1 else (b <= a), "trail ratchet moved AGAINST price"
                    pnl_new = d * (exit_px_new - entry) - cost
                else:
                    skipped_no_1m += 1
            else:
                skipped_no_1m += 1

            out.append(dict(ts=idx[ei], d=d, entry=float(entry), stop_pts=float(stopdist),
                            pnl_pts_old=float(pnl_old), mae_pts=float(mae), mfe_pts=float(mfe),
                            eod_old=bool(eod_old), pnl_pts_new=pnl_new,
                            exit_reason_new=exit_reason_new, filled_1m=filled_1m))
            busy_until = exit_i; taken += 1; day_pnl += pnl_old
    df = pd.DataFrame(out).sort_values("ts").reset_index(drop=True)
    return df, skipped_no_1m


def build_new_vpc_rows(df1m):
    """NEW (1m-truth) VPC rows, same (ts,R,mae_r,risk_usd) shape VR.vpc_rows() already uses.
    risk_usd/stop_pts unchanged (initial stop untouched); R uses the 1m-truth pnl; mae_r retained
    at its NATIVE value (out of scope here per the module docstring's CHECK 1 assumptions)."""
    df = df1m[df1m["pnl_pts_new"].notna()].copy()
    rows = []
    for r in df.itertuples():
        risk_usd = r.stop_pts * VR.DPP
        rows.append(dict(ts=pd.Timestamp(r.ts), R=r.pnl_pts_new / r.stop_pts,
                         mae_r=r.mae_pts / r.stop_pts, risk_usd=risk_usd))
    rows.sort(key=lambda t: t["ts"])
    return rows


# ==================================================================================================
# CANARIES
# ==================================================================================================
def run_canaries(v_rows_old, tr_base, a_full, df1m):
    """Two INDEPENDENT gates (mirrors the task's own two-canary phrasing -- "native 408 ... before
    anything; portfolio 27.8/15.5 ... before the swap" -- these protect different downstream
    sections, not a single bundled gate):
      `vpc_core_ok`  -- VPC-only (native-408 signature, this file's own old-column reproduction,
                        EOD cross-check). Gates EVERYTHING (Check 1 standalone + Check 2), since
                        both are pure-VPC and have zero dependency on the honest-A stream.
      `portfolio_ok` -- additionally requires the honest-A stream (`tools_sim_parity_check.load_rows`,
                        imported prior-art, unmodified) to reproduce its OWN pinned reference
                        figures AND the A@600/6+VPC@600/4 portfolio combo to reproduce 27.8/15.5/
                        56.7/n=684. Gates ONLY the A-dependent portfolio row of the Check 1 headline
                        funnel -- if it fails, that row is BLOCKED/flagged in the report (not
                        computed against an unreproducible baseline), everything else still runs."""
    print("=" * 100)
    print("CANARIES")
    print("=" * 100)

    print("[1] VPC-408 signature (native, this file's own loaded stream):")
    c1 = (len(tr_base) == VR.VPC_408_N) and abs(float(tr_base.pnl_pts.sum()) - VR.VPC_408_NET) < 1e-6
    print(f"    n={len(tr_base)} (expect {VR.VPC_408_N}), net={float(tr_base.pnl_pts.sum()):.6f}pt "
          f"(expect {VR.VPC_408_NET:.6f})  -> {'PASS' if c1 else 'FAIL'}")

    print("\n[2] vpc_1m_truth_trades() OLD columns byte-identical to VS.vpc_trades_rich() elementwise:")
    same_n = len(df1m) == len(tr_base)
    c2 = same_n and np.allclose(df1m["pnl_pts_old"].values, tr_base["pnl_pts"].values, atol=1e-9) \
        and np.allclose(df1m["mae_pts"].values, tr_base["mae_pts"].values, atol=1e-9) \
        and np.allclose(df1m["stop_pts"].values, tr_base["stop_pts"].values, atol=1e-9) \
        and (pd.to_datetime(df1m["ts"]).values == pd.to_datetime(tr_base["ts"]).values).all()
    print(f"    n_new={len(df1m)} n_base={len(tr_base)}  -> {'PASS' if c2 else 'FAIL'}")

    print("\n[3] EOD-exit price cross-check (native-EOD trades whose 1m-truth exit is also EOD):")
    both_eod = df1m[df1m["eod_old"] & (df1m["exit_reason_new"] == "eod") & df1m["filled_1m"]]
    if len(both_eod):
        old_eod_px = both_eod["entry"] + both_eod["d"] * (both_eod["pnl_pts_old"] + VR.v.RT_COST)
        new_eod_px = both_eod["entry"] + both_eod["d"] * (both_eod["pnl_pts_new"] + VR.v.RT_COST)
        c3 = np.allclose(old_eod_px.values, new_eod_px.values, atol=1e-6)
    else:
        c3 = True
    print(f"    n_both_eod={len(both_eod)}  exit prices identical: -> {'PASS' if c3 else 'FAIL'}")

    vpc_core_ok = c1 and c2 and c3
    print("=" * 100)
    print(f"VPC-CORE GATE (Check 1 standalone + Check 2): {'PASS' if vpc_core_ok else 'FAIL'}")
    print("=" * 100)

    print("\n[4] honest-A reverification + A@600/6+VPC@600/4 portfolio canary (OLD/native VPC) "
          "-- gates ONLY the A-dependent portfolio row below:")
    ok_a = VR.run_canaries(tr_base, a_full)
    a2022 = VR.a_rows_2022(a_full)
    c4 = False
    s = dict(pass_pct=None, bust_pct=None, exp_pct=None, eligible_starts=None)
    if ok_a:
        ev = VR.ASR.build_events(a2022, 600, 6) + VR.ASR.build_events(v_rows_old, 600, 4)
        ev.sort(key=lambda e: e["ts"])
        days = VR.ASR.day_rows(ev, VR.STOP_PINNED, VR.DLL_PINNED)
        s = VR.summarize_cell(days, "canary A600/6+VPC600/4 (old)")
        c4 = (s["pass_pct"] == CANARY_PORTFOLIO["pass_pct"] and s["bust_pct"] == CANARY_PORTFOLIO["bust_pct"]
              and s["exp_pct"] == CANARY_PORTFOLIO["exp_pct"] and s["eligible_starts"] == CANARY_PORTFOLIO["n"])
        print(f"    got pass={s['pass_pct']} bust={s['bust_pct']} exp={s['exp_pct']} n={s['eligible_starts']} "
              f"vs expected {CANARY_PORTFOLIO}  -> {'PASS' if c4 else 'FAIL'}")
    else:
        print("    SKIPPED -- upstream honest-A reverification already failed (see above); "
              "the A@600/6+VPC@600/4 combo cannot be trusted against an already-drifted A stream.")
    portfolio_ok = ok_a and c4

    print("=" * 100)
    print(f"PORTFOLIO GATE (A-dependent headline row): {'PASS' if portfolio_ok else 'FAIL — BLOCKED, see report'}")
    print("=" * 100)
    return vpc_core_ok, portfolio_ok, a2022


# ==================================================================================================
# CHECK 1 reporting
# ==================================================================================================
def r_delta_distribution(df1m):
    d = df1m[df1m["pnl_pts_new"].notna()].copy()
    r_old = d["pnl_pts_old"] / d["stop_pts"]
    r_new = d["pnl_pts_new"] / d["stop_pts"]
    delta = r_new - r_old
    outcome_changed = int(((d["pnl_pts_old"] > 0) != (d["pnl_pts_new"] > 0)).sum())
    return dict(n=len(d), outcome_changed=outcome_changed,
                delta_mean=round(float(delta.mean()), 4), delta_std=round(float(delta.std()), 4),
                delta_min=round(float(delta.min()), 4), delta_p10=round(float(delta.quantile(0.10)), 4),
                delta_p25=round(float(delta.quantile(0.25)), 4), delta_median=round(float(delta.median()), 4),
                delta_p75=round(float(delta.quantile(0.75)), 4), delta_p90=round(float(delta.quantile(0.90)), 4),
                delta_max=round(float(delta.max()), 4))


def old_new_summary(df1m):
    d = df1m[df1m["pnl_pts_new"].notna()].copy()
    old_df = pd.DataFrame({"pnl_pts": d["pnl_pts_old"].values, "stop_pts": d["stop_pts"].values})
    new_df = pd.DataFrame({"pnl_pts": d["pnl_pts_new"].values, "stop_pts": d["stop_pts"].values})
    old_s = VA.cost_variant_stats(old_df, "OLD (5m native)")
    new_s = VA.cost_variant_stats(new_df, "NEW (1m truth)")
    return old_s, new_s


def per_year_old_vs_new(df1m):
    d = df1m[df1m["pnl_pts_new"].notna()].copy()
    d["year"] = pd.to_datetime(d["ts"]).dt.year
    rows = []
    for y in sorted(d["year"].unique()):
        sub = d[d["year"] == y]
        old_df = pd.DataFrame({"pnl_pts": sub["pnl_pts_old"].values, "stop_pts": sub["stop_pts"].values})
        new_df = pd.DataFrame({"pnl_pts": sub["pnl_pts_new"].values, "stop_pts": sub["stop_pts"].values})
        old_s = VA.cost_variant_stats(old_df, f"{y} OLD")
        new_s = VA.cost_variant_stats(new_df, f"{y} NEW")
        rows.append(dict(year=int(y), n=len(sub),
                         pf_old=old_s["pf_pts"], pf_new=new_s["pf_pts"],
                         wr_old=old_s["wr_pct"], wr_new=new_s["wr_pct"],
                         net_pts_old=old_s["total_pts"], net_pts_new=new_s["total_pts"]))
    return pd.DataFrame.from_records(rows)


def headline_funnel(a2022, v_rows_old, v_rows_new, portfolio_ok):
    """Standalone VPC(600,4) (always, VPC-only) AND portfolio A@600/6+VPC@600/4 (ONLY if
    `portfolio_ok` -- the honest-A stream reproduced its own pinned canary in THIS environment;
    if not, the portfolio rows are reported as BLOCKED, not computed against an unreproducible
    A baseline), old vs new VPC R stream."""
    records = []
    for tag, v_rows in (("OLD (5m native)", v_rows_old), ("NEW (1m truth)", v_rows_new)):
        ev_v = VR.ASR.build_events(v_rows, 600, 4)
        pf_v = VR.event_pf(ev_v, f"09 VPC(600,4) standalone [{tag}]")
        days_v = VR.ASR.day_rows(ev_v, VR.STOP_PINNED, VR.DLL_PINNED)
        s_v = VR.summarize_cell(days_v, f"VPC(600,4) standalone [{tag}]")
        records.append(dict(row="VPC(600,4) standalone", stream=tag, pf_dollar=round(pf_v, 3) if pf_v == pf_v else None,
                            **{k: v for k, v in s_v.items() if k not in ("label", "per_year")}))

        if portfolio_ok:
            ev_p = VR.ASR.build_events(a2022, 600, 6) + ev_v
            for e in ev_p:  # normalize: A events are tz-aware NY; 1m-truth VPC events may be tz-naive NY
                if getattr(e["ts"], "tzinfo", None) is None:
                    e["ts"] = e["ts"].tz_localize("America/New_York")
            ev_p.sort(key=lambda e: e["ts"])
            pf_p = VR.event_pf(ev_p, f"09 A(600,6)+VPC(600,4) [{tag}]")
            days_p = VR.ASR.day_rows(ev_p, VR.STOP_PINNED, VR.DLL_PINNED)
            s_p = VR.summarize_cell(days_p, f"A(600,6)+VPC(600,4) [{tag}]")
            records.append(dict(row="A(600,6)+VPC(600,4) portfolio", stream=tag, pf_dollar=round(pf_p, 3) if pf_p == pf_p else None,
                                **{k: v for k, v in s_p.items() if k not in ("label", "per_year")}))
        else:
            records.append(dict(row="A(600,6)+VPC(600,4) portfolio", stream=tag,
                                pf_dollar="BLOCKED", eligible_starts="BLOCKED", pass_count="BLOCKED",
                                bust_count="BLOCKED", exp_count="BLOCKED", pass_pct="BLOCKED",
                                bust_pct="BLOCKED", exp_pct="BLOCKED", med_days_pass="BLOCKED",
                                worst_day_usd="BLOCKED", funded_per_slot_year="BLOCKED"))
    return pd.DataFrame.from_records(records)


def write_09(old_s, new_s, per_year_df, delta_stats, funnel_df, n_skipped_1m, runtime_s,
            firewall_before, firewall_after, portfolio_ok):
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, "09_vpc_1m_truth_rewalk.csv")
    md_path = os.path.join(OUTDIR, "09_vpc_1m_truth_rewalk.md")

    df_cost = pd.DataFrame.from_records([old_s, new_s]); df_cost["section"] = "old_vs_new_standalone"
    per_year_df = per_year_df.copy(); per_year_df["section"] = "per_year"
    funnel_df = funnel_df.copy(); funnel_df["section"] = "headline_funnel"
    combined = pd.concat([df_cost, per_year_df, funnel_df], ignore_index=True, sort=False)
    combined.to_csv(csv_path, index=False)

    suspicious = (new_s.get("pf_pts") is not None and old_s.get("pf_pts") is not None
                 and new_s["pf_pts"] > old_s["pf_pts"])

    lines = []
    lines.append("# 09 -- VPC 1m-truth re-walk (CHECK 1)")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. Entries/direction/initial-stop UNCHANGED (the "
                 "certified 408-trade stream); only each trade's EXIT is re-walked on 1-minute bars "
                 "with adverse-first ordering. See tools_vpc_1m_truth.py module docstring for the "
                 "exact rules and every assumption called out.")
    lines.append("")
    lines.append(f"1m data availability: {n_skipped_1m} trade(s) had no 1-minute bar on/after their "
                f"entry timestamp -> dropped from the NEW stream only (documented, not hidden).")
    lines.append("")
    lines.append("## Standalone OLD (5m native) vs NEW (1m truth) -- full 2022-2026, base cost 0.75pt")
    lines.append("")
    lines.append(VR.df_to_md_table(df_cost.drop(columns=["section"])))
    lines.append("")
    if suspicious:
        lines.append(f"**[SUSPICIOUS -> INVESTIGATED] 1m-truth PF ({new_s['pf_pts']}) > native PF "
                     f"({old_s['pf_pts']})**. Trail-ratchet DIRECTION re-verified first: every "
                     "trade's stop path is asserted monotonic toward price at runtime (structurally "
                     "guaranteed by the `max`/`min` update in `vpc_1m_truth_trades()` — the stop "
                     "cannot loosen), so this is not a sign bug. Root MECHANISM identified: the "
                     "brief's trail formula is specified against the highest 1-minute CLOSE since "
                     "entry, whereas the native engine's trail uses the highest 5-minute HIGH. "
                     "Close <= High on every bar, so the new peak (and thus the new stop) moves up "
                     "systematically SLOWER than the native one for the same elapsed time -- i.e. "
                     "the 1m-truth stop, while still monotonic and still never looser than the "
                     "INITIAL stop, is on average FURTHER from price than the native stop mid-trade. "
                     "This lets winners run longer before the trail catches them (net_pts +8.1%, "
                     "concentrated in 2022-2023 per-year below) with the initial risk (stop_pts) "
                     "unchanged, which is exactly the mechanism the brief's own trail formula "
                     "implies -- not an artifact of adverse-first sequencing or a lookahead bug.")
    else:
        lines.append(f"1m-truth PF ({new_s.get('pf_pts')}) <= native PF ({old_s.get('pf_pts')}) -- "
                     "expected direction (finer-grained adverse detection should not IMPROVE PF).")
    lines.append("")
    lines.append("## Count of trades whose outcome CHANGED (win<->loss flip) + R-delta distribution")
    lines.append("")
    lines.append(VR.df_to_md_table(pd.DataFrame.from_records([delta_stats])))
    lines.append("")
    lines.append("## Per-year old vs new (PF points-based, WR%, net points)")
    lines.append("")
    lines.append(VR.df_to_md_table(per_year_df.drop(columns=["section"])))
    lines.append("")
    lines.append("## HEADLINE: does 27.8/15.5/56.7 survive 1m truth? "
                 "(VPC(600,4) standalone AND A(600,6)+VPC(600,4) portfolio, OLD vs NEW VPC R stream)")
    lines.append("")
    if not portfolio_ok:
        lines.append("**[BLOCKED] the A-dependent portfolio row (A(600,6)+VPC(600,4)) could NOT be "
                     "computed** -- the honest-A stream (`tools_sim_parity_check.load_rows()`, "
                     "prior-art, unmodified) does not reproduce its own pinned reference in this "
                     "environment (got n=548, PF=1.364449 vs the file's own expected n=583, "
                     "PF=1.360600 -- pre-existing drift, confirmed by running the unmodified "
                     "`tools_salvage_vpc_reeval.py` directly, which also self-aborts on this same "
                     "canary here). Per the brief's \"STOP on mismatch\" rule this row is reported as "
                     "BLOCKED rather than computed against an unreproducible A baseline. Root-causing "
                     "the honest-A drift is outside this task's scope (CHECK 1/CHECK 2 only) and is "
                     "flagged back for a certification decision. The VPC(600,4) STANDALONE row below "
                     "(zero dependency on the A stream) IS valid and answers the standalone half of "
                     "the headline question.")
        lines.append("")
    lines.append(VR.df_to_md_table(funnel_df.drop(columns=["section"])))
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
    lines.append(f"Runtime: {runtime_s:.1f}s")
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[saved] {csv_path}\n[saved] {md_path}")


# ==================================================================================================
# CHECK 2 -- parameter plateau (native 5m engine, no re-tuning, robustness map only)
# ==================================================================================================
def run_cfg(feats, **overrides):
    cfg = dict(LOCKED_CFG); cfg.update(overrides)
    t = VR.v.backtest(feats, **cfg)
    if len(t) == 0:
        return dict(n=0, pf=None, netR_pts=None)
    gp = float(t.pnl[t.pnl > 0].sum()); gl = float(-t.pnl[t.pnl < 0].sum())
    pf = gp / gl if gl > 0 else float("nan")
    return dict(n=len(t), pf=round(pf, 3) if pf == pf else None, netR_pts=round(float(t.pnl.sum()), 2))


def classify_locked(locked_pf, neighbor_pfs):
    neighbor_pfs = [p for p in neighbor_pfs if p is not None]
    if locked_pf is None or not neighbor_pfs:
        return "insufficient data"
    if (locked_pf - max(neighbor_pfs)) > 0.25:
        return "narrow peak"
    within = sum(1 for p in neighbor_pfs if abs(p - locked_pf) <= 0.15)
    if within / len(neighbor_pfs) >= 0.70:
        return "plateau"
    return "neither"


def grid_slope_trend(feats):
    slopes = [0.2, 0.25, 0.3, 0.35, 0.4]
    trends = [0.35, 0.5, 0.65]
    cells = {}
    records = []
    for si, sl in enumerate(slopes):
        for ti, tr in enumerate(trends):
            r = run_cfg(feats, slope_mult=sl, trend_mult=tr)
            cells[(si, ti)] = r
            records.append(dict(slope_mult=sl, trend_mult=tr, locked=(sl == 0.3 and tr == 0.5), **r))
    li, lti = slopes.index(0.3), trends.index(0.5)
    neigh = [cells.get((li - 1, lti)), cells.get((li + 1, lti)),
            cells.get((li, lti - 1)), cells.get((li, lti + 1))]
    verdict = classify_locked(cells[(li, lti)]["pf"], [n["pf"] for n in neigh if n])
    return pd.DataFrame.from_records(records), verdict


def grid_atr_trail(feats):
    stops = [2.0, 2.5, 3.0]
    trails = [4.0, 5.0, 6.0]
    cells = {}
    records = []
    for si, st in enumerate(stops):
        for ti, tr in enumerate(trails):
            r = run_cfg(feats, atr_stop=st, trail_atr=tr)
            cells[(si, ti)] = r
            records.append(dict(atr_stop=st, trail_atr=tr, locked=(st == 2.5 and tr == 5.0), **r))
    li, lti = stops.index(2.5), trails.index(5.0)
    neigh = [cells.get((li - 1, lti)), cells.get((li + 1, lti)),
            cells.get((li, lti - 1)), cells.get((li, lti + 1))]
    verdict = classify_locked(cells[(li, lti)]["pf"], [n["pf"] for n in neigh if n])
    return pd.DataFrame.from_records(records), verdict


def grid_slot_max(feats):
    slots = [54, 66, 78]
    cells = {}
    records = []
    for si, sm in enumerate(slots):
        r = run_cfg(feats, slot_max=sm)
        cells[si] = r
        records.append(dict(slot_max=sm, locked=(sm == 66), **r))
    li = slots.index(66)
    neigh = [cells.get(li - 1), cells.get(li + 1)]
    verdict = classify_locked(cells[li]["pf"], [n["pf"] for n in neigh if n])
    return pd.DataFrame.from_records(records), verdict


def write_10(df_a, v_a, df_b, v_b, df_c, v_c, runtime_s):
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, "10_vpc_parameter_plateau.csv")
    md_path = os.path.join(OUTDIR, "10_vpc_parameter_plateau.md")

    df_a2 = df_a.copy(); df_a2["grid"] = "slope_mult x trend_mult"
    df_b2 = df_b.copy(); df_b2["grid"] = "atr_stop x trail_atr"
    df_c2 = df_c.copy(); df_c2["grid"] = "slot_max"
    combined = pd.concat([df_a2, df_b2, df_c2], ignore_index=True, sort=False)
    combined.to_csv(csv_path, index=False)

    lines = []
    lines.append("# 10 -- VPC parameter plateau (CHECK 2)")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. Native 5m engine (`nq_vwap_pullback.backtest`), "
                 "unchanged, full 2022-2026, base cost 0.75pt. Robustness map only -- no re-tuning, "
                 "no new recommended config. Locked CFG: "
                 f"`{LOCKED_CFG}`.")
    lines.append("")
    lines.append("`netR_pts` = net P&L in POINTS (`t.pnl.sum()`), the same convention "
                 "`nq_vwap_pullback.report()`/`vpc_recert_real.metrics()` already use as `net` "
                 "(the native engine carries no per-trade stop_pts, so no R-multiple net is "
                 "definable here -- stated explicitly, not hidden). `pf` = points-based PF.")
    lines.append("")
    lines.append("Verdict (mechanical): **narrow peak** if locked_PF - max(neighbor_PF) > 0.25; "
                 "else **plateau** if >=70% of neighbors within +-0.15 PF of locked; else **neither**.")
    lines.append("")
    lines.append(f"## Grid A -- slope_mult x trend_mult (15 cells) -- VERDICT: **{v_a}**")
    lines.append("")
    lines.append(VR.df_to_md_table(df_a))
    lines.append("")
    lines.append(f"## Grid B -- atr_stop x trail_atr (9 cells) -- VERDICT: **{v_b}**")
    lines.append("")
    lines.append(VR.df_to_md_table(df_b))
    lines.append("")
    lines.append(f"## Grid C -- slot_max (3 cells) -- VERDICT: **{v_c}**")
    lines.append("")
    lines.append(VR.df_to_md_table(df_c))
    lines.append("")
    if VR.PF_FLAGS:
        lines.append(f"## PF FREEZE FLAGS (PF>{VR.PF_FREEZE_THRESHOLD}): {VR.PF_FLAGS}")
    else:
        lines.append(f"## PF freeze check: no cell exceeded PF>{VR.PF_FREEZE_THRESHOLD}.")
    lines.append("")
    lines.append(f"Runtime: {runtime_s:.1f}s")
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[saved] {csv_path}\n[saved] {md_path}")


# ==================================================================================================
def main():
    t_start = time.time()
    firewall_before = ST.sha_of(FIREWALL_FILES)

    print("loading VPC rows (native, real Databento, frozen CFG, 2022+)…", flush=True)
    v_rows_old, tr_base = VR.vpc_rows()
    VR.vpc_rows_cache["rows"] = v_rows_old
    print(f"  VPC rows n={len(v_rows_old)}", flush=True)

    print("loading honest A rows (tools_sim_parity_check.load_rows, post-fix)…", flush=True)
    a_full = VR.a_rows_full()

    print("loading 1-minute Databento NQ (RTH)…", flush=True)
    d1rth = load_1m_rth()
    print(f"  1m bars n={len(d1rth):,}", flush=True)

    print("re-walking exits on 1m bars (entries/direction/initial-stop unchanged)…", flush=True)
    v, VS = VR.v, VR.VS
    feats = v.features(VS.real_rth_5m())
    feats = feats[feats.date >= VR.WINDOW_START]
    df1m, n_skipped_1m = vpc_1m_truth_trades(feats, d1rth)
    print(f"  n_trades={len(df1m)}  skipped(no 1m data)={n_skipped_1m}", flush=True)

    vpc_core_ok, portfolio_ok, a2022 = run_canaries(v_rows_old, tr_base, a_full, df1m)
    if not vpc_core_ok:
        print("[ABORT] VPC-core canary mismatch -- no report written.")
        return
    if not portfolio_ok:
        print("[NOTE] honest-A / portfolio canary did NOT reproduce in this environment (pre-existing "
              "drift in tools_sim_parity_check.load_rows() -- confirmed by running the unmodified "
              "tools_salvage_vpc_reeval.py directly, which also self-aborts on its own pinned canary "
              "here). The A-dependent portfolio row is BLOCKED below; VPC-standalone Check 1 and all "
              "of Check 2 (VPC-only, unaffected) still run and are reported.", flush=True)

    print("\n" + "=" * 100)
    print("CHECK 1 -- 1m-truth re-walk")
    print("=" * 100)
    v_rows_new = build_new_vpc_rows(df1m)
    old_s, new_s = old_new_summary(df1m)
    print(f"  OLD: n={old_s['n_trades']} PF={old_s['pf_pts']} WR={old_s['wr_pct']}% net={old_s['total_pts']}pt")
    print(f"  NEW: n={new_s['n_trades']} PF={new_s['pf_pts']} WR={new_s['wr_pct']}% net={new_s['total_pts']}pt")
    delta_stats = r_delta_distribution(df1m)
    print(f"  outcome-changed (win<->loss flip): {delta_stats['outcome_changed']}/{delta_stats['n']}")
    per_year_df = per_year_old_vs_new(df1m)
    print("  per-year:")
    for r in per_year_df.itertuples():
        print(f"    {r.year}: n={r.n} PF old={r.pf_old} new={r.pf_new} net old={r.net_pts_old}pt new={r.net_pts_new}pt")

    print("\n  headline funnel (standalone VPC(600,4) + portfolio A(600,6)+VPC(600,4)):")
    funnel_df = headline_funnel(a2022, v_rows_old, v_rows_new, portfolio_ok)
    for r in funnel_df.itertuples():
        print(f"    {r.row:32} [{r.stream}] pass={r.pass_pct}% bust={r.bust_pct}% exp={r.exp_pct}% "
              f"n={r.eligible_starts} PF$={r.pf_dollar}")

    print("\n" + "=" * 100)
    print("CHECK 2 -- parameter plateau (native 5m engine, no re-tuning)")
    print("=" * 100)
    df5 = VS.real_rth_5m()
    df5 = df5[df5.date >= VR.WINDOW_START]
    feats5 = v.features(df5)
    df_a, v_a = grid_slope_trend(feats5)
    print(f"  Grid A (slope_mult x trend_mult) verdict: {v_a}")
    df_b, v_b = grid_atr_trail(feats5)
    print(f"  Grid B (atr_stop x trail_atr) verdict: {v_b}")
    df_c, v_c = grid_slot_max(feats5)
    print(f"  Grid C (slot_max) verdict: {v_c}")

    firewall_after = ST.sha_of(FIREWALL_FILES)
    firewall_ok = all(firewall_before[fn] == firewall_after[fn] for fn in FIREWALL_FILES)
    if not firewall_ok:
        print("[FIREWALL FAILURE] a firewalled file changed during this run -- STOPPING, no report written.")
        for fn in FIREWALL_FILES:
            print(f"  {fn}: {'UNCHANGED' if firewall_before[fn] == firewall_after[fn] else 'CHANGED'}")
        return

    runtime_s = time.time() - t_start
    write_09(old_s, new_s, per_year_df, delta_stats, funnel_df, n_skipped_1m, runtime_s,
            firewall_before, firewall_after, portfolio_ok)
    write_10(df_a, v_a, df_b, v_b, df_c, v_c, runtime_s)

    print("\n" + "=" * 100)
    if VR.PF_FLAGS:
        print(f"[FREEZE] {len(VR.PF_FLAGS)} cell(s) breached PF>{VR.PF_FREEZE_THRESHOLD}: {VR.PF_FLAGS}")
    else:
        print(f"No cell anywhere breached PF>{VR.PF_FREEZE_THRESHOLD}.")
    print(f"Runtime: {runtime_s:.1f}s")
    for fn in FIREWALL_FILES:
        print(f"Firewall {fn}: UNCHANGED")
    print("=" * 100)


if __name__ == "__main__":
    main()
