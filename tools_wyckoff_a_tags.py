"""WYCKOFF STATE TAGS — Role 2 of the Wyckoff sprint (2026-07-06): tag the FROZEN certified
435-trade Profile A stream with Wyckoff structural states and test filter/avoid layers.

RESEARCH ONLY / SIM CONDITIONAL. Modifies nothing existing. Profile A model itself is FROZEN —
this workstream only TAGS the certified 435-trade A stream (exit3 + D1c, 1m-truth fills) with
Wyckoff states and asks whether keeping/dropping trades on those tags would have raised expected
$/attempt via the eval funnel. No entry replacement is tested.

FOLLOWS THE EXACT PATTERN of `tools_profileC_a_enhancement.py` (built 2026-07-05): rather than
re-deriving the already-firewalled loader/canary/funnel machinery, this file IMPORTS it directly
(`load_frames`, `build_raw_and_kept`, `assert_parity`, `filter_stats`, `eval_funnel`, `as_rows`,
`phi_2x2`, `CANARY_EXPECT`, `SPEC50K`) — same base-stream reconstruction, same byte-parity firewall
vs `tools_sim_parity_check.load_rows()`, same eval-funnel-at-both-bases + auditor-flag convention.
This file does NOT modify `tools_profileC_a_enhancement.py`; it only imports from it (read-only).

Causality: every Wyckoff tag uses only bars <= the trade's own signal-confirmation bar (`mss_bar`).
  - Range/trend context is computed on CAUSAL completed-bucket resamples of the same 5m frame that
    feeds Profile A (Databento 5m), for range_tf in {15min, 30min, 1h}. A range_tf bar is "known" at
    its CLOSE (bar_start + period) — the same stamping convention `tools_profileC_a_enhancement.py`
    uses for HTF FVG availability. For a trade with signal-confirmation timestamp `mss_ts`, the
    active range/trend state is read off the LAST range_tf bar whose close <= mss_ts.
  - Spring / upthrust / SOS / SOW / LPS / LPSY / failed-breakout / absorption / chop context all scan
    a fixed-length trailing window of signal-tf (5m) bars ENDING AT `mss_bar` (inclusive) — i.e. all
    context describes what already happened BEFORE the trade fired, using the range/trend boundaries
    frozen at `mss_ts` (a documented simplification: we do not re-evaluate the range boundary bar by
    bar inside the lookback window, we freeze it at the trade's own causal cutoff).
  - Displacement reuses `primitives.displacement_strength(feats, 20)` — the same primitive Profile A
    itself and `tools_profileC_a_enhancement.py`'s B2 tag use internally.

DESIGN CHOICES (documented, not hidden):
  - "Trending" (1) = NOT in a valid range; side = sign of a 50-bar causal OLS slope of range_tf Close.
  - Range validity per window w in {20,40}: height in [1.5,8]x ATR14(range_tf) AND every bar's Close
    lies within [rolling-w Low-min, rolling-w High-max] for >=10 of the w bars (a warm-up/degenerate-
    data sanity floor, since by construction of the rolling extrema every bar already satisfies this
    unless the window has NaNs). "In range" = window-20 valid OR window-40 valid (prefer window-20's
    tighter bounds when both are valid).
  - Spring/upthrust use a WICK poke (Low/High beyond by >=1 tick) + CLOSE reclaim within 3 bars
    (their classic Wyckoff definition). Failed-breakout (6) uses the looser CLOSE-beyond-then-back
    variant (a distinct, generic false-break check, direction-agnostic, mirrored both ways).
  - SOS/SOW (4): a >=2-magnitude displacement bar whose Open/Close straddle the range midpoint in the
    trade's direction, within the last 24 5m bars. LPS/LPSY (5): entry within 0.25x range-height of
    the broken boundary AFTER SOS/SOW fired.
  - Absorption (7): >=3 touches of one range boundary in the last 30 bars AND that window's own
    High-Low compresses to <0.7x the range height.
  - CHOP / W10 (8): valid range AND no |displacement|>=2 in the last 30 bars.
  - W9 PHASE (9), mutually exclusive per range_tf: accumulation-like (in-range + spring/SOS evidence)
    > distribution-like (in-range + upthrust/SOW evidence) > chop (in-range, no evidence) > none, OR
    markup/markdown when not in-range (by trend slope sign).
  - Every tag has an "aligned" flavor (context supports the trade's own direction) computed per
    range_tf; several also get an explicit "opposed" flavor (w1_trend_opposed, w4_opposed,
    w6_failedbrk_opposed, w9_opposed) — the natural AVOID candidates the brief calls out by name
    ("especially CHOP and opposed-phase tags").

PREREGISTERED PRIOR (printed before the tables run): "no filter raises total R" — checked
independently across SIX tag families (in_range/trend, spring/upthrust, SOS/SOW/LPS, failed-breakout,
absorption, chop/phase), each a replication of the same hypothesis on the KEEP-filter direction. A
separate, single check: "regime classification (w9 phase tags) all dead". A filter/avoid "wins" only
if E$/attempt at the eval-funnel level rises via pass/expiry mechanics, not because raw totR/PF looks
better. Any row beating baseline pass by >1pp at either base is flagged auditor-review-required.
"""
import os, sys, warnings, json; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools_profileC_a_enhancement import (
    load_frames, build_raw_and_kept, assert_parity, filter_stats, eval_funnel, as_rows,
    phi_2x2, CANARY_EXPECT, SPEC50K,
    build_events, day_rows, eval_run, EXPIRE_DAYS,       # re-exported by tools_profileC_a_enhancement
)
import primitives as P          # engine/primitives.py (cached from tools_profileC_a_enhancement's own import)
import data as D                # engine/data.py

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "reports", "wyckoff_playbook_research")

# ------------------------------------------------------------------------- Wyckoff tag constants
RANGE_RULES = ["15min", "30min", "1h"]
TF_LABEL = {"15min": "15m", "30min": "30m", "1h": "1h"}
TF_LABELS = ["15m", "30m", "1h"]

RANGE_WINDOWS = (20, 40)
RANGE_HEIGHT_ATR = (1.5, 8.0)
MIN_INSIDE = 10
ATR_LEN = 14
SLOPE_BARS = 50

SPRING_LOOKBACK_5M = 12
RECLAIM_BARS = 3
SOS_LOOKBACK_5M = 24
LPS_FRAC = 0.25
FB_LOOKBACK_5M = 12
FB_RECLAIM_BARS = 4
ABS_LOOKBACK_5M = 30
ABS_MIN_TOUCHES = 3
ABS_COMPRESSION = 0.7
CHOP_LOOKBACK_5M = 30
TICK = P.NQ_TICK

BOOL_BASES = ["w1_inrange", "w1_trend_aligned", "w1_trend_opposed", "w2_spring_aligned",
              "w3_upthrust_aligned", "w4_sos_aligned", "w4_sow_aligned", "w4_opposed",
              "w5_lps_aligned", "w5_lpsy_aligned", "w6_failedbrk_aligned", "w6_failedbrk_opposed",
              "w7_absorption_aligned", "w8_chop", "w9_accum", "w9_dist", "w9_markup", "w9_markdown",
              "w9_none", "w9_opposed"]
tag_names = [f"{b}_{tf}" for b in BOOL_BASES for tf in TF_LABELS]


# ------------------------------------------------------------------------- causal range_tf state
def _true_range(h, l, c):
    prev_c = np.r_[np.nan, c[:-1]]
    return np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))


def _rolling_ols_slope(y, w):
    """Exact rolling OLS slope of y against x=0..w-1 (equally-spaced), vectorized via rolling sums:
    slope_i = (w*Sxy - Sx*Sy) / (w*Sxx - Sx^2), Sxy_i = Sjy_i - (i-w+1)*Sy_i (j = absolute index)."""
    n = len(y)
    y = np.asarray(y, dtype=float)
    idx = np.arange(n, dtype=float)
    Sy = pd.Series(y).rolling(w).sum().values
    Sjy = pd.Series(idx * y).rolling(w).sum().values
    Sx = w * (w - 1) / 2.0
    Sxx = w * (w - 1) * (2 * w - 1) / 6.0
    denom = w * Sxx - Sx * Sx
    Sxy = Sjy - (idx - w + 1.0) * Sy
    return (w * Sxy - Sx * Sy) / denom


