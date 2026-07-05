"""EVAL-PASSRATE SPRINT — Wave 2: fill-damage sensitivity on the surviving sizing cells (2026-07-05).

RESEARCH ONLY. Does not touch any live/config/funded file; only writes under
reports/eval_passrate_sprint/. Modifies nothing existing — this is a new, standalone tool.

Reuses (by import, never copied) the base machinery from `tools_eval_sizing_sweep.py`:
  - SWEEP.run_cell(rows, cap, budget, mode, param)  -> the day_rows/eval_run funnel (pass/bust/
    expire/E$/...), with the uniform-slippage ("uniform"), size-scaled-k ("size"), and
    asymmetric-partial-fill ("frac") overlays ALREADY implemented exactly per this sprint's spec
    (both R and mae_r are damaged consistently for uniform/size; frac only haircuts winners' q).
  - SWEEP.CANARY_A / SWEEP.DPP (dollar-per-point, used to recover stop-distance in points from
    risk_usd, since risk_usd = stop_distance_pts * DPP for every certified-stream trade).
  - tools_sim_parity_check.load_rows() -> the certified exit3+D1c, 1m-truth A stream (identical
    loader already used and canary-verified by tools_sprint_cap_risk.py's 1A section).

NEW here (not in the base machinery): overlay (d) touch-without-fill (drop t% of trades, two
selection bounds — deterministic-uniform "neutral" and highest-R-first "adverse"), and the
tight-stop-penalty variant (uniform 0.05R applied ONLY to trades with stop < 45pt). Both are
built by pre-processing the trade list BEFORE handing it to SWEEP.build_events/run_cell (mode=
"none") — i.e. they extend the existing build_events pattern from the outside rather than
duplicating its internals.

CELLS UNDER TEST (fixed, per spec): (10,1200) reference · (15,1000) candidate · (20,1100) ·
(25,1100) · (30,1100) [cap x budget maxima by raw E$/attempt from cap_risk_matrix.csv].

Canary (mandatory, abort if it fails): (10,1200) with NO damage must give pass=47.8 / bust=15.9 /
exp=36.2 exactly (SWEEP.CANARY_A) before anything else runs.
"""
import os, sys, csv, time, warnings; warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tools_sim_parity_check as PARITY        # certified stream loader (canary-verified elsewhere)
import tools_eval_sizing_sweep as SWEEP        # build_events/run_cell + uniform/size/frac overlays

FRAME = "SIM CONDITIONAL — pending live fill evidence"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "eval_passrate_sprint")

CELLS = [(10, 1200), (15, 1000), (20, 1100), (25, 1100), (30, 1100)]
REF_CELL = (10, 1200)

UNIFORM_S = [0.0, 0.01, 0.02, 0.03, 0.05, 0.075, 0.10]
SIZE_K = [0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02]
PARTIAL_F = [1.0, 0.75, 0.5, 0.25]
TOUCH_T = [0, 10, 20, 30]                       # percent of trades dropped (unfilled entries)

TIGHT_STOP_S = 0.05
TIGHT_STOP_THRESHOLD_PTS = 45.0

REALISTIC = dict(uniform=0.05, size=0.02, frac=0.5, touch_adverse=10)   # "plausible damage" bar
E_ATTEMPT_FLOOR = 0.0                            # machine-viability line, not a cap-choice line


def cell_key(cap, budget):
    return f"cap{cap}_b{budget}"


# ---------------------------------------------------------------- overlay (d): touch-without-fill
def touch_without_fill_neutral(rows, t_pct):
    """NEUTRAL: deterministic uniform selection — drop every k-th trade by time order,
    k = round(100/t). No RNG. Returns (kept_rows, actual_drop_pct)."""
    rows_sorted = sorted(rows, key=lambda r: r["ts"])
    n = len(rows_sorted)
    if t_pct <= 0:
        return list(rows_sorted), 0.0
    k = max(1, round(100.0 / t_pct))
    kept = [r for i, r in enumerate(rows_sorted) if (i + 1) % k != 0]
    return kept, round(100.0 * (n - len(kept)) / n, 2)


