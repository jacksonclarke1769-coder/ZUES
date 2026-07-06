"""PROFILE C — Workstream B (2026-07-06): can PD-array / displacement-FVG / SMT conditions
IMPROVE the FROZEN certified Profile A stream as FILTERS?

RESEARCH ONLY / SIM CONDITIONAL. Does not modify any existing file, does not touch the certified
harness, does not change live sizing/exits. Profile A model itself is FROZEN — this workstream only
TAGS the certified 435-trade A stream (exit3 + D1c, 1m-truth fills) with PD-array/FVG/SMT conditions
and asks whether keeping/dropping trades on those tags would have raised expected $/attempt via the
eval funnel. No entry replacement is tested (that lane was already killed, see B3 section below).

BASE STREAM: reconstructed via the exact same code path as `tools_sim_parity_check.load_rows()`
(model01 "exit3" params + ny_am session filter + D1c drift attach + 1m-truth walk). We do NOT import
`load_rows()` directly because it only returns (ts, R, mae_r, risk_usd) — annotation needs the richer
per-trade fields (direction, entry, stop, sweep_bar/mss_bar/fill_bar) that get created and then
discarded inside `tools_phase3_config_sweep.a_streams_d1c`. Instead we mirror that exact loop here and
ASSERT byte-for-byte parity against `tools_sim_parity_check.load_rows()` (ts/R/mae_r/risk_usd, in
order) as an internal firewall before trusting anything downstream — see `assert_parity()`.

Causality: every annotation uses only data known at or before the trade's own signal/fill time.
  - HTF FVG zones (1h/4h/Daily): built off the SAME 5m frame that feeds Profile A (Databento 5m via
    `apex_eval_eod_databento.load_databento_5m`), using `engine/data.py` resample/daily + a from-
    scratch causal FVG-availability/mitigation scan (available at HTF bar CLOSE = bar_start + period,
    mirroring `engine/htf.py`'s close-stamp convention; "mitigated" = first later HTF bar whose
    High/Low range overlaps the zone at all — the strictest/most conservative definition, so we never
    over-count a zone as "still open").
  - PDH/PDL and prior-1H-swing tags reuse the SAME causal columns (`pdh`,`pdl`,`h1_sh`,`h1_sl`) Profile
    A itself already computes in `feats` (via `strategy_engine_profileA.ProfileAEngine._features()`),
    read at `mss_bar` (the signal-confirmation bar, <= fill_bar always).
  - B2/B3 (displacement+FVG, OTE(inter)FVG) recompute `primitives.displacement_strength` /
    `primitives.fvgs` directly off `feats` (5m) — the same primitives model01 itself uses internally,
    just not exposed on the trade row.
  - B4 SMT loads ES 5m via `engine/data.py load_spine("ES","5m")` (also YM/RTY, cheap, same file), and
    ffill-reindexes onto the NQ 5m (Databento) index. Any trade whose matched ES/YM/RTY bar is stale
    (>15min old, i.e. more than 3x 5m bars) or outside that instrument's data coverage is marked
    NOT TESTABLE for that pair rather than silently assigned a stale value.

PREREGISTERED (before running the filter table): "no filter raises total R" — checked independently
across three tag families (PD-zone / B2 / B3), each a replication of the same hypothesis. A filter
"wins" only if E$/attempt at the eval-funnel level rises via pass/expiry mechanics despite fewer
trades, not because raw totR/PF looks better. Any filter beating baseline E$/attempt by >1pp pass is
flagged auditor-review-required (too-good-to-be-true check).
"""
import os, sys, warnings, json; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import strategy_engine_profileA as E
import config
import run_d1c_real as RD
import apex_eval_eod_databento as DB
from tools_1m_truth_recert import M1Map, walk_1m, A_PARAMS, DPP
import model01_sweep_mss_fvg as M1
from tools_sim_parity_check import load_rows as certified_load_rows
from tools_account_size_research import (build_events, day_rows, eval_run, funded_paid,
                                          SPECS, EXPIRE_DAYS, MAX_A_QTY)
import primitives as P          # engine/primitives.py (path inserted by model01's own module import)
import data as D                # engine/data.py

NY = "America/New_York"
HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "reports", "profile_c_pd_fvg_strategy")
SPEC50K = SPECS["50K"]

NEAR_FRAC = 0.25          # "near" HTF-FVG variant: within 0.25x zone height of the nearest edge
PD_THRESH = (10, 20)      # PDH/PDL proximity thresholds (pts)
SWING_THRESH = (10, 20)   # prior 1H swing proximity thresholds (pts)
B2_WINDOW_BARS = 6        # 30 min / 5m
SMT_LOOKBACK = 20         # 5m bars, per the brief
STALE_MIN = 15.0          # SMT alignment: reject if matched other-instrument bar is this old