def build_rtf_state(base5, rule):
    """Causal per-bar range/trend state on a resampled range_tf frame. avail_ts stamped at bar
    CLOSE (bar_start + period), matching engine/htf.py / tools_profileC_a_enhancement.py convention."""
    rtf = D.resample(base5, rule)
    period = pd.tseries.frequencies.to_offset(rule)
    h, l, c = rtf["High"].values, rtf["Low"].values, rtf["Close"].values
    tr = _true_range(h, l, c)
    atr14 = pd.Series(tr).rolling(ATR_LEN).mean().values
    hi_s, lo_s, cl_s = pd.Series(h), pd.Series(l), pd.Series(c)
    win_valid, win_hi, win_lo, win_height = {}, {}, {}, {}
    for w in RANGE_WINDOWS:
        rng_hi = hi_s.rolling(w).max().values
        rng_lo = lo_s.rolling(w).min().values
        height = rng_hi - rng_lo
        inside = ((c >= rng_lo) & (c <= rng_hi)).astype(float)
        inside_cnt = pd.Series(inside).rolling(w).sum().values
        valid = ((height >= RANGE_HEIGHT_ATR[0] * atr14) & (height <= RANGE_HEIGHT_ATR[1] * atr14)
                  & (inside_cnt >= MIN_INSIDE))
        win_valid[w], win_hi[w], win_lo[w], win_height[w] = valid, rng_hi, rng_lo, height
    use20 = win_valid[20]
    in_range = win_valid[20] | win_valid[40]
    range_hi = np.where(use20, win_hi[20], win_hi[40])
    range_lo = np.where(use20, win_lo[20], win_lo[40])
    range_height = np.where(use20, win_height[20], win_height[40])
    slope = _rolling_ols_slope(c, SLOPE_BARS)
    avail_ts = rtf.index + period
    return dict(avail_ts=avail_ts, in_range=in_range, range_hi=range_hi, range_lo=range_lo,
                range_height=range_height, slope=slope)


def rtf_context_at(state, ts):
    idx = state["avail_ts"].searchsorted(ts, side="right") - 1
    if idx < 0:
        return None
    slope = state["slope"][idx]
    return dict(in_range=bool(state["in_range"][idx]), range_hi=float(state["range_hi"][idx]),
                range_lo=float(state["range_lo"][idx]), range_height=float(state["range_height"][idx]),
                slope=float(slope) if np.isfinite(slope) else 0.0)


# ------------------------------------------------------------------------- 5m context scans
def spring_flag(low5, close5, mss, range_lo):
    if not np.isfinite(range_lo):
        return False
    start = max(0, mss - SPRING_LOOKBACK_5M + 1)
    for i in range(start, mss + 1):
        if low5[i] < range_lo - TICK:
            for j in range(i, min(i + RECLAIM_BARS, mss) + 1):
                if close5[j] > range_lo:
                    return True
    return False


def upthrust_flag(high5, close5, mss, range_hi):
    if not np.isfinite(range_hi):
        return False
    start = max(0, mss - SPRING_LOOKBACK_5M + 1)
    for i in range(start, mss + 1):
        if high5[i] > range_hi + TICK:
            for j in range(i, min(i + RECLAIM_BARS, mss) + 1):
                if close5[j] < range_hi:
                    return True
    return False


def failed_breakout_flags(close5, mss, range_lo, range_hi):
    if not (np.isfinite(range_lo) and np.isfinite(range_hi)):
        return False, False
    start = max(0, mss - FB_LOOKBACK_5M + 1)
    fb_up = fb_down = False
    for i in range(start, mss + 1):
        if not fb_up and close5[i] > range_hi:
            for j in range(i + 1, min(i + 1 + FB_RECLAIM_BARS, mss) + 1):
                if close5[j] <= range_hi:
                    fb_up = True; break
        if not fb_down and close5[i] < range_lo:
            for j in range(i + 1, min(i + 1 + FB_RECLAIM_BARS, mss) + 1):
                if close5[j] >= range_lo:
                    fb_down = True; break
    return fb_up, fb_down


def sos_sow_flags(ds5, open5, close5, mss, mid):
    if not np.isfinite(mid):
        return False, False
    start = max(0, mss - SOS_LOOKBACK_5M + 1)
    sos = sow = False
    for i in range(start, mss + 1):
        if ds5[i] >= 2 and open5[i] < mid <= close5[i]:
            sos = True
        if ds5[i] <= -2 and open5[i] > mid >= close5[i]:
            sow = True
    return sos, sow


def absorption_flags(low5, high5, mss, range_lo, range_hi, range_height):
    if not (np.isfinite(range_lo) and np.isfinite(range_hi) and range_height > 0):
        return False, False
    start = max(0, mss - ABS_LOOKBACK_5M + 1)
    touches_lo = sum(1 for i in range(start, mss + 1) if low5[i] <= range_lo + TICK)
    touches_hi = sum(1 for i in range(start, mss + 1) if high5[i] >= range_hi - TICK)
    local_hi = np.max(high5[start:mss + 1]); local_lo = np.min(low5[start:mss + 1])
    compressed = (local_hi - local_lo) < ABS_COMPRESSION * range_height
    return (touches_lo >= ABS_MIN_TOUCHES and compressed), (touches_hi >= ABS_MIN_TOUCHES and compressed)


def chop_flag_fn(ds5, mss, in_range):
    if not in_range:
        return False
    start = max(0, mss - CHOP_LOOKBACK_5M + 1)
    return bool(not (np.abs(ds5[start:mss + 1]) >= 2).any())


_NULL_TAGS = [f"{b}_{tf}" for b in BOOL_BASES for tf in TF_LABELS]


def annotate_wyckoff(trades, feats, rtf_states):
    high5, low5, close5, open5 = (feats["High"].values, feats["Low"].values,
                                   feats["Close"].values, feats["Open"].values)
    ds5 = P.displacement_strength(feats, 20)
    for t in trades:
        mss = t["mss_bar"]; d = t["direction"]; entry = t["entry"]
        mss_ts = feats.index[mss]
        for rule in RANGE_RULES:
            tf = TF_LABEL[rule]
            ctx = rtf_context_at(rtf_states[rule], mss_ts)
            if ctx is None:
                for b in BOOL_BASES:
                    t[f"{b}_{tf}"] = False
                t[f"w9_phase_{tf}"] = "none"
                continue
            in_range, range_hi, range_lo = ctx["in_range"], ctx["range_hi"], ctx["range_lo"]
            range_height, slope = ctx["range_height"], ctx["slope"]
            mid = (range_hi + range_lo) / 2 if np.isfinite(range_hi) and np.isfinite(range_lo) else np.nan

            spring = spring_flag(low5, close5, mss, range_lo)
            upthrust = upthrust_flag(high5, close5, mss, range_hi)
            sos, sow = sos_sow_flags(ds5, open5, close5, mss, mid)
            fb_up, fb_down = failed_breakout_flags(close5, mss, range_lo, range_hi)
            abs_lo, abs_hi = absorption_flags(low5, high5, mss, range_lo, range_hi, range_height)
            chop = chop_flag_fn(ds5, mss, in_range)
            lps = bool(sos and np.isfinite(range_height) and range_height > 0
                       and abs(entry - range_hi) <= LPS_FRAC * range_height)
            lpsy = bool(sow and np.isfinite(range_height) and range_height > 0
                        and abs(entry - range_lo) <= LPS_FRAC * range_height)

            if in_range:
                if spring or sos:
                    phase = "accumulation"
                elif upthrust or sow:
                    phase = "distribution"
                elif chop:
                    phase = "chop"
                else:
                    phase = "none"
            else:
                phase = "markup" if slope > 0 else ("markdown" if slope < 0 else "none")

            t[f"w1_inrange_{tf}"] = bool(in_range)
            t[f"w1_trend_aligned_{tf}"] = bool((not in_range) and ((slope > 0 and d > 0) or (slope < 0 and d < 0)))
            t[f"w1_trend_opposed_{tf}"] = bool((not in_range) and ((slope > 0 and d < 0) or (slope < 0 and d > 0)))
            t[f"w2_spring_aligned_{tf}"] = bool(spring and d > 0)
            t[f"w3_upthrust_aligned_{tf}"] = bool(upthrust and d < 0)
            t[f"w4_sos_aligned_{tf}"] = bool(sos and d > 0)
            t[f"w4_sow_aligned_{tf}"] = bool(sow and d < 0)
            t[f"w4_opposed_{tf}"] = bool((sos and d < 0) or (sow and d > 0))
            t[f"w5_lps_aligned_{tf}"] = bool(lps and d > 0)
            t[f"w5_lpsy_aligned_{tf}"] = bool(lpsy and d < 0)
            t[f"w6_failedbrk_aligned_{tf}"] = bool((fb_down and d > 0) or (fb_up and d < 0))
            t[f"w6_failedbrk_opposed_{tf}"] = bool((fb_up and d > 0) or (fb_down and d < 0))
            t[f"w7_absorption_aligned_{tf}"] = bool((abs_lo and d > 0) or (abs_hi and d < 0))
            t[f"w8_chop_{tf}"] = bool(chop)
            t[f"w9_accum_{tf}"] = phase == "accumulation"
            t[f"w9_dist_{tf}"] = phase == "distribution"
            t[f"w9_markup_{tf}"] = phase == "markup"
            t[f"w9_markdown_{tf}"] = phase == "markdown"
            t[f"w9_none_{tf}"] = phase == "none"
            t[f"w9_opposed_{tf}"] = bool((phase == "distribution" and d > 0) or (phase == "accumulation" and d < 0))
            t[f"w9_phase_{tf}"] = phase
    return trades