def touch_without_fill_adverse(rows, t_pct):
    """ADVERSE: drop the t% of trades with the HIGHEST R (winners-first — unfilled retests skew
    toward would-be winners). Deterministic (sort, no RNG). Returns (kept_rows, actual_drop_pct)."""
    rows_sorted = sorted(rows, key=lambda r: r["ts"])
    n = len(rows_sorted)
    if t_pct <= 0:
        return list(rows_sorted), 0.0
    n_drop = round(t_pct / 100.0 * n)
    order = sorted(range(n), key=lambda i: -rows_sorted[i]["R"])
    drop_idx = set(order[:n_drop])
    kept = [r for i, r in enumerate(rows_sorted) if i not in drop_idx]
    return kept, round(100.0 * n_drop / n, 2)


# ---------------------------------------------------------------- tight-stop penalty variant
def apply_tight_stop_penalty(rows, s, threshold_pts):
    """Uniform slippage s (subtracted from R AND mae_r, consistent with the (a) overlay's own
    damage rule) applied ONLY to the fill-suspect cohort: trades whose stop distance in points
    (risk_usd / DPP) < threshold_pts. Every other trade is untouched."""
    out = []
    for t in rows:
        stop_pts = t["risk_usd"] / SWEEP.DPP
        if stop_pts < threshold_pts:
            r = dict(t)
            r["R"] = t["R"] - s
            r["mae_r"] = t["mae_r"] - s
            out.append(r)
        else:
            out.append(t)
    return out


# ---------------------------------------------------------------- cell runners
def cells_e(rows_or_matrix_fn):
    return {cell_key(cap, budget): rows_or_matrix_fn(cap, budget) for cap, budget in CELLS}


def run_base(rows):
    return cells_e(lambda cap, budget: SWEEP.run_cell(rows, cap, budget))


def run_uniform(rows):
    return {s: cells_e(lambda cap, budget, s=s: SWEEP.run_cell(rows, cap, budget, "uniform", s))
            for s in UNIFORM_S}


def run_size(rows):
    return {k: cells_e(lambda cap, budget, k=k: SWEEP.run_cell(rows, cap, budget, "size", k))
            for k in SIZE_K}


def run_frac(rows):
    return {f: cells_e(lambda cap, budget, f=f: SWEEP.run_cell(rows, cap, budget, "frac", f))
            for f in PARTIAL_F}


def run_touch(rows, variant):
    fn = touch_without_fill_neutral if variant == "neutral" else touch_without_fill_adverse
    out = {}
    for t in TOUCH_T:
        filtered, drop_actual = fn(rows, t)
        out[t] = dict(drop_pct_actual=drop_actual,
                       cells=cells_e(lambda cap, budget, filtered=filtered:
                                     SWEEP.run_cell(filtered, cap, budget)))
    return out


def run_tight_stop(rows):
    damaged = apply_tight_stop_penalty(rows, TIGHT_STOP_S, TIGHT_STOP_THRESHOLD_PTS)
    n_penalized = sum(1 for t in rows if t["risk_usd"] / SWEEP.DPP < TIGHT_STOP_THRESHOLD_PTS)
    return dict(n_penalized=n_penalized, n_total=len(rows),
                cells=cells_e(lambda cap, budget: SWEEP.run_cell(damaged, cap, budget)))


def check_cap10_size_invariance(base_matrix, size_overlay):
    key10 = cell_key(*REF_CELL)
    base_e = base_matrix[key10]["e_attempt"]
    vals = {size_overlay[k][key10]["e_attempt"] for k in SIZE_K}
    return len(vals) == 1 and abs(next(iter(vals)) - base_e) < 1e-9