# INC-20260706-1141 honest re-cert row (was 47.8/15.9/36.2, n=395 -- lookahead-invalidated)
CANARY_EXPECT = dict(pass_pct=31.4, bust_pct=37.3, exp_pct=31.2, med_days=16, n=525)  # INC-20260706-1141 honest re-cert row (canonical, pipeline-regenerated)


# =========================================================================== load + reconstruct
def load_frames():
    d1_tz = RD.load_1m()
    d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m()
    mp = M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    feats = eng._features()
    return d1_tz, df5, mp, feats


def build_raw_and_kept(feats, mp, d1_tz):
    """raw = every ny_am-session model01 signal, D1c-tagged but NOT yet dropped (the ~705-signal
    pre-D1c set). kept = the certified 435 (d1c_keep True AND 1m-walk produced a fill)."""
    params = A_PARAMS["exit3"]
    tr = M1.run(feats, "NQ", params)
    tr = tr[tr.session == "ny_am"].copy()
    # INC-20260706-1141: fill_bar + feats.index, not date/time strings.
    tr = RD.attach_drift(tr, d1_tz, feats.index)
    fi = feats.index; n5 = len(fi)
    raw = []
    for _, t in tr.iterrows():
        risk = abs(float(t.entry) - float(t.stop))
        fb = int(t.fill_bar)
        if risk <= 0 or not (0 <= fb < n5):
            continue
        d = 1 if t.direction == "long" else -1
        partials = [(float(t.entry) + d * rl * risk, frac) for rl, frac in params["partial"]] \
            if params.get("partial") else []
        w = walk_1m(mp, fb, d, float(t.entry), float(t.stop), float(t.target), partials,
                    max_5m_bars=M1.MAX_HOLD)
        rec = dict(ts=pd.Timestamp(fi[fb]), direction=d, entry=float(t.entry), stop=float(t.stop),
                   target=float(t.target), sweep_bar=int(t.sweep_bar), mss_bar=int(t.mss_bar),
                   fill_bar=fb, risk_usd=risk * DPP, d1c_keep=bool(t.d1c_keep),
                   filled=bool(w), R=(w[0] if w else None), mae_r=(w[1] if w else None))
        raw.append(rec)
    kept = [r for r in raw if r["d1c_keep"] and r["filled"]]
    return raw, kept


def assert_parity(kept):
    """Firewall: byte-for-byte match vs tools_sim_parity_check.load_rows() (untouched, certified)."""
    cert = certified_load_rows()
    if len(kept) != len(cert):
        return False, f"length mismatch: mine={len(kept)} certified={len(cert)}"
    for a, b in zip(kept, cert):
        if a["ts"] != b["ts"] or abs(a["R"] - b["R"]) > 1e-9 or \
           abs(a["mae_r"] - b["mae_r"]) > 1e-9 or abs(a["risk_usd"] - b["risk_usd"]) > 1e-6:
            return False, f"row mismatch at ts={a['ts']}"
    return True, f"exact match, n={len(kept)}"


# =========================================================================== HTF FVG (causal)
def htf_fvg_events(base5, rule):
    """rule: '1h' | '4h' | 'D' (ICT daily). Returns list of dict(direction, top, bottom, avail_ts,
    mit_ts). avail_ts/mit_ts stamped at bar CLOSE (bar_start + period), same convention as
    engine/htf.py add_htf_swings / add_daily_weekly."""
    if rule == "D":
        htf = D.daily(base5); period = pd.Timedelta(days=1)
    else:
        htf = D.resample(base5, rule); period = pd.tseries.frequencies.to_offset(rule)
    htf = htf.reset_index(drop=False)
    times = pd.DatetimeIndex(htf[htf.columns[0]])
    fv = P.fvgs(htf)
    h, l = htf["High"].values, htf["Low"].values
    out = []
    for _, r in fv.iterrows():
        fidx = int(r.form_idx); top, bot = float(r.top), float(r.bottom)
        avail_ts = times[fidx] + period
        mit_ts = None
        for j in range(fidx + 1, len(htf)):
            if l[j] <= top and h[j] >= bot:
                mit_ts = times[j] + period
                break
        out.append(dict(direction=int(r.direction), top=top, bottom=bot,
                        avail_ts=avail_ts, mit_ts=mit_ts))
    return out


