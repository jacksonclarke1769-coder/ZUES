"""tools_salvage_funded_exits.py — SALVAGE PROGRAM Track A, items A4 + A5.

HONEST-RECERT DRAFT — RESEARCH ONLY. LIVE HOLD ACTIVE. Promotes nothing; changes nothing live,
config, or funded-config. `tools_recert_funded.py` and `apex_funded_40.py` are READ-ONLY prior art
(imported, not modified). This file only reads real Databento data + the frozen model and writes
new report files under `reports/new_edge_salvage_program/`.

STREAMS (per task brief, used as instructed):
  kept       = `tools_sim_parity_check.load_rows()` — D1c-honest A/exit3 stream, 583 trades,
               PF 1.361, netR +89.2R (verified below, CANARY).
  unfiltered = `tools_1m_truth_recert.a_streams()["exit3"]`, all-705 path (no D1c gate; 1m-truth
               R_new), PF 1.237, netR +74.7R (verified below, CANARY).

A4 — FUNDED-ONLY VIABILITY: extends `tools_recert_funded.py`'s generalized (budget $, cap
contracts) funded-PA runner (`daily_series`/`monthly_starts`/`run_pa_instrumented`/`cell_report`,
imported unmodified) across both streams x the task's 10 sizing cells. Mechanical classification
only (FUNDED-VIABLE / MARGINAL / NOT-VIABLE per the pinned thresholds) — the auditor makes the
real viability call.

A5 — EXIT RECHECK ON THE HONEST STREAM: re-derives the KEPT stream's 583 raw trade parameters
(entry, stop, direction, model target, risk, 5m fill-bar) via the SAME filter
`tools_phase3_config_sweep.a_streams_d1c()["exit3"]` uses (D1c gate via `run_d1c_real.attach_drift`,
frozen `model01_sweep_mss_fvg` signals) — necessary because the kept stream's R-only rows (as
returned by `tools_sim_parity_check.load_rows()`) do not carry entry/stop/target, and every exit
variant below needs to re-walk the SAME trades under a DIFFERENT exit rule. Each variant re-walk
either calls `tools_1m_truth_recert.walk_1m` UNMODIFIED (variants 1-4, which only change the
(target, partials) arguments already supported by that function) or is a verbatim copy of its body
with ONE documented addition (variants 5-6, which need new exit logic walk_1m does not support) —
every variant preserves the F1 no-same-bar guard, stop-first ordering, and A_SLIP-on-stop
convention. CANARY (mandatory): variant 1 (EXIT3) must reproduce the kept stream's +89.2R/PF 1.361
EXACTLY, using the model's own stored `t.target` (not a recomputed 2R — verified bit-for-bit
against `tools_sim_parity_check.load_rows()` this session; a naive recomputed-2R target differs by
~1e-3R/trade from tick-rounding in the frozen model's own target field). STOP on mismatch.

PRE-REGISTERED PRIOR (printed verbatim in A5's own output too): SINGLE_1R's old promotion was an
F1 (entry-bar target look-ahead) artifact; exit comparisons are certification-sensitive; this
report states numbers only, no recommendation.

Eval funnel (A5's two sizing points) reuses `tools_account_size_research.py`'s pinned formulas
verbatim (imported, not retyped): `build_events`/`day_rows`/`eval_run`, EXPIRE_DAYS=30, eligible
starts = one start per unique trading day with >30-day forward runway, `funded_per_slot_year` =
365.25 / mean_days_all x (pass_count / eligible_starts).
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import strategy_engine_profileA as E        # also inserts .../ict-nq-framework/models onto sys.path
import model01_sweep_mss_fvg as M1          # FROZEN model — read-only import
import config
import run_d1c_real as RD
import apex_eval_eod_databento as DB
import tools_1m_truth_recert as H1M         # prior art, READ-ONLY (walk_1m, M1Map, A_PARAMS, DPP, A_SLIP, a_streams)
import tools_sim_parity_check as SPC        # prior art, READ-ONLY (load_rows == the 'kept' stream)
import tools_recert_funded as RF            # prior art, READ-ONLY (generalized funded-PA runner)
import tools_account_size_research as ASR   # prior art, READ-ONLY (eval funnel pinned formulas)

OUTDIR = "reports/new_edge_salvage_program"
os.makedirs(OUTDIR, exist_ok=True)

MAX_BARS = M1.MAX_HOLD                      # 48 5m bars — same convention as the certified A stream
EXPIRE_DAYS = ASR.EXPIRE_DAYS                # 30, imported not retyped
SPEC_50K = dict(start=50_000.0, trail=2_500.0, target=3_000.0)   # ASR.SPECS["50K"] eval-relevant fields
STOP_50K, DLL_50K = 550.0, 1_000.0                                # ASR.SPECS["50K"]["stop"/"dll"]

PRE_REGISTERED_PRIOR = ("SINGLE_1R's old promotion was an F1 artifact; exit comparisons are "
                         "certification-sensitive; report numbers, no recommendation.")

LABEL = "HONEST-RECERT DRAFT — pending auditor verdict + operator approval"


# =============================================================================================
# STREAM LOADERS + CANARIES
# =============================================================================================

KEPT_EXPECT = dict(n=583, PF=1.361, WR=44.9, netR=89.2)
UNFILTERED_EXPECT = dict(n=705, PF=1.237, WR=42.8, netR=74.7)


def _stream_stats(rows):
    r = np.array([t["R"] for t in rows], float)
    wins = r[r > 0].sum()
    losses = -r[r <= 0].sum()
    return dict(n=len(r), PF=round(float(wins / losses), 3),
                WR=round(100.0 * float((r > 0).mean()), 1), netR=round(float(r.sum()), 1))


def load_kept_stream():
    """Stream 'kept': `tools_sim_parity_check.load_rows()`, used as instructed — not regenerated."""
    rows = SPC.load_rows()
    s = _stream_stats(rows)
    ok = s == KEPT_EXPECT
    print(f"  kept stream (tools_sim_parity_check.load_rows()): n={s['n']} PF={s['PF']} "
          f"WR={s['WR']}% netR={s['netR']:+.1f}R  |  expect n={KEPT_EXPECT['n']} "
          f"PF={KEPT_EXPECT['PF']} WR={KEPT_EXPECT['WR']}% netR={KEPT_EXPECT['netR']:+.1f}R "
          f"-> {'OK' if ok else 'MISMATCH'}")
    return rows, ok


def load_unfiltered_stream():
    """Stream 'unfiltered': `tools_1m_truth_recert.a_streams()['exit3']` all-705 path (no D1c
    gate), mapped to the (ts, R, mae_r, risk_usd) row shape shared with the kept stream."""
    d1 = RD.load_1m()
    if d1.index.tz is not None:
        d1 = d1.tz_localize(None)
    df5 = DB.load_databento_5m()
    mp = H1M.M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT)
    eng.buf = df5
    feats = eng._features()
    A = H1M.a_streams(feats, mp, df5)
    rows = [dict(ts=t["ts"], R=t["R_new"], mae_r=(t["mae_new"] or 0.0), risk_usd=t["risk_usd"])
            for t in A["exit3"] if t["R_new"] is not None]
    s = _stream_stats(rows)
    ok = s == UNFILTERED_EXPECT
    print(f"  unfiltered stream (tools_1m_truth_recert.a_streams()['exit3'], all-705): n={s['n']} "
          f"PF={s['PF']} WR={s['WR']}% netR={s['netR']:+.1f}R  |  expect n={UNFILTERED_EXPECT['n']} "
          f"PF={UNFILTERED_EXPECT['PF']} WR={UNFILTERED_EXPECT['WR']}% "
          f"netR={UNFILTERED_EXPECT['netR']:+.1f}R -> {'OK' if ok else 'MISMATCH'}")
    return rows, ok


# =============================================================================================
# A4 — FUNDED-ONLY VIABILITY
# =============================================================================================

CELLS_A4 = [(100, 2), (150, 2), (200, 2), (250, 4), (300, 4), (400, 4), (480, 4), (480, 5),
            (600, 6), (640, 4)]


def classify(bust_pct, e_paid):
    """Mechanical sorting only, per the task brief's pinned thresholds — NOT a viability verdict
    (the auditor makes the real call)."""
    if bust_pct <= 15 and e_paid >= 5_000:
        return "FUNDED-VIABLE"
    if bust_pct <= 25 and e_paid >= 4_000:
        return "MARGINAL"
    return "NOT-VIABLE"


def run_a4(streams):
    print("\n=== A4 — FUNDED-ONLY VIABILITY ===")
    print("canary: tools_recert_funded's generalized (budget,cap) runner vs apex_funded_40 "
          "(kept stream, sizes A3-A6 as a runner-validity check, stream-agnostic):")
    ok = RF.canary(streams["kept"])
    if not ok:
        print("[A4 STOP] tools_recert_funded generalized-runner canary mismatch — "
              "do not trust the A4 cells below.")
        return None

    rows_out = []
    for stream_name, rows in streams.items():
        for budget, cap in CELLS_A4:
            r = RF.cell_report(rows, budget, cap)
            r = dict(r)
            r["stream"] = stream_name
            r["label"] = classify(r["bust_pct"], r["e_paid"])
            rows_out.append(r)
    return rows_out


def write_a4(cells):
    hdr = ["stream", "budget", "cap", "n_starts", "e_paid", "med_paid", "med_months", "bust_pct",
           "closed_max_pct", "data_end_pct", "safety_net_pct", "med_days_to_safety_net",
           "worst_day", "payout_dist_0_pct", "payout_dist_1_pct", "payout_dist_2_pct",
           "payout_dist_3_pct", "payout_dist_4_pct", "payout_dist_5_pct", "payout_dist_6_pct",
           "label"]
    lines = [",".join(hdr)]
    for r in cells:
        pd_ = r["payout_count_dist_pct"]
        row = [r["stream"], r["budget"], r["cap"], r["n_starts"], r["e_paid"], r["med_paid"],
               r["med_months"], r["bust_pct"], r["closed_max_pct"], r["data_end_pct"],
               r["safety_net_pct"],
               (r["med_days_to_safety_net"] if r["med_days_to_safety_net"] is not None else ""),
               r["worst_day"], pd_.get(0, 0.0), pd_.get(1, 0.0), pd_.get(2, 0.0), pd_.get(3, 0.0),
               pd_.get(4, 0.0), pd_.get(5, 0.0), pd_.get(6, 0.0), r["label"]]
        lines.append(",".join(str(x) for x in row))
    with open(f"{OUTDIR}/A4_funded_only_viability.csv", "w") as f:
        f.write("\n".join(lines) + "\n")

    md = []
    md.append("# A4 — Funded-Only Viability\n")
    md.append(f"{LABEL}\n")
    md.append("SALVAGE PROGRAM Track A. Mechanical output only — no interpretation, no candidate "
               "selection. The auditor judges viability; this file is data.\n")
    md.append("## Streams\n")
    md.append("- `kept` = `tools_sim_parity_check.load_rows()` (D1c-honest A/exit3, 583 trades, "
               "PF 1.361, netR +89.2R — verified, see run header).")
    md.append("- `unfiltered` = `tools_1m_truth_recert.a_streams()[\"exit3\"]` all-705 path (no "
               "D1c gate, 1m-truth R_new, PF 1.237, netR +74.7R — verified, see run header).\n")
    md.append("## Runner\n")
    md.append("`tools_recert_funded.py` (imported, not modified): `daily_series(rows, budget, "
               "cap)` generalizes `apex_funded_40.daily_series` to independent (budget $, cap "
               "contracts) pairs; `run_pa_instrumented` reproduces `apex_funded_40.run_pa` "
               "outcome-for-outcome with extra bookkeeping (safety-net day, payout list, "
               "start-year). CANARY (`tools_recert_funded.canary`, run above): generalized runner "
               "reproduces `apex_funded_40.daily_series`/`run_pa` byte-for-byte / "
               "outcome-for-outcome at every equivalent (budget=160xA, cap=A) size — OK, 0 "
               "mismatches.\n")
    md.append("## Mechanical classification (pinned thresholds — sorting only, not a verdict)\n")
    md.append("- **FUNDED-VIABLE**: bust% <= 15 AND E[paid] >= $5,000")
    md.append("- **MARGINAL**: bust% <= 25 AND E[paid] >= $4,000")
    md.append("- **NOT-VIABLE**: else\n")
    md.append("## Table (both streams, all 10 cells, n=49 monthly starts per cell)\n")
    cols = ["stream", "budget", "cap", "n", "E[paid]$", "med paid$", "med months", "bust%",
            "closed_max%", "data_end%", "SN%", "med days->SN", "worst day$", "LABEL"]
    md.append("| " + " | ".join(cols) + " |")
    md.append("|" + "---|" * len(cols))
    for r in cells:
        md.append(f"| {r['stream']} | {r['budget']} | {r['cap']} | {r['n_starts']} | "
                   f"{r['e_paid']:,} | {r['med_paid']:,} | {r['med_months']} | {r['bust_pct']} | "
                   f"{r['closed_max_pct']} | {r['data_end_pct']} | {r['safety_net_pct']} | "
                   f"{r['med_days_to_safety_net'] if r['med_days_to_safety_net'] is not None else '-'} | "
                   f"{r['worst_day']:,} | **{r['label']}** |")
    md.append("\nCSV with the full payout-count distribution per cell/stream: "
               "`A4_funded_only_viability.csv`.\n")
    md.append("## Payout-count distribution (% of 49 starts banking exactly k payouts)\n")
    cols2 = ["stream", "budget", "cap", "k=0", "k=1", "k=2", "k=3", "k=4", "k=5",
             "k=6 (CLOSED_MAX)"]
    md.append("| " + " | ".join(cols2) + " |")
    md.append("|" + "---|" * len(cols2))
    for r in cells:
        pd_ = r["payout_count_dist_pct"]
        md.append(f"| {r['stream']} | {r['budget']} | {r['cap']} | "
                   + " | ".join(f"{pd_.get(k, 0.0)}" for k in range(7)) + " |")
    md.append("\n## Per-start-year outcome split (bust% / closed_max% / data_end%)\n")
    for r in cells:
        years = sorted(r["per_start_year"].keys())
        md.append(f"\n**{r['stream']} — {r['budget']}/{r['cap']}**\n")
        md.append("| " + " | ".join(f"{y} (n={r['per_start_year'][y]['n']})" for y in years)
                   + " |")
        md.append("|" + "---|" * len(years))
        md.append("| " + " | ".join(
            f"{r['per_start_year'][y]['bust_pct']}/{r['per_start_year'][y]['closed_pct']}/"
            f"{r['per_start_year'][y]['data_end_pct']}" for y in years) + " |")
    md.append(f"\n## Caveat (verbatim, `apex_funded_40` / `tools_recert_funded.OVERLAP_CAVEAT`)\n")
    md.append(f"> {RF.OVERLAP_CAVEAT}\n")
    md.append("Every bust%/closed_max%/data_end%/safety_net% figure in this file is an **observed "
               "rate in this model**, over a small number of effectively-independent overlapping-"
               "start samples — not a guaranteed probability. The mechanical labels above are "
               "sorting only; the auditor makes the real viability call.\n")
    with open(f"{OUTDIR}/A4_funded_only_viability.md", "w") as f:
        f.write("\n".join(md) + "\n")


# =============================================================================================
# A5 — EXIT RECHECK ON THE HONEST STREAM
# =============================================================================================

def kept_raw_trades():
    """Raw (ts, direction d, entry, stop, model target, risk, risk_usd, 5m fill-bar) for the SAME
    D1c-kept, ny_am exit3 signals as `tools_phase3_config_sweep.a_streams_d1c()['exit3']` / the
    'kept' stream (583 rows) — kept as raw parameters (not reduced to R) so the six exit variants
    below can re-walk each trade under a different exit rule. Filter mirrored verbatim (risk>0,
    valid fill-bar range, d1c_keep==True); the 1m-truth-fillable gate (walk returns not None) is
    applied per-variant in `build_variant_rows` (entry-fill depends only on entry/direction, not
    on the exit rule, so it is the same 583-trade set for every variant — verified via the
    variant-1 CANARY below)."""
    d1_tz = RD.load_1m()
    d1 = d1_tz.copy()
    d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m()
    mp = H1M.M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT)
    eng.buf = df5
    feats = eng._features()
    params = H1M.A_PARAMS["exit3"]
    tr = M1.run(feats, "NQ", params)
    tr = tr[tr.session == "ny_am"].copy()
    tr = RD.attach_drift(tr, d1_tz, feats.index)
    fi = feats.index
    n5 = len(fi)
    raw = []
    for _, t in tr.iterrows():
        risk = abs(float(t.entry) - float(t.stop))
        fb = int(t.fill_bar)
        if risk <= 0 or not (0 <= fb < n5):
            continue
        if not bool(t["d1c_keep"]):
            continue
        d = 1 if t.direction == "long" else -1
        raw.append(dict(ts=pd.Timestamp(fi[fb]), d=d, entry=float(t.entry), stop=float(t.stop),
                         target_model=float(t.target), risk=risk, risk_usd=risk * H1M.DPP, fb=fb))
    return raw, mp


def walk_exit3(mp, row):
    """(1) EXIT3 baseline — CANARY. Imported `tools_1m_truth_recert.walk_1m`, UNMODIFIED, called
    with the model's OWN target (`t.target`, a tick-rounded ~2R level — not a recomputed pure 2R;
    using the recomputed 2R was verified this session to diverge from the certified stream by
    ~1e-3R/trade). This is what makes it reproduce the kept stream bit-for-bit."""
    partials = [(row["entry"] + row["d"] * 1.0 * row["risk"], 0.5)]
    return H1M.walk_1m(mp, row["fb"], row["d"], row["entry"], row["stop"], row["target_model"],
                        partials, max_5m_bars=MAX_BARS)


def walk_fixed_r(mult):
    """(2)/(3)/(4) fixed all-at-{1,1.5,2}R — thin wrappers around the unmodified imported
    `walk_1m` (only the (target, partials) arguments change; no partial scale-out, target = entry
    + d*mult*risk, i.e. a clean R-multiple of `risk = |entry-stop|`, independent of the model's own
    stored target)."""
    def _walk(mp, row):
        target = row["entry"] + row["d"] * mult * row["risk"]
        return H1M.walk_1m(mp, row["fb"], row["d"], row["entry"], row["stop"], target, [],
                            max_5m_bars=MAX_BARS)
    return _walk


def walk_be_after_tp1(mp, row):
    """(5) BE-after-TP1 — verbatim copy of `walk_1m`'s body (F1 no-same-bar guard / stop-first /
    A_SLIP-on-stop all unchanged) with ONE addition: once the +1R partial fills on bar x, the
    remaining 50%'s stop becomes `entry` starting bar x+1 (`moved_to_be` flag applied at the TOP of
    the next loop iteration, so the partial's own bar still uses the original stop — no same-bar
    retroactive effect; matches the brief: 'stop level = entry from the bar AFTER the partial').
    Same exit3 structure otherwise: partial 50%@+1R (level derived from `risk`), final 50% still
    targets the model's own `target_model` (same level EXIT3 uses) unless stopped at breakeven
    first."""
    d, entry, stop0, risk = row["d"], row["entry"], row["stop"], row["risk"]
    target = row["target_model"]
    fb = row["fb"]
    a, b = mp.window(fb, MAX_BARS)
    if a >= b:
        return None
    a5, b5 = mp.window(fb, 1)
    fill_i = None
    for x in range(a5, min(b5, b)):
        if (mp.L[x] <= entry) if d > 0 else (mp.H[x] >= entry):
            fill_i = x
            break
    if fill_i is None:
        return None
    realized, remaining, mae = 0.0, 1.0, 0.0
    scales = sorted([(entry + d * 1.0 * risk, 0.5)], key=lambda z: z[0] * d)
    si = 0
    stop = stop0
    moved_to_be = False
    for x in range(fill_i, b):
        if moved_to_be:
            stop = entry                       # NEW: BE-after-TP1, effective the bar AFTER the partial
        hi, lo = mp.H[x], mp.L[x]
        adv = (lo - entry) * d if d > 0 else (hi - entry) * d
        mae = min(mae, adv / risk)
        if (lo <= stop) if d > 0 else (hi >= stop):
            r_exit = ((stop - H1M.A_SLIP - entry) / risk) if d > 0 else \
                ((entry - (stop + H1M.A_SLIP)) / risk)
            return realized + remaining * r_exit, mae
        if x == fill_i:
            continue                            # F1: no same-bar target/partial on the fill bar
        while si < len(scales):
            lvl, frac = scales[si]
            if (hi >= lvl) if d > 0 else (lo <= lvl):
                realized += frac * (lvl - entry) * d / risk
                remaining -= frac
                si += 1
                moved_to_be = True               # NEW: engages from the NEXT bar (top-of-loop check)
            else:
                break
        if remaining > 0 and ((hi >= target) if d > 0 else (lo <= target)):
            return realized + remaining * (target - entry) * d / risk, mae
    x = b - 1
    return realized + remaining * (mp.C[x] - entry) * d / risk, mae


def walk_trail_after_1r(mp, row):
    """(6) trail-after-1R — verbatim-style copy of `walk_1m`'s causal skeleton (F1 guard /
    stop-first / A_SLIP-on-stop unchanged), replacing the fixed partial+target with: once price
    touches +1R (favorable, derived from `risk`), engage a trailing stop at (highest close since
    the trigger bar) minus 1R distance (long; mirrored for short), re-evaluated every 1m bar,
    stop-first, with the trail level driving bar x's stop check fixed as of bar x-1's close (no
    lookahead — same 'effective the bar after' causality as variant 5). No partial scale-out, no
    fixed final target — full size rides until the trailing stop is touched or the window times
    out."""
    d, entry, stop0, risk = row["d"], row["entry"], row["stop"], row["risk"]
    trigger = entry + d * 1.0 * risk
    fb = row["fb"]
    a, b = mp.window(fb, MAX_BARS)
    if a >= b:
        return None
    a5, b5 = mp.window(fb, 1)
    fill_i = None
    for x in range(a5, min(b5, b)):
        if (mp.L[x] <= entry) if d > 0 else (mp.H[x] >= entry):
            fill_i = x
            break
    if fill_i is None:
        return None
    mae = 0.0
    stop = stop0
    triggered = False
    hi_since = None
    for x in range(fill_i, b):
        hi, lo, cl = mp.H[x], mp.L[x], mp.C[x]
        adv = (lo - entry) * d if d > 0 else (hi - entry) * d
        mae = min(mae, adv / risk)
        if (lo <= stop) if d > 0 else (hi >= stop):
            r_exit = ((stop - H1M.A_SLIP - entry) / risk) if d > 0 else \
                ((entry - (stop + H1M.A_SLIP)) / risk)
            return r_exit, mae
        if x == fill_i:
            continue                            # F1: no same-bar trigger on the fill bar
        if not triggered:
            touched = (hi >= trigger) if d > 0 else (lo <= trigger)
            if touched:
                triggered = True
                hi_since = cl
                stop = (hi_since - risk) if d > 0 else (hi_since + risk)
        else:
            hi_since = max(hi_since, cl) if d > 0 else min(hi_since, cl)
            stop = (hi_since - risk) if d > 0 else (hi_since + risk)
    x = b - 1
    return (mp.C[x] - entry) * d / risk, mae


VARIANTS = [
    ("1_exit3_baseline", walk_exit3),
    ("2_fixed_1R", walk_fixed_r(1.0)),
    ("3_fixed_1.5R", walk_fixed_r(1.5)),
    ("4_fixed_2R", walk_fixed_r(2.0)),
    ("5_be_after_tp1", walk_be_after_tp1),
    ("6_trail_after_1R", walk_trail_after_1r),
]

SIZING_POINTS = [(1200.0, 10), (400.0, 4)]     # (budget $, cap contracts)


def build_variant_rows(raw, mp, walk_fn):
    rows = []
    for row in raw:
        w = walk_fn(mp, row)
        if w is None:
            continue
        rows.append(dict(ts=row["ts"], R=w[0], mae_r=w[1], risk_usd=row["risk_usd"]))
    return rows


def variant_stats(rows):
    rows_s = sorted(rows, key=lambda x: x["ts"])
    r = np.array([x["R"] for x in rows_s], float)
    wins = r[r > 0].sum()
    losses = -r[r <= 0].sum()
    cum = np.cumsum(r)
    peak = np.maximum.accumulate(cum) if len(cum) else np.array([])
    dd = peak - cum
    maxdd = float(dd.max()) if len(dd) else 0.0
    per_year = {}
    for x in rows_s:
        y = x["ts"].year
        per_year[y] = per_year.get(y, 0.0) + x["R"]
    return dict(n=len(r), WR=round(100.0 * float((r > 0).mean()), 1),
                PF=round(float(wins / losses), 3), expR=round(float(r.mean()), 3),
                totR=round(float(r.sum()), 1), maxDD_R=round(maxdd, 1),
                per_year={y: round(v, 1) for y, v in sorted(per_year.items())})


def eval_funnel(rows, budget, cap):
    """Pinned-formula eval funnel, reusing `tools_account_size_research.py`'s runner verbatim
    (imported, not retyped): `build_events`/`day_rows`/`eval_run`, EXPIRE_DAYS=30. eligible_starts
    = one start per unique trading day with >30-day forward runway. funded_per_slot_year =
    365.25/mean_days_all x (pass_count/eligible_starts)."""
    ev = ASR.build_events(rows, budget, cap)
    days = ASR.day_rows(ev, STOP_50K, DLL_50K)
    if not days:
        return dict(eligible_starts=0, pass_pct=0.0, bust_pct=0.0, exp_pct=0.0,
                    median_days_pass=None, mean_days_all=None, pass_count=0,
                    funded_per_slot_year=0.0)
    starts, seen = [], set()
    for i, (d, _, _) in enumerate(days):
        if d not in seen and (days[-1][0] - d).days > EXPIRE_DAYS:
            seen.add(d)
            starts.append(i)
    res = [ASR.eval_run(days, s, SPEC_50K) for s in starts]
    n = len(res)
    if n == 0:
        return dict(eligible_starts=0, pass_pct=0.0, bust_pct=0.0, exp_pct=0.0,
                    median_days_pass=None, mean_days_all=None, pass_count=0,
                    funded_per_slot_year=0.0)
    pass_count = sum(1 for r in res if r[0] == "PASS")
    bust_count = sum(1 for r in res if r[0] == "BUST")
    exp_count = sum(1 for r in res if r[0] == "EXPIRE")
    mean_days_all = float(np.mean([r[1] for r in res]))
    pass_days = [r[1] for r in res if r[0] == "PASS"]
    median_days_pass = float(np.median(pass_days)) if pass_days else None
    fpsy = (365.25 / mean_days_all) * (pass_count / n) if mean_days_all else 0.0
    return dict(eligible_starts=n, pass_pct=round(100.0 * pass_count / n, 1),
                bust_pct=round(100.0 * bust_count / n, 1),
                exp_pct=round(100.0 * exp_count / n, 1),
                median_days_pass=(round(median_days_pass, 1) if median_days_pass is not None
                                  else None),
                mean_days_all=round(mean_days_all, 2), pass_count=pass_count,
                funded_per_slot_year=round(fpsy, 4))


def run_a5():
    print("\n=== A5 — EXIT RECHECK ON HONEST STREAM ===")
    print(f"PRE-REGISTERED PRIOR: {PRE_REGISTERED_PRIOR}")
    raw, mp = kept_raw_trades()
    print(f"  raw D1c-kept trades: n={len(raw)} (pre 1m-fillable gate)")

    results = {}
    for name, walk_fn in VARIANTS:
        rows = build_variant_rows(raw, mp, walk_fn)
        stats = variant_stats(rows)
        stats["rows"] = rows
        results[name] = stats

    v1 = results["1_exit3_baseline"]
    ok = (v1["n"] == 583 and v1["PF"] == 1.361 and round(v1["totR"], 1) == 89.2)
    print(f"  CANARY (variant 1 EXIT3 vs kept stream): n={v1['n']} PF={v1['PF']} "
          f"totR={v1['totR']:+.1f}R  |  expect n=583 PF=1.361 totR=+89.2R -> "
          f"{'OK' if ok else 'MISMATCH'}")
    if not ok:
        print("[A5 STOP] EXIT3 canary mismatch — do not trust the variant table below.")
        return None

    for name, stats in results.items():
        stats["funnel"] = {f"b{int(b)}c{c}": eval_funnel(stats["rows"], b, c)
                            for b, c in SIZING_POINTS}
        del stats["rows"]
    return results


def write_a5(results):
    hdr = ["variant", "n", "WR", "PF", "expR", "totR", "maxDD_R"]
    years = sorted({y for s in results.values() for y in s["per_year"]})
    hdr += [f"totR_{y}" for y in years]
    for b, c in SIZING_POINTS:
        tag = f"b{int(b)}c{c}"
        hdr += [f"{tag}_pass_pct", f"{tag}_bust_pct", f"{tag}_exp_pct",
                f"{tag}_median_days_pass", f"{tag}_mean_days_all", f"{tag}_pass_count",
                f"{tag}_eligible_starts", f"{tag}_funded_per_slot_year"]
    lines = [",".join(hdr)]
    for name, s in results.items():
        row = [name, s["n"], s["WR"], s["PF"], s["expR"], s["totR"], s["maxDD_R"]]
        row += [s["per_year"].get(y, 0.0) for y in years]
        for b, c in SIZING_POINTS:
            tag = f"b{int(b)}c{c}"
            f = s["funnel"][tag]
            row += [f["pass_pct"], f["bust_pct"], f["exp_pct"],
                    (f["median_days_pass"] if f["median_days_pass"] is not None else ""),
                    (f["mean_days_all"] if f["mean_days_all"] is not None else ""),
                    f["pass_count"], f["eligible_starts"], f["funded_per_slot_year"]]
        lines.append(",".join(str(x) for x in row))
    with open(f"{OUTDIR}/A5_exit_recheck_honest_stream.csv", "w") as f:
        f.write("\n".join(lines) + "\n")

    md = []
    md.append("# A5 — Exit Recheck on the Honest Stream\n")
    md.append(f"{LABEL}\n")
    md.append(f"**PRE-REGISTERED PRIOR**: {PRE_REGISTERED_PRIOR}\n")
    md.append("SALVAGE PROGRAM Track A. Mechanical output only — no interpretation, no candidate "
               "selection.\n")
    md.append("## Source\n")
    md.append("Kept stream's 583 raw trades (D1c-kept, ny_am, exit3 signal set — same filter as "
               "`tools_phase3_config_sweep.a_streams_d1c()['exit3']`), re-derived with full "
               "entry/stop/target/fill-bar precision (not from a CSV round-trip). CANARY: variant "
               "1 (EXIT3 baseline, using the imported unmodified `tools_1m_truth_recert.walk_1m` "
               "with the model's own stored target) reproduces the kept stream's n=583, "
               "PF=1.361, totR=+89.2R EXACTLY.\n")
    md.append("## Variants\n")
    md.append("1. EXIT3 baseline (50%@+1R / 50%@+2R-ish model target) — CANARY.")
    md.append("2. Fixed all-at-1R (no partial).")
    md.append("3. Fixed all-at-1.5R (no partial).")
    md.append("4. Fixed all-at-2R (no partial).")
    md.append("5. BE-after-TP1: exit3 split, but the remaining 50%'s stop moves to entry starting "
               "the bar AFTER the +1R partial fills.")
    md.append("6. Trail-after-1R: no partial/fixed target; once +1R touched, stop trails at "
               "(highest close since the trigger bar) minus 1R distance, evaluated per 1m bar, "
               "stop-first.\n")
    md.append("All six preserve the F1 no-same-bar guard, stop-first ordering, and A_SLIP-on-stop "
              "convention from `tools_1m_truth_recert.walk_1m` (variants 1-4 call that function "
              "unmodified; variants 5-6 are verbatim-copied-and-extended, diffed in code "
              "comments).\n")
    md.append("## Results (all n=583 fillable trades unless noted)\n")
    cols = ["variant", "n", "WR%", "PF", "expR", "totR", "maxDD-R"]
    md.append("| " + " | ".join(cols) + " |")
    md.append("|" + "---|" * len(cols))
    for name, s in results.items():
        md.append(f"| {name} | {s['n']} | {s['WR']} | {s['PF']} | {s['expR']:+.3f} | "
                   f"{s['totR']:+.1f} | {s['maxDD_R']:.1f} |")
    years = sorted({y for s in results.values() for y in s["per_year"]})
    md.append(f"\n## Per-year totR\n")
    md.append("| variant | " + " | ".join(str(y) for y in years) + " |")
    md.append("|" + "---|" * (len(years) + 1))
    for name, s in results.items():
        md.append(f"| {name} | " + " | ".join(f"{s['per_year'].get(y, 0.0):+.1f}"
                                                for y in years) + " |")
    md.append("\n## Eval funnel (pinned formulas from the re-cert — "
               "`tools_account_size_research.py`, imported not retyped)\n")
    for b, c in SIZING_POINTS:
        tag = f"b{int(b)}c{c}"
        md.append(f"\n**({c}, ${int(b)})**\n")
        cols2 = ["variant", "eligible_starts", "pass%", "bust%", "exp%", "median_days_pass",
                 "mean_days_all", "pass_count", "funded_per_slot_year"]
        md.append("| " + " | ".join(cols2) + " |")
        md.append("|" + "---|" * len(cols2))
        for name, s in results.items():
            f = s["funnel"][tag]
            md.append(f"| {name} | {f['eligible_starts']} | {f['pass_pct']} | {f['bust_pct']} | "
                       f"{f['exp_pct']} | "
                       f"{f['median_days_pass'] if f['median_days_pass'] is not None else '-'} | "
                       f"{f['mean_days_all'] if f['mean_days_all'] is not None else '-'} | "
                       f"{f['pass_count']} | {f['funded_per_slot_year']} |")
    md.append("\nNo recommendation is made here — exit comparisons are certification-sensitive "
               "per the pre-registered prior above; the auditor decides.\n")
    with open(f"{OUTDIR}/A5_exit_recheck_honest_stream.md", "w") as f:
        f.write("\n".join(md) + "\n")


# =============================================================================================
def main():
    print("=== SALVAGE PROGRAM Track A — A4/A5 ===")
    print("LIVE HOLD ACTIVE. Research only. Loading + verifying streams…")
    kept_rows, kept_ok = load_kept_stream()
    unfiltered_rows, unfiltered_ok = load_unfiltered_stream()
    if not (kept_ok and unfiltered_ok):
        print("[STOP] one or both stream canaries mismatched their reference numbers — "
              "aborting before A4/A5.")
        return

    streams = dict(kept=kept_rows, unfiltered=unfiltered_rows)

    a4 = run_a4(streams)
    if a4 is not None:
        write_a4(a4)
        print(f"[saved] {OUTDIR}/A4_funded_only_viability.csv / .md")

    a5 = run_a5()
    if a5 is not None:
        write_a5(a5)
        print(f"[saved] {OUTDIR}/A5_exit_recheck_honest_stream.csv / .md")


if __name__ == "__main__":
    main()