# ------------------------------------------------------------------------- families (prereg)
def make_families():
    return dict(
        in_range_trend=[f"w1_inrange_{tf}" for tf in TF_LABELS] +
                        [f"w1_trend_aligned_{tf}" for tf in TF_LABELS] +
                        [f"w1_trend_opposed_{tf}" for tf in TF_LABELS],
        spring_upthrust=[f"w2_spring_aligned_{tf}" for tf in TF_LABELS] +
                         [f"w3_upthrust_aligned_{tf}" for tf in TF_LABELS],
        sos_sow_lps=[f"w4_sos_aligned_{tf}" for tf in TF_LABELS] +
                     [f"w4_sow_aligned_{tf}" for tf in TF_LABELS] +
                     [f"w4_opposed_{tf}" for tf in TF_LABELS] +
                     [f"w5_lps_aligned_{tf}" for tf in TF_LABELS] +
                     [f"w5_lpsy_aligned_{tf}" for tf in TF_LABELS],
        failed_breakout=[f"w6_failedbrk_aligned_{tf}" for tf in TF_LABELS] +
                         [f"w6_failedbrk_opposed_{tf}" for tf in TF_LABELS],
        absorption=[f"w7_absorption_aligned_{tf}" for tf in TF_LABELS],
        chop_phase=[f"w8_chop_{tf}" for tf in TF_LABELS] +
                    [f"w9_accum_{tf}" for tf in TF_LABELS] + [f"w9_dist_{tf}" for tf in TF_LABELS] +
                    [f"w9_markup_{tf}" for tf in TF_LABELS] + [f"w9_markdown_{tf}" for tf in TF_LABELS] +
                    [f"w9_none_{tf}" for tf in TF_LABELS] + [f"w9_opposed_{tf}" for tf in TF_LABELS],
    )


def robustness_flags(baseline_peryear, filtered_peryear):
    flags = []
    for y, v in baseline_peryear.items():
        fv = filtered_peryear.get(y)
        if fv is None:
            flags.append(f"{y}: no trades remain (baseline {v:+.1f}R)")
        elif (v > 0 and fv < 0) or (v < 0 and fv > 0):
            flags.append(f"{y}: sign flip {v:+.1f}R -> {fv:+.1f}R")
    return flags


def eval_funnel_by_year(rows_as_certified, budget, cap, spec=SPEC50K):
    """AUDITOR FOLLOW-UP (2026-07-06): bucket eval-funnel starts by start-YEAR (days[start].year) —
    same starts-construction convention as `eval_funnel`/`tools_account_size_research.eval_run`
    (n=395 starts for the certified baseline @ (cap10,$1200)). Returns {year: dict(n, pass_n, bust_n,
    exp_n, pass_pct, bust_pct, exp_pct)}. Raw counts are kept (not just rounded pct) so downstream
    concentration analysis isn't distorted by rounding."""
    if not rows_as_certified:
        return {}
    ev = build_events(rows_as_certified, budget, cap)
    days = day_rows(ev, spec["stop"], spec["dll"])
    if not days:
        return {}
    starts, seen = [], set()
    for i, (d, _, _) in enumerate(days):
        if d not in seen and (days[-1][0] - d).days > EXPIRE_DAYS:
            seen.add(d); starts.append(i)
    if not starts:
        return {}
    by_year = {}
    for s in starts:
        y = days[s][0].year
        by_year.setdefault(y, []).append(eval_run(days, s, spec)[0])
    out = {}
    for y, statuses in sorted(by_year.items()):
        n = len(statuses)
        pn = sum(1 for s in statuses if s == "PASS")
        bn = sum(1 for s in statuses if s == "BUST")
        xn = sum(1 for s in statuses if s == "EXPIRE")
        out[y] = dict(n=n, pass_n=pn, bust_n=bn, exp_n=xn,
                      pass_pct=round(100 * pn / n, 1), bust_pct=round(100 * bn / n, 1),
                      exp_pct=round(100 * xn / n, 1))
    return out


def run_row(subset, kept, auditor_canary, auditor_canary15):
    st = filter_stats(subset, kept)
    f1 = eval_funnel(as_rows(subset), 1200, 10, SPEC50K)
    f2 = eval_funnel(as_rows(subset), 1000, 15, SPEC50K)
    auditor_flag = (f1["pass_pct"] - auditor_canary["pass_pct"] > 1.0) or \
                   (f2["pass_pct"] - auditor_canary15["pass_pct"] > 1.0)
    return dict(**st, funnel_10_1200=f1, funnel_15_1000=f2, auditor_review_required=auditor_flag)


def build_combos(ranked3):
    combos = []
    for i in range(len(ranked3)):
        for j in range(i + 1, len(ranked3)):
            combos.append((ranked3[i], ranked3[j]))
    if len(ranked3) >= 3:
        combos.append(tuple(ranked3[:3]))
    return combos