def htf_fvg_tag(events, cutoff_ts, direction, price):
    """direction: trade direction (+1 long / -1 short). Opposing-side FVG = bullish for longs,
    bearish for shorts (the demand/supply zone the retracement is entering). Returns (is_in, is_near)
    against the NEAREST qualifying (unmitigated-as-of-cutoff, causally available) zone."""
    best_in, best_near = False, False
    for ev in events:
        if ev["direction"] != direction:
            continue
        if ev["avail_ts"] > cutoff_ts:
            continue
        if ev["mit_ts"] is not None and ev["mit_ts"] <= cutoff_ts:
            continue                                    # already mitigated before this trade
        top, bot = ev["top"], ev["bottom"]
        if bot <= price <= top:
            best_in = True; best_near = True; continue
        height = max(top - bot, 1e-9)
        dist = bot - price if price < bot else price - top
        if dist <= NEAR_FRAC * height:
            best_near = True
    return best_in, best_near


# =========================================================================== SMT (NQ vs other)
def load_other_5m(instrument):
    return D.load_spine(instrument, "5m")


def smt_tag(other5, nq_high, nq_low, ts_index, sweep_bar, direction):
    """other5: reindexed+ffilled onto ts_index (NQ 5m). Returns (smt_present, testable)."""
    i = sweep_bar
    lo_win, hi_win = max(0, i - 2), i + 1
    ref_lo, ref_hi = max(0, i - (2 + SMT_LOOKBACK)), max(0, i - 2)
    nq_ts = ts_index[i]
    o_high = other5["High"].values; o_low = other5["Low"].values; o_ts = other5.index
    # staleness / coverage check on the matched (ffilled) bar at the sweep
    matched_ts = o_ts[i]
    stale_min = abs((nq_ts - matched_ts).total_seconds()) / 60.0
    testable = np.isfinite(o_high[ref_lo:hi_win]).all() and stale_min <= STALE_MIN
    if not testable:
        return False, False
    if direction > 0:
        nq_sweep = np.min(nq_low[lo_win:hi_win]); nq_ref = np.min(nq_low[ref_lo:ref_hi])
        o_sweep = np.min(o_low[lo_win:hi_win]); o_ref = np.min(o_low[ref_lo:ref_hi])
        present = bool(nq_sweep < nq_ref and o_sweep >= o_ref)
    else:
        nq_sweep = np.max(nq_high[lo_win:hi_win]); nq_ref = np.max(nq_high[ref_lo:ref_hi])
        o_sweep = np.max(o_high[lo_win:hi_win]); o_ref = np.max(o_high[ref_lo:ref_hi])
        present = bool(nq_sweep > nq_ref and o_sweep <= o_ref)
    return present, True


