"""EVAL-IMPROVEMENT SPRINT — Ideas 3/4/5/6 (2026-07-06). RESEARCH ONLY, on the FROZEN certified
435-trade Profile A stream (exit3 + D1c, 1m-truth fills). Modifies nothing existing.

FOLLOWS THE ESTABLISHED PATTERN of `tools_wyckoff_a_tags.py` / `tools_sprint_state_policies.py`:
  - Stream + byte-parity firewall: imports `load_frames`/`build_raw_and_kept`/`assert_parity`
    (which itself asserts byte-for-byte identity vs `tools_sim_parity_check.load_rows()`) from
    `tools_profileC_a_enhancement.py` — same base-stream reconstruction, same firewall, no
    duplication of the certified loader.
  - Funnel machinery: `filter_stats`/`eval_funnel`/`as_rows`/`CANARY_EXPECT`/`SPEC50K` (also from
    `tools_profileC_a_enhancement`), run at BOTH sizing bases: (cap10, $1200 — certified/deployed)
    and (cap15, $1000 — standing candidate).
  - Per-year eligible/passing-start COUNTS (not just rounded pass%): `eval_funnel_by_year` /
    `robustness_flags` imported from `tools_wyckoff_a_tags.py` (read-only import; that file already
    built the per-start-year funnel + denominator-artifact-check machinery this sprint's mandatory
    method rule requires).

MANDATORY METHOD RULE (DEC-20260706-1108): every skip/avoid/filter variant reports
funded-accounts-per-slot-year on a COUNT basis (passing-start COUNT and eligible-start COUNT) at
BOTH bases, not just rounded pass%. `count_basis_check()` below flags the "pass% up, pass COUNT
down via start-shrinkage" denominator artifact exactly as `tools_wyckoff_a_tags.py`'s auditor
follow-up does, generalized to every row this file produces (Ideas 3/4/5b). Idea 6 is a
STATE-POLICY trade-skip replay on a FIXED set of 395 eval-starts (same mechanism as
`tools_sprint_state_policies.py`'s 1C stop-bucket-cap policies) — the eligible-start count cannot
shrink there by construction (no start is ever excluded, only individual trades within a start are
skipped), so its count-basis column is reported for completeness but cannot exhibit the
denominator-artifact failure mode Ideas 3/4/5b can.

Causality / documented simplifications (Idea 4 D1c-strength recompute):
  - Raw drift value (points) at a trade's own `ts` (the certified stream's fill-bar timestamp, the
    SAME cutoff `run_d1c_real.attach_drift` uses to decide keep/drop) is recomputed causally off the
    1m frame: last completed 1m close <= ts, minus that calendar day's 09:30 1m open. This is the
    exact `attach_drift` formula, just returning the signed VALUE instead of only the keep/drop bool
    (the stored certified stream keeps only the bool).
  - drift/ATR14(1m) normalizes by a rolling-14-bar ATR of the continuous 1m series (true range,
    causal — uses only bars up to and including the trade's own cutoff bar). Not session-reset per
    day (a documented simplification, same spirit as "freeze the range boundary at the trade's own
    causal cutoff" in `tools_wyckoff_a_tags.py`).
  - Percentile-by-minutes-since-open ranks |drift| against the FULL-SAMPLE historical distribution
    of |drift| at that same minute-of-session offset (built once across all days, all years) — this
    is a RESEARCH-ONLY normalization for post-hoc banding, not a causal/live statistic (the brief
    explicitly says "the live gate stays zero-parameter"; this normalization is not proposed as a
    live rule, only as an analysis lens).
  - Bands are QUINTILES ONLY (`pd.qcut` on rank, 5 equal-count bins) of the certified 435-trade
    population for each normalization — no tuned thresholds, per the brief's explicit anti-parameter-
    soup instruction.

Idea 6 (second trade after first loss, SAME DAY) note: distinct from the prior sprint's C3
(`tools_sprint_state_policies.DoubleLossAwarePolicy`), which sizes down after 2 CONSECUTIVE losses
counted ACROSS DAYS within one eval run. Here "first loss" / "second trade" are counted WITHIN a
single calendar trading day only (the day-scoped state resets every day) — a different, narrower
question. PREREGISTERED PRIORS (checked, not assumed): cross-day consecutive-loss policies (C0-C4)
were all found dead in the prior sprint; "bust and expiry cost the same" (E$/attempt is a pass-rate-
driven proxy, not distinguishing bust vs expire); the 2-loss cliff figure P(pass|2-loss)=14.4% is
quoted from `tools_sprint_state_policies.PRIOR_BASELINE_COHORT` for context but is NOT the same
statistic as this file's same-day double-loss frequency (that figure is per-EVAL-RUN, cross-day
max-consecutive-losses >= 2; this file's is per-TRADING-DAY, first-two-trades-both-lose) — the two
are not directly comparable and this file does not conflate them.
"""
import os, sys, json, csv, subprocess, warnings; warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools_profileC_a_enhancement import (
    load_frames, build_raw_and_kept, assert_parity, filter_stats, eval_funnel, as_rows,
    CANARY_EXPECT, SPEC50K, build_events, day_rows, eval_run, EXPIRE_DAYS,
)
from tools_wyckoff_a_tags import eval_funnel_by_year, robustness_flags
from tools_1m_truth_recert import DPP

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "reports", "eval_improvement_8_ideas")
BASES = (("10_1200", 1200, 10), ("15_1000", 1000, 15))
NY = "America/New_York"


# ============================================================================ shared helpers
def git_head():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE).decode().strip()
    except Exception as e:
        return f"unavailable ({e})"


def count_basis(rows_as_certified, budget, cap, spec=SPEC50K):
    """Sum per-year (n, pass_n) from eval_funnel_by_year -> (total eligible-start COUNT,
    total passing-start COUNT). Same construction `tools_wyckoff_a_tags.py`'s denominator-artifact
    check uses, generalized to every row here."""
    yr = eval_funnel_by_year(rows_as_certified, budget, cap, spec)
    total_n = sum(v["n"] for v in yr.values())
    total_pass_n = sum(v["pass_n"] for v in yr.values())
    return total_n, total_pass_n


def count_basis_check(base_total_n, base_pass_n, var_total_n, var_pass_n):
    """DEC-20260706-1108's specific failure mode is 'pass% UP while pass COUNT DOWN via
    denominator shrinkage' -- NOT merely 'raw pass count fell while the eligible pool shrank'
    (that is true of almost every stream filter trivially, since removing trades can only shrink
    or hold the eligible-starts pool, and usually also removes some passing starts -- flagging on
    that alone would mark nearly every filter variant as an 'artifact' and destroy the signal).
    The check therefore requires BOTH: pass% (recomputed from raw counts, not the rounded funnel
    dict) is HIGHER for the variant, AND the raw passing-start COUNT is LOWER."""
    base_pct = 100.0 * base_pass_n / base_total_n if base_total_n else 0.0
    var_pct = 100.0 * var_pass_n / var_total_n if var_total_n else 0.0
    net_gain = var_pass_n - base_pass_n
    denom_shrink = base_total_n - var_total_n
    artifact = bool(var_pct > base_pct and net_gain < 0 and denom_shrink > 0)
    return dict(baseline_total_n=base_total_n, baseline_pass_n=base_pass_n,
                baseline_pass_pct=round(base_pct, 1),
                variant_total_n=var_total_n, variant_pass_n=var_pass_n,
                variant_pass_pct=round(var_pct, 1),
                net_gain_pass_n=net_gain, denom_shrink=denom_shrink,
                denominator_artifact=artifact)


