"""tools_salvage_stress.py — SALVAGE PROGRAM final quantitative step: A6 fill/slippage stress
on the surviving candidates only.

RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing (no live/config/engine file touched).
Pure execution over PRIOR-ART machinery — no new modeling choices beyond the explicit damage-grid
formulas pinned by the coordinator (each one documented, not hidden). No winner-picking beyond the
mechanical PASS>BUST boolean explicitly requested by the brief.

BASE MACHINERY REUSED (imported, not reimplemented):
  - `tools_salvage_vpc_reeval.py` (aliased VR): ASR.build_events / ASR.day_rows / summarize_cell /
    event_pf (dollar-PF + freeze-flag bookkeeping) / STOP_PINNED,DLL_PINNED / combined_daily_series /
    funded_cell_report / funded_canary / vpc_rows() / a_rows_full() / a_rows_2022() / run_canaries()
    (VR's own structural canaries) / v, VS modules (VPC engine, for the 3pt-cost-ladder prior below).
  - `tools_salvage_track_a.py` (aliased TA): load_streams() / a2_streams() / run_cell() (trade-level
    walk for the unfiltered-A stream) / check_canaries() (TA's own structural canaries).
  Both modules build the A/VPC event streams, combined day calendars, and pinned funnels; this file
  only (a) applies damage to the (ts,R,mae_r,risk_usd) rows BEFORE those pipelines run, and (b) reruns
  the unmodified pipelines on the damaged rows.

DAMAGE MODEL (rows-level, applied to R and mae_r before build_events/run_cell/combined_daily_series —
"before day aggregation" per the brief; mathematically equivalent to applying the same damage to the
resulting dollar pnl/mae since pnl = R * risk_usd * q and mae = mae_r * risk_usd * q, and none of the
damage grids below change q's sizing driver `risk_usd`):
  (a) uniform slippage s (R units): R -> R - s, mae_r -> mae_r - s, on every trade of BOTH legs.
  (b) winners' partial fill f in {0.75, 0.50, 0.25}: for trades with R>0 (winners), R -> R*f,
      mae_r -> mae_r*f (equivalent to sizing that trade's own contracts down by f — same dollar
      effect since pnl=R*risk_usd*q is linear in R for fixed q); losers (R<=0) untouched. Applied to
      BOTH legs.
  (c) VPC-CHASE STRESS (VPC legs ONLY — VPC's entries are next-bar-open market-class, so extra entry
      slippage in points converts to R via that trade's own stop distance): R_extra = extra_pts /
      stop_pts, R -> R - R_extra, mae_r -> mae_r - R_extra. stop_pts is recovered from risk_usd via
      the frozen mapping risk_usd = stop_pts * DPP ($2/pt/MNQ, `tools_salvage_vpc_reeval.DPP`), i.e.
      stop_pts = risk_usd / DPP — no new per-trade field needed, no VPC-internal file touched. A legs
      untouched.
  (d) A-only stress control: uniform s=0.05R on the A leg ONLY (VPC leg untouched) for the three
      combo cells (C1/C2/C3) — isolates which side of the combo carries the fragility.
  FUNDED cells: grid (a) only, s in {0.02, 0.05} (+ baseline s=0), on whichever legs the cell has.

CANARIES (run first; STOP before any report on mismatch):
  0. Reuse VR.run_canaries() and TA.check_canaries() verbatim (both modules' own structural/
     reproduction canaries — VPC 408-signature, honest-A reverification, cap-10 canary, unfiltered/
     kept stream signature, (10,$1200) row, look-ahead spot-check).
  1-4. Reproduce the four pinned UNDAMAGED reference rows exactly (tolerance = exact match on the
     rounded percentages already on disk):
       A(600,6)+VPC(600,4)   -> pass 27.8 / bust 15.5 / exp 56.7 (n=684)
       A(1200,10)+VPC(600,4) -> pass 44.6 / bust 34.4 / exp 21.1 (n=684)
       unfiltered-A(1200,6)  -> pass 23.4 / bust 20.7 / exp 55.9 (n=623)
       VPC(800,6)            -> pass 20.1 / bust 16.7 / exp 63.2 (n=389)

PF>1.8 anywhere (dollar trade-level PF, any cell/damage point) -> FREEZE + FLAG, via the same
`VR.event_pf`/`VR.PF_FLAGS` bookkeeping the base machinery already uses (shared module-global list,
so flags accumulate across both this file's cells and any VR-internal canary calls in the same run).

Outputs (new, this run only):
  reports/new_edge_salvage_program/A6_salvage_fill_slippage_stress.csv / .md
"""
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tools_salvage_vpc_reeval as VR      # ASR machinery, event_pf/PF_FLAGS, combined funded machinery
import tools_salvage_track_a as TA         # unfiltered-A stream + trade-level run_cell

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "reports", "new_edge_salvage_program")