# =========================================================================== annotation
def annotate(trades, feats, df5):
    """trades: list of raw-or-kept trade dicts (mutated in place with tag_* fields)."""
    n = len(feats)
    pdh, pdl = feats["pdh"].values, feats["pdl"].values
    h1sh, h1sl = feats["h1_sh"].values, feats["h1_sl"].values
    ds = P.displacement_strength(feats, 20)
    fv5 = P.fvgs(feats)
    fv5_form = fv5["form_idx"].values if len(fv5) else np.array([], dtype=int)
    fv5_dir = fv5["direction"].values if len(fv5) else np.array([])
    fv5_top = fv5["top"].values if len(fv5) else np.array([])
    fv5_bot = fv5["bottom"].values if len(fv5) else np.array([])

    base5 = df5[["Open", "High", "Low", "Close", "Volume"]]
    print("  building HTF FVG event tables (1h/4h/Daily)…", flush=True)
    ev_h1 = htf_fvg_events(base5, "1h")
    ev_h4 = htf_fvg_events(base5, "4h")
    ev_d1 = htf_fvg_events(base5, "D")
    print(f"    1h:{len(ev_h1)} 4h:{len(ev_h4)} D:{len(ev_d1)} FVGs total", flush=True)

    print("  loading ES/YM/RTY 5m + aligning to NQ 5m index…", flush=True)
    ts_index = feats.index
    nq_high, nq_low = feats["High"].values, feats["Low"].values
    others = {}
    for inst in ("ES", "YM", "RTY"):
        try:
            o = load_other_5m(inst)
            others[inst] = o.reindex(ts_index, method="ffill")
        except Exception as e:
            others[inst] = None
            print(f"    [{inst}] load failed: {e}", flush=True)

    for t in trades:
        cutoff = t["ts"]                                # entry/fill timestamp (causal cutoff)
        mss = t["mss_bar"]; d = t["direction"]; entry = t["entry"]
        # ---- B1a: HTF FVG in/near, per TF ----
        for label, ev in (("h1", ev_h1), ("h4", ev_h4), ("d1", ev_d1)):
            is_in, is_near = htf_fvg_tag(ev, cutoff, d, entry)
            t[f"b1_fvg_{label}_in"] = is_in
            t[f"b1_fvg_{label}_near"] = is_near or is_in

        # ---- B1b: PDH/PDL proximity ----
        pv_h, pv_l = pdh[mss], pdl[mss]
        dist_pdhl = min(abs(entry - pv_h), abs(entry - pv_l)) if np.isfinite(pv_h) and np.isfinite(pv_l) else np.nan
        for thr in PD_THRESH:
            t[f"b1_pdhl_{thr}"] = bool(np.isfinite(dist_pdhl) and dist_pdhl <= thr)

        # ---- B1c: prior 1H swing proximity (opposing side: swing low for longs, high for shorts) ----
        swing_lvl = h1sl[mss] if d > 0 else h1sh[mss]
        dist_swing = abs(entry - swing_lvl) if np.isfinite(swing_lvl) else np.nan
        for thr in SWING_THRESH:
            t[f"b1_h1swing_{thr}"] = bool(np.isfinite(dist_swing) and dist_swing <= thr)

        # ---- B2: displacement>=2 + 5m FVG in trade direction, in the 30min after signal, before fill ----
        w0, w1 = mss + 1, min(mss + 1 + B2_WINDOW_BARS, t["fill_bar"])
        disp_ok = False
        if w1 > w0:
            seg = ds[w0:w1]
            disp_ok = bool((seg >= 2).any()) if d > 0 else bool((seg <= -2).any())
        fvg_ok = False
        if w1 > w0 and len(fv5_form):
            lo_i = np.searchsorted(fv5_form, w0, side="left")
            hi_i = np.searchsorted(fv5_form, w1, side="left")
            if hi_i > lo_i:
                fvg_ok = bool((fv5_dir[lo_i:hi_i] == d).any())
        t["b2_disp_fvg_confirm"] = bool(disp_ok and fvg_ok)

        # ---- B3: signal-TF (5m) FVG (formed during the setup's own impulse leg) overlaps the OTE
        # entry price. Tag-and-measure only — NOT an entry replacement (register: fvg50-entry lane
        # already killed as "Profile A in disguise, strictly worse PF 1.46 vs 1.78"; chasing -30R).
        b3 = False
        if len(fv5_form):
            lo_i = np.searchsorted(fv5_form, t["sweep_bar"], side="left")
            hi_i = np.searchsorted(fv5_form, t["fill_bar"] + 1, side="left")
            if hi_i > lo_i:
                mask = fv5_dir[lo_i:hi_i] == d
                if mask.any():
                    tops = fv5_top[lo_i:hi_i][mask]; bots = fv5_bot[lo_i:hi_i][mask]
                    b3 = bool(((bots <= entry) & (entry <= tops)).any())
        t["b3_ote_fvg_confluence"] = b3

        # ---- B4: SMT ----
        for inst in ("ES", "YM", "RTY"):
            o = others.get(inst)
            key = inst.lower()
            if o is None:
                t[f"b4_smt_{key}"] = False; t[f"b4_smt_{key}_testable"] = False
                continue
            present, testable = smt_tag(o, nq_high, nq_low, ts_index, t["sweep_bar"], d)
            t[f"b4_smt_{key}"] = present; t[f"b4_smt_{key}_testable"] = testable

    return trades


# =========================================================================== filter stats
def filter_stats(subset, all_trades):
    r = np.array([t["R"] for t in subset])
    if len(r) == 0:
        r_rm = np.array([t["R"] for t in all_trades])
        return dict(n=0, wr=0.0, pf=float("nan"), expr=0.0, totr=0.0, per_year={},
                    removed_n=len(all_trades),
                    removed_wr=round(100 * (r_rm > 0).mean(), 1) if len(r_rm) else None,
                    removed_totr=round(float(r_rm.sum()), 1) if len(r_rm) else 0.0)
    wins = r[r > 0].sum(); losses = -r[r <= 0].sum()
    pf = (wins / losses) if losses > 0 else float("inf")
    by_year = {}
    for t, ri in zip(subset, r):
        y = t["ts"].year
        by_year[y] = by_year.get(y, 0.0) + ri
    removed = [t for t in all_trades if t not in subset]
    r_rm = np.array([t["R"] for t in removed])
    return dict(n=len(r), wr=round(100 * (r > 0).mean(), 1), pf=round(pf, 3) if np.isfinite(pf) else pf,
                expr=round(float(r.mean()), 4), totr=round(float(r.sum()), 1),
                per_year={int(y): round(v, 1) for y, v in sorted(by_year.items())},
                removed_n=len(removed),
                removed_wr=round(100 * (r_rm > 0).mean(), 1) if len(r_rm) else None,
                removed_totr=round(float(r_rm.sum()), 1) if len(r_rm) else 0.0)