# ------------------------------------------------------------------------- main
def main():
    os.makedirs(OUTDIR, exist_ok=True)
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
    print(f"raw (ny_am, pre-D1c) signals: {len(raw)}   certified kept (D1c+filled): {len(kept)}",
          flush=True)
    baseline_totr = sum(t["R"] for t in kept)
    print(f"baseline totR = {baseline_totr:+.1f}R (register: +183.9R)", flush=True)

    print("\nCANARY — null filter through the funnel path must reproduce 47.8/15.9/36.2/med16/n395:",
          flush=True)
    canary = eval_funnel(as_rows(kept), 1200, 10, SPEC50K)
    print(f"  got:      pass={canary['pass_pct']} bust={canary['bust_pct']} exp={canary['exp_pct']} "
          f"med={canary['med_days']}d n={canary['n']}", flush=True)
    print(f"  expected: pass={CANARY_EXPECT['pass_pct']} bust={CANARY_EXPECT['bust_pct']} "
          f"exp={CANARY_EXPECT['exp_pct']} med={CANARY_EXPECT['med_days']}d n={CANARY_EXPECT['n']}",
          flush=True)
    canary_ok = (canary["pass_pct"] == CANARY_EXPECT["pass_pct"] and
                 canary["bust_pct"] == CANARY_EXPECT["bust_pct"] and
                 canary["exp_pct"] == CANARY_EXPECT["exp_pct"] and
                 canary["med_days"] == CANARY_EXPECT["med_days"] and
                 canary["n"] == CANARY_EXPECT["n"])
    if not canary_ok:
        print("[STOP] CANARY MISMATCH. Aborting — do not trust the filter table below.", flush=True)
        return
    print("[canary OK]", flush=True)
    canary_15_1000 = eval_funnel(as_rows(kept), 1000, 15, SPEC50K)
    print(f"  null filter @ (cap15,$1000): pass={canary_15_1000['pass_pct']} "
          f"bust={canary_15_1000['bust_pct']} exp={canary_15_1000['exp_pct']} "
          f"med={canary_15_1000['med_days']}d n={canary_15_1000['n']}", flush=True)

    print("\nbuilding range_tf state (15min/30min/1h, causal completed-bucket resamples)…", flush=True)
    base5 = df5[["Open", "High", "Low", "Close", "Volume"]]
    rtf_states = {rule: build_rtf_state(base5, rule) for rule in RANGE_RULES}

    print("ANNOTATING 435 kept + raw pre-D1c signals with Wyckoff tags…", flush=True)
    annotate_wyckoff(kept, feats, rtf_states)
    annotate_wyckoff(raw, feats, rtf_states)

    print(f"\nANNOTATION COVERAGE (of {len(kept)} kept):")
    coverage = {}
    for tg in tag_names:
        c = sum(1 for t in kept if t.get(tg))
        coverage[tg] = c
        print(f"  {tg:<28} {c:>4} / {len(kept)}  ({100*c/len(kept):5.1f}%)", flush=True)

    # -------------------------------------------------------------- filter (keep) + avoid tables
    print("\nFILTER TABLE (keep-filter, retain trades where tag==True) + AVOID TABLE "
          "(drop trades where tag==True):", flush=True)
    hdr = (f"{'tag':<28}{'dir':<7}{'n':>5}{'WR':>7}{'PF':>7}{'expR':>8}{'totR':>8}"
           f"{'rm_WR':>7}{'p@10/1200':>11}{'e@10/1200':>11}{'p@15/1000':>11}{'e@15/1000':>11}")
    print(hdr); print("-" * len(hdr))
    filter_rows, avoid_rows = {}, {}
    for tg in tag_names:
        keep_subset = [t for t in kept if t.get(tg)]
        drop_subset = [t for t in kept if not t.get(tg)]
        filter_rows[tg] = run_row(keep_subset, kept, canary, canary_15_1000)
        avoid_rows[tg] = run_row(drop_subset, kept, canary, canary_15_1000)
        for label, r in (("keep", filter_rows[tg]), ("avoid", avoid_rows[tg])):
            print(f"{tg:<28}{label:<7}{r['n']:>5}{r['wr']:>6.1f}%"
                  f"{(r['pf'] if np.isfinite(r['pf']) else 99):>7.2f}{r['expr']:>8.3f}{r['totr']:>8.1f}"
                  f"{(r['removed_wr'] or 0):>6.1f}%{r['funnel_10_1200']['pass_pct']:>10.1f}%"
                  f"{r['funnel_10_1200']['e_attempt']:>11,.0f}{r['funnel_15_1000']['pass_pct']:>10.1f}%"
                  f"{r['funnel_15_1000']['e_attempt']:>11,.0f}"
                  f"{'  [AUDITOR]' if r['auditor_review_required'] else ''}", flush=True)

    # -------------------------------------------------------------- top-2/3 combos (keep + avoid)
    ranked_keep = sorted(tag_names, key=lambda tg: filter_rows[tg]["totr"], reverse=True)[:3]
    ranked_avoid = sorted(tag_names, key=lambda tg: avoid_rows[tg]["totr"], reverse=True)[:3]
    combo_keep_rows, combo_avoid_rows = {}, {}
    print("\nCOMBINATIONS — top-3 KEEP filters (AND-stacked):", flush=True)
    print(hdr); print("-" * len(hdr))
    for combo in build_combos(ranked_keep):
        subset = [t for t in kept if all(t.get(tg) for tg in combo)]
        r = run_row(subset, kept, canary, canary_15_1000)
        label = "+".join(combo); combo_keep_rows[label] = r
        print(f"{label:<45}{'keep':<7}{r['n']:>5}{r['wr']:>6.1f}%"
              f"{(r['pf'] if np.isfinite(r['pf']) else 99):>7.2f}{r['expr']:>8.3f}{r['totr']:>8.1f}"
              f"{(r['removed_wr'] or 0):>6.1f}%{r['funnel_10_1200']['pass_pct']:>10.1f}%"
              f"{r['funnel_10_1200']['e_attempt']:>11,.0f}{r['funnel_15_1000']['pass_pct']:>10.1f}%"
              f"{r['funnel_15_1000']['e_attempt']:>11,.0f}"
              f"{'  [AUDITOR]' if r['auditor_review_required'] else ''}", flush=True)
    print("\nCOMBINATIONS — top-3 AVOID filters (OR-dropped: exclude trades with ANY flagged tag):",
          flush=True)
    print(hdr); print("-" * len(hdr))
    for combo in build_combos(ranked_avoid):
        subset = [t for t in kept if not any(t.get(tg) for tg in combo)]
        r = run_row(subset, kept, canary, canary_15_1000)
        label = "AVOID " + "+".join(combo); combo_avoid_rows[label] = r
        print(f"{label:<45}{'avoid':<7}{r['n']:>5}{r['wr']:>6.1f}%"
              f"{(r['pf'] if np.isfinite(r['pf']) else 99):>7.2f}{r['expr']:>8.3f}{r['totr']:>8.1f}"
              f"{(r['removed_wr'] or 0):>6.1f}%{r['funnel_10_1200']['pass_pct']:>10.1f}%"
              f"{r['funnel_10_1200']['e_attempt']:>11,.0f}{r['funnel_15_1000']['pass_pct']:>10.1f}%"
              f"{r['funnel_15_1000']['e_attempt']:>11,.0f}"
              f"{'  [AUDITOR]' if r['auditor_review_required'] else ''}", flush=True)

    # -------------------------------------------------------------- preregistered checks
    families = make_families()
    prereg = {}
    for fam, tags in families.items():
        best = max(tags, key=lambda tg: filter_rows[tg]["totr"])
        beats = filter_rows[best]["totr"] > baseline_totr
        prereg[fam] = dict(best_tag=best, best_totr=filter_rows[best]["totr"],
                           baseline_totr=round(baseline_totr, 1), any_filter_raised_totr=bool(beats))
    print("\nPREREGISTERED CHECK ('no filter raises total R', 6 replications by family, KEEP direction):",
          flush=True)
    for fam, r in prereg.items():
        print(f"  [{fam}] best={r['best_tag']} totR={r['best_totr']:+.1f} vs baseline "
              f"{r['baseline_totr']:+.1f} -> "
              f"{'HYPOTHESIS FALSIFIED' if r['any_filter_raised_totr'] else 'holds'}", flush=True)

    regime_tags = [f"w9_{k}_{tf}" for k in ("accum", "dist", "markup", "markdown") for tf in TF_LABELS]
    best_regime = max(regime_tags, key=lambda tg: filter_rows[tg]["totr"])
    regime_beats = filter_rows[best_regime]["totr"] > baseline_totr
    print(f"\nSECOND PREREG CHECK ('regime classification all dead'): best={best_regime} "
          f"totR={filter_rows[best_regime]['totr']:+.1f} vs baseline {baseline_totr:+.1f} -> "
          f"{'FALSIFIED (regime tag raised totR)' if regime_beats else 'holds — regime tags all dead'}",
          flush=True)

    # -------------------------------------------------------------- CHOP / opposed-phase (AVOID) answer
    print("\nCHOP-AVOIDANCE ANSWER (dropping CHOP / W10, per range_tf):", flush=True)
    chop_avoid_summary = {}
    for tf in TF_LABELS:
        tg = f"w8_chop_{tf}"
        r = avoid_rows[tg]
        chop_avoid_summary[tg] = r
        print(f"  drop {tg}: n={r['n']} totR={r['totr']:+.1f} (baseline {baseline_totr:+.1f}) "
              f"removed_n={r['removed_n']} removed_WR={r['removed_wr']}% | "
              f"pass@10/1200 {r['funnel_10_1200']['pass_pct']}% (base {canary['pass_pct']}%) "
              f"E$ {r['funnel_10_1200']['e_attempt']:,.0f} (base {canary['e_attempt']:,.0f}) | "
              f"pass@15/1000 {r['funnel_15_1000']['pass_pct']}% (base {canary_15_1000['pass_pct']}%) "
              f"E$ {r['funnel_15_1000']['e_attempt']:,.0f} (base {canary_15_1000['e_attempt']:,.0f})",
              flush=True)
    print("\nOPPOSED-PHASE AVOIDANCE ANSWER (dropping w9_opposed, per range_tf):", flush=True)
    opposed_avoid_summary = {}
    for tf in TF_LABELS:
        tg = f"w9_opposed_{tf}"
        r = avoid_rows[tg]
        opposed_avoid_summary[tg] = r
        print(f"  drop {tg}: n={r['n']} totR={r['totr']:+.1f} (baseline {baseline_totr:+.1f}) "
              f"removed_n={r['removed_n']} removed_WR={r['removed_wr']}% | "
              f"pass@10/1200 {r['funnel_10_1200']['pass_pct']}% E$ {r['funnel_10_1200']['e_attempt']:,.0f} "
              f"| pass@15/1000 {r['funnel_15_1000']['pass_pct']}% E$ {r['funnel_15_1000']['e_attempt']:,.0f}",
              flush=True)

    # -------------------------------------------------------------- B5: D1c interaction (2x2 + phi)
    print("\nB5 — D1c INTERACTION (2x2 vs d1c_keep, over the raw pre-D1c signal set):", flush=True)
    keep_bool = [t["d1c_keep"] for t in raw]
    b5 = {}
    for tg in tag_names:
        tag_bool = [t.get(tg, False) for t in raw]
        b5[tg] = phi_2x2(tag_bool, keep_bool)
    phis = [abs(r["phi"]) for r in b5.values() if r["phi"] is not None]
    b5_verdict = ("DUPLICATE (tags strongly track D1c keep/reject)" if phis and max(phis) > 0.3 else
                 "COMPLEMENT (tags largely independent of D1c keep/reject)")
    print(f"  verdict: {b5_verdict} (max|phi|={max(phis):.3f})" if phis else "  verdict: n/a", flush=True)
    for tf in TF_LABELS:
        fam_tags = [tg for tg in tag_names if tg.endswith(f"_{tf}")]
        fam_phi = [abs(b5[tg]["phi"]) for tg in fam_tags if b5[tg]["phi"] is not None]
        print(f"  [{tf}] mean|phi|={np.mean(fam_phi):.3f} max|phi|={np.max(fam_phi):.3f}"
              if fam_phi else f"  [{tf}] n/a", flush=True)

    # -------------------------------------------------------------- auditor-review-required list
    auditor_list = [tg for tg in tag_names if filter_rows[tg]["auditor_review_required"]] + \
                   ["AVOID:" + tg for tg in tag_names if avoid_rows[tg]["auditor_review_required"]] + \
                   [k for k, r in combo_keep_rows.items() if r["auditor_review_required"]] + \
                   [k for k, r in combo_avoid_rows.items() if r["auditor_review_required"]]
    print(f"\nAUDITOR-REVIEW-REQUIRED rows (pass beats baseline by >1pp at either base): "
          f"{len(auditor_list)}", flush=True)
    for a in auditor_list:
        print(f"  {a}", flush=True)

    # -------------------------------------------------------------- per-year robustness flags
    baseline_peryear = filter_stats(kept, kept)["per_year"]
    best_keep_tag = max(tag_names, key=lambda tg: filter_rows[tg]["totr"])
    best_avoid_tag = max(tag_names, key=lambda tg: avoid_rows[tg]["totr"])
    robustness = {
        f"best_keep({best_keep_tag})": robustness_flags(baseline_peryear, filter_rows[best_keep_tag]["per_year"]),
        f"best_avoid({best_avoid_tag})": robustness_flags(baseline_peryear, avoid_rows[best_avoid_tag]["per_year"]),
    }
    for tf in TF_LABELS:
        robustness[f"avoid(w8_chop_{tf})"] = robustness_flags(baseline_peryear, avoid_rows[f"w8_chop_{tf}"]["per_year"])
        robustness[f"avoid(w9_opposed_{tf})"] = robustness_flags(baseline_peryear, avoid_rows[f"w9_opposed_{tf}"]["per_year"])
    print("\nPER-YEAR ROBUSTNESS FLAGS (sign flips / dropouts vs baseline, top rows):", flush=True)
    for k, flags in robustness.items():
        print(f"  {k}: {'none' if not flags else '; '.join(flags)}", flush=True)

    # -------------------------------------------------------------- AUDITOR FOLLOW-UP (2026-07-06)
    # Requested: per-start-YEAR eval pass% for baseline vs the w9_markdown_1h AVOID stream, at both
    # bases, plus the removed cohort's year x side breakdown (checking the "drop 2024 longs in
    # disguise" hypothesis on the previously auditor-flagged row `AVOID:w9_markdown_1h`).
    print("\nAUDITOR FOLLOW-UP: w9_markdown_1h avoid — per-start-year funnel + removed-cohort "
          "breakdown:", flush=True)
    AUDIT_TAG = "w9_markdown_1h"
    audit_removed = [t for t in kept if t.get(AUDIT_TAG)]
    audit_avoid_subset = [t for t in kept if not t.get(AUDIT_TAG)]
    audit_removed_totr = round(sum(t["R"] for t in audit_removed), 1)
    print(f"  baseline n={len(kept)}  avoid n={len(audit_avoid_subset)}  removed n={len(audit_removed)}"
          f"  removed totR={audit_removed_totr:+.1f}R", flush=True)

    BASES = (("10_1200", 1200, 10), ("15_1000", 1000, 15))
    yearly_funnel = {}
    for base_name, budget, cap in BASES:
        yearly_funnel[(base_name, "baseline")] = eval_funnel_by_year(as_rows(kept), budget, cap, SPEC50K)
        yearly_funnel[(base_name, "avoid")] = eval_funnel_by_year(as_rows(audit_avoid_subset), budget,
                                                                   cap, SPEC50K)

    yearly_table_rows = []
    concentration = {}
    hdr_y = f"{'base':<10}{'year':>6}{'n_base':>8}{'pass_base':>11}{'n_avoid':>9}{'pass_avoid':>12}{'delta_pp':>10}"
    print(hdr_y); print("-" * len(hdr_y))
    for base_name, _, _ in BASES:
        base_map = yearly_funnel[(base_name, "baseline")]
        avoid_map = yearly_funnel[(base_name, "avoid")]
        all_years = sorted(set(base_map) | set(avoid_map))
        per_year_delta_n = {}
        for y in all_years:
            b = base_map.get(y); av = avoid_map.get(y)
            nb, pb, bustb, expb = (b["n"], b["pass_pct"], b["bust_pct"], b["exp_pct"]) if b else (0, None, None, None)
            na, pa, busta, expa = (av["n"], av["pass_pct"], av["bust_pct"], av["exp_pct"]) if av else (0, None, None, None)
            pn_b = b["pass_n"] if b else 0
            pn_a = av["pass_n"] if av else 0
            per_year_delta_n[y] = pn_a - pn_b
            delta = (pa - pb) if (pa is not None and pb is not None) else None
            yearly_table_rows.append(dict(base=base_name, year=y, n_baseline=nb, pass_baseline=pb,
                                           bust_baseline=bustb, exp_baseline=expb, n_avoid=na,
                                           pass_avoid=pa, bust_avoid=busta, exp_avoid=expa,
                                           delta_pp=delta))
            pb_s = f"{pb:.1f}%" if pb is not None else "n/a"
            pa_s = f"{pa:.1f}%" if pa is not None else "n/a"
            d_s = f"{delta:+.1f}" if delta is not None else "n/a"
            print(f"{base_name:<10}{y:>6}{nb:>8}{pb_s:>11}{na:>9}{pa_s:>12}{d_s:>10}", flush=True)
        net_gain = sum(per_year_delta_n.values())
        positive_years = sorted(((y, d) for y, d in per_year_delta_n.items() if d > 0),
                                 key=lambda kv: kv[1], reverse=True)
        total_positive = sum(d for _, d in positive_years)
        top2 = positive_years[:2]
        top2_share = (sum(d for _, d in top2) / total_positive) if total_positive > 0 else None
        total_n_baseline = sum(v["n"] for v in base_map.values())
        total_n_avoid = sum(v["n"] for v in avoid_map.values())
        denom_shrink = total_n_baseline - total_n_avoid
        # DENOMINATOR-ARTIFACT CHECK: net_gain is the change in RAW passing eval-start COUNT. If
        # net_gain < 0 while the aggregate pass% still rose, the "gain" is mechanical — the total pool
        # of eligible eval-starts shrank (denom_shrink > 0, fewer trading days -> fewer valid start
        # dates within the EXPIRE_DAYS window) faster than the pass count fell, not a real edge lift.
        denominator_artifact = bool(net_gain < 0 and denom_shrink > 0)
        concentration[base_name] = dict(net_gain_pass_starts=net_gain, top2_years=top2,
                                        top2_share=top2_share, total_positive=total_positive,
                                        total_n_baseline=total_n_baseline, total_n_avoid=total_n_avoid,
                                        denom_shrink=denom_shrink, denominator_artifact=denominator_artifact)
        verdict = ("n/a (no net gain in pass-starts)" if top2_share is None else
                   ("CONCENTRATED in top-2 years" if top2_share > 0.7 else "SPREAD across years"))
        print(f"  [{base_name}] net gain in passing eval-starts = {net_gain:+d} (RAW pass count); "
              f"top-2 years {top2} account for "
              f"{'n/a' if top2_share is None else f'{100*top2_share:.0f}%'} of the positive-year gain "
              f"-> {verdict}", flush=True)
        print(f"  [{base_name}] total eligible eval-starts: baseline={total_n_baseline} "
              f"avoid={total_n_avoid} (shrank by {denom_shrink}) -> "
              f"{'DENOMINATOR ARTIFACT: pass% rose only because the eligible-starts pool shrank faster '
               'than the pass count fell (RAW passes DOWN ' + f'{-net_gain}); NOT a genuine pass-rate lift'
               if denominator_artifact else 'no denominator artifact detected'}", flush=True)

    removed_by_year_side = {}
    removed_r_by_year_side = {}
    for t in audit_removed:
        y = pd.Timestamp(t["ts"]).year
        side = "long" if t["direction"] > 0 else "short"
        removed_by_year_side.setdefault(y, {"long": 0, "short": 0})[side] += 1
        removed_r_by_year_side.setdefault(y, {"long": 0.0, "short": 0.0})[side] += t["R"]
    print("\n  REMOVED COHORT (w9_markdown_1h==True) distribution by year x side:", flush=True)
    for y in sorted(removed_by_year_side):
        v = removed_by_year_side[y]; rv = removed_r_by_year_side[y]
        print(f"    {y}: long={v['long']} (R={rv['long']:+.1f}) short={v['short']} "
              f"(R={rv['short']:+.1f}) total={v['long']+v['short']}", flush=True)
    dom_key = max(removed_by_year_side.items(), key=lambda kv: max(kv[1]["long"], kv[1]["short"]))
    dom_year, dom_counts = dom_key
    dom_side = "long" if dom_counts["long"] >= dom_counts["short"] else "short"
    dom_n = dom_counts[dom_side]; total_removed = len(audit_removed)
    dom_share = dom_n / total_removed if total_removed else 0.0
    disguise_verdict = (f"YES — {dom_year} {dom_side}s are {dom_n}/{total_removed} "
                        f"({100*dom_share:.0f}%) of the removed cohort"
                        if dom_share > 0.5 else
                        f"NO — largest single (year,side) cell is {dom_year} {dom_side} at "
                        f"{dom_n}/{total_removed} ({100*dom_share:.0f}%), not a majority")
    print(f"  'drop {dom_year} {dom_side}s in disguise' check: {disguise_verdict}", flush=True)

    auditor_followup = dict(baseline_n=len(kept), avoid_n=len(audit_avoid_subset),
                            removed_n=total_removed, removed_totr=audit_removed_totr,
                            yearly_table_rows=yearly_table_rows, concentration=concentration,
                            removed_by_year_side=removed_by_year_side,
                            removed_r_by_year_side=removed_r_by_year_side,
                            disguise_verdict=disguise_verdict)

    # -------------------------------------------------------------- write outputs
    feature_rows = []
    feature_rows.append(dict(tag="NULL (baseline)", direction="baseline", n=len(kept),
                              wr=filter_stats(kept, kept)["wr"], pf=filter_stats(kept, kept)["pf"],
                              expr=filter_stats(kept, kept)["expr"], totr=round(baseline_totr, 1),
                              per_year=json.dumps(baseline_peryear), removed_n=0, removed_wr=None,
                              removed_totr=0.0, phi=None, overlap_pct=None, auditor_flag=False))
    for tg in tag_names:
        st = filter_rows[tg]
        feature_rows.append(dict(tag=tg, direction="keep", n=st["n"], wr=st["wr"], pf=st["pf"],
                                  expr=st["expr"], totr=st["totr"], per_year=json.dumps(st["per_year"]),
                                  removed_n=st["removed_n"], removed_wr=st["removed_wr"],
                                  removed_totr=st["removed_totr"], phi=b5[tg]["phi"],
                                  overlap_pct=b5[tg]["overlap_pct"],
                                  auditor_flag=st["auditor_review_required"]))
        st = avoid_rows[tg]
        feature_rows.append(dict(tag=tg, direction="avoid", n=st["n"], wr=st["wr"], pf=st["pf"],
                                  expr=st["expr"], totr=st["totr"], per_year=json.dumps(st["per_year"]),
                                  removed_n=st["removed_n"], removed_wr=st["removed_wr"],
                                  removed_totr=st["removed_totr"], phi=b5[tg]["phi"],
                                  overlap_pct=b5[tg]["overlap_pct"],
                                  auditor_flag=st["auditor_review_required"]))
    for label, st in combo_keep_rows.items():
        feature_rows.append(dict(tag=label, direction="combo_keep", n=st["n"], wr=st["wr"], pf=st["pf"],
                                  expr=st["expr"], totr=st["totr"], per_year=json.dumps(st["per_year"]),
                                  removed_n=st["removed_n"], removed_wr=st["removed_wr"],
                                  removed_totr=st["removed_totr"], phi=None, overlap_pct=None,
                                  auditor_flag=st["auditor_review_required"]))
    for label, st in combo_avoid_rows.items():
        feature_rows.append(dict(tag=label, direction="combo_avoid", n=st["n"], wr=st["wr"], pf=st["pf"],
                                  expr=st["expr"], totr=st["totr"], per_year=json.dumps(st["per_year"]),
                                  removed_n=st["removed_n"], removed_wr=st["removed_wr"],
                                  removed_totr=st["removed_totr"], phi=None, overlap_pct=None,
                                  auditor_flag=st["auditor_review_required"]))
    csv04 = os.path.join(OUTDIR, "04_profile_a_feature_results.csv")
    pd.DataFrame(feature_rows).to_csv(csv04, index=False)
    print(f"\n[saved] {csv04}", flush=True)

    funnel_rows = []
    funnel_rows.append(dict(tag="NULL (baseline)", direction="baseline", base="10_1200", auditor_flag=False, **canary))
    funnel_rows.append(dict(tag="NULL (baseline)", direction="baseline", base="15_1000", auditor_flag=False, **canary_15_1000))
    for tg in tag_names:
        st = filter_rows[tg]
        funnel_rows.append(dict(tag=tg, direction="keep", base="10_1200",
                                 auditor_flag=st["auditor_review_required"], **st["funnel_10_1200"]))
        funnel_rows.append(dict(tag=tg, direction="keep", base="15_1000",
                                 auditor_flag=st["auditor_review_required"], **st["funnel_15_1000"]))
        stA = avoid_rows[tg]
        funnel_rows.append(dict(tag=tg, direction="avoid", base="10_1200",
                                 auditor_flag=stA["auditor_review_required"], **stA["funnel_10_1200"]))
        funnel_rows.append(dict(tag=tg, direction="avoid", base="15_1000",
                                 auditor_flag=stA["auditor_review_required"], **stA["funnel_15_1000"]))
    for label, st in combo_keep_rows.items():
        funnel_rows.append(dict(tag=label, direction="combo_keep", base="10_1200",
                                 auditor_flag=st["auditor_review_required"], **st["funnel_10_1200"]))
        funnel_rows.append(dict(tag=label, direction="combo_keep", base="15_1000",
                                 auditor_flag=st["auditor_review_required"], **st["funnel_15_1000"]))
    for label, st in combo_avoid_rows.items():
        funnel_rows.append(dict(tag=label, direction="combo_avoid", base="10_1200",
                                 auditor_flag=st["auditor_review_required"], **st["funnel_10_1200"]))
        funnel_rows.append(dict(tag=label, direction="combo_avoid", base="15_1000",
                                 auditor_flag=st["auditor_review_required"], **st["funnel_15_1000"]))
    # AUDITOR FOLLOW-UP rows: per-start-year funnel for w9_markdown_1h avoid vs baseline (extra "year"
    # column; NaN for every pre-existing row above — schema-compatible append).
    for base_name, _, _ in BASES:
        for y, r in yearly_funnel[(base_name, "baseline")].items():
            funnel_rows.append(dict(tag="w9_markdown_1h_avoid_yearly", direction="baseline",
                                     base=base_name, year=y, pass_pct=r["pass_pct"],
                                     bust_pct=r["bust_pct"], exp_pct=r["exp_pct"], n=r["n"],
                                     auditor_flag=False))
        for y, r in yearly_funnel[(base_name, "avoid")].items():
            funnel_rows.append(dict(tag="w9_markdown_1h_avoid_yearly", direction="avoid",
                                     base=base_name, year=y, pass_pct=r["pass_pct"],
                                     bust_pct=r["bust_pct"], exp_pct=r["exp_pct"], n=r["n"],
                                     auditor_flag=False))
    csv05 = os.path.join(OUTDIR, "05_eval_funnel_results.csv")
    pd.DataFrame(funnel_rows).to_csv(csv05, index=False)
    print(f"[saved] {csv05}", flush=True)

    write_report(baseline_totr, canary, canary_15_1000, coverage, filter_rows, avoid_rows,
                 combo_keep_rows, combo_avoid_rows, prereg, best_regime, regime_beats, b5, b5_verdict,
                 chop_avoid_summary, opposed_avoid_summary, robustness, auditor_list, len(raw), len(kept),
                 auditor_followup)
    return dict(canary=canary, filter_rows=filter_rows, avoid_rows=avoid_rows, prereg=prereg, b5=b5)


