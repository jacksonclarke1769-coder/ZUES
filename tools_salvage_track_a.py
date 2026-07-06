"""SALVAGE PROGRAM — Track A (items A1+A2+A3), 2026-07-06.

RESEARCH ONLY. Modifies nothing existing. LIVE HOLD ACTIVE. Every output below is
"HONEST-RECERT DRAFT — pending auditor verdict". This module is pure execution against
formulas pinned by the coordinator; no judgment calls are made here (they are reserved to
the auditor). On any reference-canary mismatch this module STOPS and prints both numbers
rather than silently reconciling.

Two canonical streams (both post-INC-20260706-1141, i.e. after the D1c lookahead fix):

  KEPT (honest D1c):   `tools_sim_parity_check.load_rows()` — the certified honest-D1c
                        Profile A + Exit#3 + 1m-truth stream. Reference: n=583, PF 1.361,
                        WR 44.9%, netR +89.2.
  UNFILTERED:          `tools_1m_truth_recert.a_streams(feats, mp, df5)["exit3"]`, filtered
                        to `filled=True`, mapped to rows format dict(ts, R, mae_r, risk_usd)
                        via (R_new, mae_new, risk_usd). This module never used attach_drift,
                        so it walks every Profile-A signal's exit regardless of what D1c would
                        have done — uncontaminated by the D1c lookahead defect from the start.
                        Reference: n=705, PF 1.237, WR 42.8%, totR +74.7.

A per-trade "kept" flag for the UNFILTERED stream is joined by timestamp from the honest CSV
`reports/emergency_recert_d1c_lookahead/honest_d1c_stream.csv` (705 rows, `kept` column =
True for the 583 D1c would keep, False for the 122 it would drop). This flag drives A2 rows
3-5 (engine-window-only / outside-window-only / sizing-modifier).

Sizing machine (identical to the emergency re-cert Wave 2, `tools_account_size_research.py`):
  eligible_starts = one start per unique trading day with >30d runway (module's start
  construction, mirrored here since dl_freq/tl_freq need a trade-level walk that ASR's
  day-collapsed `day_rows` cannot provide -- see `run_cell()`; the day-level bust/pass/expire
  semantics are IDENTICAL to `build_events`+`day_rows`+`eval_run`, verified below by canary).
  Apex 50K spec: start=$50,000 trail=$2,500 target=$3,000 dll=$1,000 ARES-stop=$550.
  E_proxy = pass_pct/100 * 8000 - 131 (column label carries the "8k pending A4" placeholder
  per the coordinator's brief -- NOT a dollar certification).
"""
import os, sys, json, csv, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import strategy_engine_profileA as E
import config
import run_d1c_real as RD
import apex_eval_eod_databento as DB
from tools_1m_truth_recert import M1Map, a_streams as truth_a_streams
from tools_sim_parity_check import load_rows as kept_load_rows
import tools_account_size_research as T

OUT_DIR = "reports/new_edge_salvage_program"
NY = "America/New_York"
EXPIRE_DAYS = 30
SPEC = T.SPECS["50K"]                 # start 50k, trail 2500, target 3000, dll 1000, stop 550
HONEST_CSV = "reports/emergency_recert_d1c_lookahead/honest_d1c_stream.csv"

# ---- pinned reference canaries (STOP on mismatch) --------------------------------------
REF_UNFILTERED = dict(n=705, PF=1.237, WR=42.8, netR=74.7)
REF_KEPT = dict(n=583, PF=1.361, WR=44.9, netR=89.2)
REF_1200_10 = dict(pass_pct=31.4, bust_pct=37.3, exp_pct=31.2, med_days=16, n=525)

BUDGETS_A3 = [100, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800, 900, 1000, 1200]
CAPS_A3 = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20]
SIZING_POINTS_A2 = [(10, 1200), (4, 400), (6, 600)]
YEARS = [2021, 2022, 2023, 2024, 2025, 2026]