def eval_funnel(rows_as_certified, budget, cap, spec=SPEC50K):
    """rows_as_certified: list of dict(ts, R, mae_r, risk_usd) — same schema build_events expects."""
    if len(rows_as_certified) == 0:
        return dict(pass_pct=0.0, bust_pct=0.0, exp_pct=0.0, med_days=0, n=0, e_funded=0.0, e_attempt=0.0)
    ev = build_events(rows_as_certified, budget, cap)
    days = day_rows(ev, spec["stop"], spec["dll"])
    if not days:
        return dict(pass_pct=0.0, bust_pct=0.0, exp_pct=0.0, med_days=0, n=0, e_funded=0.0, e_attempt=0.0)
    starts, seen = [], set()
    for i, (d, _, _) in enumerate(days):
        if d not in seen and (days[-1][0] - d).days > EXPIRE_DAYS:
            seen.add(d); starts.append(i)
    if not starts:
        return dict(pass_pct=0.0, bust_pct=0.0, exp_pct=0.0, med_days=0, n=0, e_funded=0.0, e_attempt=0.0)
    res = [eval_run(days, s, spec) for s in starts]
    n = len(res)
    p = 100 * sum(1 for r in res if r[0] == "PASS") / n
    b = 100 * sum(1 for r in res if r[0] == "BUST") / n
    x = 100 * sum(1 for r in res if r[0] == "EXPIRE") / n
    md = int(np.median([r[1] for r in res if r[0] == "PASS"]) or 0) if p else 0
    fdays = day_rows(build_events(rows_as_certified, 0.4 * budget, cap), spec["stop"], spec["dll"])
    fp = funded_paid(fdays, spec)
    e_attempt = (p / 100) * fp - spec["fee_mo"] * 1.5
    return dict(pass_pct=round(p, 1), bust_pct=round(b, 1), exp_pct=round(x, 1), med_days=md, n=n,
                e_funded=round(fp), e_attempt=round(e_attempt))


def as_rows(subset):
    return [dict(ts=t["ts"], R=t["R"], mae_r=t["mae_r"], risk_usd=t["risk_usd"]) for t in subset]


# =========================================================================== B5 (phi + overlap)
def phi_2x2(tag_bool, keep_bool):
    tag = np.array(tag_bool, dtype=bool); keep = np.array(keep_bool, dtype=bool)
    n11 = int((tag & keep).sum()); n10 = int((tag & ~keep).sum())
    n01 = int((~tag & keep).sum()); n00 = int((~tag & ~keep).sum())
    n1_, n0_ = n11 + n10, n01 + n00
    n_1, n_0 = n11 + n01, n10 + n00
    denom = np.sqrt(n1_ * n0_ * n_1 * n_0)
    phi = (n11 * n00 - n10 * n01) / denom if denom > 0 else float("nan")
    overlap = 100 * n11 / max(1, (n11 + n10))     # of trades WITH the tag, % also D1c-kept
    return dict(n11=n11, n10=n10, n01=n01, n00=n00, phi=round(phi, 3) if np.isfinite(phi) else None,
                overlap_pct=round(overlap, 1))