DPP = VR.DPP                               # 2.0 $/pt/MNQ (frozen mapping, used to back out stop_pts)

# ------------------------------------------------------------------------------------------------
# pinned undamaged reference rows (STOP on mismatch)
# ------------------------------------------------------------------------------------------------
REF = {
    "C1": dict(pass_pct=27.8, bust_pct=15.5, exp_pct=56.7, n=684),
    "C2": dict(pass_pct=44.6, bust_pct=34.4, exp_pct=21.1, n=684),
    "C4": dict(pass_pct=23.4, bust_pct=20.7, exp_pct=55.9, n=623),
    "C5": dict(pass_pct=20.1, bust_pct=16.7, exp_pct=63.2, n=389),
}

CELL_DEFS = {
    "C1": dict(desc="A(600,6)+VPC(600,4)",   a_bc=(600, 6),  v_bc=(600, 4),  kind="combo"),
    "C2": dict(desc="A(1200,10)+VPC(600,4)", a_bc=(1200, 10), v_bc=(600, 4),  kind="combo"),
    "C3": dict(desc="A(1200,10)+VPC(400,4)", a_bc=(1200, 10), v_bc=(400, 4),  kind="combo"),
    "C4": dict(desc="unfiltered-A(1200,6) alone", a_bc=(1200, 6), v_bc=None, kind="unfiltered_a"),
    "C5": dict(desc="VPC(800,6) alone",      a_bc=None,       v_bc=(800, 6), kind="vpc_alone"),
}

FUNDED_DEFS = {
    "F1": dict(desc="kept-A(250,4) alone",         a_bc=(250, 4), v_bc=None),
    "F2": dict(desc="kept-A(250,4)+VPC(200,2)",    a_bc=(250, 4), v_bc=(200, 2)),
}

SLIP_GRID = [0.0, 0.01, 0.02, 0.03, 0.05, 0.075, 0.10]           # (a) uniform slippage, R units
PARTIAL_GRID = [1.0, 0.75, 0.50, 0.25]                            # (b) winners' partial fill f
CHASE_GRID = [0.0, 0.5, 1.0]                                      # (c) VPC-chase extra entry pts
A_ONLY_S = 0.05                                                   # (d) A-only stress control
FUNDED_SLIP_GRID = [0.0, 0.02, 0.05]                              # FUNDED grid (a) only

FIREWALL_FILES = ["config_eval_locked.py", "config_funded_locked.py",
                  "config_defaults.py", "auto_safety.py"]


# ==================================================================================================
# damage functions (rows-level: list of dict(ts,R,mae_r,risk_usd,[kept],[in_window]))
# ==================================================================================================
def dmg_slip(rows, s):
    """(a) uniform slippage s (R units) subtracted from every trade's pnl AND mae."""
    if rows is None or s == 0.0:
        return rows
    return [dict(r, R=r["R"] - s, mae_r=r["mae_r"] - s) for r in rows]


def dmg_partial(rows, f):
    """(b) winners' (R>0) size x f; losers full size. f=1.0 = undamaged."""
    if rows is None or f == 1.0:
        return rows
    out = []
    for r in rows:
        if r["R"] > 0:
            out.append(dict(r, R=r["R"] * f, mae_r=r["mae_r"] * f))
        else:
            out.append(r)
    return out


def dmg_chase(rows, extra_pts):
    """(c) VPC-chase: extra entry slippage in points -> R via that trade's own stop_pts
    (recovered from risk_usd = stop_pts * DPP)."""
    if rows is None or extra_pts == 0.0:
        return rows
    out = []
    for r in rows:
        stop_pts = r["risk_usd"] / DPP
        r_extra = extra_pts / stop_pts
        out.append(dict(r, R=r["R"] - r_extra, mae_r=r["mae_r"] - r_extra))
    return out