# ============================================================== stream construction
def load_streams():
    """Build both canonical streams + the joined kept flag on the 705-row unfiltered set."""
    d1_tz = RD.load_1m(); d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m(); mp = M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    feats = eng._features()

    A = truth_a_streams(feats, mp, df5)
    unfiltered_raw = [t for t in A["exit3"] if t["filled"]]

    honest = pd.read_csv(HONEST_CSV)
    honest["ts_p"] = pd.to_datetime(honest["ts"])
    kept_map = dict(zip(honest["ts_p"], honest["kept"]))

    unfiltered = []
    for t in unfiltered_raw:
        ts = t["ts"]
        ts_l = ts.tz_localize(NY) if ts.tzinfo is None else ts
        kept = bool(kept_map.get(ts_l, False))
        unfiltered.append(dict(ts=ts, R=t["R_new"], mae_r=t["mae_new"], risk_usd=t["risk_usd"],
                               kept=kept, in_window=(ts.hour == 10 and ts.minute < 30)))
    unfiltered.sort(key=lambda x: x["ts"])

    kept_rows_ref = kept_load_rows()          # canonical honest-D1c stream (583)

    weeks_span = (d1_tz.index.max() - d1_tz.index.min()).days / 7.0
    return dict(unfiltered=unfiltered, kept_ref=kept_rows_ref, weeks_span=weeks_span,
                span_start=str(d1_tz.index.min()), span_end=str(d1_tz.index.max()))


def stream_stats(rs):
    r = np.array([x for x in rs if x is not None], float)
    wins = r[r > 0].sum(); losses = -r[r <= 0].sum()
    return dict(n=len(r), netR=round(float(r.sum()), 1), PF=round(float(wins / losses), 3) if losses else None,
                WR=round(float(100.0 * (r > 0).mean()), 1), expR=round(float(r.mean()), 3))


# ============================================================== canary checks
def check_canaries(streams):
    unf = streams["unfiltered"]; kept = streams["kept_ref"]
    su = stream_stats([t["R"] for t in unf])
    sk = stream_stats([t["R"] for t in kept])

    ok = True
    if (su["n"], round(su["PF"], 3), su["WR"], round(su["netR"], 1)) != \
       (REF_UNFILTERED["n"], REF_UNFILTERED["PF"], REF_UNFILTERED["WR"], REF_UNFILTERED["netR"]):
        print(f"[CANARY MISMATCH] UNFILTERED: got n={su['n']} PF={su['PF']} WR={su['WR']} "
              f"netR={su['netR']}  expected {REF_UNFILTERED}")
        ok = False
    if (sk["n"], round(sk["PF"], 3), sk["WR"], round(sk["netR"], 1)) != \
       (REF_KEPT["n"], REF_KEPT["PF"], REF_KEPT["WR"], REF_KEPT["netR"]):
        print(f"[CANARY MISMATCH] KEPT: got n={sk['n']} PF={sk['PF']} WR={sk['WR']} "
              f"netR={sk['netR']}  expected {REF_KEPT}")
        ok = False

    row = run_cell(kept, cap=10, budget=1200, mode="plain")
    if (row["pass_pct"], row["bust_pct"], row["exp_pct"], row["median_days_pass"], row["eligible_starts"]) != \
       (REF_1200_10["pass_pct"], REF_1200_10["bust_pct"], REF_1200_10["exp_pct"],
        REF_1200_10["med_days"], REF_1200_10["n"]):
        print(f"[CANARY MISMATCH] (10,$1200) kept row: got pass={row['pass_pct']} bust={row['bust_pct']} "
              f"exp={row['exp_pct']} med={row['median_days_pass']}d n={row['eligible_starts']}  "
              f"expected {REF_1200_10}")
        ok = False

    return ok, su, sk, row