def run_row_full(subset, kept_all, baseline_funnels, baseline_counts):
    """subset: list of kept-trade dicts (a stream variant of `kept_all`). Returns filter_stats +
    funnel + count-basis (both bases) + auditor flag + denominator-artifact flag."""
    st = filter_stats(subset, kept_all)
    rows_as_cert = as_rows(subset)
    f10 = eval_funnel(rows_as_cert, 1200, 10, SPEC50K)
    f15 = eval_funnel(rows_as_cert, 1000, 15, SPEC50K)
    n10, pn10 = count_basis(rows_as_cert, 1200, 10)
    n15, pn15 = count_basis(rows_as_cert, 1000, 15)
    cb10 = count_basis_check(*baseline_counts["c10"], n10, pn10)
    cb15 = count_basis_check(*baseline_counts["c15"], n15, pn15)
    auditor_flag = (f10["pass_pct"] - baseline_funnels["f10"]["pass_pct"] > 1.0) or \
                   (f15["pass_pct"] - baseline_funnels["f15"]["pass_pct"] > 1.0)
    return dict(**st, funnel_10_1200=f10, funnel_15_1000=f15,
                count_basis_10_1200=cb10, count_basis_15_1000=cb15,
                auditor_review_required=auditor_flag)


def qband(values):
    """Quintile bands (0..4, 0=lowest) via rank-based qcut — no tuned thresholds, ties broken by
    stable rank so every band gets as close to an equal count as the sample allows."""
    s = pd.Series(values)
    ranks = s.rank(method="first")
    bands = pd.qcut(ranks, 5, labels=False)
    return bands.values.astype(int)


# ============================================================================ Idea 3: pockets
POCKET_BOUNDS = [("09:30-10:00", 570, 600), ("10:00-10:30 (engine)", 600, 630),
                  ("10:30-10:45", 630, 645), ("10:45-11:00", 645, 660),
                  ("11:00-11:30", 660, 690)]


def pocket_of(ts):
    m = ts.hour * 60 + ts.minute
    for label, lo, hi in POCKET_BOUNDS:
        if lo <= m < hi:
            return label
    return "other(fill slipped outside 09:30-11:30)"


# ============================================================================ Idea 4: D1c drift
def build_day_opens(d1_tz):
    et = d1_tz.index
    is_open = (et.hour == 9) & (et.minute == 30)
    opens = pd.Series(d1_tz["open"].values[is_open], index=et.normalize()[is_open])
    return opens[~opens.index.duplicated(keep="first")]