# ---------------------------------------------------------------- headline table 1: break-even
def interpolate_breakeven(damage_values, diffs):
    """damage_values ascending (increasing damage); diffs = E[candidate]-E[(10,1200)] at each
    damage level. Returns (breakeven_value_or_None, label)."""
    if all(d > 0 for d in diffs):
        return None, f">{damage_values[-1]}"
    if diffs[0] <= 0:
        return damage_values[0], f"<={damage_values[0]} (never wins)"
    for (x0, d0), (x1, d1) in zip(zip(damage_values, diffs), zip(damage_values[1:], diffs[1:])):
        if d0 > 0 and d1 <= 0:
            x_star = x0 + (0 - d0) * (x1 - x0) / (d1 - d0)
            return round(x_star, 5), None
    return None, "no clean single crossing in grid"


def breakeven_for_cell(cap, budget, base_matrix, uniform_ov, size_ov, frac_ov, touch_n_ov, touch_a_ov):
    key, key10 = cell_key(cap, budget), cell_key(*REF_CELL)

    s_vals = UNIFORM_S
    s_diffs = [uniform_ov[s][key]["e_attempt"] - uniform_ov[s][key10]["e_attempt"] for s in s_vals]
    be_s, lbl_s = interpolate_breakeven(s_vals, s_diffs)

    k_vals = [0.0] + SIZE_K
    k_diffs = [base_matrix[key]["e_attempt"] - base_matrix[key10]["e_attempt"]]
    k_diffs += [size_ov[k][key]["e_attempt"] - size_ov[k][key10]["e_attempt"] for k in SIZE_K]
    be_k, lbl_k = interpolate_breakeven(k_vals, k_diffs)

    f_vals = PARTIAL_F                              # ascending damage: 1.0(none) -> 0.25(most)
    f_diffs = [frac_ov[f][key]["e_attempt"] - frac_ov[f][key10]["e_attempt"] for f in f_vals]
    be_f, lbl_f = interpolate_breakeven(f_vals, f_diffs)

    t_vals = TOUCH_T
    tn_diffs = [touch_n_ov[t]["cells"][key]["e_attempt"] - touch_n_ov[t]["cells"][key10]["e_attempt"]
                for t in t_vals]
    be_tn, lbl_tn = interpolate_breakeven(t_vals, tn_diffs)
    ta_diffs = [touch_a_ov[t]["cells"][key]["e_attempt"] - touch_a_ov[t]["cells"][key10]["e_attempt"]
                for t in t_vals]
    be_ta, lbl_ta = interpolate_breakeven(t_vals, ta_diffs)

    return dict(cap=cap, budget=budget,
                breakeven_uniform_s=(be_s if be_s is not None else lbl_s),
                breakeven_size_k=(be_k if be_k is not None else lbl_k),
                breakeven_frac_f=(be_f if be_f is not None else lbl_f),
                breakeven_touch_neutral_t=(be_tn if be_tn is not None else lbl_tn),
                breakeven_touch_adverse_t=(be_ta if be_ta is not None else lbl_ta))


def survives_realistic_damage(be_row):
    """SURVIVES if the cell's break-even point on every overlay is beyond the REALISTIC 'plausible
    damage' bar (or 'never crosses'); COLLAPSES if any break-even falls inside that bar."""
    checks = []
    v = be_row["breakeven_uniform_s"]
    checks.append(isinstance(v, str) or v > REALISTIC["uniform"])
    v = be_row["breakeven_size_k"]
    checks.append(isinstance(v, str) or v > REALISTIC["size"])
    v = be_row["breakeven_frac_f"]
    # frac breakeven is a damage LEVEL where f drops below the value -> survives if breakeven f
    # value (the f at which it flips) is BELOW the realistic floor 0.5 (i.e. still winning at f=0.5)
    checks.append(isinstance(v, str) or v < REALISTIC["frac"])
    v = be_row["breakeven_touch_adverse_t"]
    checks.append(isinstance(v, str) or v > REALISTIC["touch_adverse"])
    return all(checks)