# ============================================================== trade-level eval-cell engine
def _q_plain(t, budget, cap):
    return min(cap, int(budget // t["risk_usd"]))


def _q_sizing_modifier(t, budget, cap):
    b = budget if t.get("kept", True) else budget / 2.0
    return min(cap, int(b // t["risk_usd"]))


def run_cell(rows, cap, budget, mode="plain", spec=SPEC):
    """Full eval-cell run: build_events-equivalent sizing -> day-level bust/pass/expire
    (identical semantics to `tools_account_size_research.build_events/day_rows/eval_run`,
    verified by the (10,$1200) canary) -- but walked at TRADE granularity so dl_freq/tl_freq
    (consecutive-losing-trade runs) can be measured in the same pass. mode='plain' sizes
    every trade off the single `budget`; mode='sizing_modifier' halves the budget for
    kept==False trades (D1c-rejected) and uses the full budget for kept==True trades.
    """
    q_fn = _q_sizing_modifier if mode == "sizing_modifier" else _q_plain
    n_pool = len(rows)
    n_too_small = 0
    trades = []
    risk_pool, contracts_pool = [], []
    for t in rows:
        q = q_fn(t, budget, cap)
        if q < 1:
            n_too_small += 1
            continue
        trades.append(dict(ts=pd.Timestamp(t["ts"]), risk=t["risk_usd"], R=t["R"],
                           mae_r=t["mae_r"], q=q))
        risk_pool.append(t["risk_usd"]); contracts_pool.append(q)

    if n_pool == 0 or n_too_small / n_pool > 0.5:
        return dict(skipped=True, n_pool=n_pool, n_too_small=n_too_small)

    trades.sort(key=lambda x: x["ts"])
    days_trades = {}
    for t in trades:
        d = t["ts"].normalize()
        days_trades.setdefault(d, []).append(t)
    unique_days = sorted(days_trades)
    last_day = unique_days[-1]
    starts = [i for i, d in enumerate(unique_days) if (last_day - d).days > EXPIRE_DAYS]

    sb, tr, tg = spec["start"], spec["trail"], spec["target"]
    stop, dll = spec["stop"], spec["dll"]

    results = []            # (status, day_offset_or_None, max_streak, n_exec, start_day)
    for s0 in starts:
        thr, bal, peak, locked = sb - tr, sb, sb, False
        t0 = unique_days[s0]
        streak = 0; max_streak = 0; n_exec = 0
        status, offset = "INCOMPLETE", None
        for di in range(s0, len(unique_days)):
            d = unique_days[di]
            if (d - t0).days > EXPIRE_DAYS:
                status, offset = "EXPIRE", EXPIRE_DAYS
                break
            day_real, day_trough, day_stopped = 0.0, 0.0, False
            for t in days_trades[d]:
                if day_stopped:
                    break
                pnl = t["R"] * t["risk"] * t["q"]
                mae = min(0.0, t["mae_r"]) * t["risk"] * t["q"]
                day_trough = min(day_trough, day_real + mae)
                day_real += pnl
                n_exec += 1
                if pnl <= 0:
                    streak += 1; max_streak = max(max_streak, streak)
                else:
                    streak = 0
                if day_real <= -stop:
                    day_stopped = True
            if day_trough <= -dll:
                real, trough = -dll, -dll
            else:
                real, trough = day_real, day_trough
            if bal + min(0.0, trough) <= thr:
                status, offset = "BUST", (d - t0).days
                break
            bal += real
            peak = max(peak, bal)
            if not locked:
                thr = max(thr, peak - tr)
                if peak - tr >= sb + 100.0:
                    thr = sb + 100.0; locked = True
            if bal <= thr:
                status, offset = "BUST", (d - t0).days
                break
            if bal >= sb + tg:
                status, offset = "PASS", (d - t0).days
                break
        results.append((status, offset, max_streak, n_exec, t0))

    n = len(results)
    pass_r = [r for r in results if r[0] == "PASS"]
    bust_r = [r for r in results if r[0] == "BUST"]
    exp_r = [r for r in results if r[0] == "EXPIRE"]
    pass_pct = 100 * len(pass_r) / n
    bust_pct = 100 * len(bust_r) / n
    exp_pct = 100 * len(exp_r) / n
    med = round(float(np.median([r[1] for r in pass_r])), 1) if pass_r else None
    mean_days = float(np.mean([(r[1] if r[0] != "EXPIRE" else EXPIRE_DAYS) for r in results]))
    dl = 100 * sum(1 for r in results if r[2] >= 2) / n
    tl = 100 * sum(1 for r in results if r[2] >= 3) / n
    trades_per_eval = float(np.mean([r[3] for r in results]))
    funded_per_slot_year = (365.25 / mean_days) * (len(pass_r) / n) if mean_days else 0.0
    e_proxy = (pass_pct / 100) * 8000.0 - 131.0

    return dict(skipped=False, pass_pct=round(pass_pct, 1), bust_pct=round(bust_pct, 1),
                exp_pct=round(exp_pct, 1), median_days_pass=med,
                mean_days_per_attempt=round(mean_days, 2), pass_count=len(pass_r),
                eligible_starts=n, funded_per_slot_year=round(funded_per_slot_year, 4),
                e_proxy=round(e_proxy, 1), dl_freq=round(dl, 1), tl_freq=round(tl, 1),
                trades_per_eval=round(trades_per_eval, 2),
                mean_risk_usd=round(float(np.mean(risk_pool)), 2) if risk_pool else None,
                mean_contracts=round(float(np.mean(contracts_pool)), 3) if contracts_pool else None,
                results=results, n_pool=n_pool, n_too_small=n_too_small)


def per_year_pass(results):
    out = {}
    for y in YEARS:
        yr = [r for r in results if r[4].year == y]
        out[y] = round(100 * sum(1 for r in yr if r[0] == "PASS") / len(yr), 1) if yr else None
    return out


# ============================================================== A2 stream construction
def a2_streams(unfiltered):
    row1 = [t for t in unfiltered]                                              # unfiltered A (705)
    row2 = [t for t in unfiltered if t["kept"]]                                  # honest D1c kept (583)
    row3 = [t for t in unfiltered if t["kept"] or t["in_window"]]                # engine-window-only
    row4 = [t for t in unfiltered if t["kept"] or (not t["in_window"])]          # outside-window-only
    row5 = list(unfiltered)                                                     # sizing-modifier (all 705)
    return {
        "(1) unfiltered A": row1,
        "(2) honest-D1c kept": row2,
        "(3) D1c-engine-window-only": row3,
        "(4) D1c-outside-window-only": row4,
        "(5) D1c-as-sizing-modifier": row5,
    }


# ============================================================== report writers
def write_a1(streams, su, sk, row_1200_10, canary_ok):
    os.makedirs(OUT_DIR, exist_ok=True)
    payload = dict(
        status="HONEST-RECERT DRAFT — pending auditor verdict",
        repo_head=REPO_HEAD, incident="INC-20260706-1141",
        stream_unfiltered=dict(source="tools_1m_truth_recert.a_streams(...)['exit3'] "
                                       "(filled==True only), rows(ts,R=R_new,mae_r=mae_new,risk_usd)",
                                measured=su, reference=REF_UNFILTERED,
                                match=(su["n"] == REF_UNFILTERED["n"] and su["PF"] == REF_UNFILTERED["PF"]
                                       and su["WR"] == REF_UNFILTERED["WR"] and su["netR"] == REF_UNFILTERED["netR"])),
        stream_kept=dict(source="tools_sim_parity_check.load_rows()", measured=sk, reference=REF_KEPT,
                         match=(sk["n"] == REF_KEPT["n"] and sk["PF"] == REF_KEPT["PF"]
                                and sk["WR"] == REF_KEPT["WR"] and sk["netR"] == REF_KEPT["netR"])),
        row_10_1200=dict(measured=dict(pass_pct=row_1200_10["pass_pct"], bust_pct=row_1200_10["bust_pct"],
                                        exp_pct=row_1200_10["exp_pct"], med_days=row_1200_10["median_days_pass"],
                                        n=row_1200_10["eligible_starts"]),
                         reference=REF_1200_10, tolerance_pp=0.5),
        canary_ok=canary_ok,
        data_span=dict(start=streams["span_start"], end=streams["span_end"],
                       weeks=round(streams["weeks_span"], 1)),
    )
    with open(f"{OUT_DIR}/A1_honest_baseline_reproduction.json", "w") as f:
        json.dump(payload, f, indent=1, default=str)

    md = f"""# A1 — Honest Baseline Reproduction

HONEST-RECERT DRAFT — pending auditor verdict

Incident: INC-20260706-1141 (D1c lookahead fix). Repo HEAD: `{REPO_HEAD}`.
LIVE HOLD ACTIVE — no live/config/funded changes made. Research only.

## Stream canaries (both post-INC-fix)

| stream | source | n | PF | WR% | netR | reference | match |
|---|---|---|---|---|---|---|---|
| UNFILTERED | `tools_1m_truth_recert.a_streams(...)["exit3"]`, filled==True | {su['n']} | {su['PF']} | {su['WR']} | {su['netR']:+.1f} | n={REF_UNFILTERED['n']} PF={REF_UNFILTERED['PF']} WR={REF_UNFILTERED['WR']} netR={REF_UNFILTERED['netR']:+.1f} | {'MATCH' if su['n']==REF_UNFILTERED['n'] and su['PF']==REF_UNFILTERED['PF'] and su['WR']==REF_UNFILTERED['WR'] and su['netR']==REF_UNFILTERED['netR'] else 'MISMATCH'} |
| KEPT (honest D1c) | `tools_sim_parity_check.load_rows()` | {sk['n']} | {sk['PF']} | {sk['WR']} | {sk['netR']:+.1f} | n={REF_KEPT['n']} PF={REF_KEPT['PF']} WR={REF_KEPT['WR']} netR={REF_KEPT['netR']:+.1f} | {'MATCH' if sk['n']==REF_KEPT['n'] and sk['PF']==REF_KEPT['PF'] and sk['WR']==REF_KEPT['WR'] and sk['netR']==REF_KEPT['netR'] else 'MISMATCH'} |

Data span: {streams['span_start']} .. {streams['span_end']} ({streams['weeks_span']:.1f} weeks).

## (10, $1,200) kept-stream eval row

Apex 50K spec (start $50,000, trail $2,500, target $3,000, DLL $1,000, ARES stop $550),
`MAX_A_QTY` overridden to cap=10, budget=$1,200, via `build_events`/`day_rows`/`eval_run`-equivalent
trade-level walk (`tools_salvage_track_a.run_cell`, verified structurally identical to
`tools_account_size_research.build_events`+`day_rows`+`eval_run`).

| | pass% | bust% | expire% | median_days(pass) | n |
|---|---|---|---|---|---|
| computed | {row_1200_10['pass_pct']} | {row_1200_10['bust_pct']} | {row_1200_10['exp_pct']} | {row_1200_10['median_days_pass']} | {row_1200_10['eligible_starts']} |
| reference | {REF_1200_10['pass_pct']} | {REF_1200_10['bust_pct']} | {REF_1200_10['exp_pct']} | {REF_1200_10['med_days']} | {REF_1200_10['n']} |

Tolerance: 0.5pp per leg. Verdict: **{'MATCH' if canary_ok else 'MISMATCH — SEE ABOVE'}**

## Canary verdict

{'All three canaries MATCH within tolerance. Proceeding to A2/A3.' if canary_ok else 'CANARY MISMATCH DETECTED — see JSON for both numbers. STOPPING per task instructions.'}
"""
    with open(f"{OUT_DIR}/A1_honest_baseline_reproduction.md", "w") as f:
        f.write(md)


def write_a2(streams):
    unfiltered = streams["unfiltered"]
    stream_defs = a2_streams(unfiltered)
    weeks = streams["weeks_span"]

    fieldnames = ["stream", "n_trades_in_stream", "trades_per_week", "PF", "WR_pct", "expR", "netR",
                  "budget", "cap", "mode", "skipped", "pass_pct", "bust_pct", "exp_pct",
                  "median_days_pass", "mean_days_per_attempt", "pass_count", "eligible_starts",
                  "funded_per_slot_year", "dl_freq", "tl_freq", "trades_per_eval",
                  "mean_risk_usd", "mean_contracts"] + [f"pass_pct_{y}" for y in YEARS]

    csv_rows = []
    md_rows = []
    for label, rows in stream_defs.items():
        s = stream_stats([t["R"] for t in rows])
        tpw = round(len(rows) / weeks, 3)
        mode = "sizing_modifier" if label.startswith("(5)") else "plain"
        for cap, budget in SIZING_POINTS_A2:
            cell = run_cell(rows, cap=cap, budget=budget, mode=mode)
            base = dict(stream=label, n_trades_in_stream=len(rows), trades_per_week=tpw,
                       PF=s["PF"], WR_pct=s["WR"], expR=s["expR"], netR=s["netR"],
                       budget=budget, cap=cap, mode=mode)
            if cell.get("skipped"):
                row = dict(base, skipped=True, pass_pct=None, bust_pct=None, exp_pct=None,
                          median_days_pass=None, mean_days_per_attempt=None, pass_count=None,
                          eligible_starts=None, funded_per_slot_year=None, dl_freq=None,
                          tl_freq=None, trades_per_eval=None, mean_risk_usd=None,
                          mean_contracts=None)
                for y in YEARS:
                    row[f"pass_pct_{y}"] = None
            else:
                py = per_year_pass(cell["results"])
                row = dict(base, skipped=False, pass_pct=cell["pass_pct"], bust_pct=cell["bust_pct"],
                          exp_pct=cell["exp_pct"], median_days_pass=cell["median_days_pass"],
                          mean_days_per_attempt=cell["mean_days_per_attempt"],
                          pass_count=cell["pass_count"], eligible_starts=cell["eligible_starts"],
                          funded_per_slot_year=cell["funded_per_slot_year"], dl_freq=cell["dl_freq"],
                          tl_freq=cell["tl_freq"], trades_per_eval=cell["trades_per_eval"],
                          mean_risk_usd=cell["mean_risk_usd"], mean_contracts=cell["mean_contracts"])
                for y in YEARS:
                    row[f"pass_pct_{y}"] = py[y]
            csv_rows.append(row)
            md_rows.append(row)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(f"{OUT_DIR}/A2_d1c_vs_unfiltered_funnel.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in csv_rows:
            w.writerow(r)

    hdr = "| " + " | ".join(fieldnames) + " |\n" + "|" + "---|" * len(fieldnames) + "\n"
    body = ""
    for r in md_rows:
        body += "| " + " | ".join("" if r[k] is None else str(r[k]) for k in fieldnames) + " |\n"

    md = f"""# A2 — D1c vs Unfiltered Funnel

HONEST-RECERT DRAFT — pending auditor verdict

Incident: INC-20260706-1141. Numbers only, no interpretation — the auditor writes the interpretation.
Repo HEAD: `{REPO_HEAD}`. LIVE HOLD ACTIVE.

Five streams, each evaluated at three sizing points {{(cap=10,$1200) legacy, (cap=4,$400), (cap=6,$600)}}:

1. Unfiltered A (705 signals, `tools_1m_truth_recert.a_streams(...)["exit3"]`, filled==True) — plain sizing.
2. Honest D1c kept (583, `tools_sim_parity_check.load_rows()`) — plain sizing.
3. D1c-engine-window-only: keep = d1c_keep OR entry in 10:00-10:29 ET (D1c gates only non-engine-window trades) — plain sizing.
4. D1c-outside-window-only: keep = d1c_keep OR entry NOT in 10:00-10:29 ET — plain sizing.
5. D1c-as-sizing-modifier: all 705 trades; kept==False trades sized at HALF budget
   (q=min(cap,(budget/2)//risk_usd)), kept==True trades at full budget. Kept flag joined onto
   the unfiltered 705-row stream by timestamp from `{HONEST_CSV}`'s `kept` column.

`trades_per_week` = n_trades_in_stream / {weeks:.1f} (data span {streams['span_start']} .. {streams['span_end']}).
PF/WR/expR/netR are stream-level (unsized, R units) trade stats of that filtered row-set, not eval outputs.
`mean_days_per_attempt`/`funded_per_slot_year`/`dl_freq`/`tl_freq`/E_proxy formulas per
`tools_salvage_track_a.run_cell` (identical semantics to `tools_account_size_research`
`build_events`/`day_rows`/`eval_run`, verified by the A1 (10,$1200) canary).
`pass_pct_<year>` = pass% restricted to eligible starts whose start day falls in that calendar year.

{hdr}{body}
"""
    with open(f"{OUT_DIR}/A2_d1c_vs_unfiltered_funnel.md", "w") as f:
        f.write(md)


def write_a3(streams):
    unfiltered = streams["unfiltered"]
    a2s = a2_streams(unfiltered)
    stream_defs = {
        "unfiltered": (a2s["(1) unfiltered A"], "plain"),
        "kept": (a2s["(2) honest-D1c kept"], "plain"),
        "sizing-modifier": (a2s["(5) D1c-as-sizing-modifier"], "sizing_modifier"),
    }

    fieldnames = ["stream", "budget", "cap", "skipped", "pass_pct", "bust_pct", "exp_pct",
                  "median_days_pass", "mean_days_per_attempt", "pass_count", "eligible_starts",
                  "funded_per_slot_year", "E_proxy_PLACEHOLDER_funded_value_8k_pending_A4",
                  "dl_freq", "tl_freq", "trades_per_eval", "mean_risk_usd", "mean_contracts"]

    rows = []
    total = len(BUDGETS_A3) * len(CAPS_A3) * len(stream_defs)
    done = 0
    for sname, (srows, mode) in stream_defs.items():
        for budget in BUDGETS_A3:
            for cap in CAPS_A3:
                cell = run_cell(srows, cap=cap, budget=budget, mode=mode)
                done += 1
                if done % 50 == 0:
                    print(f"  A3 progress: {done}/{total}", flush=True)
                if cell.get("skipped"):
                    rows.append(dict(stream=sname, budget=budget, cap=cap, skipped="SKIPPED_TOO_SMALL",
                                     pass_pct=None, bust_pct=None, exp_pct=None, median_days_pass=None,
                                     mean_days_per_attempt=None, pass_count=None, eligible_starts=None,
                                     funded_per_slot_year=None,
                                     **{"E_proxy_PLACEHOLDER_funded_value_8k_pending_A4": None},
                                     dl_freq=None, tl_freq=None, trades_per_eval=None,
                                     mean_risk_usd=None, mean_contracts=None))
                else:
                    rows.append(dict(stream=sname, budget=budget, cap=cap, skipped="",
                                     pass_pct=cell["pass_pct"], bust_pct=cell["bust_pct"],
                                     exp_pct=cell["exp_pct"], median_days_pass=cell["median_days_pass"],
                                     mean_days_per_attempt=cell["mean_days_per_attempt"],
                                     pass_count=cell["pass_count"], eligible_starts=cell["eligible_starts"],
                                     funded_per_slot_year=cell["funded_per_slot_year"],
                                     **{"E_proxy_PLACEHOLDER_funded_value_8k_pending_A4": cell["e_proxy"]},
                                     dl_freq=cell["dl_freq"], tl_freq=cell["tl_freq"],
                                     trades_per_eval=cell["trades_per_eval"],
                                     mean_risk_usd=cell["mean_risk_usd"], mean_contracts=cell["mean_contracts"]))

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(f"{OUT_DIR}/A3_conservative_sizing_frontier.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    sorted_rows = sorted(rows, key=lambda r: (r["funded_per_slot_year"] is None,
                                              -(r["funded_per_slot_year"] or -1)))
    shortlist = [r for r in rows if r["pass_pct"] is not None and r["pass_pct"] > r["bust_pct"]
                and r["pass_pct"] >= 20]
    shortlist.sort(key=lambda r: -(r["funded_per_slot_year"] or 0))

    def row_line(r):
        return "| " + " | ".join("" if r[k] in (None, "") else str(r[k]) for k in fieldnames) + " |"

    hdr = "| " + " | ".join(fieldnames) + " |\n" + "|" + "---|" * len(fieldnames) + "\n"
    full_body = "\n".join(row_line(r) for r in sorted_rows)
    shortlist_body = "\n".join(row_line(r) for r in shortlist)

    md = f"""# A3 — Conservative Sizing Frontier

HONEST-RECERT DRAFT — pending auditor verdict

Incident: INC-20260706-1141. Numbers only — no ranking commentary, no candidate selection.
The auditor judges the frontier and viability. Repo HEAD: `{REPO_HEAD}`. LIVE HOLD ACTIVE.

{len(BUDGETS_A3)} budgets x {len(CAPS_A3)} caps x {len(stream_defs)} streams = {len(rows)} cells.
Budgets: {BUDGETS_A3}. Caps: {CAPS_A3}. Streams: unfiltered (705, plain sizing), kept (583,
honest D1c, plain sizing), sizing-modifier (all 705, kept==False trades at half budget).
Cells with q<1 for >50% of that stream's trades at the given (budget,cap) are marked
`SKIPPED_TOO_SMALL` (all metric columns blank). Formulas: see `tools_salvage_track_a.run_cell`
docstring (identical eval semantics to `tools_account_size_research.build_events`/`day_rows`/
`eval_run`, verified by the A1 (10,$1200) canary).

## Full table, sorted by funded_per_slot_year desc

{hdr}{full_body}

## Viability shortlist (mechanical filter: pass_pct > bust_pct AND pass_pct >= 20)

{hdr}{shortlist_body if shortlist_body else '(no cells meet this filter)'}
"""
    with open(f"{OUT_DIR}/A3_conservative_sizing_frontier.md", "w") as f:
        f.write(md)

    return rows, shortlist


# ============================================================== main
REPO_HEAD = None


def main():
    global REPO_HEAD
    import subprocess
    try:
        REPO_HEAD = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=os.path.dirname(
            os.path.abspath(__file__))).decode().strip()
    except Exception:
        REPO_HEAD = "unknown"

    print("loading frames + both canonical streams…", flush=True)
    streams = load_streams()

    print("checking canaries…", flush=True)
    ok, su, sk, row_1200_10 = check_canaries(streams)
    write_a1(streams, su, sk, row_1200_10, ok)
    if not ok:
        print("\n[STOP] canary mismatch — A1 report written with both numbers; "
              "not proceeding to A2/A3.", flush=True)
        return
    print("[canaries OK]\n", flush=True)

    print("building A2 (D1c vs unfiltered funnel, 5 streams x 3 sizing points)…", flush=True)
    write_a2(streams)
    print("[A2 done]\n", flush=True)

    print("building A3 (conservative sizing frontier, 495 cells)…", flush=True)
    rows, shortlist = write_a3(streams)
    print(f"[A3 done] {len(rows)} cells, {len(shortlist)} in viability shortlist", flush=True)


if __name__ == "__main__":
    main()