def build_atr14_1m(d1_tz):
    h, l, c = d1_tz["high"].values, d1_tz["low"].values, d1_tz["close"].values
    prev_c = np.r_[np.nan, c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    return pd.Series(tr).rolling(14).mean().values


def build_minute_drift_table(d1_tz, opens):
    """day x minute-offset(0..120, 9:30..11:30) drift table for percentile-by-minutes-since-open."""
    et = d1_tz.index
    moc = et.hour * 60 + et.minute
    mask = (moc >= 570) & (moc <= 690)
    sub = pd.DataFrame({"close": d1_tz["close"].values[mask]}, index=et[mask])
    sub["day"] = sub.index.normalize()
    sub["moff"] = (sub.index.hour * 60 + sub.index.minute) - 570
    sub["open"] = sub["day"].map(opens)
    sub["drift"] = sub["close"] - sub["open"]
    return sub.pivot_table(index="day", columns="moff", values="drift", aggfunc="first")


def drift_value_at(d1_tz, opens, ts):
    day = ts.normalize()
    op = opens.get(day, np.nan)
    pos = d1_tz.index.searchsorted(ts, side="right") - 1
    if pos < 0 or not np.isfinite(op):
        return np.nan, -1
    return float(d1_tz["close"].iloc[pos] - op), int(pos)


def pct_rank_at(minute_table, moff, value):
    moff = int(np.clip(moff, 0, 120))
    if moff not in minute_table.columns:
        return np.nan
    col = minute_table[moff].dropna().abs().values
    if len(col) == 0 or not np.isfinite(value):
        return np.nan
    return 100.0 * float((col < abs(value)).mean())


def annotate_pocket_and_drift(kept, d1_tz, atr14_1m):
    opens = build_day_opens(d1_tz)
    minute_table = build_minute_drift_table(d1_tz, opens)
    raw_vals, atr_vals, pct_vals = [], [], []
    for t in kept:
        ts = pd.Timestamp(t["ts"])
        t["pocket"] = pocket_of(ts)
        dr, pos = drift_value_at(d1_tz, opens, ts)
        moff = (ts.hour * 60 + ts.minute) - 570
        atr = atr14_1m[pos] if 0 <= pos < len(atr14_1m) else np.nan
        norm_atr = abs(dr) / atr if (np.isfinite(dr) and np.isfinite(atr) and atr > 0) else np.nan
        pct = pct_rank_at(minute_table, moff, dr)
        t["drift_pts"] = dr
        t["drift_atr_norm"] = norm_atr
        t["drift_pct_rank"] = pct
        raw_vals.append(abs(dr) if np.isfinite(dr) else np.nan)
        atr_vals.append(norm_atr)
        pct_vals.append(pct)
    # fill NaNs (should be none in-sample, but fail-safe: lowest band if missing) before qcut
    raw_vals = pd.Series(raw_vals).fillna(pd.Series(raw_vals).min())
    atr_vals = pd.Series(atr_vals).fillna(pd.Series(atr_vals).min())
    pct_vals = pd.Series(pct_vals).fillna(pd.Series(pct_vals).min())
    band_raw, band_atr, band_pct = qband(raw_vals), qband(atr_vals), qband(pct_vals)
    for i, t in enumerate(kept):
        t["band_raw"] = int(band_raw[i])
        t["band_atr"] = int(band_atr[i])
        t["band_pct"] = int(band_pct[i])
    return kept


# ============================================================================ per-year totR table
def peryear_totr(subset):
    """Plain-python-float per_year dict (filter_stats' numpy round() preserves np.float64, which
    prints ugly as `np.float64(...)` when a dict is f-string-interpolated directly for MD tables)."""
    py = filter_stats(subset, subset)["per_year"]
    return {int(y): float(v) for y, v in py.items()}


def bucket_line_stats(subset):
    r = np.array([t["R"] for t in subset])
    n = len(r)
    if n == 0:
        return dict(n=0, wr=None, pf=None, expr=None, totr=0.0)
    wins = r[r > 0].sum(); losses = -r[r <= 0].sum()
    pf = (wins / losses) if losses > 0 else float("inf")
    return dict(n=n, wr=round(100 * (r > 0).mean(), 1),
                pf=round(pf, 3) if np.isfinite(pf) else pf,
                expr=round(float(r.mean()), 4), totr=round(float(r.sum()), 1))


# ============================================================================ 00 baseline reproduction
def do_baseline(kept, raw, canary10, canary15):
    os.makedirs(OUTDIR, exist_ok=True)
    wr = filter_stats(kept, kept)["wr"]
    ts_all = sorted(pd.Timestamp(t["ts"]) for t in kept)
    weeks = max(1e-9, (ts_all[-1] - ts_all[0]).days / 7.0)
    tr_per_wk = len(kept) / weeks
    head = git_head()
    out = dict(
        head=head,
        provenance="reports/apex_validation.json -> cap10_relock_2026-07-05 (DEC-20260705-1102): "
                   "eval pass_pct 47.8 / bust 15.9 / expire 36.2 / median 16d, same A10 Exit#3+D1c "
                   "config this file's canary reproduces via eval_funnel(as_rows(kept),1200,10).",
        n_kept=len(kept), n_raw=len(raw),
        canary_10_1200=canary10, canary_15_1000=canary15,
        canary_expected=CANARY_EXPECT,
        wr_pct=wr, trades_per_week=round(tr_per_wk, 2),
        span_start=str(ts_all[0]), span_end=str(ts_all[-1]),
    )
    with open(os.path.join(OUTDIR, "00_baseline_reproduction.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    match10 = (canary10["pass_pct"] == CANARY_EXPECT["pass_pct"] and
               canary10["bust_pct"] == CANARY_EXPECT["bust_pct"] and
               canary10["exp_pct"] == CANARY_EXPECT["exp_pct"] and
               canary10["med_days"] == CANARY_EXPECT["med_days"] and
               canary10["n"] == CANARY_EXPECT["n"])
    lines = [
        "# 00 — Baseline reproduction (CANARY) — Ideas 3/4/5/6 sprint",
        "",
        "**RESEARCH ONLY.** Frozen certified Profile A stream (exit3 + D1c, 1m-truth fills). "
        "No entry/exit/live change of any kind.",
        "",
        f"- repo HEAD: `{head}`",
        f"- provenance: {out['provenance']}",
        "",
        "## Canary @ (cap10, $1200 — certified/deployed)",
        f"- got:      pass={canary10['pass_pct']} bust={canary10['bust_pct']} "
        f"exp={canary10['exp_pct']} med={canary10['med_days']}d n={canary10['n']}",
        f"- expected: pass={CANARY_EXPECT['pass_pct']} bust={CANARY_EXPECT['bust_pct']} "
        f"exp={CANARY_EXPECT['exp_pct']} med={CANARY_EXPECT['med_days']}d n={CANARY_EXPECT['n']}",
        f"- **{'MATCH' if match10 else 'MISMATCH — STOP, do not trust anything below'}**",
        "",
        "## Canary @ (cap15, $1000 — standing candidate, for reference)",
        f"- pass={canary15['pass_pct']} bust={canary15['bust_pct']} exp={canary15['exp_pct']} "
        f"med={canary15['med_days']}d n={canary15['n']}",
        "",
        "## Stream confirmations",
        f"- n kept (certified): {len(kept)}  (pre-D1c raw ny_am signals: {len(raw)})",
        f"- WR (raw 435-trade pass, R>0 share): {wr}% — expected ~58.6%",
        f"- trades/week over full span ({out['span_start']} -> {out['span_end']}, "
        f"{round(weeks,1)} weeks): {round(tr_per_wk,2)} — expected ~1.7-1.8/wk",
        "",
        "## Firewall",
        "`assert_parity()` (byte-for-byte vs `tools_sim_parity_check.load_rows()`) checked before "
        "any of the above is trusted — see console output / calling script's PARITY FIREWALL line.",
        "",
        "---",
        "All numbers RESEARCH ONLY / SIM CONDITIONAL. No commits.",
    ]
    with open(os.path.join(OUTDIR, "00_baseline_reproduction.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return match10, out


# ============================================================================ Idea 3: time-of-day
def do_idea3(kept, canary10, canary15, base_counts):
    os.makedirs(OUTDIR, exist_ok=True)
    baseline_funnels = dict(f10=canary10, f15=canary15)
    pocket_labels = [p[0] for p in POCKET_BOUNDS] + ["other(fill slipped outside 09:30-11:30)"]

    per_pocket = {}
    for label in pocket_labels:
        subset = [t for t in kept if t["pocket"] == label]
        st = bucket_line_stats(subset)
        st["per_year"] = peryear_totr(subset) if subset else {}
        per_pocket[label] = st

    policies = {}
    policies["P0_keep_all (baseline)"] = run_row_full(kept, kept, baseline_funnels, base_counts)
    drop_1130 = [t for t in kept if t["pocket"] != "11:00-11:30"]
    policies["P1_drop_11:00-11:30"] = run_row_full(drop_1130, kept, baseline_funnels, base_counts)
    engine_only = [t for t in kept if t["pocket"] == "10:00-10:30 (engine)"]
    policies["P2_engine-only_10:00-10:30"] = run_row_full(engine_only, kept, baseline_funnels, base_counts)

    # pocket x D1c-band(atr) interaction matrix (descriptive n/WR/PF/expR only — cells are thin,
    # NOT run through the funnel; see report note on why)
    band_labels = [0, 1, 2, 3, 4]
    interaction = {}
    for label in pocket_labels:
        for b in band_labels:
            subset = [t for t in kept if t["pocket"] == label and t["band_atr"] == b]
            interaction[(label, b)] = bucket_line_stats(subset)

    # two focused, funnel-tested combo policies from the interaction lens
    combo_drop1130_band0 = [t for t in kept if not (t["pocket"] == "11:00-11:30" and t["band_atr"] == 0)]
    policies["P3a_drop(11:00-11:30 AND band0)"] = run_row_full(combo_drop1130_band0, kept,
                                                                baseline_funnels, base_counts)
    combo_engine_band23 = [t for t in kept if not (t["pocket"] == "10:00-10:30 (engine)"
                                                    and t["band_atr"] not in (2, 3))]
    policies["P3b_engine-pocket_requires_band2-3_else_drop"] = run_row_full(
        combo_engine_band23, kept, baseline_funnels, base_counts)

    baseline_peryear = peryear_totr(kept)
    robustness = {name: robustness_flags(baseline_peryear, r["per_year"])
                  for name, r in policies.items() if name != "P0_keep_all (baseline)"}

    # honest verification of the "11:00-11:30 nearly dead" prior
    nd = per_pocket["11:00-11:30"]
    nearly_dead_verdict = (
        f"n={nd['n']} WR={nd['wr']}% PF={nd['pf']} expR={nd['expr']} totR={nd['totr']:+.1f} -> "
        + ("CONFIRMED weak/dead" if (nd["n"] == 0 or (nd["expr"] is not None and nd["expr"] <= 0.02))
           else "NOT dead — prior overstated, pocket carries positive expectancy")
    )

    _write_idea3_outputs(per_pocket, policies, interaction, robustness, nearly_dead_verdict,
                          baseline_peryear, band_labels, pocket_labels)
    return policies


def _write_idea3_outputs(per_pocket, policies, interaction, robustness, nearly_dead_verdict,
                          baseline_peryear, band_labels, pocket_labels):
    csv_path = os.path.join(OUTDIR, "03_ny_adjacent_window.csv")
    rows = []
    for label, st in per_pocket.items():
        rows.append(dict(section="per_pocket", pocket=label, band="", n=st["n"], wr=st["wr"],
                          pf=st["pf"], expr=st["expr"], totr=st["totr"],
                          per_year=json.dumps(st["per_year"])))
    for name, r in policies.items():
        rows.append(dict(section="policy", pocket=name, band="",
                          n=r["n"], wr=r["wr"], pf=r["pf"], expr=r["expr"], totr=r["totr"],
                          pass_10_1200=r["funnel_10_1200"]["pass_pct"],
                          pass_15_1000=r["funnel_15_1000"]["pass_pct"],
                          eligible_n_10_1200=r["count_basis_10_1200"]["variant_total_n"],
                          pass_n_10_1200=r["count_basis_10_1200"]["variant_pass_n"],
                          eligible_n_15_1000=r["count_basis_15_1000"]["variant_total_n"],
                          pass_n_15_1000=r["count_basis_15_1000"]["variant_pass_n"],
                          denom_artifact_10=r["count_basis_10_1200"]["denominator_artifact"],
                          denom_artifact_15=r["count_basis_15_1000"]["denominator_artifact"],
                          auditor_flag=r["auditor_review_required"]))
    for (label, b), st in interaction.items():
        rows.append(dict(section="pocket_x_band_atr", pocket=label, band=b, n=st["n"], wr=st["wr"],
                          pf=st["pf"], expr=st["expr"], totr=st["totr"]))
    fieldnames = sorted({k for row in rows for k in row})
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    lines = ["# Idea 3 — Time-of-day pockets — RESEARCH ONLY / SIM CONDITIONAL", "",
             "09:30-11:30 is A's whole entry window; pockets tested here are SUBSETS of it. "
             "Pocket assigned from each trade's own `ts` (the certified stream's fill-bar "
             "timestamp, NY-local) — the same convention used for `filter_stats`/`eval_funnel`.",
             "", "## Per-pocket stats (n / WR / PF / expR / totR, pooled over the 435-trade stream)",
             "", "| pocket | n | WR% | PF | expR | totR | per-year totR |", "|---|---|---|---|---|---|---|"]
    for label, st in per_pocket.items():
        lines.append(f"| {label} | {st['n']} | {st['wr']} | {st['pf']} | {st['expr']} | "
                      f"{st['totr']:+.1f} | {st['per_year']} |")
    lines += ["", f"**'11:00-11:30 nearly dead' prior check:** {nearly_dead_verdict}", ""]
    lines += ["## Policies — filter/funnel/count-basis (both bases)", "",
              "| policy | n | WR% | PF | expR | totR | pass@10/1200 | eligible/pass-COUNT @10/1200 | "
              "pass@15/1000 | eligible/pass-COUNT @15/1000 | denom artifact? | auditor? |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, r in policies.items():
        cb10, cb15 = r["count_basis_10_1200"], r["count_basis_15_1000"]
        lines.append(
            f"| {name} | {r['n']} | {r['wr']} | {r['pf']} | {r['expr']} | {r['totr']:+.1f} | "
            f"{r['funnel_10_1200']['pass_pct']}% | {cb10['variant_total_n']}/{cb10['variant_pass_n']} "
            f"(base {cb10['baseline_total_n']}/{cb10['baseline_pass_n']}) | "
            f"{r['funnel_15_1000']['pass_pct']}% | {cb15['variant_total_n']}/{cb15['variant_pass_n']} "
            f"(base {cb15['baseline_total_n']}/{cb15['baseline_pass_n']}) | "
            f"{'ARTIFACT@10' if cb10['denominator_artifact'] else ''}"
            f"{' ARTIFACT@15' if cb15['denominator_artifact'] else ''}"
            f"{'none' if not (cb10['denominator_artifact'] or cb15['denominator_artifact']) else ''} | "
            f"{'YES' if r['auditor_review_required'] else 'no'} |")
    lines += ["", "## Per-year robustness flags (vs baseline)"]
    for name, flags in robustness.items():
        lines.append(f"- **{name}**: {'none' if not flags else '; '.join(flags)}")
    lines += ["", "## Pocket x D1c-band(atr-normalized) interaction (descriptive only — cells thin, "
              "NOT funnel-tested individually; combo policies P3a/P3b above ARE funnel-tested)", "",
              "| pocket | band | n | WR% | PF | expR | totR |", "|---|---|---|---|---|---|---|"]
    for label in pocket_labels:
        for b in band_labels:
            st = interaction[(label, b)]
            lines.append(f"| {label} | {b} | {st['n']} | {st['wr']} | {st['pf']} | {st['expr']} | "
                         f"{st['totr']:+.1f} |")
    lines += ["", "---", "All numbers RESEARCH ONLY / SIM CONDITIONAL. No commits."]
    with open(os.path.join(OUTDIR, "03_ny_adjacent_window.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


# ============================================================================ Idea 4: D1c bands
def do_idea4(kept, canary10, canary15, base_counts):
    os.makedirs(OUTDIR, exist_ok=True)
    baseline_funnels = dict(f10=canary10, f15=canary15)
    norm_labels = [("band_raw", "raw points"), ("band_atr", "drift/ATR14(1m)"),
                   ("band_pct", "percentile-by-minutes-since-open")]

    per_band = {}
    for key, label in norm_labels:
        for b in range(5):
            subset = [t for t in kept if t[key] == b]
            st = bucket_line_stats(subset)
            st["per_year"] = peryear_totr(subset) if subset else {}
            per_band[(label, b)] = st

    policies = {}
    baseline_peryear = peryear_totr(kept)
    for key, label in norm_labels:
        drop0 = [t for t in kept if t[key] != 0]
        policies[f"drop_band0[{label}]"] = run_row_full(drop0, kept, baseline_funnels, base_counts)
        allow23 = [t for t in kept if t[key] in (2, 3)]
        policies[f"allow_only_band2-3[{label}]"] = run_row_full(allow23, kept, baseline_funnels,
                                                                 base_counts)
        drop4 = [t for t in kept if t[key] != 4]
        policies[f"drop_band4[{label}]_exhaustion-check"] = run_row_full(drop4, kept, baseline_funnels,
                                                                          base_counts)

    robustness = {name: robustness_flags(baseline_peryear, r["per_year"]) for name, r in policies.items()}
    # one-year-driven check: flag if >70% of a policy's totR delta vs baseline comes from one year
    one_year_flags = {}
    for name, r in policies.items():
        py = r["per_year"]
        deltas = {y: py.get(y, 0.0) - baseline_peryear.get(y, 0.0) for y in set(py) | set(baseline_peryear)}
        pos_sum = sum(v for v in deltas.values() if v > 0)
        if pos_sum > 0:
            worst_share = max(v for v in deltas.values() if v > 0) / pos_sum
            one_year_flags[name] = (f"top single-year share of positive totR delta = "
                                    f"{100*worst_share:.0f}% -> "
                                    f"{'ONE-YEAR-DRIVEN, REJECT' if worst_share > 0.7 else 'spread, OK'}")
        else:
            one_year_flags[name] = "no positive totR delta vs baseline (n/a)"

    _write_idea4_outputs(per_band, policies, robustness, one_year_flags, norm_labels)
    return policies


def _write_idea4_outputs(per_band, policies, robustness, one_year_flags, norm_labels):
    csv_path = os.path.join(OUTDIR, "04_d1c_strength_bands.csv")
    rows = []
    for (label, b), st in per_band.items():
        rows.append(dict(section="per_band", normalization=label, band=b, n=st["n"], wr=st["wr"],
                          pf=st["pf"], expr=st["expr"], totr=st["totr"],
                          per_year=json.dumps(st["per_year"])))
    for name, r in policies.items():
        rows.append(dict(section="policy", normalization=name, band="",
                          n=r["n"], wr=r["wr"], pf=r["pf"], expr=r["expr"], totr=r["totr"],
                          pass_10_1200=r["funnel_10_1200"]["pass_pct"],
                          pass_15_1000=r["funnel_15_1000"]["pass_pct"],
                          eligible_n_10_1200=r["count_basis_10_1200"]["variant_total_n"],
                          pass_n_10_1200=r["count_basis_10_1200"]["variant_pass_n"],
                          eligible_n_15_1000=r["count_basis_15_1000"]["variant_total_n"],
                          pass_n_15_1000=r["count_basis_15_1000"]["variant_pass_n"],
                          denom_artifact_10=r["count_basis_10_1200"]["denominator_artifact"],
                          denom_artifact_15=r["count_basis_15_1000"]["denominator_artifact"],
                          auditor_flag=r["auditor_review_required"],
                          one_year_flag=one_year_flags.get(name)))
    fieldnames = sorted({k for row in rows for k in row})
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    lines = ["# Idea 4 — D1c strength bands — RESEARCH ONLY / SIM CONDITIONAL", "",
             "Analysis only — the LIVE D1c gate stays zero-parameter (sign-agreement only). "
             "Every kept trade's drift already agrees in sign with its own direction (that IS the "
             "D1c gate); bands here measure HOW STRONGLY aligned, not whether. Quintile bands "
             "(0=weakest..4=strongest) computed on the certified 435-trade population, per "
             "normalization, via rank-based `qcut` — no tuned thresholds.", "",
             "## Per-band stats, all 3 normalizations", ""]
    for _, label in norm_labels:
        lines += [f"### {label}", "", "| band | n | WR% | PF | expR | totR | per-year totR |",
                  "|---|---|---|---|---|---|---|"]
        for b in range(5):
            st = per_band[(label, b)]
            lines.append(f"| {b} | {st['n']} | {st['wr']} | {st['pf']} | {st['expr']} | "
                         f"{st['totr']:+.1f} | {st['per_year']} |")
        lines.append("")
    lines += ["## Policies — filter/funnel/count-basis (both bases) + one-year-driven check", "",
              "| policy | n | WR% | PF | expR | totR | pass@10/1200 | eligible/pass-COUNT @10/1200 | "
              "pass@15/1000 | eligible/pass-COUNT @15/1000 | denom artifact? | one-year check | auditor? |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, r in policies.items():
        cb10, cb15 = r["count_basis_10_1200"], r["count_basis_15_1000"]
        lines.append(
            f"| {name} | {r['n']} | {r['wr']} | {r['pf']} | {r['expr']} | {r['totr']:+.1f} | "
            f"{r['funnel_10_1200']['pass_pct']}% | {cb10['variant_total_n']}/{cb10['variant_pass_n']} "
            f"(base {cb10['baseline_total_n']}/{cb10['baseline_pass_n']}) | "
            f"{r['funnel_15_1000']['pass_pct']}% | {cb15['variant_total_n']}/{cb15['variant_pass_n']} "
            f"(base {cb15['baseline_total_n']}/{cb15['baseline_pass_n']}) | "
            f"{'ARTIFACT' if (cb10['denominator_artifact'] or cb15['denominator_artifact']) else 'none'} | "
            f"{one_year_flags.get(name)} | {'YES' if r['auditor_review_required'] else 'no'} |")
    lines += ["", "## Per-year robustness flags (vs baseline)"]
    for name, flags in robustness.items():
        lines.append(f"- **{name}**: {'none' if not flags else '; '.join(flags)}")
    lines += ["", "---", "All numbers RESEARCH ONLY / SIM CONDITIONAL. No commits."]
    with open(os.path.join(OUTDIR, "04_d1c_strength_bands.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


# ============================================================================ Idea 5: stop-width
STOP_SPRINT_MD = os.path.join(HERE, "reports", "eval_passrate_sprint", "stop_bucket_caps.md")
FILL_SENS_MD = os.path.join(HERE, "reports", "eval_passrate_sprint", "fill_sensitivity.md")


def do_idea5(kept, canary10, canary15, base_counts):
    os.makedirs(OUTDIR, exist_ok=True)
    baseline_funnels = dict(f10=canary10, f15=canary15)

    # (a) sub-20pt SKIP: already tested as B3_<20-SKIP_rest-15 in the prior sprint's stop_bucket_caps
    # report (trade-level state-policy replay, SAME n=395 eligible starts both variants — a
    # trade-skip within a fixed set of starts, not a stream filter, so its "count basis" cannot
    # shrink by construction). CITED, not rerun.
    citation_a = dict(
        source="reports/eval_passrate_sprint/stop_bucket_caps.md (B3_<20-SKIP_rest-15)",
        note="full SKIP of stop<20pt trades, rest cap15 (vs B0_all-10 flat baseline)",
        rows=[
            dict(policy="B0_all-10 (baseline)", base="10,$1200", n=395, pass_pct=47.8, bust_pct=15.9,
                 exp_pct=36.2),
            dict(policy="B0_all-10 (baseline)", base="15,$1000", n=395, pass_pct=44.8, bust_pct=12.7,
                 exp_pct=42.5),
            dict(policy="B3_<20-SKIP_rest-15", base="10,$1200", n=395, pass_pct=51.9, bust_pct=18.2,
                 exp_pct=29.9),
            dict(policy="B3_<20-SKIP_rest-15", base="15,$1000", n=395, pass_pct=50.4, bust_pct=13.4,
                 exp_pct=36.2),
        ],
        same_base_verdict="1C same-base verdict (all bucket-cap policies incl. B3): best real-policy "
                          "delta over its own same-base flat/null anchor is -0.2pt @10/1200 -- AGREES "
                          "with 'account-state sizing policies all dead'. B3 ALONE (skip<20) shows "
                          "+4.1pt vs B0 @10/1200, but its per-year table (stop_bucket_caps.md lines "
                          "175-182) shows 2024 +12.2pt / 2025 flat / 2021 +2.2pt spread across years, "
                          "not single-year-concentrated -- a real but modest effect, not a denominator "
                          "artifact (n=395 fixed both variants, no start-shrinkage mechanism here).",
    )

    # (b) sub-20pt requires D1c band(atr) >= 2 (combo with Idea 4) — NEW cell, stream-filter, needs
    # full funnel + count-basis machinery (this IS a stream filter -> denominator CAN shrink).
    combo_b = [t for t in kept if not (t["stop_pts"] < 20 and t["band_atr"] < 2)]
    row_b = run_row_full(combo_b, kept, baseline_funnels, base_counts)

    # (c) B5 wide-stop preference — TAG-ONLY report (bucket stats on the raw 435-trade certified
    # stream itself, trade-level, NOT the start-pooled replay stop_bucket_caps.md uses — a different,
    # simpler denominator, documented as such).
    def _bucket(sp):
        if sp < 20: return "b1_<20"
        if sp < 30: return "b2_20-30"
        if sp < 45: return "b3_30-45"
        if sp < 60: return "b4_45-60"
        if sp < 80: return "b5_60-80"
        return "b6_80+"
    tagonly = {}
    for b in ["b1_<20", "b2_20-30", "b3_30-45", "b4_45-60", "b5_60-80", "b6_80+"]:
        subset = [t for t in kept if _bucket(t["stop_pts"]) == b]
        tagonly[b] = bucket_line_stats(subset)

    _write_idea5_outputs(citation_a, row_b, tagonly)
    return dict(citation_a=citation_a, combo_b=row_b, tagonly_c=tagonly)


def _write_idea5_outputs(citation_a, row_b, tagonly):
    csv_path = os.path.join(OUTDIR, "05_stop_width_treatment.csv")
    rows = []
    for r in citation_a["rows"]:
        rows.append(dict(section="citation_a", **r))
    cb10, cb15 = row_b["count_basis_10_1200"], row_b["count_basis_15_1000"]
    rows.append(dict(section="new_cell_b", policy="sub20_requires_band_atr>=2_else_drop",
                      n=row_b["n"], wr=row_b["wr"], pf=row_b["pf"], expr=row_b["expr"],
                      totr=row_b["totr"], pass_10_1200=row_b["funnel_10_1200"]["pass_pct"],
                      pass_15_1000=row_b["funnel_15_1000"]["pass_pct"],
                      eligible_n_10_1200=cb10["variant_total_n"], pass_n_10_1200=cb10["variant_pass_n"],
                      eligible_n_15_1000=cb15["variant_total_n"], pass_n_15_1000=cb15["variant_pass_n"],
                      denom_artifact=cb10["denominator_artifact"] or cb15["denominator_artifact"],
                      auditor_flag=row_b["auditor_review_required"]))
    for b, st in tagonly.items():
        rows.append(dict(section="tagonly_c_B5_pref", policy=b, n=st["n"], wr=st["wr"], pf=st["pf"],
                          expr=st["expr"], totr=st["totr"]))
    fieldnames = sorted({k for row in rows for k in row})
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    lines = ["# Idea 5 — Stop-width treatment — RESEARCH ONLY / SIM CONDITIONAL", "",
             "Mostly PRIOR ART. Cites `reports/eval_passrate_sprint/stop_bucket_caps.md` (B0-B5 all "
             "failed to beat flat at the same base, same-base verdict -0.2pt) and "
             "`reports/eval_passrate_sprint/fill_sensitivity.md` (tight-stop uniform penalty changes "
             "cap ordering by E$/attempt — cited, not rerun).", "",
             "## (a) skip sub-20pt stops entirely — CITED (already tested as B3, prior sprint)", "",
             f"Source: `{citation_a['source']}` — {citation_a['note']}", "",
             "| policy | base | n | pass% | bust% | exp% |", "|---|---|---|---|---|---|"]
    for r in citation_a["rows"]:
        lines.append(f"| {r['policy']} | {r['base']} | {r['n']} | {r['pass_pct']} | {r['bust_pct']} "
                     f"| {r['exp_pct']} |")
    lines += ["", f"**Same-base verdict (cited):** {citation_a['same_base_verdict']}", "",
              "## (b) sub-20pt requires D1c band(atr) >= 2 — NEW cell (combo with Idea 4)", "",
              "Stream filter (drop a trade only if stop<20pt AND band_atr<2) — a genuine denominator-"
              "shrink mechanism, so full funnel + count-basis is required (unlike (a)'s fixed-n state "
              "policy).", "",
              "| n | WR% | PF | expR | totR | pass@10/1200 | eligible/pass-COUNT @10/1200 | "
              "pass@15/1000 | eligible/pass-COUNT @15/1000 | denom artifact? | auditor? |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    cb10b, cb15b = row_b["count_basis_10_1200"], row_b["count_basis_15_1000"]
    lines.append(f"| {row_b['n']} | {row_b['wr']} | {row_b['pf']} | {row_b['expr']} | "
                f"{row_b['totr']:+.1f} | {row_b['funnel_10_1200']['pass_pct']}% | "
                f"{cb10b['variant_total_n']}/{cb10b['variant_pass_n']} "
                f"(base {cb10b['baseline_total_n']}/{cb10b['baseline_pass_n']}) | "
                f"{row_b['funnel_15_1000']['pass_pct']}% | "
                f"{cb15b['variant_total_n']}/{cb15b['variant_pass_n']} "
                f"(base {cb15b['baseline_total_n']}/{cb15b['baseline_pass_n']}) | "
                f"{'ARTIFACT' if (cb10b['denominator_artifact'] or cb15b['denominator_artifact']) else 'none'} | "
                f"{'YES' if row_b['auditor_review_required'] else 'no'} |")
    lines += ["", "## (c) B5 wide-stop preference — TAG-ONLY (trade-level bucket stats on the "
              "certified 435, NOT the start-pooled replay stop_bucket_caps.md uses)", "",
              "| bucket | n | WR% | PF | expR | totR |", "|---|---|---|---|---|---|"]
    for b, st in tagonly.items():
        lines.append(f"| {b} | {st['n']} | {st['wr']} | {st['pf']} | {st['expr']} | {st['totr']:+.1f} |")
    lines += ["", "## Everything else: citation table", "",
              "| item | verdict | source |", "|---|---|---|",
              "| B0-B5 stop-bucket caps (all variants) | all failed to beat flat at same base "
              "(-0.2pt best real-policy delta) | `reports/eval_passrate_sprint/stop_bucket_caps.md` |",
              "| fill-sensitivity tight-stop penalty | cap ordering by E$/attempt CHANGES under "
              "uniform 0.05R tight-stop damage on stop<45pt trades | "
              "`reports/eval_passrate_sprint/fill_sensitivity.md` |",
              "", "---", "All numbers RESEARCH ONLY / SIM CONDITIONAL. No commits."]
    with open(os.path.join(OUTDIR, "05_stop_width_treatment.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


# ============================================================================ Idea 6: 2nd trade after 1st loss
def simulate_start_idea6(days_trades, unique_days, s0_idx, spec, cap, budget, decide_fn):
    """Day-scoped state (resets every day): day_trade_idx (1-based), first_trade_result (R of the
    day's 1st TAKEN trade, None if none taken yet), first_trade_direction, loss_occurred_yet (any
    taken trade this day so far resulted in R<=0). `decide_fn(day_trade_idx, first_result,
    first_direction, cur_direction, stop_pts, band_atr, loss_occurred_yet) -> (take: bool,
    budget_mult: float)`. Day-level bookkeeping ($550 stop / $1000 DLL / EOD ratchet / 30d expiry /
    bust-pass-expire) copied verbatim from `tools_sim_parity_check.simulate_start`."""
    sb, tr, tg = spec["start"], spec["trail"], spec["target"]
    stop, dll = spec["stop"], spec["dll"]
    thr, bal, peak, locked = sb - tr, sb, sb, False
    t0 = unique_days[s0_idx]
    day_double_loss_days, day_triple_loss_days, day_2plus_days = 0, 0, 0

    for di in range(s0_idx, len(unique_days)):
        d = unique_days[di]
        if (d - t0).days > EXPIRE_DAYS:
            return "EXPIRE", EXPIRE_DAYS, day_double_loss_days, day_triple_loss_days, day_2plus_days

        day_real, day_trough, day_stopped = 0.0, 0.0, False
        day_trade_idx, first_result, first_direction, loss_occurred_yet = 0, None, None, False
        taken_results = []
        for t in days_trades[d]:
            if day_stopped:
                break
            day_trade_idx += 1
            risk1 = t["risk_usd"]
            take, mult = decide_fn(day_trade_idx, first_result, first_direction, t["direction"],
                                    t["stop_pts"], t["band_atr"], loss_occurred_yet)
            if not take:
                continue
            q = min(cap, int((budget * mult) // risk1))
            if q < 1:
                continue
            R = t["R"]
            pnl = R * risk1 * q
            mae = min(0.0, t["mae_r"]) * risk1 * q
            day_trough = min(day_trough, day_real + mae)
            day_real += pnl
            taken_results.append(R)
            if day_trade_idx == 1 or first_result is None:
                first_result, first_direction = R, t["direction"]
            if R <= 0:
                loss_occurred_yet = True
            if day_real <= -stop:
                day_stopped = True

        if len(taken_results) >= 2:
            day_2plus_days += 1
            if taken_results[0] <= 0 and taken_results[1] <= 0:
                day_double_loss_days += 1
        if len(taken_results) >= 3 and taken_results[0] <= 0 and taken_results[1] <= 0 and taken_results[2] <= 0:
            day_triple_loss_days += 1

        if day_trough <= -dll:
            real, trough = -dll, -dll
        else:
            real, trough = day_real, day_trough
        if bal + min(0.0, trough) <= thr:
            return "BUST", (d - t0).days, day_double_loss_days, day_triple_loss_days, day_2plus_days
        bal += real
        peak = max(peak, bal)
        if not locked:
            thr = max(thr, peak - tr)
            if peak - tr >= sb + 100.0:
                thr = sb + 100.0; locked = True
        if bal <= thr:
            return "BUST", (d - t0).days, day_double_loss_days, day_triple_loss_days, day_2plus_days
        if bal >= sb + tg:
            return "PASS", (d - t0).days, day_double_loss_days, day_triple_loss_days, day_2plus_days
    return "INCOMPLETE", None, day_double_loss_days, day_triple_loss_days, day_2plus_days


def _policy_A(idx, first_r, first_d, cur_d, stop_pts, band, loss_yet):
    return True, 1.0


def _policy_B(idx, first_r, first_d, cur_d, stop_pts, band, loss_yet):
    if idx == 2 and first_r is not None and first_r <= 0:
        return False, 1.0
    return True, 1.0


def _policy_C(idx, first_r, first_d, cur_d, stop_pts, band, loss_yet):
    if idx == 2 and first_r is not None and first_r <= 0:
        return (band >= 2), 1.0
    return True, 1.0


def _policy_D(idx, first_r, first_d, cur_d, stop_pts, band, loss_yet):
    if idx == 2 and first_r is not None and first_r <= 0:
        return (cur_d != first_d), 1.0
    return True, 1.0


def _policy_E(idx, first_r, first_d, cur_d, stop_pts, band, loss_yet):
    if idx == 2 and first_r is not None and first_r <= 0:
        return (cur_d == first_d), 1.0
    return True, 1.0


def _policy_F(idx, first_r, first_d, cur_d, stop_pts, band, loss_yet):
    if idx == 2 and first_r is not None and first_r <= 0:
        return True, 0.5
    return True, 1.0


def _policy_G(idx, first_r, first_d, cur_d, stop_pts, band, loss_yet):
    if idx == 2 and first_r is not None and first_r <= 0 and stop_pts < 20:
        return False, 1.0
    return True, 1.0


def _policy_H(idx, first_r, first_d, cur_d, stop_pts, band, loss_yet):
    if loss_yet:
        return False, 1.0
    return True, 1.0


IDEA6_POLICIES = {
    "A_baseline": _policy_A,
    "B_skip_2nd_after_1st_loss": _policy_B,
    "C_2nd_after_loss_only_if_band>=2": _policy_C,
    "D_2nd_after_loss_only_if_opposite_dir": _policy_D,
    "E_2nd_after_loss_only_if_same_dir": _policy_E,
    "F_half_risk_2nd_after_loss": _policy_F,
    "G_skip_2nd_after_loss_if_sub20pt_stop": _policy_G,
    "H_stop_trading_after_any_loss_same_day": _policy_H,
}


def group_by_day_annotated(kept):
    """Same grouping convention as tools_sim_parity_check.group_by_day, but on the richer kept-trade
    dicts (direction/stop_pts/band_atr preserved for Idea 6's decide_fn)."""
    days_trades = {}
    for t in kept:
        d = pd.Timestamp(t["ts"]).normalize()
        days_trades.setdefault(d, []).append(t)
    unique_days = sorted(days_trades)
    return days_trades, unique_days


def do_idea6(kept, canary10, canary15):
    os.makedirs(OUTDIR, exist_ok=True)
    for t in kept:
        t["stop_pts"] = t["risk_usd"] / DPP
    days_trades, unique_days = group_by_day_annotated(kept)
    last_day = unique_days[-1]
    starts = [i for i, d in enumerate(unique_days) if (last_day - d).days > EXPIRE_DAYS]

    def run_at_base(cap, budget):
        out = {}
        for name, fn in IDEA6_POLICIES.items():
            results = [simulate_start_idea6(days_trades, unique_days, s, SPEC50K, cap, budget, fn)
                       for s in starts]
            n = len(results)
            p = 100 * sum(1 for r in results if r[0] == "PASS") / n
            b = 100 * sum(1 for r in results if r[0] == "BUST") / n
            x = 100 * sum(1 for r in results if r[0] == "EXPIRE") / n
            md = int(np.median([r[1] for r in results if r[0] == "PASS"]) or 0) if p else 0
            pass_n = sum(1 for r in results if r[0] == "PASS")
            dbl = sum(r[2] for r in results); trp = sum(r[3] for r in results)
            two_plus = sum(r[4] for r in results)
            out[name] = dict(n=n, pass_pct=round(p, 1), bust_pct=round(b, 1), exp_pct=round(x, 1),
                              med_days=md, pass_n=pass_n, eligible_n=n,
                              double_loss_days_total=dbl, triple_loss_days_total=trp,
                              two_plus_trade_days_total=two_plus)
        return out

    r10 = run_at_base(10, 1200.0)
    r15 = run_at_base(15, 1000.0)

    canary_ok = (r10["A_baseline"]["pass_pct"] == CANARY_EXPECT["pass_pct"] and
                 r10["A_baseline"]["bust_pct"] == CANARY_EXPECT["bust_pct"] and
                 r10["A_baseline"]["exp_pct"] == CANARY_EXPECT["exp_pct"] and
                 r10["A_baseline"]["med_days"] == CANARY_EXPECT["med_days"] and
                 r10["A_baseline"]["n"] == CANARY_EXPECT["n"])

    # per-year pass% for A vs B (the headline comparison) at cap10/$1200
    def per_year_for(fn):
        by_year = {}
        for s in starts:
            outcome = simulate_start_idea6(days_trades, unique_days, s, SPEC50K, 10, 1200.0, fn)
            y = unique_days[s].year
            by_year.setdefault(y, []).append(outcome[0])
        return {y: (round(100 * sum(1 for o in v if o == "PASS") / len(v), 1), len(v))
                for y, v in sorted(by_year.items())}
    peryear_A = per_year_for(_policy_A)
    peryear_B = per_year_for(_policy_B)

    total_2plus = r10["A_baseline"]["two_plus_trade_days_total"]
    total_double = r10["A_baseline"]["double_loss_days_total"]
    total_triple = r10["A_baseline"]["triple_loss_days_total"]

    _write_idea6_outputs(r10, r15, canary_ok, peryear_A, peryear_B, total_2plus, total_double, total_triple)
    return dict(cap10=r10, cap15=r15, canary_ok=canary_ok)


def _write_idea6_outputs(r10, r15, canary_ok, peryear_A, peryear_B, total_2plus, total_double, total_triple):
    csv_path = os.path.join(OUTDIR, "06_second_trade_after_loss.csv")
    rows = []
    for base_label, r in (("10_1200", r10), ("15_1000", r15)):
        for name, st in r.items():
            rows.append(dict(base=base_label, policy=name, **st))
    fieldnames = sorted({k for row in rows for k in row})
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    lines = ["# Idea 6 — Second trade after first loss (SAME DAY) — RESEARCH ONLY / SIM CONDITIONAL",
             "",
             "Day-scoped state (resets every calendar trading day) — distinct from the prior "
             "sprint's C3 (`tools_sprint_state_policies.DoubleLossAwarePolicy`), which acts on "
             "CROSS-DAY consecutive losses within one eval run.", "",
             f"## Mandatory canary (A_baseline, cap10/$1200 must reproduce 47.8/15.9/36.2/med16/n395)",
             f"- got: pass={r10['A_baseline']['pass_pct']} bust={r10['A_baseline']['bust_pct']} "
             f"exp={r10['A_baseline']['exp_pct']} med={r10['A_baseline']['med_days']}d "
             f"n={r10['A_baseline']['n']} -> {'MATCH' if canary_ok else 'MISMATCH — STOP'}", "",
             "## Preregistered priors (printed before results)",
             "- consecutive-loss (cross-day) policies died in the prior sprint (C0-C4, "
             "`stop_bucket_caps.md`/`cushion_aware_sizing.md`) -- this is a DIFFERENT (same-day) "
             "mechanism, not assumed to inherit that verdict.",
             "- 'bust and expiry cost the same' -- E$/attempt (not computed here directly; pass%/"
             "bust%/exp% reported separately so this is not silently baked in).",
             "- prior 2-loss cliff figure: P(pass|max-consec-losses>=2, CROSS-DAY)=14.4% "
             "(`tools_sprint_state_policies.PRIOR_BASELINE_COHORT`) -- quoted for context ONLY; NOT "
             "the same statistic as this file's SAME-DAY double-loss-day frequency below (do not "
             "conflate).",
             "- question under test: does PREVENTING the 2nd same-day trade after a 1st-trade loss "
             "beat losing the trades that would have won (57%+ of 2nd trades win, per the brief)?",
             "",
             "## Double/triple-loss-day frequency (baseline A, cap10/$1200, n=395 eval-starts, "
             "summed across ALL overlapping starts -- a single calendar day can appear in multiple "
             "starts' windows)",
             f"- trading-days-with-2+-taken-trades (summed over starts): {total_2plus}",
             f"- of those, DOUBLE-loss days (1st AND 2nd taken trades both R<=0): {total_double} "
             f"({100*total_double/total_2plus:.1f}% of 2+-trade days)" if total_2plus else
             f"- trading-days-with-2+-taken-trades: 0 -- too thin to compute a double-loss rate",
             ]
    if total_2plus:
        lines.append(f"- of days with 3+ taken trades, TRIPLE-loss days: {total_triple}")
    lines += ["", "## Per-policy funnel + count basis (both bases)", "",
              "| policy | base | n(eligible) | pass% | pass-COUNT | bust% | exp% | med days | "
              "2+trade-days | double-loss-days | triple-loss-days |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for base_label, r in (("10,$1200", r10), ("15,$1000", r15)):
        for name, st in r.items():
            lines.append(f"| {name} | {base_label} | {st['eligible_n']} | {st['pass_pct']}% | "
                        f"{st['pass_n']} | {st['bust_pct']}% | {st['exp_pct']}% | {st['med_days']} | "
                        f"{st['two_plus_trade_days_total']} | {st['double_loss_days_total']} | "
                        f"{st['triple_loss_days_total']} |")
    lines += ["", "## Per-year pass% — A (baseline) vs B (skip 2nd-after-loss), cap10/$1200", "",
              "| year | A pass% (n) | B pass% (n) | delta |", "|---|---|---|---|"]
    for y in sorted(set(peryear_A) | set(peryear_B)):
        pa, na = peryear_A.get(y, (None, 0))
        pb, nb = peryear_B.get(y, (None, 0))
        d = f"{pb-pa:+.1f}pt" if (pa is not None and pb is not None) else "n/a"
        lines.append(f"| {y} | {pa}% ({na}) | {pb}% ({nb}) | {d} |")
    pos_year_deltas = []
    for y in sorted(set(peryear_A) & set(peryear_B)):
        pa, _ = peryear_A[y]; pb, _ = peryear_B[y]
        if pb - pa > 0:
            pos_year_deltas.append(pb - pa)
    n_years_with_gain = len(pos_year_deltas)
    if not pos_year_deltas:
        one_year_note = "**One-year-driven check:** B shows no positive per-year delta vs A."
    elif n_years_with_gain <= 1:
        one_year_note = (f"**One-year-driven check:** B's entire pass% gain over A comes from "
                         f"{n_years_with_gain} start-year out of {len(peryear_A)} (all other years "
                         f"show +0.0pt) -> ONE-YEAR-DRIVEN, treat as noise on a thin sample (159 "
                         f"2+trade-days system-wide, 26 double-loss days).")
    else:
        one_year_note = (f"**One-year-driven check:** B's pass% gain over A comes from "
                         f"{n_years_with_gain} start-years out of {len(peryear_A)} -> spread across "
                         f"years.")
    lines += ["", one_year_note]
    lines += ["", "## tr/wk lost to skip-based policies (B/G/H) vs baseline A",
              "See `n_trades`-equivalent via the CSV's per-policy funnel rows; because trade "
              "frequency here is ~1.7-1.8/wk system-wide, days with a 2nd trade at all are the "
              "binding constraint on how much any of these policies can move the needle -- see the "
              "2+trade-days count above before over-reading any pass% delta.",
              "", "---", "All numbers RESEARCH ONLY / SIM CONDITIONAL. No commits."]
    with open(os.path.join(OUTDIR, "06_second_trade_after_loss.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


# ============================================================================ main
def main():
    print("loading frames + reconstructing certified A stream (exit3+D1c, 1m truth)…", flush=True)
    d1_tz, df5, mp, feats = load_frames()
    raw, kept = build_raw_and_kept(feats, mp, d1_tz)
    ok, msg = assert_parity(kept)
    print(f"PARITY FIREWALL vs tools_sim_parity_check.load_rows(): {'OK' if ok else 'FAIL'} — {msg}",
          flush=True)
    if not ok:
        print("[STOP] base-stream reconstruction does not match the certified loader. "
              "Aborting — do not trust anything downstream.", flush=True)
        return

    canary10 = eval_funnel(as_rows(kept), 1200, 10, SPEC50K)
    canary15 = eval_funnel(as_rows(kept), 1000, 15, SPEC50K)
    print(f"CANARY @10/1200: pass={canary10['pass_pct']} bust={canary10['bust_pct']} "
          f"exp={canary10['exp_pct']} med={canary10['med_days']}d n={canary10['n']}", flush=True)
    match10, base_out = do_baseline(kept, raw, canary10, canary15)
    if not match10:
        print("[STOP] CANARY MISMATCH vs CANARY_EXPECT. Aborting — do not trust the rest of this "
              "sprint's reports.", flush=True)
        return
    print("[canary OK]\n", flush=True)

    base_counts = dict(c10=count_basis(as_rows(kept), 1200, 10), c15=count_basis(as_rows(kept), 1000, 15))
    print(f"baseline count-basis: @10/1200 eligible/pass={base_counts['c10']}  "
          f"@15/1000 eligible/pass={base_counts['c15']}", flush=True)

    print("\nannotating pocket + D1c-strength bands…", flush=True)
    atr14_1m = build_atr14_1m(d1_tz)
    annotate_pocket_and_drift(kept, d1_tz, atr14_1m)
    for t in kept:
        t["stop_pts"] = t["risk_usd"] / DPP

    print("\n=== IDEA 3: time-of-day pockets ===", flush=True)
    idea3 = do_idea3(kept, canary10, canary15, base_counts)
    for name, r in idea3.items():
        print(f"  {name}: n={r['n']} totR={r['totr']:+.1f} pass@10/1200={r['funnel_10_1200']['pass_pct']}% "
              f"pass@15/1000={r['funnel_15_1000']['pass_pct']}%", flush=True)

    print("\n=== IDEA 4: D1c strength bands ===", flush=True)
    idea4 = do_idea4(kept, canary10, canary15, base_counts)
    for name, r in idea4.items():
        print(f"  {name}: n={r['n']} totR={r['totr']:+.1f} pass@10/1200={r['funnel_10_1200']['pass_pct']}% "
              f"pass@15/1000={r['funnel_15_1000']['pass_pct']}%", flush=True)

    print("\n=== IDEA 5: stop-width treatment ===", flush=True)
    idea5 = do_idea5(kept, canary10, canary15, base_counts)
    print(f"  (b) combo n={idea5['combo_b']['n']} totR={idea5['combo_b']['totr']:+.1f} "
          f"pass@10/1200={idea5['combo_b']['funnel_10_1200']['pass_pct']}%", flush=True)

    print("\n=== IDEA 6: second trade after first loss (same day) ===", flush=True)
    idea6 = do_idea6(kept, canary10, canary15)
    if not idea6["canary_ok"]:
        print("[WARNING] Idea 6's own internal canary (state-replay path) did not match "
              "CANARY_EXPECT — treat idea 6 outputs with suspicion.", flush=True)
    for name, r in idea6["cap10"].items():
        print(f"  {name} @10/1200: pass={r['pass_pct']}% 2+trade-days={r['two_plus_trade_days_total']} "
              f"double-loss-days={r['double_loss_days_total']}", flush=True)

    print(f"\n[saved all reports to] {OUTDIR}", flush=True)


if __name__ == "__main__":
    main()
