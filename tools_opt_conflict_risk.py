"""tools_opt_conflict_risk.py — A+VPC PORTFOLIO OPTIMISATION Lane 2: conflict/arbitration rules
+ daily risk allocation, all at the BASELINE sizing A600/6 + VPC600/4.

RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing (no live/config/engine file touched).
Pure execution over PRIOR-ART machinery — no new modeling choices beyond the explicit rule/variant
definitions pinned by the coordinator brief (each documented below, not hidden).

PRIOR ART REUSED (imported, not reimplemented):
  - `tools_salvage_vpc_reeval.py` (VR): ASR (`tools_account_size_research`) re-export — build_events /
    day_rows / eval_run / SPECS["50K"] / EXPIRE_DAYS; VR's own vpc_rows() / a_rows_full() /
    a_rows_2022() / run_canaries() / summarize_cell() / event_pf() / weeks_span() / df_to_md_table() /
    combined_daily_series() / funded_cell_report() / funded_canary() / STOP_PINNED,DLL_PINNED / DPP /
    v, VS modules (VPC engine access).
  - `tools_vpc_1m_truth.py` (VT): load_1m_rth() / vpc_1m_truth_trades() / build_new_vpc_rows() /
    old_new_summary() — the certified 1m-truth VPC stream (PF 1.318/n=408).
  - `tools_salvage_stress.py` (ST): FIREWALL_FILES / sha_of() — firewall bookkeeping.
  - `tools_sim_parity_check.py` (SPC, via VR): load_rows() — the honest A stream (post D1c-recert,
    n=583, PF=1.361).
  - `tools_phase3_config_sweep.py` (PCS): A_PARAMS — used only to re-derive each A trade's
    `direction`, which `a_streams_d1c`'s own row dict does not expose (see DIRECTION TAGGING below).
  - `tools_recert_funded.py` (TF, via VR): monthly_starts / run_pa_instrumented — the funded lifecycle
    walk `funded_cell_report` calls.
  - `model01_sweep_mss_fvg` (M1) / `tools_1m_truth_recert` (walk_1m, M1Map) / `run_d1c_real` (RD) /
    `apex_eval_eod_databento` (DB) / `strategy_engine_profileA` (E) / `config` — the same A-stream
    generation stack `tools_sim_parity_check.load_rows()` already uses.

STREAMS (pinned per brief):
  A   = `tools_sim_parity_check.load_rows()`, restricted to 2022+ (VR.a_rows_2022). Full-stream
        canary: n=583, PF=1.361.
  VPC = 1m-truth stream from `tools_vpc_1m_truth` (`build_new_vpc_rows` over `vpc_1m_truth_trades`).
        Canary: n=408, PF=1.318 (point-based, matches `09_vpc_1m_truth_rewalk.md`'s NEW row exactly).
  BASELINE sizing throughout: A budget=$600/cap=6, VPC budget=$600/cap=4 (STOP_PINNED=$550,
  DLL_PINNED=$1,000). Naive-union canary (no arbitration, no risk variant): pass=28.7/bust=17.0/
  exp=54.4/n=684 (`reports/a_vpc_portfolio_optimisation/00_preflight.md` line 8, reproduced here from
  first principles) — 0.3pp tolerance, STOP on miss.

DIRECTION TAGGING (new in this file; documented, not hidden — needed for rules R4/R5/R7/R9/R10 which
require each event's trade direction, a field `tools_sim_parity_check.load_rows()` /
`tools_vpc_1m_truth.build_new_vpc_rows()` do not carry through to their (ts,R,mae_r,risk_usd) row
shape):
  - A: `a_rows_direction_tagged()` below re-runs `tools_phase3_config_sweep.a_streams_d1c`'s own
    'exit3' loop verbatim (same M1.run / attach_drift / walk_1m calls, same filters), additionally
    keeping each kept trade's `t.direction` ("long"->+1, "short"->-1). Verified below (canary) to
    reproduce `tools_sim_parity_check.load_rows()` row-for-row (n, ts, R, mae_r, risk_usd all
    identical) before its direction column is trusted.
  - VPC: `vpc_1m_truth_trades()` already computes `d` (direction) per trade internally (used for its
    own long/short branch) and returns it in `df1m["d"]`; `v_rows_direction_tagged()` below is
    `build_new_vpc_rows()` plus that same `d` column, verified to reproduce `build_new_vpc_rows()`
    row-for-row (R, mae_r, risk_usd, ts identical) before trusting the direction column.

EVENT-STREAM TRANSFORM DESIGN (03, the 11 arbitration rules): rules are applied at the TAGGED-ROW
level (ts, R, mae_r, risk_usd, direction, lane), i.e. BEFORE `ASR.build_events`' own $ sizing/q-gate
runs and before `ASR.day_rows`' day-collapse — this is deliberate: a rule like R6 ("after the day's
first NEGATIVE event") or R9 ("after a positive A event") needs to test each trade's own sign, which
is sizing-invariant (sign(R) == sign(R*risk_usd*q) for any q>=1) but must be evaluated in the
correct chronological, cross-lane order BEFORE the two legs are separately sized and merged into $
events — filtering post-sizing $ events would give an identical numeric result for the sign tests
(same monotone relationship) but the day-collapse/stop machinery is only reused correctly by
re-running `ASR.build_events`/`ASR.day_rows` on the (filtered) rows, so rows-level filtering is the
natural place to do it once and pass forward unmodified. After a rule filters the merged, ts-sorted
row list, the survivors are split back into A-only / VPC-only row lists (by their `lane` tag) and fed
through the UNMODIFIED `ASR.build_events` -> `ASR.day_rows` -> `VR.summarize_cell` pipeline exactly as
every other cell in this repo.

R1 "one-position-at-a-time" — exit times are NOT in these rows (only entry ts + R/mae_r/risk_usd),
so the honest proxy pinned by the brief is used: "busy" = same calendar 30-minute bucket as the last
TAKEN event that day (`rule_r1_bucket30`). The brief also asks for the stricter variant "one trade
per 60 minutes" (`rule_r1_strict60`, a rolling 60-minute exclusion from the last taken event's own
ts, not a fixed calendar bucket) — both are reported side by side, explicitly labeled as proxies, not
a reconstruction of real position-open/close state.

E$ (used identically in both 03 and 04, "same as everywhere" formula pinned by the brief): this repo
has exactly one existing formula for a portfolio-combo dollar expectancy —
`tools_account_size_research.main()`'s `e_attempt = (pass_pct/100) * E[funded_paid] - fee_mo*1.5`,
generalized to two legs by `VR.funded_cell_report`'s own `e_paid` (mean lifetime paid across funded
monthly starts). Reused verbatim here:
    E$ = (pass_pct / 100) * e_paid_funded - EVAL_FEE_EST   (EVAL_FEE_EST = 45.0 * 1.5 = 67.5, the
                                                             50K spec's fee_mo, ASR.SPECS["50K"])
  - Section 03 (arbitration rules): `e_paid_funded` is computed on the SAME rule-filtered rows, at
    the established funded-combo pair A@250/4 + VPC@200/2 (`tools_salvage_vpc_reeval.part2_funded`'s
    own canonical funded cell) — an arbitration rule is a genuine trade-selection change, so it is
    carried forward to what a funded account would also do.
  - Section 04 (daily risk allocation): `e_paid_funded` is held CONSTANT across all variants, computed
    ONCE on the UNFILTERED (naive-union) rows at the same established A@250/4+VPC@200/2 pair — these
    variants are pure EVAL-side risk/sizing knobs (daily stop, per-trade budget, loss-count gates),
    not a strategy change a live funded account (which runs its OWN fixed apex_funded_40 daily-stop/
    DLL policy, untouched here) would inherit. This asymmetry is a modeling choice, stated explicitly.

WORST-WEEK $ (new metric, no exact prior-art precedent for a single-week aggregate, though the same
ISO-calendar-week aggregation style is precedented by `tools_vpc_audit_portfolio.py`'s "same-week
joint-loss frequency"): min over ISO-calendar weeks of that week's summed REALIZED (day_rows-clamped)
$ P&L.

DENOMINATOR-ARTIFACT FLAG (DEC-20260706-1108, mechanical, no winner-picking): a rule/variant is
flagged if it improves bust_pct vs the R0/baseline row AND its funded_per_slot_year is LOWER than
R0/baseline's — i.e. the bust improvement may be substantially a shrinking-denominator (fewer
funded-per-year slots), not a genuine edge improvement.

CANARIES (run first; any FAIL stops the script before any report is written):
  1-4. VR.run_canaries(tr_base, a_full) reused verbatim (VPC 408-signature/net, honest-A n=583/
       PF=1.360600..., honest-A internal cap-10 canary, look-ahead merge/sort spot-check).
  5. VPC 1m-truth stream: n=408, PF=1.318 (VT.old_new_summary's new_s, point-based PF).
  6. Direction-tagging fidelity: `a_rows_direction_tagged()` reproduces `SPC.load_rows()` row-for-row;
     `v_rows_direction_tagged()` reproduces `VT.build_new_vpc_rows()` row-for-row.
  7. Baseline naive-union (R0, no arbitration, no risk variant) A@600/6(2022+)+VPC@600/4(1m-truth) ->
     pass=28.7/bust=17.0/exp=54.4/n=684 (0.3pp tol; STOP on miss).
  8. `day_replay_variant()` (04's generalized day-collapse) reproduces `ASR.day_rows` byte-identical
     when shared_stop=550, dll=1000, max_losses=None, no_new_after_loss=None (the "reproduces
     baseline when set to $550/none" canary the brief requires).
  9. pandas pinned <3 (INC-20260706-1627).
PF>1.8 anywhere (dollar trade-level PF) -> FREEZE + FLAG via the shared `VR.event_pf`/`VR.PF_FLAGS`
bookkeeping.

Outputs (new, this run only):
  reports/a_vpc_portfolio_optimisation/03_conflict_arbitration.csv / .md
  reports/a_vpc_portfolio_optimisation/04_daily_risk_allocation.csv / .md

No commits. No winner-picking beyond the mechanical denominator-artifact flag explicitly requested.
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

import strategy_engine_profileA as E
import model01_sweep_mss_fvg as M1
import config
import run_d1c_real as RD
import apex_eval_eod_databento as DB
from tools_1m_truth_recert import M1Map, walk_1m, A_PARAMS, DPP as A_DPP

import tools_salvage_vpc_reeval as VR       # ASR machinery, event_pf/PF_FLAGS, funded machinery
import tools_vpc_1m_truth as VT             # 1m-truth VPC rewalk
import tools_salvage_stress as ST           # FIREWALL_FILES, sha_of
import tools_sim_parity_check as SPC        # load_rows (honest A stream)

NY = "America/New_York"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "reports", "a_vpc_portfolio_optimisation")
FIREWALL_FILES = ST.FIREWALL_FILES

BASE_A_BC = (600, 6)          # pinned baseline sizing (task brief)
BASE_V_BC = (600, 4)
FUNDED_A_BC = (250, 4)        # established funded-combo pair (VR.part2_funded)
FUNDED_V_BC = (200, 2)
EVAL_FEE_EST = VR.ASR.SPECS["50K"]["fee_mo"] * 1.5     # 67.5

CANARY_BASELINE = dict(pass_pct=28.7, bust_pct=17.0, exp_pct=54.4, n=684)
TOL = 0.3

SLIP_PROBE = [0.015, 0.03, 0.046]

WINDOW_60MIN = pd.Timedelta(minutes=60)
CUTOFF_1130 = pd.Timestamp("11:30:00").time()


# ==================================================================================================
# STREAM LOADERS (direction-tagged)
# ==================================================================================================
def a_rows_direction_tagged():
    """`tools_phase3_config_sweep.a_streams_d1c`'s 'exit3' loop, verbatim, plus each trade's
    direction. See module docstring DIRECTION TAGGING section."""
    d1_tz = RD.load_1m(); d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m(); mp = M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    feats = eng._features()
    params = A_PARAMS["exit3"]
    tr = M1.run(feats, "NQ", params)
    tr = tr[tr.session == "ny_am"].copy()
    tr = RD.attach_drift(tr, d1_tz, feats.index)
    fi = feats.index; n5 = len(fi)
    rows = []
    for _, t in tr.iterrows():
        risk = abs(float(t.entry) - float(t.stop))
        fb = int(t.fill_bar)
        if risk <= 0 or not (0 <= fb < n5):
            continue
        if not bool(t["d1c_keep"]):
            continue
        d = 1 if t.direction == "long" else -1
        partials = []
        if params.get("partial"):
            partials = [(float(t.entry) + d * rl * risk, frac) for rl, frac in params["partial"]]
        w = walk_1m(mp, fb, d, float(t.entry), float(t.stop), float(t.target),
                    partials, max_5m_bars=M1.MAX_HOLD)
        if w is None:
            continue
        rows.append(dict(ts=pd.Timestamp(fi[fb]), R=w[0], mae_r=w[1], risk_usd=risk * A_DPP,
                         direction=d))
    rows.sort(key=lambda t: t["ts"])
    return rows


def v_rows_direction_tagged(df1m):
    """`tools_vpc_1m_truth.build_new_vpc_rows` plus each trade's `d` (direction), already computed
    by `vpc_1m_truth_trades` internally."""
    df = df1m[df1m["pnl_pts_new"].notna()].copy()
    rows = []
    for r in df.itertuples():
        risk_usd = r.stop_pts * VR.DPP
        rows.append(dict(ts=pd.Timestamp(r.ts), R=r.pnl_pts_new / r.stop_pts,
                         mae_r=r.mae_pts / r.stop_pts, risk_usd=risk_usd, direction=int(r.d)))
    rows.sort(key=lambda t: t["ts"])
    return rows


def _rows_match(tagged, untagged):
    if len(tagged) != len(untagged):
        return False
    for a, b in zip(tagged, untagged):
        if pd.Timestamp(a["ts"]) != pd.Timestamp(b["ts"]):
            return False
        if abs(a["R"] - b["R"]) > 1e-9 or abs(a["mae_r"] - b["mae_r"]) > 1e-9:
            return False
        if abs(a["risk_usd"] - b["risk_usd"]) > 1e-6:
            return False
    return True


# ==================================================================================================
# MERGE + rule filters (row-level, ts/lane/direction/R — sizing-invariant sign tests)
# ==================================================================================================
def _localize(ts):
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        ts = ts.tz_localize(NY)
    return ts


def build_tagged_rows(a_tag, v_tag, slip=0.0):
    out = []
    for r in a_tag:
        out.append(dict(ts=_localize(r["ts"]), R=r["R"] - slip, mae_r=r["mae_r"] - slip,
                        risk_usd=r["risk_usd"], direction=r["direction"], lane="A"))
    for r in v_tag:
        out.append(dict(ts=_localize(r["ts"]), R=r["R"] - slip, mae_r=r["mae_r"] - slip,
                        risk_usd=r["risk_usd"], direction=r["direction"], lane="VPC"))
    out.sort(key=lambda t: t["ts"])
    return out


def _group_by_day(rows):
    days = {}
    for r in rows:
        d = pd.Timestamp(r["ts"]).normalize()
        days.setdefault(d, []).append(r)
    for d in days:
        days[d].sort(key=lambda r: r["ts"])
    return days


def _rebuild(days_dict):
    out = []
    for d in sorted(days_dict):
        out.extend(days_dict[d])
    out.sort(key=lambda r: r["ts"])
    return out


def rule_r0_naive_union(rows):
    return list(rows)


def rule_r1_bucket30(rows):
    days = _group_by_day(rows)
    out = {}
    for d, evs in days.items():
        kept, last_bucket = [], None
        for e in evs:
            b = pd.Timestamp(e["ts"]).floor("30min")
            if last_bucket is not None and b == last_bucket:
                continue
            kept.append(e); last_bucket = b
        out[d] = kept
    return _rebuild(out)


def rule_r1_strict60(rows):
    days = _group_by_day(rows)
    out = {}
    for d, evs in days.items():
        kept, last_ts = [], None
        for e in evs:
            if last_ts is not None and (e["ts"] - last_ts) < WINDOW_60MIN:
                continue
            kept.append(e); last_ts = e["ts"]
        out[d] = kept
    return _rebuild(out)


def rule_r2_priority_a(rows):
    days = _group_by_day(rows)
    out = {}
    for d, evs in days.items():
        a_ts = [e["ts"] for e in evs if e["lane"] == "A"]
        kept = [e for e in evs if not (e["lane"] == "VPC"
                and any(abs((e["ts"] - at).total_seconds()) <= 3600 for at in a_ts))]
        out[d] = kept
    return _rebuild(out)


def rule_r3_priority_vpc(rows):
    days = _group_by_day(rows)
    out = {}
    for d, evs in days.items():
        v_ts = [e["ts"] for e in evs if e["lane"] == "VPC"]
        kept = [e for e in evs if not (e["lane"] == "A"
                and any(abs((e["ts"] - vt).total_seconds()) <= 3600 for vt in v_ts))]
        out[d] = kept
    return _rebuild(out)


def rule_r4_same_dir_dup(rows):
    days = _group_by_day(rows)
    out = {}
    for d, evs in days.items():
        kept = []
        for e in evs:
            conflict = any(k["direction"] == e["direction"]
                          and (e["ts"] - k["ts"]).total_seconds() <= 3600 for k in kept)
            if not conflict:
                kept.append(e)
        out[d] = kept
    return _rebuild(out)


def rule_r5_opp_dir_conflict(rows):
    days = _group_by_day(rows)
    out = {}
    for d, evs in days.items():
        kept = []
        for e in evs:
            conflict = any(k["direction"] != e["direction"]
                          and (e["ts"] - k["ts"]).total_seconds() <= 3600 for k in kept)
            if not conflict:
                kept.append(e)
        out[d] = kept
    return _rebuild(out)


def rule_r6_one_loser_stop(rows):
    days = _group_by_day(rows)
    out = {}
    for d, evs in days.items():
        kept, stopped = [], False
        for e in evs:
            if stopped:
                break
            kept.append(e)
            if e["R"] < 0:
                stopped = True
        out[d] = kept
    return _rebuild(out)


def rule_r7_vpc_only_before_a(rows):
    days = _group_by_day(rows)
    out = {}
    for d, evs in days.items():
        a_first_ts = next((e["ts"] for e in evs if e["lane"] == "A"), None)
        kept = []
        for e in evs:
            if e["lane"] == "A":
                kept.append(e)
            elif a_first_ts is None or e["ts"] < a_first_ts:
                kept.append(e)
        out[d] = kept
    return _rebuild(out)


def rule_r8_time_separated(rows):
    out = []
    for e in rows:
        t = e["ts"].time()
        if e["lane"] == "A" and t <= CUTOFF_1130:
            out.append(e)
        elif e["lane"] == "VPC" and t >= CUTOFF_1130:
            out.append(e)
    out.sort(key=lambda e: e["ts"])
    return out


def rule_r9_vpc_after_a_win(rows):
    days = _group_by_day(rows)
    out = {}
    for d, evs in days.items():
        kept, a_win_ts = [], []
        for e in evs:
            if e["lane"] == "A":
                kept.append(e)
                if e["R"] > 0:
                    a_win_ts.append(e["ts"])
            elif any(at < e["ts"] for at in a_win_ts):
                kept.append(e)
        out[d] = kept
    return _rebuild(out)


def rule_r10_vpc_a_flat_days(rows):
    days = _group_by_day(rows)
    out = {}
    for d, evs in days.items():
        has_a = any(e["lane"] == "A" for e in evs)
        out[d] = [e for e in evs if e["lane"] == "A"] if has_a else evs
    return _rebuild(out)


RULES = [
    ("R0", "naive union (baseline)", rule_r0_naive_union),
    ("R1a", "one-position-at-a-time (30min bucket proxy)", rule_r1_bucket30),
    ("R1b", "one-position-at-a-time (strict 60min/trade)", rule_r1_strict60),
    ("R2", "priority-A (drop VPC within 60min of an A event)", rule_r2_priority_a),
    ("R3", "priority-VPC (drop A within 60min of a VPC event)", rule_r3_priority_vpc),
    ("R4", "no same-direction duplicate within 60min", rule_r4_same_dir_dup),
    ("R5", "no opposite-direction conflict within 60min", rule_r5_opp_dir_conflict),
    ("R6", "max-one-loser-then-stop (day)", rule_r6_one_loser_stop),
    ("R7", "VPC only before A's first event / A-flat days", rule_r7_vpc_only_before_a),
    ("R8", "time-separated (A<=11:30, VPC>=11:30 ET)", rule_r8_time_separated),
    ("R9", "VPC only strictly after an A win same day", rule_r9_vpc_after_a_win),
    ("R10", "VPC only on A-flat days (calendar widener)", rule_r10_vpc_a_flat_days),
]


# ==================================================================================================
# metrics
# ==================================================================================================
def _split_lanes(rows):
    return [r for r in rows if r["lane"] == "A"], [r for r in rows if r["lane"] == "VPC"]


def lane_daily(ev):
    out = {}
    for e in ev:
        d = pd.Timestamp(e["ts"]).normalize()
        out[d] = out.get(d, 0.0) + e["pnl"]
    return out


def dl_tl_stats(ev_a, ev_v):
    da, dv = lane_daily(ev_a), lane_daily(ev_v)
    all_days = sorted(set(da) | set(dv))
    n = len(all_days)
    if n == 0:
        return dict(n_days=0, dl_freq_pct=None, tl_freq_pct=None, joint_loss_days=0)
    xa = [da.get(d, 0.0) for d in all_days]
    xv = [dv.get(d, 0.0) for d in all_days]
    joint = sum(1 for a, v in zip(xa, xv) if a < 0 and v < 0)
    tot = sum(1 for a, v in zip(xa, xv) if (a + v) < 0)
    return dict(n_days=n, dl_freq_pct=round(100 * joint / n, 1), tl_freq_pct=round(100 * tot / n, 1),
               joint_loss_days=joint)


def worst_week_usd(days):
    wk = {}
    for d, real, _trough in days:
        iso = d.isocalendar()
        key = (iso[0], iso[1])
        wk[key] = wk.get(key, 0.0) + real
    return round(min(wk.values()), 0) if wk else None


def eval_funnel(rows, label, a_bc=BASE_A_BC, v_bc=BASE_V_BC):
    a_r, v_r = _split_lanes(rows)
    ev_a = VR.ASR.build_events(a_r, a_bc[0], a_bc[1])
    ev_v = VR.ASR.build_events(v_r, v_bc[0], v_bc[1])
    ev = sorted(ev_a + ev_v, key=lambda e: e["ts"])
    pf = VR.event_pf(ev, label)
    days = VR.ASR.day_rows(ev, VR.STOP_PINNED, VR.DLL_PINNED)
    s = VR.summarize_cell(days, label)
    dltl = dl_tl_stats(ev_a, ev_v)
    trades_wk = round(len(rows) / VR.weeks_span(rows), 2) if rows else 0.0
    return dict(s=s, pf_dollar=round(pf, 3) if pf == pf else None, ev=ev, days=days,
               a_r=a_r, v_r=v_r, dltl=dltl, trades_per_week=trades_wk,
               worst_week_usd=worst_week_usd(days))


def e_dollar_funded(a_r, v_r, pass_pct, label):
    if pass_pct is None:
        return None, None
    days_f = VR.combined_daily_series(a_r, FUNDED_A_BC[0], FUNDED_A_BC[1],
                                      v_r, FUNDED_V_BC[0], FUNDED_V_BC[1])
    rep = VR.funded_cell_report(days_f, label)
    e_paid = rep.get("e_paid") if rep.get("n_starts") else 0.0
    return round((pass_pct / 100.0) * e_paid - EVAL_FEE_EST), e_paid


def slip_probe(a_tag, v_tag, rule_fn, a_bc=BASE_A_BC, v_bc=BASE_V_BC):
    out = {}
    for s in SLIP_PROBE:
        merged = build_tagged_rows(a_tag, v_tag, slip=s)
        filtered = rule_fn(merged)
        a_r, v_r = _split_lanes(filtered)
        ev = sorted(VR.ASR.build_events(a_r, a_bc[0], a_bc[1])
                   + VR.ASR.build_events(v_r, v_bc[0], v_bc[1]), key=lambda e: e["ts"])
        days = VR.ASR.day_rows(ev, VR.STOP_PINNED, VR.DLL_PINNED)
        cell = VR.summarize_cell(days, f"slip{s}")
        out[s] = (cell["pass_pct"], cell["bust_pct"])
    return out


def denominator_flag(row, baseline_row):
    bp, bb, bf = baseline_row["s"]["bust_pct"], baseline_row["s"]["pass_pct"], baseline_row["s"]["funded_per_slot_year"]
    p, s = row["s"]["pass_pct"], row["s"]["funded_per_slot_year"]
    if bp is None or p is None or bf is None or s is None:
        return False
    return (row["s"]["bust_pct"] < bp) and (s < bf)


# ==================================================================================================
# 03 -- CONFLICT / ARBITRATION RULES
# ==================================================================================================
def run_03(a_tag, v_tag):
    print("\n" + "=" * 100)
    print("03 -- CONFLICT/ARBITRATION RULES (11 rules, 12 rows incl. R1's two proxy variants)")
    print("=" * 100)
    merged0 = build_tagged_rows(a_tag, v_tag, slip=0.0)
    records = []
    computed = {}
    for rid, desc, fn in RULES:
        filtered = fn(merged0)
        fun = eval_funnel(filtered, f"03-{rid}")
        computed[rid] = fun
        pass_pct = fun["s"]["pass_pct"]
        e_dol, e_paid = e_dollar_funded(fun["a_r"], fun["v_r"], pass_pct, f"03-{rid}-funded")
        probe = slip_probe(a_tag, v_tag, fn)
        rec = dict(rule=rid, desc=desc, n_events=len(filtered),
                   pf_dollar=fun["pf_dollar"], trades_per_week=fun["trades_per_week"],
                   worst_week_usd=fun["worst_week_usd"], e_paid_funded=round(e_paid) if e_paid is not None else None,
                   e_dollar=e_dol,
                   **{k: v for k, v in fun["s"].items() if k not in ("label", "per_year")},
                   **fun["dltl"])
        for s in SLIP_PROBE:
            p, b = probe[s]
            rec[f"slip{s}_pass_pct"] = p
            rec[f"slip{s}_bust_pct"] = b
        records.append(rec)
        print(f"  {rid:>4} {desc[:45]:<45} pass={rec['pass_pct']}% bust={rec['bust_pct']}% "
              f"exp={rec['exp_pct']}% n={rec['eligible_starts']} f/slot/yr={rec['funded_per_slot_year']} "
              f"trades/wk={rec['trades_per_week']} E$={rec['e_dollar']}", flush=True)
    baseline_row = None
    for rec, (rid, *_a) in zip(records, RULES):
        if rid == "R0":
            baseline_row = computed["R0"]
    for rec, (rid, *_a) in zip(records, RULES):
        rec["denominator_artifact_flag"] = denominator_flag(computed[rid], baseline_row)
    return pd.DataFrame.from_records(records), computed


def write_03(df, canary_row, runtime_s, firewall_before, firewall_after):
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, "03_conflict_arbitration.csv")
    md_path = os.path.join(OUTDIR, "03_conflict_arbitration.md")
    df.to_csv(csv_path, index=False)

    lines = []
    lines.append("# 03 -- A+VPC conflict/arbitration rules (Lane 2)")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing. All rows at the pinned "
                "BASELINE sizing A@600/6 (2022+) + VPC@600/4 (1m-truth). Rules are event-stream "
                "transforms applied to the merged, ts-sorted, direction-tagged row stream BEFORE "
                "`ASR.build_events`/`ASR.day_rows` (see module docstring for the full rule-by-rule "
                "definitions and the R1 30min-bucket / strict-60min honest proxy note).")
    lines.append("")
    lines.append(f"R0 naive-union baseline canary: pass={canary_row['pass_pct']} bust={canary_row['bust_pct']} "
                f"exp={canary_row['exp_pct']} n={canary_row['eligible_starts']} "
                f"(expected {CANARY_BASELINE}, tol {TOL}pp) -> "
                f"{'PASS' if _canary_ok(canary_row) else 'FAIL -- SEE STOP ABOVE'}")
    lines.append("")
    lines.append("E$ formula: (pass_pct/100) * e_paid_funded - 67.5, where e_paid_funded is "
                "`VR.funded_cell_report`'s E[paid] on the SAME rule-filtered rows at the established "
                "funded pair A@250/4+VPC@200/2 (`tools_salvage_vpc_reeval.part2_funded`).")
    lines.append("")
    lines.append("Denominator-artifact flag (DEC-20260706-1108, mechanical): bust_pct improved vs R0 "
                "AND funded_per_slot_year LOWER than R0 -- flagged rows may be cutting bust mainly by "
                "shrinking the number of funded-per-year slots, not via a genuine edge change.")
    lines.append("")
    lines.append(VR.df_to_md_table(df))
    lines.append("")
    flagged = df[df["denominator_artifact_flag"] == True]  # noqa: E712
    lines.append(f"## Denominator-artifact flags: {len(flagged)}/{len(df)} rows")
    if len(flagged):
        lines.append(VR.df_to_md_table(flagged[["rule", "desc", "pass_pct", "bust_pct",
                                                 "funded_per_slot_year"]]))
    else:
        lines.append("(none)")
    lines.append("")
    if VR.PF_FLAGS:
        lines.append(f"## PF FREEZE FLAGS (PF>{VR.PF_FREEZE_THRESHOLD}): {VR.PF_FLAGS}")
    lines.append("")
    lines.append(f"Runtime this section: {runtime_s:.1f}s")
    lines.append("Firewall (before/after, must be unchanged):")
    for fn in FIREWALL_FILES:
        lines.append(f"  {fn}: {'UNCHANGED' if firewall_before[fn] == firewall_after[fn] else 'CHANGED'}")
    with open(md_path, "w") as f:
        f.write("\n".join(lines))
    print(f"[saved] {csv_path}\n[saved] {md_path}")


def _canary_ok(row):
    return (abs(row["pass_pct"] - CANARY_BASELINE["pass_pct"]) <= TOL
            and abs(row["bust_pct"] - CANARY_BASELINE["bust_pct"]) <= TOL
            and abs(row["exp_pct"] - CANARY_BASELINE["exp_pct"]) <= TOL
            and row["eligible_starts"] == CANARY_BASELINE["n"])


# ==================================================================================================
# 04 -- DAILY RISK ALLOCATION
# ==================================================================================================
def day_replay_variant(a_rows, budget_a, cap_a, v_rows, budget_v, cap_v,
                       shared_stop=550.0, dll=1000.0, max_losses=None, no_new_after_loss=None):
    """Generalization of `ASR.day_rows` (canaried below to reproduce it exactly at
    shared_stop=550/dll=1000/max_losses=None/no_new_after_loss=None): variable shared daily $ stop,
    optional max-losing-trades-per-day gate, optional no-new-trade-after-realized-loss gate. Both
    extra gates are evaluated BEFORE taking each event (i.e. they drop future events, same
    event-stream-transform style as the 03 rules) -- documented, not hidden."""
    ev = VR.ASR.build_events(a_rows, budget_a, cap_a) + VR.ASR.build_events(v_rows, budget_v, cap_v)
    ev.sort(key=lambda e: e["ts"])
    days = {}
    gated = 0
    for e in ev:
        d = e["ts"].normalize()
        r = days.setdefault(d, dict(real=0.0, trough=0.0, stopped=False, loss_count=0))
        if r["stopped"]:
            continue
        if max_losses is not None and r["loss_count"] >= max_losses:
            gated += 1
            continue
        if no_new_after_loss is not None and r["real"] <= -no_new_after_loss:
            gated += 1
            continue
        r["trough"] = min(r["trough"], r["real"] + e["mae"])
        r["real"] += e["pnl"]
        if e["pnl"] < 0:
            r["loss_count"] += 1
        if r["real"] <= -shared_stop:
            r["stopped"] = True
    out = []
    dll_touch = 0
    for d in sorted(days):
        r = days[d]
        if r["trough"] <= -dll:
            real, trough = -dll, -dll
            dll_touch += 1
        else:
            real, trough = r["real"], r["trough"]
        out.append((d, real, trough))
    return out, ev, gated, dll_touch


def variant_row(label, group, a_rows, v_rows, budget_a, cap_a, budget_v, cap_v,
               shared_stop, max_losses, no_new_after_loss, e_paid_const):
    days, ev, gated, dll_touch = day_replay_variant(a_rows, budget_a, cap_a, v_rows, budget_v, cap_v,
                                                    shared_stop=shared_stop, max_losses=max_losses,
                                                    no_new_after_loss=no_new_after_loss)
    s = VR.summarize_cell(days, label)
    n_days = len(days)
    dll_touch_pct = round(100 * dll_touch / n_days, 1) if n_days else None
    trades_wk = round(len(ev) / VR.weeks_span(ev), 2) if ev else 0.0
    gated_wk = round(gated / VR.weeks_span(ev), 2) if ev else 0.0
    pass_pct = s["pass_pct"]
    e_dol = round((pass_pct / 100.0) * e_paid_const - EVAL_FEE_EST) if pass_pct is not None else None
    rec = dict(variant_group=group, variant=label, shared_stop=shared_stop, budget_a=budget_a,
              cap_a=cap_a, budget_v=budget_v, cap_v=cap_v, max_losses=max_losses,
              no_new_after_loss=no_new_after_loss, e_dollar=e_dol,
              trades_per_week=trades_wk, trades_per_week_lost_to_gate=gated_wk,
              dll_touch_freq_pct=dll_touch_pct,
              **{k: v for k, v in s.items() if k not in ("label", "per_year")})
    return rec, ev


def run_04(a2022, v_rows_new):
    print("\n" + "=" * 100)
    print("04 -- DAILY RISK ALLOCATION (naive-union rows, no arbitration; risk knobs only)")
    print("=" * 100)

    days0, ev0, gated0, dll0 = day_replay_variant(a2022, BASE_A_BC[0], BASE_A_BC[1],
                                                  v_rows_new, BASE_V_BC[0], BASE_V_BC[1],
                                                  shared_stop=550.0)
    days_ref = VR.ASR.day_rows(sorted(VR.ASR.build_events(a2022, *BASE_A_BC)
                                     + VR.ASR.build_events(v_rows_new, *BASE_V_BC),
                                     key=lambda e: e["ts"]), VR.STOP_PINNED, VR.DLL_PINNED)
    canary_ok = (days0 == days_ref)
    print(f"[canary] day_replay_variant(shared_stop=550, dll=1000, no gates) == ASR.day_rows: "
          f"{'PASS' if canary_ok else 'FAIL'}", flush=True)
    if not canary_ok:
        print("[CANARY FAILURE] STOPPING 04 -- day_replay_variant does not reproduce ASR.day_rows.")
        return None, canary_ok

    print("computing established funded pair E[paid] (constant across all 04 variants)…", flush=True)
    days_funded_const = VR.combined_daily_series(a2022, FUNDED_A_BC[0], FUNDED_A_BC[1],
                                                 v_rows_new, FUNDED_V_BC[0], FUNDED_V_BC[1])
    rep_const = VR.funded_cell_report(days_funded_const, "04-established-funded-pair")
    e_paid_const = rep_const.get("e_paid") if rep_const.get("n_starts") else 0.0
    print(f"  E[paid] (A@250/4+VPC@200/2, established pair) = ${e_paid_const:,.0f}", flush=True)

    records = []

    for stop in (400, 500, 550, 600, 700, 800):
        rec, _ = variant_row(f"shared_stop={stop}", "shared_stop", a2022, v_rows_new,
                             BASE_A_BC[0], BASE_A_BC[1], BASE_V_BC[0], BASE_V_BC[1],
                             shared_stop=float(stop), max_losses=None, no_new_after_loss=None,
                             e_paid_const=e_paid_const)
        records.append(rec)
        print(f"  shared_stop={stop:>4} pass={rec['pass_pct']}% bust={rec['bust_pct']}% "
              f"exp={rec['exp_pct']}% n={rec['eligible_starts']}", flush=True)

    for ba in (300, 400, 500, 600):
        for bv in (200, 300, 400, 500):
            rec, _ = variant_row(f"A@{ba}/6+VPC@{bv}/4", "lane_caps", a2022, v_rows_new,
                                 ba, 6, bv, 4, shared_stop=550.0, max_losses=None,
                                 no_new_after_loss=None, e_paid_const=e_paid_const)
            records.append(rec)
            print(f"  A@{ba}/6+VPC@{bv}/4 pass={rec['pass_pct']}% bust={rec['bust_pct']}% "
                  f"exp={rec['exp_pct']}%", flush=True)

    for ml in (1, 2):
        rec, _ = variant_row(f"max_{ml}_loss_stop", "max_losses", a2022, v_rows_new,
                             BASE_A_BC[0], BASE_A_BC[1], BASE_V_BC[0], BASE_V_BC[1],
                             shared_stop=550.0, max_losses=ml, no_new_after_loss=None,
                             e_paid_const=e_paid_const)
        records.append(rec)
        print(f"  max_losses={ml} pass={rec['pass_pct']}% bust={rec['bust_pct']}% "
              f"exp={rec['exp_pct']}%", flush=True)

    rec, _ = variant_row("no_new_trade_after_-500", "no_new_after_loss", a2022, v_rows_new,
                         BASE_A_BC[0], BASE_A_BC[1], BASE_V_BC[0], BASE_V_BC[1],
                         shared_stop=550.0, max_losses=None, no_new_after_loss=500.0,
                         e_paid_const=e_paid_const)
    records.append(rec)
    print(f"  no_new_after_loss=-500 pass={rec['pass_pct']}% bust={rec['bust_pct']}% "
          f"exp={rec['exp_pct']}%", flush=True)

    baseline_rec = next(r for r in records if r["variant"] == "shared_stop=550")
    for r in records:
        bp, bf = baseline_rec["bust_pct"], baseline_rec["funded_per_slot_year"]
        p, s = r["bust_pct"], r["funded_per_slot_year"]
        r["denominator_artifact_flag"] = (bp is not None and p is not None and bf is not None
                                          and s is not None and p < bp and s < bf)

    print("computing 3-point slip probes per variant (this may take a while)…", flush=True)
    for r in records:
        probe = {}
        for slip in SLIP_PROBE:
            a_s = [dict(rr, R=rr["R"] - slip, mae_r=rr["mae_r"] - slip) for rr in a2022]
            v_s = [dict(rr, R=rr["R"] - slip, mae_r=rr["mae_r"] - slip) for rr in v_rows_new]
            days_s, _ev_s, _g, _d = day_replay_variant(
                a_s, r["budget_a"], r["cap_a"], v_s, r["budget_v"], r["cap_v"],
                shared_stop=r["shared_stop"], max_losses=r["max_losses"],
                no_new_after_loss=r["no_new_after_loss"])
            cell = VR.summarize_cell(days_s, "slip")
            probe[slip] = (cell["pass_pct"], cell["bust_pct"])
        for slip in SLIP_PROBE:
            r[f"slip{slip}_pass_pct"] = probe[slip][0]
            r[f"slip{slip}_bust_pct"] = probe[slip][1]

    return pd.DataFrame.from_records(records), canary_ok


def write_04(df, e_paid_const, runtime_s, firewall_before, firewall_after):
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, "04_daily_risk_allocation.csv")
    md_path = os.path.join(OUTDIR, "04_daily_risk_allocation.md")
    df.to_csv(csv_path, index=False)

    lines = []
    lines.append("# 04 -- A+VPC daily risk allocation (Lane 2)")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing. Naive-union (R0, no "
                "arbitration) rows only -- these are pure eval-side risk-policy knobs on top of the "
                "baseline A@600/6(2022+)+VPC@600/4(1m-truth) sizing, via `day_replay_variant` "
                "(generalizes `ASR.day_rows` with a variable shared daily stop and two optional "
                "intraday gates; canaried to reproduce `ASR.day_rows` exactly at shared_stop=550, "
                "no gates).")
    lines.append("")
    lines.append(f"E$ formula: (pass_pct/100) * e_paid_funded - 67.5, where e_paid_funded = "
                f"${e_paid_const:,.0f} is HELD CONSTANT across every row in this table -- computed "
                "once on the UNFILTERED rows at the established funded pair A@250/4+VPC@200/2 (these "
                "variants are eval-side risk knobs, not a strategy change a separately-governed "
                "funded account would inherit; see module docstring).")
    lines.append("")
    lines.append("Denominator-artifact flag: bust_pct improved vs the shared_stop=550 baseline row "
                "AND funded_per_slot_year LOWER than that baseline.")
    lines.append("")
    lines.append(VR.df_to_md_table(df))
    lines.append("")
    flagged = df[df["denominator_artifact_flag"] == True]  # noqa: E712
    lines.append(f"## Denominator-artifact flags: {len(flagged)}/{len(df)} rows")
    if len(flagged):
        lines.append(VR.df_to_md_table(flagged[["variant_group", "variant", "pass_pct", "bust_pct",
                                                 "funded_per_slot_year"]]))
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("## Which policy keeps pass while cutting the bust tail (mechanical, no "
                "winner-picking): rows where bust_pct < baseline bust_pct AND pass_pct >= baseline "
                "pass_pct AND denominator_artifact_flag is False:")
    baseline_bust = df[df["variant"] == "shared_stop=550"]["bust_pct"].iloc[0]
    baseline_pass = df[df["variant"] == "shared_stop=550"]["pass_pct"].iloc[0]
    dominant = df[(df["bust_pct"] < baseline_bust) & (df["pass_pct"] >= baseline_pass)
                 & (df["denominator_artifact_flag"] == False)]  # noqa: E712
    if len(dominant):
        lines.append(VR.df_to_md_table(dominant[["variant_group", "variant", "pass_pct", "bust_pct",
                                                  "exp_pct", "funded_per_slot_year", "e_dollar"]]))
    else:
        lines.append("(none)")
    lines.append("")
    if VR.PF_FLAGS:
        lines.append(f"## PF FREEZE FLAGS (PF>{VR.PF_FREEZE_THRESHOLD}): {VR.PF_FLAGS}")
    lines.append("")
    lines.append(f"Runtime this section: {runtime_s:.1f}s")
    lines.append("Firewall (before/after, must be unchanged):")
    for fn in FIREWALL_FILES:
        lines.append(f"  {fn}: {'UNCHANGED' if firewall_before[fn] == firewall_after[fn] else 'CHANGED'}")
    with open(md_path, "w") as f:
        f.write("\n".join(lines))
    print(f"[saved] {csv_path}\n[saved] {md_path}")


# ==================================================================================================
# main
# ==================================================================================================
def main():
    t_start = time.time()
    firewall_before = ST.sha_of(FIREWALL_FILES)

    print("pandas version check (INC-20260706-1627 pin):", pd.__version__, flush=True)
    if int(pd.__version__.split(".")[0]) >= 3:
        print("[ABORT] pandas >=3 detected -- pinned incident. STOPPING.")
        return

    print("loading VPC rows (native, real Databento, frozen CFG, 2022+)…", flush=True)
    v_rows_old, tr_base = VR.vpc_rows()
    VR.vpc_rows_cache["rows"] = v_rows_old

    print("loading honest A rows (tools_sim_parity_check.load_rows, post-recert)…", flush=True)
    a_full = VR.a_rows_full()

    print("re-walking VPC exits on 1m bars (1m-truth stream)…", flush=True)
    d1rth = VT.load_1m_rth()
    v, VS = VR.v, VR.VS
    feats = v.features(VS.real_rth_5m())
    feats = feats[feats.date >= VR.WINDOW_START]
    df1m, n_skipped_1m = VT.vpc_1m_truth_trades(feats, d1rth)
    print(f"  1m-truth VPC trades n={len(df1m)} skipped={n_skipped_1m}", flush=True)

    print("\n" + "=" * 100)
    print("CANARIES")
    print("=" * 100)
    ok = VR.run_canaries(tr_base, a_full)
    old_s, new_s = VT.old_new_summary(df1m)
    c5 = (len(df1m) == 408 and abs(new_s["pf_pts"] - 1.318) < 1e-6)
    print(f"5. VPC 1m-truth stream: n={len(df1m)} (expect 408), PF={new_s['pf_pts']} (expect 1.318) "
          f"-> {'PASS' if c5 else 'FAIL'}")
    ok &= c5
    if not ok:
        print("[CANARY FAILURE] STOPPING -- upstream (1-4) canary mismatch.")
        return

    print("\nbuilding direction-tagged A/VPC rows…", flush=True)
    a_tag_full = a_rows_direction_tagged()
    v_tag = v_rows_direction_tagged(df1m)
    a_load_rows = SPC.load_rows()
    c6a = _rows_match(a_tag_full, a_load_rows)
    v_build_new = VT.build_new_vpc_rows(df1m)
    c6b = _rows_match(v_tag, v_build_new)
    print(f"6a. a_rows_direction_tagged() reproduces SPC.load_rows() row-for-row: "
          f"{'PASS' if c6a else 'FAIL'} (n_tag={len(a_tag_full)}, n_ref={len(a_load_rows)})")
    print(f"6b. v_rows_direction_tagged() reproduces VT.build_new_vpc_rows() row-for-row: "
          f"{'PASS' if c6b else 'FAIL'} (n_tag={len(v_tag)}, n_ref={len(v_build_new)})")
    if not (c6a and c6b):
        print("[CANARY FAILURE] STOPPING -- direction tagging corrupted the base rows.")
        return

    # NORMALIZE TZ ONCE, GLOBALLY: v_tag's ts are tz-naive NY (inherited from vpc_1m_truth_trades'
    # 1m-bar index, matching VT.build_new_vpc_rows byte-for-byte per canary 6b just above); A rows'
    # ts are tz-aware NY. Both 03 (build_tagged_rows) and 04 (day_replay_variant/ASR.build_events,
    # which does not itself localize) need a single consistent tz from here on -- localize once,
    # after the 6b byte-identical check (which deliberately compared against the still-naive
    # reference), not before.
    v_tag = [dict(r, ts=_localize(r["ts"])) for r in v_tag]

    a2022_tag = VR.a_rows_2022(a_tag_full)
    print(f"  a2022 (direction-tagged) n={len(a2022_tag)}  v (1m-truth, direction-tagged) n={len(v_tag)}")

    merged0 = build_tagged_rows(a2022_tag, v_tag, slip=0.0)
    fun0 = eval_funnel(merged0, "R0 naive-union baseline")
    print(f"\n7. R0 naive-union baseline: pass={fun0['s']['pass_pct']} bust={fun0['s']['bust_pct']} "
          f"exp={fun0['s']['exp_pct']} n={fun0['s']['eligible_starts']} vs expected {CANARY_BASELINE} "
          f"(tol {TOL}pp) -> {'PASS' if _canary_ok(fun0['s']) else 'FAIL'}")
    if not _canary_ok(fun0["s"]):
        print("[CANARY FAILURE] STOPPING -- baseline naive-union canary did not reproduce. "
              "Everything downstream (03 and 04) is untrustworthy; not computed.")
        return
    print("[all canaries PASS]\n")

    t03 = time.time()
    df03, computed03 = run_03(a2022_tag, v_tag)
    runtime03 = time.time() - t03

    t04 = time.time()
    df04, canary04_ok = run_04(a2022_tag, v_tag)
    runtime04 = time.time() - t04
    if not canary04_ok:
        print("[ABORT] 04 canary failed -- no 04 report written.")
        df04 = None

    firewall_after = ST.sha_of(FIREWALL_FILES)
    firewall_ok = all(firewall_before[fn] == firewall_after[fn] for fn in FIREWALL_FILES)
    if not firewall_ok:
        print("[FIREWALL FAILURE] a firewalled file changed during this run -- STOPPING, no report written.")
        for fn in FIREWALL_FILES:
            print(f"  {fn}: {'UNCHANGED' if firewall_before[fn] == firewall_after[fn] else 'CHANGED'}")
        return

    write_03(df03, fun0["s"], runtime03, firewall_before, firewall_after)
    if df04 is not None:
        days_funded_const = VR.combined_daily_series(a2022_tag, FUNDED_A_BC[0], FUNDED_A_BC[1],
                                                     v_tag, FUNDED_V_BC[0], FUNDED_V_BC[1])
        rep_const = VR.funded_cell_report(days_funded_const, "04-established-funded-pair")
        e_paid_const = rep_const.get("e_paid") if rep_const.get("n_starts") else 0.0
        write_04(df04, e_paid_const, runtime04, firewall_before, firewall_after)

    runtime_s = time.time() - t_start
    print("\n" + "=" * 100)
    if VR.PF_FLAGS:
        print(f"[FREEZE] {len(VR.PF_FLAGS)} cell(s) breached PF>{VR.PF_FREEZE_THRESHOLD}: {VR.PF_FLAGS}")
    else:
        print(f"No cell anywhere breached PF>{VR.PF_FREEZE_THRESHOLD}.")
    print(f"Total runtime: {runtime_s:.1f}s (03: {runtime03:.1f}s, 04: {runtime04:.1f}s)")
    for fn in FIREWALL_FILES:
        print(f"Firewall {fn}: UNCHANGED")
    print("=" * 100)


if __name__ == "__main__":
    main()