# ---------------------------------------------------------------- headline table 2: cap-15 confirmations
def cap15_confirmations(rows, base_matrix, size_ov, frac_ov):
    key15, key10 = cell_key(15, 1000), cell_key(*REF_CELL)

    k_check_vals = [0.0] + SIZE_K
    k_ok = True
    k_rows = []
    for k in k_check_vals:
        e15 = base_matrix[key15]["e_attempt"] if k == 0.0 else size_ov[k][key15]["e_attempt"]
        e10 = base_matrix[key10]["e_attempt"] if k == 0.0 else size_ov[k][key10]["e_attempt"]
        beats = e15 > e10
        k_ok = k_ok and beats
        k_rows.append(dict(k=k, e15=e15, e10=e10, beats=beats))

    f_check_vals = [f for f in PARTIAL_F if f >= 0.5]         # 1.0, .75, .5
    f_ok = True
    f_rows = []
    for f in f_check_vals:
        e15 = frac_ov[f][key15]["e_attempt"]
        e10 = frac_ov[f][key10]["e_attempt"]
        beats = e15 > e10
        f_ok = f_ok and beats
        f_rows.append(dict(f=f, e15=e15, e10=e10, beats=beats))

    t_check_vals = [t for t in TOUCH_T if t <= 20]            # 0, 10, 20
    touch_a_ov = run_touch(rows, "adverse")
    t_ok = True
    t_rows = []
    for t in t_check_vals:
        e15 = touch_a_ov[t]["cells"][key15]["e_attempt"]
        e10 = touch_a_ov[t]["cells"][key10]["e_attempt"]
        beats = e15 > e10
        t_ok = t_ok and beats
        t_rows.append(dict(t=t, e15=e15, e10=e10, beats=beats, drop_pct_actual=touch_a_ov[t]["drop_pct_actual"]))

    return dict(k_ok=k_ok, k_rows=k_rows, f_ok=f_ok, f_rows=f_rows, t_ok=t_ok, t_rows=t_rows), touch_a_ov


# ---------------------------------------------------------------- headline table 3: tight-stop ordering
def cap_ordering_change(base_matrix, tight_matrix):
    base_order = sorted(CELLS, key=lambda c: -base_matrix[cell_key(*c)]["e_attempt"])
    tight_order = sorted(CELLS, key=lambda c: -tight_matrix[cell_key(*c)]["e_attempt"])
    return base_order, tight_order, base_order != tight_order


# ---------------------------------------------------------------- viability-floor flags
def viability_flags(base_matrix, uniform_ov, size_ov, frac_ov, touch_n_ov, touch_a_ov, tight_matrix):
    flags = []
    for cap, budget in CELLS:
        key = cell_key(cap, budget)
        hits = []
        for s in UNIFORM_S:
            e = uniform_ov[s][key]["e_attempt"]
            if e <= E_ATTEMPT_FLOOR:
                hits.append(f"uniform s={s} -> E$={e:,.0f}")
        for k in SIZE_K:
            e = size_ov[k][key]["e_attempt"]
            if e <= E_ATTEMPT_FLOOR:
                hits.append(f"size k={k} -> E$={e:,.0f}")
        for f in PARTIAL_F:
            e = frac_ov[f][key]["e_attempt"]
            if e <= E_ATTEMPT_FLOOR:
                hits.append(f"frac f={f} -> E$={e:,.0f}")
        for t in TOUCH_T:
            e = touch_n_ov[t]["cells"][key]["e_attempt"]
            if e <= E_ATTEMPT_FLOOR:
                hits.append(f"touch-neutral t={t}% -> E$={e:,.0f}")
            e = touch_a_ov[t]["cells"][key]["e_attempt"]
            if e <= E_ATTEMPT_FLOOR:
                hits.append(f"touch-adverse t={t}% -> E$={e:,.0f}")
        e = tight_matrix[key]["e_attempt"]
        if e <= E_ATTEMPT_FLOOR:
            hits.append(f"tight-stop-penalty -> E$={e:,.0f}")
        if hits:
            flags.append(dict(cap=cap, budget=budget, hits=hits))
    return flags