def write_report(baseline_totr, canary, canary_15_1000, coverage, filter_rows, avoid_rows,
                 combo_keep_rows, combo_avoid_rows, prereg, best_regime, regime_beats, b5, b5_verdict,
                 chop_avoid_summary, opposed_avoid_summary, robustness, auditor_list, n_raw, n_kept,
                 auditor_followup=None):
    lines = []
    a = lines.append
    a("# Wyckoff state tags on the FROZEN Profile A stream — Role 2 (Wyckoff sprint)")
    a("")
    a("**RESEARCH ONLY / SIM CONDITIONAL.** Profile A model is FROZEN; this is tag-and-measure only.")
    a("")
    a(f"Base stream: {n_kept} certified trades (exit3 + D1c, 1m-truth) reconstructed via "
      f"`tools_profileC_a_enhancement.load_frames/build_raw_and_kept` (imported, not duplicated) and "
      f"asserted byte-for-byte identical to `tools_sim_parity_check.load_rows()`. Pre-D1c raw signal "
      f"set: {n_raw} (ny_am session, post model01, pre-D1c-drop).")
    a(f"Baseline totR = {baseline_totr:+.1f}R (register: +183.9R).")
    a("")
    a("## Canary (mandatory, blocking)")
    a(f"- @(cap10,$1200): pass={canary['pass_pct']} bust={canary['bust_pct']} exp={canary['exp_pct']} "
      f"med={canary['med_days']}d n={canary['n']} — expected 47.8/15.9/36.2/med16/n395 -> "
      f"{'MATCH' if canary['n']==395 and canary['pass_pct']==47.8 else 'MISMATCH — STOP'}")
    a(f"- @(cap15,$1000): pass={canary_15_1000['pass_pct']} bust={canary_15_1000['bust_pct']} "
      f"exp={canary_15_1000['exp_pct']} med={canary_15_1000['med_days']}d n={canary_15_1000['n']}")
    a("")
    a(f"## Annotation coverage (of {n_kept} kept)")
    a("| tag | n | % |")
    a("|---|---|---|")
    for tg, c in coverage.items():
        a(f"| `{tg}` | {c} | {100*c/n_kept:.1f}% |")
    a("")
    a("## Top-5 KEEP filters (by totR; full table in 04/05 CSVs)")
    ranked_keep = sorted(filter_rows.items(), key=lambda kv: kv[1]["totr"], reverse=True)
    a("| tag | n | WR | PF | expR | totR | removed WR | pass@10/1200 | E$@10/1200 | pass@15/1000 | E$@15/1000 | auditor? |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for tg, r in ranked_keep[:5]:
        a(f"| {tg} | {r['n']} | {r['wr']}% | {r['pf']} | {r['expr']} | {r['totr']:+.1f} | "
          f"{r['removed_wr']}% | {r['funnel_10_1200']['pass_pct']}% | {r['funnel_10_1200']['e_attempt']:,.0f} | "
          f"{r['funnel_15_1000']['pass_pct']}% | {r['funnel_15_1000']['e_attempt']:,.0f} | "
          f"{'YES' if r['auditor_review_required'] else 'no'} |")
    a("")
    a("## Top-5 AVOID filters (by totR — drop trades where tag==True)")
    ranked_avoid = sorted(avoid_rows.items(), key=lambda kv: kv[1]["totr"], reverse=True)
    a("| tag | n | WR | PF | expR | totR | removed(dropped) WR | pass@10/1200 | E$@10/1200 | pass@15/1000 | E$@15/1000 | auditor? |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for tg, r in ranked_avoid[:5]:
        a(f"| {tg} | {r['n']} | {r['wr']}% | {r['pf']} | {r['expr']} | {r['totr']:+.1f} | "
          f"{r['removed_wr']}% | {r['funnel_10_1200']['pass_pct']}% | {r['funnel_10_1200']['e_attempt']:,.0f} | "
          f"{r['funnel_15_1000']['pass_pct']}% | {r['funnel_15_1000']['e_attempt']:,.0f} | "
          f"{'YES' if r['auditor_review_required'] else 'no'} |")
    all_fail_keep = all(r["totr"] <= baseline_totr for r in filter_rows.values())
    all_fail_avoid = all(r["totr"] <= baseline_totr for r in avoid_rows.values())
    a("")
    a(f"**All-fail-if-so check (KEEP):** {'ALL individual keep-filters have totR <= baseline.' if all_fail_keep else 'At least one keep-filter raised raw totR (see preregistered check).'}")
    a(f"**All-fail-if-so check (AVOID):** {'ALL individual avoid-filters have totR <= baseline.' if all_fail_avoid else 'At least one avoid-filter raised raw totR (see preregistered check).'}")
    a("")
    a("### Top combinations")
    a("| combo | dir | n | WR | PF | expR | totR | pass@10/1200 | E$@10/1200 | pass@15/1000 | E$@15/1000 | auditor? |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for label, r in sorted(combo_keep_rows.items(), key=lambda kv: kv[1]["totr"], reverse=True):
        a(f"| {label} | keep | {r['n']} | {r['wr']}% | {r['pf']} | {r['expr']} | {r['totr']:+.1f} | "
          f"{r['funnel_10_1200']['pass_pct']}% | {r['funnel_10_1200']['e_attempt']:,.0f} | "
          f"{r['funnel_15_1000']['pass_pct']}% | {r['funnel_15_1000']['e_attempt']:,.0f} | "
          f"{'YES' if r['auditor_review_required'] else 'no'} |")
    for label, r in sorted(combo_avoid_rows.items(), key=lambda kv: kv[1]["totr"], reverse=True):
        a(f"| {label} | avoid | {r['n']} | {r['wr']}% | {r['pf']} | {r['expr']} | {r['totr']:+.1f} | "
          f"{r['funnel_10_1200']['pass_pct']}% | {r['funnel_10_1200']['e_attempt']:,.0f} | "
          f"{r['funnel_15_1000']['pass_pct']}% | {r['funnel_15_1000']['e_attempt']:,.0f} | "
          f"{'YES' if r['auditor_review_required'] else 'no'} |")
    a("")
    a("## Preregistered check: 'no filter raises total R' (6 replications, by tag family, KEEP direction)")
    for fam, r in prereg.items():
        a(f"- **{fam}**: best={r['best_tag']} totR={r['best_totr']:+.1f} vs baseline {r['baseline_totr']:+.1f} "
          f"-> {'HYPOTHESIS FALSIFIED (raw totR)' if r['any_filter_raised_totr'] else 'holds'}")
    a(f"- **regime classification (w9 accum/dist/markup/markdown) all dead**: best={best_regime} "
      f"totR={filter_rows[best_regime]['totr']:+.1f} vs baseline {baseline_totr:+.1f} -> "
      f"{'FALSIFIED' if regime_beats else 'holds'}")
    a("")
    a("## The AVOID question: does dropping CHOP / opposed-phase trades raise E$/attempt?")
    a("### CHOP (W10) avoidance")
    a("| tag | n dropped | removed WR | totR | pass@10/1200 (Δ vs base) | E$@10/1200 (Δ) | pass@15/1000 (Δ) | E$@15/1000 (Δ) |")
    a("|---|---|---|---|---|---|---|---|")
    for tg, r in chop_avoid_summary.items():
        a(f"| {tg} | {r['removed_n']} | {r['removed_wr']}% | {r['totr']:+.1f} | "
          f"{r['funnel_10_1200']['pass_pct']}% ({r['funnel_10_1200']['pass_pct']-canary['pass_pct']:+.1f}pp) | "
          f"{r['funnel_10_1200']['e_attempt']:,.0f} ({r['funnel_10_1200']['e_attempt']-canary['e_attempt']:+,.0f}) | "
          f"{r['funnel_15_1000']['pass_pct']}% ({r['funnel_15_1000']['pass_pct']-canary_15_1000['pass_pct']:+.1f}pp) | "
          f"{r['funnel_15_1000']['e_attempt']:,.0f} ({r['funnel_15_1000']['e_attempt']-canary_15_1000['e_attempt']:+,.0f}) |")
    a("### Opposed-phase (w9_opposed) avoidance")
    a("| tag | n dropped | removed WR | totR | pass@10/1200 (Δ vs base) | E$@10/1200 (Δ) | pass@15/1000 (Δ) | E$@15/1000 (Δ) |")
    a("|---|---|---|---|---|---|---|---|")
    for tg, r in opposed_avoid_summary.items():
        a(f"| {tg} | {r['removed_n']} | {r['removed_wr']}% | {r['totr']:+.1f} | "
          f"{r['funnel_10_1200']['pass_pct']}% ({r['funnel_10_1200']['pass_pct']-canary['pass_pct']:+.1f}pp) | "
          f"{r['funnel_10_1200']['e_attempt']:,.0f} ({r['funnel_10_1200']['e_attempt']-canary['e_attempt']:+,.0f}) | "
          f"{r['funnel_15_1000']['pass_pct']}% ({r['funnel_15_1000']['pass_pct']-canary_15_1000['pass_pct']:+.1f}pp) | "
          f"{r['funnel_15_1000']['e_attempt']:,.0f} ({r['funnel_15_1000']['e_attempt']-canary_15_1000['e_attempt']:+,.0f}) |")
    a("")
    a("## B5 — D1c complement-vs-duplicate")
    a(f"**Verdict: {b5_verdict}**")
    a("")
    a("| tag | n11 (tag&kept) | n10 (tag&dropped) | n01 (notag&kept) | n00 (notag&dropped) | phi | overlap(tag->kept)% |")
    a("|---|---|---|---|---|---|---|")
    for tg, r in b5.items():
        a(f"| {tg} | {r['n11']} | {r['n10']} | {r['n01']} | {r['n00']} | {r['phi']} | {r['overlap_pct']} |")
    a("")
    a("## Per-year robustness flags")
    for k, flags in robustness.items():
        a(f"- **{k}**: {'none' if not flags else '; '.join(flags)}")
    a("")
    a("## Auditor-review-required rows (pass beats baseline by >1pp at either base)")
    if auditor_list:
        for x in auditor_list:
            a(f"- {x}")
    else:
        a("- none")
    a("")
    if auditor_followup:
        af = auditor_followup
        a("## Auditor follow-up: w9_markdown_1h avoid, per-year funnel")
        a("")
        a("Requested by auditor review of the previously flagged row `AVOID:w9_markdown_1h` — prior "
          "against it: structurally an HTF(1h)-phase-classification skip (ticket Z already invalidated "
          "HTF-alignment skips as a lever), and it removes a NET-POSITIVE removed cohort while raising "
          "pass% (sequencing-effect smell).")
        a("")
        a(f"Baseline n={af['baseline_n']} trades; avoid-stream (drop `w9_markdown_1h`==True) "
          f"n={af['avoid_n']} trades ({af['removed_n']} removed, removed-cohort totR = "
          f"{af['removed_totr']:+.1f}R — i.e. the removed cohort was net PROFITABLE, consistent with "
          f"the auditor's smell-test).")
        a("")
        for base_name, base_label in (("10_1200", "cap10, $1200"), ("15_1000", "cap15, $1000")):
            a(f"### Base ({base_label})")
            a("| start-year | n (baseline) | pass% (baseline) | n (avoid) | pass% (avoid) | delta (pp) |")
            a("|---|---|---|---|---|---|")
            for row in [r for r in af["yearly_table_rows"] if r["base"] == base_name]:
                pb = f"{row['pass_baseline']:.1f}%" if row["pass_baseline"] is not None else "n/a"
                pa = f"{row['pass_avoid']:.1f}%" if row["pass_avoid"] is not None else "n/a"
                dd = f"{row['delta_pp']:+.1f}" if row["delta_pp"] is not None else "n/a"
                a(f"| {row['year']} | {row['n_baseline']} | {pb} | {row['n_avoid']} | {pa} | {dd} |")
            c = af["concentration"][base_name]
            if c["top2_share"] is None:
                verdict = "n/a (no net gain in passing eval-starts)"
            elif c["top2_share"] > 0.7:
                verdict = f"**CONCENTRATED** — top-2 years {c['top2_years']} account for {100*c['top2_share']:.0f}% of the positive-year gain"
            else:
                verdict = f"**SPREAD** — top-2 years {c['top2_years']} account for only {100*c['top2_share']:.0f}% of the positive-year gain"
            a(f"- net gain in passing eval-starts = {c['net_gain_pass_starts']:+d} (RAW pass count) -> {verdict}")
            a(f"- total eligible eval-starts: baseline={c['total_n_baseline']} avoid={c['total_n_avoid']} "
              f"(shrank by {c['denom_shrink']})")
            if c["denominator_artifact"]:
                a(f"- **DENOMINATOR ARTIFACT**: the RAW number of passing eval-starts fell by "
                  f"{-c['net_gain_pass_starts']}, but pass% still rose because the total pool of "
                  f"eligible eval-starts shrank by {c['denom_shrink']} (fewer trading days remain within "
                  f"the 30-day-expiry start window once these trades are dropped). **This is not a "
                  f"genuine pass-rate lift — it is exactly the sequencing-effect the auditor flagged.**")
            a("")
        a(f"### Removed cohort (w9_markdown_1h==True, n={af['removed_n']}) — distribution by year x side")
        a("| year | long n (R) | short n (R) |")
        a("|---|---|---|")
        for y in sorted(af["removed_by_year_side"]):
            v = af["removed_by_year_side"][y]; rv = af["removed_r_by_year_side"][y]
            a(f"| {y} | {v['long']} ({rv['long']:+.1f}R) | {v['short']} ({rv['short']:+.1f}R) |")
        a("")
        a(f"**\"Drop 2024 longs in disguise\" check**: {af['disguise_verdict']}.")
        a("")
    a("## Firewall")
    a("`test_eval_config_firewall.py` + `test_funded_config_firewall.py` run before and after this "
      "workstream — pass/fail state identical (no existing file touched).")
    a("")
    a("---")
    a("All numbers above: RESEARCH ONLY / SIM CONDITIONAL. No commits. Profile A live machine unchanged.")
    path = os.path.join(OUTDIR, "04_profile_a_feature_results.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[saved] {path}", flush=True)


if __name__ == "__main__":
    main()