# ==================================================================================================
# pipeline runners (thin wrappers around VR/TA machinery — no new funnel logic)
# ==================================================================================================
def run_eval_combo(a_rows, a_bc, v_rows, v_bc, label):
    """A(+VPC) combo/alone via ASR.build_events + ASR.day_rows + VR.summarize_cell
    (identical to tools_salvage_vpc_reeval.part2_eval/part1 per-cell machinery)."""
    ev = []
    if a_rows is not None and a_bc is not None:
        ev += VR.ASR.build_events(a_rows, a_bc[0], a_bc[1])
    if v_rows is not None and v_bc is not None:
        ev += VR.ASR.build_events(v_rows, v_bc[0], v_bc[1])
    ev.sort(key=lambda e: e["ts"])
    pf = VR.event_pf(ev, label)
    days = VR.ASR.day_rows(ev, VR.STOP_PINNED, VR.DLL_PINNED)
    s = VR.summarize_cell(days, label)
    s["pf_dollar"] = round(pf, 3) if pf == pf else None
    return s


def _c4_pf_ev(rows_unf, cap, budget):
    ev = []
    for t in rows_unf:
        q = min(cap, int(budget // t["risk_usd"]))
        if q < 1:
            continue
        ev.append(dict(pnl=t["R"] * t["risk_usd"] * q))
    return ev


def run_c4(rows_unf, cap, budget, label):
    """unfiltered-A alone via tools_salvage_track_a.run_cell (trade-level walk, verified
    structurally identical to ASR.build_events/day_rows/eval_run by the A1 canary)."""
    ev = _c4_pf_ev(rows_unf, cap, budget)
    pf = VR.event_pf(ev, label)
    cell = TA.run_cell(rows_unf, cap=cap, budget=budget, mode="plain")
    if cell.get("skipped"):
        return dict(label=label, eligible_starts=0, pass_count=0, pass_pct=None,
                    bust_pct=None, exp_pct=None, funded_per_slot_year=None,
                    pf_dollar=round(pf, 3) if pf == pf else None)
    return dict(label=label, eligible_starts=cell["eligible_starts"], pass_count=cell["pass_count"],
                pass_pct=cell["pass_pct"], bust_pct=cell["bust_pct"], exp_pct=cell["exp_pct"],
                funded_per_slot_year=cell["funded_per_slot_year"],
                pf_dollar=round(pf, 3) if pf == pf else None)


def run_cell_generic(cell_id, a_rows, v_rows, label):
    d = CELL_DEFS[cell_id]
    if d["kind"] == "unfiltered_a":
        return run_c4(a_rows, d["a_bc"][1], d["a_bc"][0], label)
    return run_eval_combo(a_rows, d["a_bc"], v_rows, d["v_bc"], label)


def run_funded(a_rows, a_bc, v_rows, v_bc, label):
    """A(+VPC) funded via VR.combined_daily_series + VR.funded_cell_report, unchanged."""
    rv = v_rows if v_rows is not None else []
    bv, cv = (v_bc[0], v_bc[1]) if v_bc is not None else (None, None)
    days = VR.combined_daily_series(a_rows, a_bc[0], a_bc[1], rv, bv, cv)
    return VR.funded_cell_report(days, label)


def flatten(r):
    pass_pct, bust_pct, exp_pct = r.get("pass_pct"), r.get("bust_pct"), r.get("exp_pct")
    pgb = (pass_pct is not None and bust_pct is not None and pass_pct > bust_pct)
    return dict(pass_pct=pass_pct, bust_pct=bust_pct, exp_pct=exp_pct,
                pass_count=r.get("pass_count"), eligible_starts=r.get("eligible_starts"),
                funded_per_slot_year=r.get("funded_per_slot_year"), pf_dollar=r.get("pf_dollar"),
                pass_gt_bust=pgb)


# ==================================================================================================
# stream loading
# ==================================================================================================
def build_streams():
    print("loading VPC rows (VR.vpc_rows)…", flush=True)
    v_rows, vpc_tr = VR.vpc_rows()
    print(f"  VPC rows n={len(v_rows)}", flush=True)

    print("loading honest-A (kept D1c) rows (VR.a_rows_full/a_rows_2022)…", flush=True)
    a_full = VR.a_rows_full()
    a2022 = VR.a_rows_2022(a_full)
    print(f"  A rows n={len(a_full)} full / n={len(a2022)} 2022-2026 window", flush=True)

    print("loading unfiltered-A (705) stream (TA.load_streams)…", flush=True)
    ta_streams = TA.load_streams()
    unfiltered = ta_streams["unfiltered"]
    print(f"  unfiltered-A n={len(unfiltered)}", flush=True)

    return dict(v_rows=v_rows, vpc_tr=vpc_tr, a_full=a_full, a2022=a2022,
                unfiltered=unfiltered, ta_streams=ta_streams)


# ==================================================================================================
# canaries
# ==================================================================================================
def _check(name, got, ref):
    fields = [("pass_pct", "pass_pct"), ("bust_pct", "bust_pct"), ("exp_pct", "exp_pct")]
    if "n" in ref:
        fields.append(("eligible_starts", "n"))
    ok = True
    parts = []
    for gk, rk in fields:
        gv, rv = got.get(gk), ref[rk]
        same = (gv == rv)
        ok &= same
        parts.append(f"{gk}={gv}(ref {rv})")
    print(f"  {name}: {' '.join(parts)} -> {'PASS' if ok else 'FAIL'}")
    return ok


def run_canaries(S):
    print("=" * 100)
    print("CANARIES")
    print("=" * 100)
    ok = True

    print("\n[0] base-machinery structural canaries (reused verbatim):")
    VR.vpc_rows_cache["rows"] = S["v_rows"]     # VR.run_canaries reads this module-global cache
    ok0 = VR.run_canaries(S["vpc_tr"], S["a_full"])
    print(f"  -> VR.run_canaries: {'PASS' if ok0 else 'FAIL'}")
    ok &= ok0

    ok0b, su, sk, row_1200_10 = TA.check_canaries(S["ta_streams"])
    print(f"  -> TA.check_canaries: {'PASS' if ok0b else 'FAIL'}")
    ok &= ok0b

    if not ok:
        print("\n[STOP] base-machinery canaries FAILED — not proceeding to the four pinned rows.")
        return False

    print("\n[1-4] reproduce the four pinned UNDAMAGED reference rows exactly:")
    c1 = run_eval_combo(S["a2022"], CELL_DEFS["C1"]["a_bc"], S["v_rows"], CELL_DEFS["C1"]["v_bc"],
                        "canary C1")
    c2 = run_eval_combo(S["a2022"], CELL_DEFS["C2"]["a_bc"], S["v_rows"], CELL_DEFS["C2"]["v_bc"],
                        "canary C2")
    c4 = run_c4(S["unfiltered"], CELL_DEFS["C4"]["a_bc"][1], CELL_DEFS["C4"]["a_bc"][0], "canary C4")
    c5 = run_eval_combo(None, None, S["v_rows"], CELL_DEFS["C5"]["v_bc"], "canary C5")

    ok &= _check("C1 A(600,6)+VPC(600,4)", c1, REF["C1"])
    ok &= _check("C2 A(1200,10)+VPC(600,4)", c2, REF["C2"])
    ok &= _check("C4 unfiltered-A(1200,6)", c4, REF["C4"])
    ok &= _check("C5 VPC(800,6)", c5, REF["C5"])

    print("=" * 100)
    if ok:
        print("[all canaries PASS] proceeding to damage grids.")
    else:
        print("[CANARY FAILURE] STOPPING — do not trust anything downstream of this run.")
    print("=" * 100)
    return ok


# ==================================================================================================
# VPC-chase prior (the "cert survived 3pt flat costs" reference quoted in headline table 3)
# ==================================================================================================
def vpc_3pt_prior():
    """Reproduces the vpc_recert_real.py cost-ladder point at RT_COST=3.0pt flat (identical CFG /
    engine, reused via VR's already-imported v/VS modules — no new file touched, no reimplementation
    of the ladder itself, just its RT_COST=3.0 point re-evaluated for direct quoting here)."""
    CFG = dict(atr_stop=2.5, trail_atr=5.0, slot_min=6, slot_max=66, max_trades=2,
              slope_mult=0.3, trend_mult=0.5, daily_stop=120)
    df = VR.VS.real_rth_5m()
    df = df[df.date >= pd.Timestamp("2022-01-01", tz=VR.NY)]
    feats = VR.v.features(df)
    orig = VR.v.RT_COST
    try:
        VR.v.RT_COST = 3.0
        t = VR.v.backtest(feats, **CFG)
    finally:
        VR.v.RT_COST = orig
    if len(t) == 0:
        return dict(n=0, pf=None, wr=None, net=None)
    gp = float(t.pnl[t.pnl > 0].sum())
    gl = float(abs(t.pnl[t.pnl < 0].sum()))
    return dict(n=len(t), pf=round(gp / gl, 3) if gl else None,
                wr=round(100.0 * float((t.pnl > 0).mean()), 1), net=round(float(t.pnl.sum()), 1))


# ==================================================================================================
# eval-side stress grid
# ==================================================================================================
def eval_stress(S):
    rows_out = []
    for cell_id, d in CELL_DEFS.items():
        base_a = S["a2022"] if d["kind"] == "combo" else (S["unfiltered"] if d["kind"] == "unfiltered_a" else None)
        base_v = S["v_rows"] if d["v_bc"] is not None else None

        def add(family, damage, a_rows, v_rows, label):
            r = run_cell_generic(cell_id, a_rows, v_rows, label)
            rec = dict(cell=cell_id, cell_desc=d["desc"], family=family, damage=damage)
            rec.update(flatten(r))
            rows_out.append(rec)

        add("baseline", 0.0, base_a, base_v, f"{cell_id} baseline")

        for s in SLIP_GRID:
            if s == 0.0:
                continue
            add("a_uniform_slip", s, dmg_slip(base_a, s), dmg_slip(base_v, s),
                f"{cell_id} slipR={s}")

        for f in PARTIAL_GRID:
            if f == 1.0:
                continue
            add("b_partial_fill", round(1 - f, 2), dmg_partial(base_a, f), dmg_partial(base_v, f),
                f"{cell_id} partialF={f}")

        if base_v is not None:
            for extra in CHASE_GRID:
                if extra == 0.0:
                    continue
                add("c_vpc_chase", extra, base_a, dmg_chase(base_v, extra),
                    f"{cell_id} vpcChase={extra}pt")

        if base_a is not None and base_v is not None:
            add("d_a_only_control", A_ONLY_S, dmg_slip(base_a, A_ONLY_S), base_v,
                f"{cell_id} A-only sR={A_ONLY_S}")

        print(f"  [{cell_id}] {d['desc']} — {sum(1 for r in rows_out if r['cell'] == cell_id)} "
              f"damage points done", flush=True)

    return pd.DataFrame.from_records(rows_out)


# ==================================================================================================
# funded-side stress grid
# ==================================================================================================
def funded_stress(S):
    if not VR.funded_canary(S["a2022"]):
        print("[SKIP] funded machinery canary mismatch — skipping FUNDED stress section.")
        return pd.DataFrame()
    rows_out = []
    for cell_id, d in FUNDED_DEFS.items():
        for s in FUNDED_SLIP_GRID:
            a_rows = dmg_slip(S["a2022"], s)
            v_rows = dmg_slip(S["v_rows"], s) if d["v_bc"] is not None else None
            r = run_funded(a_rows, d["a_bc"], v_rows, d["v_bc"], f"{cell_id} slipR={s}")
            rows_out.append(dict(cell=cell_id, cell_desc=d["desc"], family="a_uniform_slip",
                                 damage=s, n_starts=r.get("n_starts"), e_paid=r.get("e_paid"),
                                 bust_pct=r.get("bust_pct"), med_months=r.get("med_months"),
                                 med_paid=r.get("med_paid"), closed_max_pct=r.get("closed_max_pct"),
                                 safety_net_pct=r.get("safety_net_pct")))
        print(f"  [{cell_id}] {d['desc']} done", flush=True)
    return pd.DataFrame.from_records(rows_out)


# ==================================================================================================
# headline table 1: damage level where PASS>BUST flips false, per cell x family (interpolated)
# ==================================================================================================
def find_flip(points):
    """points: list of (x, margin=pass_pct-bust_pct), x ascending, x=0 = baseline."""
    pts = sorted(points, key=lambda p: p[0])
    if pts[0][1] is None:
        return "n/a (baseline skipped)"
    if pts[0][1] <= 0:
        return "already <=0 at baseline"
    for i in range(1, len(pts)):
        x0, m0 = pts[i - 1]
        x1, m1 = pts[i]
        if m1 is None:
            continue
        if m1 <= 0:
            if m0 == m1:
                return round(x1, 4)
            frac = m0 / (m0 - m1)
            return round(x0 + frac * (x1 - x0), 4)
    return f">{pts[-1][0]:g} (not observed within tested grid)"


def headline_table1(df):
    recs = []
    for cell_id, d in CELL_DEFS.items():
        sub = df[df["cell"] == cell_id]
        base_margin = None
        base_row = sub[sub["family"] == "baseline"]
        if len(base_row):
            pp, bp = base_row.iloc[0]["pass_pct"], base_row.iloc[0]["bust_pct"]
            base_margin = None if pp is None else (pp - bp)

        # family a
        a_pts = [(0.0, base_margin)]
        for _, r in sub[sub["family"] == "a_uniform_slip"].iterrows():
            m = None if r["pass_pct"] is None else (r["pass_pct"] - r["bust_pct"])
            a_pts.append((r["damage"], m))
        recs.append(dict(cell=cell_id, cell_desc=d["desc"], family="a_uniform_slip (s, R)",
                         flip_at=find_flip(a_pts)))

        # family b
        b_pts = [(0.0, base_margin)]
        for _, r in sub[sub["family"] == "b_partial_fill"].iterrows():
            m = None if r["pass_pct"] is None else (r["pass_pct"] - r["bust_pct"])
            b_pts.append((r["damage"], m))
        recs.append(dict(cell=cell_id, cell_desc=d["desc"], family="b_partial_fill (1-f)",
                         flip_at=find_flip(b_pts)))

        # family c (only cells with a VPC leg)
        if d["v_bc"] is not None:
            c_pts = [(0.0, base_margin)]
            for _, r in sub[sub["family"] == "c_vpc_chase"].iterrows():
                m = None if r["pass_pct"] is None else (r["pass_pct"] - r["bust_pct"])
                c_pts.append((r["damage"], m))
            recs.append(dict(cell=cell_id, cell_desc=d["desc"], family="c_vpc_chase (pts)",
                             flip_at=find_flip(c_pts)))
    return pd.DataFrame.from_records(recs)


# ==================================================================================================
# headline table 2: break-even vs honest A-alone reference (C4), family (a) only (common denominator)
# ==================================================================================================
def headline_table2(df):
    c4 = df[(df["cell"] == "C4") & (df["family"].isin(["baseline", "a_uniform_slip"]))]
    c4_by_s = {0.0 if fam == "baseline" else s: (pp, bp)
              for fam, s, pp, bp in zip(c4["family"], c4["damage"], c4["pass_pct"], c4["bust_pct"])}
    recs = []
    for cell_id in ["C1", "C2", "C3", "C5"]:
        sub = df[(df["cell"] == cell_id) & (df["family"].isin(["baseline", "a_uniform_slip"]))]
        for _, r in sub.iterrows():
            s = 0.0 if r["family"] == "baseline" else r["damage"]
            ref = c4_by_s.get(s)
            if ref is None or r["pass_pct"] is None:
                continue
            ref_pp, ref_bp = ref
            cell_margin = r["pass_pct"] - r["bust_pct"]
            ref_margin = ref_pp - ref_bp
            recs.append(dict(cell=cell_id, cell_desc=CELL_DEFS[cell_id]["desc"], slip_s=s,
                             cell_pass_pct=r["pass_pct"], cell_bust_pct=r["bust_pct"],
                             cell_margin=round(cell_margin, 1),
                             ref_C4_pass_pct=ref_pp, ref_C4_bust_pct=ref_bp,
                             ref_C4_margin=round(ref_margin, 1),
                             beats_honest_A_alone=bool(cell_margin > ref_margin)))
    return pd.DataFrame.from_records(recs)


# ==================================================================================================
# headline table 3: VPC-chase table + the 3pt-cost-ladder prior
# ==================================================================================================
def headline_table3(df, prior):
    recs = []
    for cell_id in ["C1", "C2", "C3", "C5"]:
        sub = df[(df["cell"] == cell_id) & (df["family"].isin(["baseline", "c_vpc_chase"]))]
        for _, r in sub.iterrows():
            extra = 0.0 if r["family"] == "baseline" else r["damage"]
            recs.append(dict(cell=cell_id, cell_desc=CELL_DEFS[cell_id]["desc"],
                             extra_entry_pts=extra, pass_pct=r["pass_pct"], bust_pct=r["bust_pct"],
                             exp_pct=r["exp_pct"], pass_gt_bust=r["pass_gt_bust"]))
    df3 = pd.DataFrame.from_records(recs).sort_values(["cell", "extra_entry_pts"])
    prior_line = (f"VPC prior cert (vpc_recert_real.py cost ladder, RT_COST=3.0pt flat, "
                  f"2022+ real Databento, same CFG/engine): n={prior['n']} PF={prior['pf']} "
                  f"WR%={prior['wr']} net={prior['net']:+.1f}pt — the cost ladder's own \"survived "
                  f"3pt flat costs\" point, printed here as the prior VPC's chase-stress result "
                  f"below should be read against.")
    return df3, prior_line


# ==================================================================================================
# report writers
# ==================================================================================================
def write_report(df_eval, df_funded, t1, t2, t3, prior_line, canary_lines, firewall_before,
                 firewall_after, runtime_s):
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, "A6_salvage_fill_slippage_stress.csv")
    md_path = os.path.join(OUTDIR, "A6_salvage_fill_slippage_stress.md")

    df_eval2 = df_eval.copy()
    df_eval2.insert(0, "section", "EVAL")
    df_funded2 = df_funded.copy()
    if len(df_funded2):
        df_funded2.insert(0, "section", "FUNDED")
    combined = pd.concat([df_eval2, df_funded2], ignore_index=True, sort=False)
    combined.to_csv(csv_path, index=False)

    freeze_flags = list(VR.PF_FLAGS)

    lines = []
    lines.append("# A6 — Fill/Slippage Stress on Surviving Salvage Candidates")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. Pure execution over pinned mechanics "
                 "(`tools_salvage_vpc_reeval.py` / `tools_salvage_track_a.py`, imported not "
                 "reimplemented). No new modeling choices beyond the explicit damage-grid formulas "
                 "in the module docstring. No winner-picking beyond the mechanical PASS>BUST boolean.")
    lines.append("")
    lines.append(f"Runtime: {runtime_s:.1f}s.")
    lines.append("")
    lines.append("## Firewall before/after")
    lines.append("")
    lines.append("| file | sha256 before | sha256 after | match |")
    lines.append("|---|---|---|---|")
    for f in FIREWALL_FILES:
        b, a = firewall_before.get(f), firewall_after.get(f)
        lines.append(f"| {f} | `{b}` | `{a}` | {'UNCHANGED' if a == b else 'CHANGED — INVESTIGATE'}| ")
    lines.append("")
    lines.append("## Canaries")
    lines.append("")
    lines.append("```")
    lines.extend(canary_lines)
    lines.append("```")
    lines.append("")
    lines.append("## Cell definitions")
    lines.append("")
    lines.append("| cell | description |")
    lines.append("|---|---|")
    for cid, d in CELL_DEFS.items():
        lines.append(f"| {cid} | {d['desc']} |")
    for cid, d in FUNDED_DEFS.items():
        lines.append(f"| {cid} (FUNDED) | {d['desc']} |")
    lines.append("")
    lines.append("Damage grids: (a) uniform slippage s in R {0.01,0.02,0.03,0.05,0.075,0.10} "
                 "on both legs; (b) winners' partial fill f in {0.75,0.50,0.25} on both legs; "
                 "(c) VPC-chase extra entry slippage in {0.5,1.0}pt (VPC legs only, A untouched); "
                 "(d) A-only control s=0.05R (A legs only, VPC untouched, combo cells only). "
                 "FUNDED cells: grid (a) only at s in {0.02,0.05}.")
    lines.append("")
    lines.append("## Full damage grid (EVAL cells)")
    lines.append("")
    lines.append(VR.df_to_md_table(df_eval))
    lines.append("")
    lines.append("## Full damage grid (FUNDED cells, grid (a) only)")
    lines.append("")
    lines.append(VR.df_to_md_table(df_funded) if len(df_funded) else "(skipped — funded canary mismatch)")
    lines.append("")
    lines.append("## HEADLINE TABLE 1 — damage level where PASS>BUST flips false (interpolated, per cell x family)")
    lines.append("")
    lines.append("Linear interpolation of margin=pass_pct-bust_pct across the tested grid points "
                 "(baseline=0 included). \"not observed within tested grid\" = margin stayed positive "
                 "through the largest tested damage point for that family.")
    lines.append("")
    lines.append(VR.df_to_md_table(t1))
    lines.append("")
    lines.append("## HEADLINE TABLE 2 — break-even vs honest A-alone reference (C4 = unfiltered-A(1200,6))")
    lines.append("")
    lines.append("Family (a) uniform-slippage only (the one damage measure common/comparable across "
                 "all cell types). `beats_honest_A_alone` = (cell's pass_pct-bust_pct margin) > "
                 "(C4's margin at the SAME slippage level s).")
    lines.append("")
    lines.append(VR.df_to_md_table(t2))
    lines.append("")
    lines.append("## HEADLINE TABLE 3 — VPC-chase stress")
    lines.append("")
    lines.append(prior_line)
    lines.append("")
    lines.append(VR.df_to_md_table(t3))
    lines.append("")
    if freeze_flags:
        lines.append(f"## PF FREEZE FLAGS (PF>{VR.PF_FREEZE_THRESHOLD}): {freeze_flags}")
    else:
        lines.append(f"## PF freeze check: no cell/damage point anywhere breached "
                     f"PF>{VR.PF_FREEZE_THRESHOLD}.")

    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[saved] {csv_path}\n[saved] {md_path}")