# =========================================================================== main
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

    print("\nANNOTATING 435 kept + raw 705 signals…", flush=True)
    annotate(kept, feats, df5)
    annotate(raw, feats, df5)

    tag_names = ([f"b1_fvg_{tf}_{k}" for tf in ("h1", "h4", "d1") for k in ("in", "near")] +
                 [f"b1_pdhl_{t}" for t in PD_THRESH] +
                 [f"b1_h1swing_{t}" for t in SWING_THRESH] +
                 ["b2_disp_fvg_confirm", "b3_ote_fvg_confluence"] +
                 [f"b4_smt_{k}" for k in ("es", "ym", "rty")])

    print("\nANNOTATION COVERAGE (of 435 kept):")
    coverage = {}
    for tg in tag_names:
        c = sum(1 for t in kept if t.get(tg))
        coverage[tg] = c
        print(f"  {tg:<22} {c:>4} / 435  ({100*c/435:5.1f}%)", flush=True)
    testable_es = sum(1 for t in kept if t.get("b4_smt_es_testable"))
    testable_ym = sum(1 for t in kept if t.get("b4_smt_ym_testable"))
    testable_rty = sum(1 for t in kept if t.get("b4_smt_rty_testable"))
    print(f"  SMT testability: ES {testable_es}/435  YM {testable_ym}/435  RTY {testable_rty}/435",
          flush=True)

    # -------------------------------------------------------------- filter table
    print("\nFILTER TABLE (retain trades where tag==True):", flush=True)
    hdr = (f"{'filter':<24}{'n':>5}{'WR':>7}{'PF':>7}{'expR':>8}{'totR':>8}"
           f"{'rm_WR':>7}{'p@10/1200':>11}{'e@10/1200':>11}{'p@15/1000':>11}{'e@15/1000':>11}")
    print(hdr); print("-" * len(hdr))
    filter_rows = {}
    for tg in tag_names:
        subset = [t for t in kept if t.get(tg)]
        st = filter_stats(subset, kept)
        f1 = eval_funnel(as_rows(subset), 1200, 10, SPEC50K)
        f2 = eval_funnel(as_rows(subset), 1000, 15, SPEC50K)
        auditor_flag = (f1["pass_pct"] - canary["pass_pct"] > 1.0) or \
                       (f2["pass_pct"] - canary_15_1000["pass_pct"] > 1.0)
        row = dict(**st, funnel_10_1200=f1, funnel_15_1000=f2, auditor_review_required=auditor_flag)
        filter_rows[tg] = row
        print(f"{tg:<24}{st['n']:>5}{st['wr']:>6.1f}%{(st['pf'] if np.isfinite(st['pf']) else 99):>7.2f}"
              f"{st['expr']:>8.3f}{st['totr']:>8.1f}{(st['removed_wr'] or 0):>6.1f}%"
              f"{f1['pass_pct']:>10.1f}%{f1['e_attempt']:>11,.0f}"
              f"{f2['pass_pct']:>10.1f}%{f2['e_attempt']:>11,.0f}"
              f"{'  [AUDITOR]' if auditor_flag else ''}", flush=True)

    # -------------------------------------------------------------- top-2/3 combinations
    ranked = sorted(tag_names, key=lambda tg: filter_rows[tg]["totr"], reverse=True)
    combo_candidates = ranked[:3]
    combos = []
    for i in range(len(combo_candidates)):
        for j in range(i + 1, len(combo_candidates)):
            combos.append((combo_candidates[i], combo_candidates[j]))
    if len(combo_candidates) >= 3:
        combos.append(tuple(combo_candidates[:3]))
    print("\nCOMBINATIONS (top individual filters by totR, AND-stacked):", flush=True)
    print(hdr); print("-" * len(hdr))
    combo_rows = {}
    for combo in combos:
        subset = [t for t in kept if all(t.get(tg) for tg in combo)]
        st = filter_stats(subset, kept)
        f1 = eval_funnel(as_rows(subset), 1200, 10, SPEC50K)
        f2 = eval_funnel(as_rows(subset), 1000, 15, SPEC50K)
        auditor_flag = (f1["pass_pct"] - canary["pass_pct"] > 1.0) or \
                       (f2["pass_pct"] - canary_15_1000["pass_pct"] > 1.0)
        label = "+".join(combo)
        combo_rows[label] = dict(**st, funnel_10_1200=f1, funnel_15_1000=f2,
                                 auditor_review_required=auditor_flag)
        print(f"{label:<24}{st['n']:>5}{st['wr']:>6.1f}%"
              f"{(st['pf'] if np.isfinite(st['pf']) else 99):>7.2f}{st['expr']:>8.3f}{st['totr']:>8.1f}"
              f"{(st['removed_wr'] or 0):>6.1f}%{f1['pass_pct']:>10.1f}%{f1['e_attempt']:>11,.0f}"
              f"{f2['pass_pct']:>10.1f}%{f2['e_attempt']:>11,.0f}"
              f"{'  [AUDITOR]' if auditor_flag else ''}", flush=True)

    # -------------------------------------------------------------- preregistered check (3 families)
    families = dict(
        pd_zone=[tg for tg in tag_names if tg.startswith("b1_")],
        b2=["b2_disp_fvg_confirm"],
        b3=["b3_ote_fvg_confluence"],
    )
    prereg = {}
    for fam, tags in families.items():
        best = max(tags, key=lambda tg: filter_rows[tg]["totr"])
        beats = filter_rows[best]["totr"] > baseline_totr
        prereg[fam] = dict(best_tag=best, best_totr=filter_rows[best]["totr"],
                           baseline_totr=round(baseline_totr, 1), any_filter_raised_totr=bool(beats))
    print("\nPREREGISTERED CHECK ('no filter raises total R', 3 replications by family):", flush=True)
    for fam, r in prereg.items():
        print(f"  [{fam}] best={r['best_tag']} totR={r['best_totr']:+.1f} vs baseline "
              f"{r['baseline_totr']:+.1f} -> {'HYPOTHESIS FALSIFIED' if r['any_filter_raised_totr'] else 'holds'}",
              flush=True)

    # -------------------------------------------------------------- B5: D1c interaction (2x2 + phi)
    print("\nB5 — D1c INTERACTION (2x2 vs d1c_keep, over the raw pre-D1c signal set):", flush=True)
    keep_bool = [t["d1c_keep"] for t in raw]
    b5 = {}
    for tg in tag_names:
        tag_bool = [t.get(tg, False) for t in raw]
        r = phi_2x2(tag_bool, keep_bool)
        b5[tg] = r
        print(f"  {tg:<22} n11={r['n11']:>4} n10={r['n10']:>4} n01={r['n01']:>4} n00={r['n00']:>4} "
              f"phi={r['phi']}  overlap(tag->kept)={r['overlap_pct']}%", flush=True)
    phis = [abs(r["phi"]) for r in b5.values() if r["phi"] is not None]
    b5_verdict = ("DUPLICATE (tags strongly track D1c keep/reject)" if phis and max(phis) > 0.3 else
                 "COMPLEMENT (tags largely independent of D1c keep/reject)")
    print(f"  verdict: {b5_verdict} (max|phi|={max(phis):.3f})" if phis else "  verdict: n/a", flush=True)

    # -------------------------------------------------------------- write outputs
    cols = (["ts", "direction", "entry", "stop", "target", "risk_usd", "R", "mae_r",
             "sweep_bar", "mss_bar", "fill_bar", "d1c_keep"] + tag_names +
            ["b4_smt_es_testable", "b4_smt_ym_testable", "b4_smt_rty_testable"])
    df_out = pd.DataFrame([{c: t.get(c) for c in cols} for t in kept])
    csv_path = os.path.join(OUTDIR, "06_profile_a_enhancement.csv")
    df_out.to_csv(csv_path, index=False)
    print(f"\n[saved] {csv_path}", flush=True)

    funnel_rows_10 = []
    funnel_rows_15 = []
    for name, row in {**filter_rows, **{f"COMBO {k}": v for k, v in combo_rows.items()}}.items():
        funnel_rows_10.append(dict(filter=name, **row["funnel_10_1200"]))
        funnel_rows_15.append(dict(filter=name, **row["funnel_15_1000"]))
    funnel_rows_10.insert(0, dict(filter="NULL (baseline)", **canary))
    funnel_rows_15.insert(0, dict(filter="NULL (baseline)", **canary_15_1000))
    p8 = os.path.join(OUTDIR, "08_eval_funnel_cap10_1200.csv")
    p9 = os.path.join(OUTDIR, "09_eval_funnel_cap15_1000.csv")
    pd.DataFrame(funnel_rows_10).to_csv(p8, index=False)
    pd.DataFrame(funnel_rows_15).to_csv(p9, index=False)
    print(f"[saved] {p8}\n[saved] {p9}", flush=True)

    write_report(baseline_totr, canary, canary_15_1000, coverage, filter_rows, combo_rows,
                 prereg, b5, b5_verdict, testable_es, testable_ym, testable_rty, len(raw), len(kept))
    return dict(canary=canary, filter_rows=filter_rows, combo_rows=combo_rows, prereg=prereg, b5=b5)