# ---------------------------------------------------------------- output
def write_csv(base_matrix, uniform_ov, size_ov, frac_ov, touch_n_ov, touch_a_ov, tight_matrix):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "fill_sensitivity.csv")
    fieldnames = ["overlay", "damage", "cap", "budget", "n", "pass_pct", "bust_pct", "exp_pct",
                  "e_attempt", "drop_pct_actual"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()

        def row(overlay, damage, cap, budget, m, drop=""):
            w.writerow(dict(overlay=overlay, damage=damage, cap=cap, budget=budget, n=m["n"],
                            pass_pct=m["pass_pct"], bust_pct=m["bust_pct"], exp_pct=m["exp_pct"],
                            e_attempt=m["e_attempt"], drop_pct_actual=drop))

        for cap, budget in CELLS:
            row("none", 0, cap, budget, base_matrix[cell_key(cap, budget)])
        for s in UNIFORM_S:
            for cap, budget in CELLS:
                row("uniform_s", s, cap, budget, uniform_ov[s][cell_key(cap, budget)])
        for k in SIZE_K:
            for cap, budget in CELLS:
                row("size_k", k, cap, budget, size_ov[k][cell_key(cap, budget)])
        for fr in PARTIAL_F:
            for cap, budget in CELLS:
                row("frac_f", fr, cap, budget, frac_ov[fr][cell_key(cap, budget)])
        for t in TOUCH_T:
            for cap, budget in CELLS:
                key = cell_key(cap, budget)
                row("touch_neutral_t_pct", t, cap, budget, touch_n_ov[t]["cells"][key],
                    touch_n_ov[t]["drop_pct_actual"])
        for t in TOUCH_T:
            for cap, budget in CELLS:
                key = cell_key(cap, budget)
                row("touch_adverse_t_pct", t, cap, budget, touch_a_ov[t]["cells"][key],
                    touch_a_ov[t]["drop_pct_actual"])
        for cap, budget in CELLS:
            row("tight_stop_penalty_s0.05_lt45pt", TIGHT_STOP_S, cap, budget,
                tight_matrix[cell_key(cap, budget)])
    print(f"[saved] reports/eval_passrate_sprint/fill_sensitivity.csv")


def write_md(canary_ok, canary_got, base_matrix, size_inv_ok, breakeven_rows, survival,
             confirmations, touch_a_ov, base_order, tight_order, order_changed, tight_result,
             viability, runtime_s):
    md = ["# Wave 2 — Fill-Damage Sensitivity on the Surviving Sizing Cells", "",
          f"**{FRAME}**", "", "Generated 2026-07-05. New tool: `tools_sprint_fill_sensitivity.py`. "
          "Modifies nothing existing.", "",
          "Cells under test: (10,1200) reference; (15,1000) candidate; (20,1100), (25,1100), "
          "(30,1100) — the raw-E$/attempt maxima per cap from `cap_risk_matrix.csv`. "
          "E$/attempt = pass% x 12,728 - 131.", ""]

    md.append("## Canary")
    md.append("")
    md.append(f"(10,1200) no-damage: got pass={canary_got['pass_pct']} bust={canary_got['bust_pct']} "
              f"exp={canary_got['exp_pct']} (n={canary_got['n']}) vs expected "
              f"pass={SWEEP.CANARY_A['pass_pct']} bust={SWEEP.CANARY_A['bust_pct']} "
              f"exp={SWEEP.CANARY_A['exp_pct']} (n={SWEEP.CANARY_A['n']}) "
              f"-> **{'PASS' if canary_ok else 'FAIL — ABORTED'}**")
    md.append("")
    md.append(f"Size-scaled-k cap-10 invariance check (E$[cap10,b1200] must be identical across "
              f"every k, since q<=10 always): **{'OK' if size_inv_ok else 'FAILED'}**")
    md.append("")

    md.append("## Headline table 1 — break-even damage level vs (10,1200), per overlay type "
               "(interpolated)")
    md.append("")
    md.append("Break-even = damage level at which the cell's E$/attempt advantage over (10,1200) "
              "under the SAME damage level vanishes. `frac_f` break-even is reported as the f "
              "value (descending from 1.0); the cell survives partial fills down to that f.")
    md.append("")
    md.append("| cap | budget | uniform s* | size k* | frac f* | touch-neutral t*% | "
              "touch-adverse t*% | survives realistic damage? |")
    md.append("|---|---|---|---|---|---|---|---|")
    for r in breakeven_rows:
        md.append(f"| {r['cap']} | {r['budget']} | {r['breakeven_uniform_s']} | "
                  f"{r['breakeven_size_k']} | {r['breakeven_frac_f']} | "
                  f"{r['breakeven_touch_neutral_t']} | {r['breakeven_touch_adverse_t']} | "
                  f"{'SURVIVES' if survival[(r['cap'], r['budget'])] else 'COLLAPSES'} |")
    md.append("")
    md.append(f"'Realistic damage' bar used for the survive/collapse call: uniform s<={REALISTIC['uniform']}, "
              f"size k<={REALISTIC['size']}, frac f>={REALISTIC['frac']}, touch-adverse t<={REALISTIC['touch_adverse']}%. "
              f"A cell must clear its E$ advantage over (10,1200) at EVERY one of these to be called SURVIVES.")
    md.append("")

    md.append("## Headline table 2 — cap-15 (15,1000) confirmations")
    md.append("")
    md.append(f"**(1) Does (15,1000) still beat (10,1200) under size-scaled k<=0.02?** "
              f"**{'YES' if confirmations['k_ok'] else 'NO'}**")
    md.append("")
    md.append("| k | E$[15,1000] | E$[10,1200] | 15 beats 10 |")
    md.append("|---|---|---|---|")
    for row in confirmations["k_rows"]:
        md.append(f"| {row['k']} | {row['e15']:,.0f} | {row['e10']:,.0f} | {row['beats']} |")
    md.append("")
    md.append(f"**(2) Does (15,1000) still beat (10,1200) under asymmetric-partial f>=0.5?** "
              f"**{'YES' if confirmations['f_ok'] else 'NO'}**")
    md.append("")
    md.append("| f | E$[15,1000] | E$[10,1200] | 15 beats 10 |")
    md.append("|---|---|---|---|")
    for row in confirmations["f_rows"]:
        md.append(f"| {row['f']} | {row['e15']:,.0f} | {row['e10']:,.0f} | {row['beats']} |")
    md.append("")
    md.append(f"**(3) NEW — does (15,1000) still beat (10,1200) under ADVERSE touch-without-fill "
              f"up to t=20%?** **{'YES' if confirmations['t_ok'] else 'NO'}**")
    md.append("")
    md.append("| t% (target) | t% (actual drop) | E$[15,1000] | E$[10,1200] | 15 beats 10 |")
    md.append("|---|---|---|---|---|")
    for row in confirmations["t_rows"]:
        md.append(f"| {row['t']} | {row['drop_pct_actual']} | {row['e15']:,.0f} | "
                  f"{row['e10']:,.0f} | {row['beats']} |")
    md.append("")

    md.append("## Headline table 3 — tight-stop penalty (uniform 0.05R on stop<45pt trades only)")
    md.append("")
    md.append(f"Penalized cohort: {tight_result['n_penalized']} / {tight_result['n_total']} trades "
              f"had stop distance < {TIGHT_STOP_THRESHOLD_PTS}pt.")
    md.append("")
    md.append("| rank | cap,budget (no damage) | E$ (no damage) | | cap,budget (tight-stop) | "
              "E$ (tight-stop) |")
    md.append("|---|---|---|---|---|---|")
    for i, (bo, to) in enumerate(zip(base_order, tight_order), 1):
        md.append(f"| {i} | {bo[0]},{bo[1]} | {base_matrix[cell_key(*bo)]['e_attempt']:,.0f} | | "
                  f"{to[0]},{to[1]} | {tight_result['cells'][cell_key(*to)]['e_attempt']:,.0f} |")
    md.append("")
    md.append(f"**Cap ordering by E$/attempt changes under the tight-stop penalty: "
              f"{'YES' if order_changed else 'NO'}**")
    md.append("")

    md.append("## Machine-viability flags (ABSOLUTE E$/attempt <= 0 at plausible damage)")
    md.append("")
    md.append("This is a machine-viability line, NOT a cap-choice line — it flags where the whole "
              "attempt goes value-negative regardless of which cap wins the comparison.")
    md.append("")
    if viability:
        for v in viability:
            md.append(f"- **({v['cap']},{v['budget']})**: " + "; ".join(v["hits"]))
    else:
        md.append("- None of the 5 cells hit E$/attempt <= 0 anywhere in the swept damage grids.")
    md.append("")

    md.append("## Which raw-E$-max cells survive realistic damage vs collapse")
    md.append("")
    for (cap, budget), ok in survival.items():
        md.append(f"- ({cap},{budget}): **{'SURVIVES' if ok else 'COLLAPSES'}** vs (10,1200) under "
                  f"the realistic-damage bar above.")
    md.append("")

    md.append(f"Runtime: {runtime_s:.1f}s.")
    md.append("")

    with open(os.path.join(OUT_DIR, "fill_sensitivity.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"[saved] reports/eval_passrate_sprint/fill_sensitivity.md")


def main():
    t0 = time.time()
    print(FRAME)
    print("loading certified stream via tools_sim_parity_check.load_rows()…", flush=True)
    rows = PARITY.load_rows()
    print(f"  loaded {len(rows)} trades  ({time.time()-t0:.1f}s)\n", flush=True)

    print(f"{FRAME}\nCANARY — (10,1200) no-damage must reproduce SWEEP.CANARY_A exactly")
    canary_got = SWEEP.run_cell(rows, *REF_CELL)
    c = SWEEP.CANARY_A
    canary_ok = (canary_got["n"] == c["n"] and canary_got["pass_pct"] == c["pass_pct"]
                 and canary_got["bust_pct"] == c["bust_pct"] and canary_got["exp_pct"] == c["exp_pct"])
    print(f"  got n={canary_got['n']} pass={canary_got['pass_pct']} bust={canary_got['bust_pct']} "
          f"exp={canary_got['exp_pct']}  expect n={c['n']} pass={c['pass_pct']} bust={c['bust_pct']} "
          f"exp={c['exp_pct']}  -> {'PASS' if canary_ok else 'FAIL'}")
    if not canary_ok:
        print("\n[STOP] CANARY FAILED — aborting. Nothing below is trustworthy.")
        sys.exit(1)
    print("  canary OK.\n", flush=True)

    print("computing base matrix (no damage) + overlays (a) uniform (b) size (c) frac "
          "(d) touch-without-fill + tight-stop penalty…", flush=True)
    base_matrix = run_base(rows)
    uniform_ov = run_uniform(rows)
    size_ov = run_size(rows)
    frac_ov = run_frac(rows)
    touch_n_ov = run_touch(rows, "neutral")
    touch_a_ov = run_touch(rows, "adverse")
    tight_result = run_tight_stop(rows)
    size_inv_ok = check_cap10_size_invariance(base_matrix, size_ov)
    print(f"  size-scaled cap-10 invariance: {'OK' if size_inv_ok else 'FAILED'}")

    breakeven_rows = [breakeven_for_cell(cap, budget, base_matrix, uniform_ov, size_ov, frac_ov,
                                          touch_n_ov, touch_a_ov)
                       for cap, budget in CELLS if (cap, budget) != REF_CELL]
    survival = {(r["cap"], r["budget"]): survives_realistic_damage(r) for r in breakeven_rows}

    confirmations, touch_a_ov_check = cap15_confirmations(rows, base_matrix, size_ov, frac_ov)

    base_order, tight_order, order_changed = cap_ordering_change(base_matrix, tight_result["cells"])

    viability = viability_flags(base_matrix, uniform_ov, size_ov, frac_ov, touch_n_ov, touch_a_ov,
                                tight_result["cells"])

    write_csv(base_matrix, uniform_ov, size_ov, frac_ov, touch_n_ov, touch_a_ov, tight_result["cells"])
    write_md(canary_ok, canary_got, base_matrix, size_inv_ok, breakeven_rows, survival,
             confirmations, touch_a_ov, base_order, tight_order, order_changed, tight_result,
             viability, time.time() - t0)

    print(f"\n[done] total runtime {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