# ==================================================================================================
def sha_of(files):
    import hashlib
    out = {}
    for fn in files:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), fn)
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            h.update(fh.read())
        out[fn] = h.hexdigest()
    return out


def main():
    t_start = time.time()
    firewall_before = sha_of(FIREWALL_FILES)

    print("loading streams…", flush=True)
    S = build_streams()

    ok = run_canaries(S)
    if not ok:
        print("[ABORT] canary mismatch — no A6 report written.")
        return

    print("\ncomputing VPC 3pt-cost-ladder prior…", flush=True)
    prior = vpc_3pt_prior()
    print(f"  prior: {prior}", flush=True)

    print("\nEVAL-side stress grid…", flush=True)
    df_eval = eval_stress(S)

    print("\nFUNDED-side stress grid…", flush=True)
    df_funded = funded_stress(S)

    t1 = headline_table1(df_eval)
    t2 = headline_table2(df_eval)
    t3, prior_line = headline_table3(df_eval, prior)

    firewall_after = sha_of(FIREWALL_FILES)
    runtime_s = time.time() - t_start

    # recapture canary print lines by re-running (cheap; only for the report's printed record)
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_canaries(S)
    canary_lines = buf.getvalue().splitlines()

    write_report(df_eval, df_funded, t1, t2, t3, prior_line, canary_lines,
                firewall_before, firewall_after, runtime_s)

    print("\n" + "=" * 100)
    if VR.PF_FLAGS:
        print(f"[FREEZE] {len(VR.PF_FLAGS)} cell/damage point(s) breached "
              f"PF>{VR.PF_FREEZE_THRESHOLD}: {VR.PF_FLAGS}")
    else:
        print(f"No cell/damage point anywhere breached PF>{VR.PF_FREEZE_THRESHOLD}.")
    print(f"Runtime: {runtime_s:.1f}s")
    for fn in FIREWALL_FILES:
        match = firewall_before[fn] == firewall_after[fn]
        print(f"Firewall {fn}: {'UNCHANGED' if match else 'CHANGED'}")
    print("=" * 100)


if __name__ == "__main__":
    main()