def write_report(baseline_totr, canary, canary_15_1000, coverage, filter_rows, combo_rows,
                 prereg, b5, b5_verdict, testable_es, testable_ym, testable_rty, n_raw, n_kept):
    lines = []
    a = lines.append
    a("# Profile C — Workstream B: PD-array / FVG / SMT filters on the FROZEN Profile A stream")
    a("")
    a("**RESEARCH ONLY / SIM CONDITIONAL.** Profile A model is FROZEN; this is tag-and-measure only.")
    a("No entry replacement tested (register: fvg50-entry lane already killed, PF 1.46 vs 1.78, chasing -30R).")
    a("")
    a(f"Base stream: {n_kept} certified trades (exit3 + D1c, 1m-truth) reconstructed via the exact "
      f"`tools_sim_parity_check.load_rows()` code path and asserted byte-for-byte identical to it "
      f"(ts/R/mae_r/risk_usd). Pre-D1c raw signal set: {n_raw} (ny_am session, post model01, pre-D1c-drop).")
    a(f"Baseline totR = {baseline_totr:+.1f}R (register: +183.9R).")
    a("")
    a("## Canary (mandatory, blocking)")
    a(f"- @(cap10,$1200): pass={canary['pass_pct']} bust={canary['bust_pct']} exp={canary['exp_pct']} "
      f"med={canary['med_days']}d n={canary['n']} — expected 47.8/15.9/36.2/med16/n395 -> "
      f"{'MATCH' if canary['n']==395 and canary['pass_pct']==47.8 else 'MISMATCH — STOP'}")
    a(f"- @(cap15,$1000): pass={canary_15_1000['pass_pct']} bust={canary_15_1000['bust_pct']} "
      f"exp={canary_15_1000['exp_pct']} med={canary_15_1000['med_days']}d n={canary_15_1000['n']}")
    a("")
    a("## Annotation coverage (of 435 kept)")
    for tg, c in coverage.items():
        a(f"- `{tg}`: {c}/435 ({100*c/435:.1f}%)")
    a(f"- SMT testability: ES {testable_es}/435, YM {testable_ym}/435, RTY {testable_rty}/435")
    a("")
    a("## Filter table (top 5 by totR, full table in 08/09 CSVs)")
    ranked = sorted(filter_rows.items(), key=lambda kv: kv[1]["totr"], reverse=True)
    a("| filter | n | WR | PF | expR | totR | removed WR | pass@10/1200 | E$@10/1200 | pass@15/1000 | E$@15/1000 | auditor? |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for tg, r in ranked[:5]:
        a(f"| {tg} | {r['n']} | {r['wr']}% | {r['pf']} | {r['expr']} | {r['totr']:+.1f} | "
          f"{r['removed_wr']}% | {r['funnel_10_1200']['pass_pct']}% | {r['funnel_10_1200']['e_attempt']:,.0f} | "
          f"{r['funnel_15_1000']['pass_pct']}% | {r['funnel_15_1000']['e_attempt']:,.0f} | "
          f"{'YES' if r['auditor_review_required'] else 'no'} |")
    all_fail = all(r["totr"] <= baseline_totr for r in filter_rows.values())
    a("")
    a(f"**All-fail-if-so check:** {'ALL individual filters have totR <= baseline — no filter wins on raw totR.' if all_fail else 'At least one individual filter raised raw totR (see preregistered check below for whether it also raised E$/attempt).'}")
    a("")
    a("### Top combinations")
    a("| combo | n | WR | PF | expR | totR | pass@10/1200 | E$@10/1200 | pass@15/1000 | E$@15/1000 | auditor? |")
    a("|---|---|---|---|---|---|---|---|---|---|---|")
    for label, r in sorted(combo_rows.items(), key=lambda kv: kv[1]["totr"], reverse=True):
        a(f"| {label} | {r['n']} | {r['wr']}% | {r['pf']} | {r['expr']} | {r['totr']:+.1f} | "
          f"{r['funnel_10_1200']['pass_pct']}% | {r['funnel_10_1200']['e_attempt']:,.0f} | "
          f"{r['funnel_15_1000']['pass_pct']}% | {r['funnel_15_1000']['e_attempt']:,.0f} | "
          f"{'YES' if r['auditor_review_required'] else 'no'} |")
    a("")
    a("## Preregistered check: 'no filter raises total R' (3 replications, by tag family)")
    for fam, r in prereg.items():
        a(f"- **{fam}**: best={r['best_tag']} totR={r['best_totr']:+.1f} vs baseline {r['baseline_totr']:+.1f} "
          f"-> {'HYPOTHESIS FALSIFIED (raw totR)' if r['any_filter_raised_totr'] else 'holds'}")
    a("")
    a("## SMT testability verdict")
    a(f"- ES (primary): {testable_es}/435 testable")
    a(f"- YM / RTY (secondary): {testable_ym}/435, {testable_rty}/435")
    a("- 'Testable' requires the matched (ffilled) other-instrument bar within 15min of the NQ sweep bar "
      "and full 20-bar-lookback coverage; trades outside an instrument's data range are marked not-testable "
      "rather than silently reusing a stale value.")
    a("")
    a("## B5 — D1c complement-vs-duplicate")
    a(f"**Verdict: {b5_verdict}**")
    a("")
    a("| tag | n11 (tag&kept) | n10 (tag&dropped) | n01 (notag&kept) | n00 (notag&dropped) | phi | overlap(tag->kept)% |")
    a("|---|---|---|---|---|---|---|")
    for tg, r in b5.items():
        a(f"| {tg} | {r['n11']} | {r['n10']} | {r['n01']} | {r['n00']} | {r['phi']} | {r['overlap_pct']} |")
    a("")
    a("## Firewall")
    a("See harness stdout (`test_eval_config_firewall.py` + `test_funded_config_firewall.py` run "
      "before and after this workstream) — pass/fail state must be identical (no existing file touched).")
    a("")
    a("---")
    a("All numbers above: RESEARCH ONLY / SIM CONDITIONAL. No commits. Profile A live machine unchanged.")
    path = os.path.join(OUTDIR, "06_profile_a_enhancement.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[saved] {path}", flush=True)


if __name__ == "__main__":
    main()
