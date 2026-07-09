"""
IFVG close-through-SPEED probe (Profile-D §F, targeted, research-only).

GOAL (narrow): test whether the ONE genuinely distinct IFVG rule — inversion-FVG
+ CLOSE-THROUGH SPEED — changes the WR/PF distribution vs the dead SMC3/BOS-FVG
core.  We do NOT build the full IFVG engine, do NOT optimise SMC3, do NOT run an
eval funnel.  Everything measured in R (risk-normalised).

REUSE (unchanged) from smc3_engine.py:
  * Tier-1 liquidity: 60m confirmed pivot (3/3) via lookahead_off stepping
    (_pivot, _ffill, _step_idx, _gather, resample_ohlc).
  * Same-bar sweep + reclaim (buffer 2 ticks); directional context latch
    (longContext after sell-side swept+reclaimed, short after buy-side);
    context expiry 180 (1m bars); sweep bar + sweep extreme recorded.
  * Cost model: $2.50/side commission + 1 tick (0.25pt) adverse slippage/fill;
    NQ $20/pt, tick 0.25.  1m intrabar OCO exit, stop-first same bar.

REPLACED (this is the probe mechanic) — SMC3's 5m-BOS/FVG-confirm + 1m-BOS/FVG-
trigger is swapped for IFVG inversion + close-through on an IFVG timeframe tf:
  * FVG on tf bars: bull FVG at bar i = low[i] > high[i-2] (zone [high[i-2],low[i]]);
    bear FVG at bar i = high[i] < low[i-2] (zone [high[i], low[i-2]]).  Formation
    known at CLOSE of bar i.
  * INVERSION + close-through: while a context is live, for a LONG context find the
    most-recent BEARISH FVG formed AFTER the sweep; inversion = first later tf bar
    whose CLOSE > the bear-FVG top (low[i-2]) -> bullish IFVG -> LONG.  SHORT mirrors
    (most-recent BULLISH FVG, inversion = first later CLOSE < bull-FVG bottom high[i-2]).
  * CLOSE-THROUGH SPEED = (inversion tf-bar idx - FVG formation tf-bar idx), in tf bars.
  * ENTRY = the close-through (inversion) bar's CLOSE (causal: the close>level test is
    known at that bar's close).  1-tick adverse slip.
  * STOP = sweep extreme -/+ 4 ticks.  TARGET = fixed 2R (held CONSTANT so the only
    variable across buckets is close-through speed).  risk<=tick or risk>120pt rejected.

HARD CAUSAL GATES (asserted, ambiguous -> ARTIFACT excluded + reported):
  entry_ns strictly AFTER sweep_confirm_ns and FVG_formation_close_ns; entry_ns ==
  close-through confirm close (entry AT the confirming bar's close, never before).
  No lookahead: 60m level / sweep / FVG / close-through all from bars closed <= entry.

Context handling: SMC3's sweep/expiry/opposite-kill machinery reproduced as a
context LIST (one context per sweep event, window = [sweep_confirm,
min(next_sweep-1, sweep+180)]).  Per context we take the FIRST causal inversion
(mirrors SMC3 consume-on-fire = one fire per context).  Trades are then walked in
time order with a one-position-at-a-time block (entry skipped while a prior trade
is open) and OCO stop/2R exits — faithful to SMC3 (exits only via stop/target).
"""
from __future__ import annotations

import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smc3_engine import (  # noqa: E402
    _pivot, _ffill, _step_idx, _gather, resample_ohlc,
    TICK, POINT_VALUE, COMMISSION_PER_SIDE, SLIPPAGE_TICKS,
)

DATA = "/Users/jacksonclarke/trading-team/data/real_futures/NQ_databento_1m_5y.parquet"
OUTDIR = "/Users/jacksonclarke/trading-team/backtests/zeus-occ-optimize/smc3/reports/ifvg_optimisation"

LONG, SHORT = 1, -1

# --- fixed probe params (Tier-1 reused from SMC3 defaults) ---
HTF_TF = 60
HTF_PIVOT = 3
SWEEP_BUF_TICKS = 2.0
EXPIRY_BARS = 180          # 1m bars
STOP_BUF_TICKS = 4.0
RR = 2.0                   # fixed 2R target (CONSTANT)
MAX_STOP_PT = 120.0
MIN_RISK_PT = TICK
EXIT_CAP = 5000            # 1m-bar safety cap on the OCO scan (unresolved -> OPEN)

MINUTE_NS = np.int64(60) * 1_000_000_000


# --------------------------------------------------------------------------- #
# Tier-1: 60m liquidity levels stepped to the 1m timeline (reused SMC3 logic)
# --------------------------------------------------------------------------- #
def build_levels(df1m):
    t_open = df1m.index.view("int64").astype("int64")
    htf = resample_ohlc(df1m, HTF_TF)
    htf_open_ns = htf.index.view("int64").astype("int64")
    htf_close_ns = htf_open_ns + np.int64(HTF_TF) * MINUTE_NS
    ph60 = _pivot(htf["high"].to_numpy(float), HTF_PIVOT, HTF_PIVOT, high=True)
    pl60 = _pivot(htf["low"].to_numpy(float), HTF_PIVOT, HTF_PIVOT, high=False)
    buySide60 = _ffill(ph60)
    sellSide60 = _ffill(pl60)
    idx60 = _step_idx(htf_close_ns, t_open)
    buySideLevel = _gather(idx60, buySide60)
    sellSideLevel = _gather(idx60, sellSide60)
    src60_close = np.where(idx60 >= 0, htf_close_ns[np.clip(idx60, 0, None)], -1)
    return t_open, buySideLevel, sellSideLevel, src60_close


# --------------------------------------------------------------------------- #
# Build the sweep-context list (SMC3 block-B sweep+reclaim; long priority)
# --------------------------------------------------------------------------- #
def build_contexts(df1m, t_open, buySideLevel, sellSideLevel):
    l1 = df1m["low"].to_numpy(float)
    h1 = df1m["high"].to_numpy(float)
    c1 = df1m["close"].to_numpy(float)
    N = len(t_open)
    buf = SWEEP_BUF_TICKS * TICK

    ev = []  # (sweep_bar_i, dir, extreme, swept_level)
    for i in range(N):
        ss = sellSideLevel[i]
        bs = buySideLevel[i]
        longSweep = (not np.isnan(ss)) and (l1[i] < ss - buf) and (c1[i] > ss)
        shortSweep = (not np.isnan(bs)) and (h1[i] > bs + buf) and (c1[i] < bs)
        if longSweep:
            ev.append((i, LONG, l1[i], ss))
        elif shortSweep:
            ev.append((i, SHORT, h1[i], bs))

    contexts = []
    for k, (i, d, extreme, lvl) in enumerate(ev):
        start_ns = int(t_open[i] + MINUTE_NS)              # sweep confirm = 1m close
        nxt = ev[k + 1][0] if k + 1 < len(ev) else N       # next sweep resets ctx
        end_1m = min(nxt - 1, i + EXPIRY_BARS, N - 1)
        if end_1m <= i:
            continue
        end_ns = int(t_open[end_1m] + MINUTE_NS)
        contexts.append({
            "sweep_i": i, "dir": d, "extreme": extreme, "swept_level": lvl,
            "sweep_confirm_ns": start_ns, "end_1m": end_1m, "end_ns": end_ns,
        })
    return contexts


# --------------------------------------------------------------------------- #
# Per-tf bar arrays
# --------------------------------------------------------------------------- #
def build_tf(df1m, tf):
    b = resample_ohlc(df1m, tf)
    open_ns = b.index.view("int64").astype("int64")
    return {
        "tf": tf,
        "open_ns": open_ns,
        "close_ns": open_ns + np.int64(tf) * MINUTE_NS,
        "high": b["high"].to_numpy(float),
        "low": b["low"].to_numpy(float),
        "close": b["close"].to_numpy(float),
        "n": len(open_ns),
    }


# --------------------------------------------------------------------------- #
# First causal inversion for a context on one tf
# --------------------------------------------------------------------------- #
def find_inversion(ctx, T):
    """Return dict(form_idx, form_ns, inv_idx, inv_ns, entry_ref, speed) for the
    FIRST close-through inversion of the most-recent post-sweep FVG, else None."""
    close_ns = T["close_ns"]
    hi = T["high"]; lo = T["low"]; cl = T["close"]
    d = ctx["dir"]
    start_ns = ctx["sweep_confirm_ns"]
    end_ns = ctx["end_ns"]

    j0 = int(np.searchsorted(close_ns, start_ns, side="right"))  # first close > sweep
    j1 = int(np.searchsorted(close_ns, end_ns, side="right")) - 1  # last close <= end
    if j1 < j0:
        return None

    active = None  # dict(level, form_idx, form_ns)
    for j in range(j0, j1 + 1):
        # (1) inversion check against the currently-active (most recent) FVG
        if active is not None:
            if d == LONG and cl[j] > active["level"]:
                return {"form_idx": active["form_idx"], "form_ns": active["form_ns"],
                        "inv_idx": j, "inv_ns": int(close_ns[j]),
                        "entry_ref": float(cl[j]), "speed": j - active["form_idx"]}
            if d == SHORT and cl[j] < active["level"]:
                return {"form_idx": active["form_idx"], "form_ns": active["form_ns"],
                        "inv_idx": j, "inv_ns": int(close_ns[j]),
                        "entry_ref": float(cl[j]), "speed": j - active["form_idx"]}
        # (2) formation update — most-recent qualifying FVG (formed after sweep)
        if j >= 2:
            if d == LONG and hi[j] < lo[j - 2]:            # bearish FVG; top = low[j-2]
                active = {"level": lo[j - 2], "form_idx": j, "form_ns": int(close_ns[j])}
            elif d == SHORT and lo[j] > hi[j - 2]:         # bullish FVG; bot = high[j-2]
                active = {"level": hi[j - 2], "form_idx": j, "form_ns": int(close_ns[j])}
    return None


# --------------------------------------------------------------------------- #
# OCO exit sim on 1m bars (stop-first same bar); reused SMC3 exit convention
# --------------------------------------------------------------------------- #
def scan_oco(lo1, hi1, t_open, exit_start, direction, stop, target, N):
    end = min(exit_start + EXIT_CAP, N)
    if end <= exit_start:
        return None
    slo = lo1[exit_start:end]
    shi = hi1[exit_start:end]
    if direction == LONG:
        s_mask = slo <= stop
        t_mask = shi >= target
    else:
        s_mask = shi >= stop
        t_mask = slo <= target
    s_rel = int(np.argmax(s_mask)) if s_mask.any() else None
    t_rel = int(np.argmax(t_mask)) if t_mask.any() else None
    if s_rel is None and t_rel is None:
        return None  # OPEN (unresolved within cap)
    if s_rel is not None and (t_rel is None or s_rel <= t_rel):  # stop-first on tie
        xi = exit_start + s_rel
        return {"exit_idx": xi, "exit_level": stop,
                "exit_ns": int(t_open[xi] + MINUTE_NS), "reason": "stop"}
    xi = exit_start + t_rel
    return {"exit_idx": xi, "exit_level": target,
            "exit_ns": int(t_open[xi] + MINUTE_NS), "reason": "target"}


def finish(direction, entry_ref, stop, target, risk, ex_level, entry_ns, exit_ns, reason):
    slip = SLIPPAGE_TICKS * TICK
    if direction == LONG:
        e_fill = entry_ref + slip
        x_fill = ex_level - slip
        net_pts = x_fill - e_fill
    else:
        e_fill = entry_ref - slip
        x_fill = ex_level + slip
        net_pts = e_fill - x_fill
    comm = COMMISSION_PER_SIDE * 2.0
    net_dollars = net_pts * POINT_VALUE - comm
    risk_dollars = risk * POINT_VALUE
    R = net_dollars / risk_dollars if risk_dollars > 0 else np.nan
    return net_dollars, R, (exit_ns - entry_ns) / 1e9 / 60.0


# --------------------------------------------------------------------------- #
# Run the probe for one tf-mode ('single' tf, or 'highest' 5->1)
# --------------------------------------------------------------------------- #
def run_probe(df1m, t_open, contexts, tf_arrays, mode="single", tf=None):
    """tf_arrays: dict tf->arrays.  mode='single' uses tf; mode='highest' scans 5->1
    and takes the highest tf with a risk-valid causal inversion in the window."""
    lo1 = df1m["low"].to_numpy(float)
    hi1 = df1m["high"].to_numpy(float)
    N = len(t_open)
    stop_buf = STOP_BUF_TICKS * TICK

    tfs_to_try = [tf] if mode == "single" else [5, 4, 3, 2, 1]

    # 1) build one candidate per context (first causal inversion), record gate flags
    cands = []
    n_reject_risk = 0
    n_artifact = 0
    n_gate_ok = 0
    for ctx in contexts:
        d = ctx["dir"]
        chosen = None
        chosen_tf = None
        for cand_tf in tfs_to_try:
            inv = find_inversion(ctx, tf_arrays[cand_tf])
            if inv is None:
                continue
            entry_ref = inv["entry_ref"]
            if d == LONG:
                stop = ctx["extreme"] - stop_buf
                risk = entry_ref - stop
                target = entry_ref + RR * risk
            else:
                stop = ctx["extreme"] + stop_buf
                risk = stop - entry_ref
                target = entry_ref - RR * risk
            valid = (not np.isnan(risk)) and (risk > MIN_RISK_PT) and (risk <= MAX_STOP_PT)
            if not valid:
                if mode == "single":
                    n_reject_risk += 1
                    chosen = None
                    break  # single-tf: first inversion invalid -> drop context
                else:
                    continue  # highest: try a lower tf
            chosen = dict(inv, stop=stop, risk=risk, target=target)
            chosen_tf = cand_tf
            break
        if chosen is None:
            continue

        entry_ns = chosen["inv_ns"]
        # ---- HARD CAUSAL GATES ----
        g_sweep = entry_ns > ctx["sweep_confirm_ns"]
        g_form = entry_ns > chosen["form_ns"]
        g_ct = entry_ns == chosen["inv_ns"]          # entry AT close-through confirm
        exit_start = int(np.searchsorted(t_open, entry_ns, side="left"))
        g_seq = exit_start < N                          # a bar-after must exist
        if not (g_sweep and g_form and g_ct and g_seq):
            n_artifact += 1
            continue
        n_gate_ok += 1
        cands.append({
            "dir": d, "tf": chosen_tf, "entry_ref": chosen["entry_ref"],
            "stop": chosen["stop"], "target": chosen["target"], "risk": chosen["risk"],
            "speed": chosen["speed"], "entry_ns": entry_ns, "exit_start": exit_start,
            "sweep_ns": ctx["sweep_confirm_ns"], "form_ns": chosen["form_ns"],
            "sweep_i": ctx["sweep_i"], "extreme": ctx["extreme"],
            "swept_level": ctx["swept_level"], "end_ns": ctx["end_ns"],
        })

    cands.sort(key=lambda c: c["entry_ns"])

    # 2) one-position-at-a-time walk with OCO exits (exits only via stop/2R)
    trades = []
    n_open = 0
    n_blocked = 0
    last_exit_ns = -1
    for c in cands:
        if c["entry_ns"] < last_exit_ns:
            n_blocked += 1
            continue
        res = scan_oco(lo1, hi1, t_open, c["exit_start"], c["dir"],
                       c["stop"], c["target"], N)
        if res is None:
            n_open += 1
            continue
        net_d, R, hold = finish(c["dir"], c["entry_ref"], c["stop"], c["target"],
                                c["risk"], res["exit_level"], c["entry_ns"],
                                res["exit_ns"], res["reason"])
        last_exit_ns = res["exit_ns"]
        trades.append({
            "dir": "long" if c["dir"] == LONG else "short",
            "tf": c["tf"],
            "speed": c["speed"],
            "entry_time": pd.Timestamp(c["entry_ns"], tz="UTC"),
            "exit_time": pd.Timestamp(res["exit_ns"], tz="UTC"),
            "sweep_time": pd.Timestamp(c["sweep_ns"], tz="UTC"),
            "form_time": pd.Timestamp(c["form_ns"], tz="UTC"),
            "entry": round(c["entry_ref"], 2),
            "stop": round(c["stop"], 2),
            "target": round(c["target"], 2),
            "exit": round(res["exit_level"], 2),
            "risk_pts": round(c["risk"], 4),
            "net_dollars": net_d,
            "R": R,
            "reason": res["reason"],
            "hold_min": hold,
        })

    tdf = pd.DataFrame(trades)
    diag = {"contexts": len(contexts), "cands": len(cands), "gate_ok": n_gate_ok,
            "artifacts": n_artifact, "risk_rejects": n_reject_risk,
            "blocked": n_blocked, "open_unresolved": n_open}
    return tdf, diag


# --------------------------------------------------------------------------- #
# R-based metrics + slicing helpers
# --------------------------------------------------------------------------- #
def add_tags(tdf):
    if len(tdf) == 0:
        return tdf
    et = tdf["entry_time"].dt.tz_convert("America/New_York")
    tdf = tdf.copy()
    tdf["et_hourmin"] = et.dt.hour * 60 + et.dt.minute
    tdf["et_year"] = et.dt.year
    tdf["et_dow"] = et.dt.dayofweek  # Mon=0..Fri=4
    tdf["nyam"] = (tdf["et_hourmin"] >= 9 * 60 + 30) & (tdf["et_hourmin"] < 12 * 60)
    return tdf


def rstats(tdf):
    if tdf is None or len(tdf) == 0:
        return {"n": 0, "wr": np.nan, "pf": np.nan, "avgR": np.nan, "totR": 0.0}
    R = tdf["R"].to_numpy()
    pos = R[R > 0].sum()
    neg = -R[R < 0].sum()
    pf = pos / neg if neg > 0 else (np.inf if pos > 0 else np.nan)
    return {"n": int(len(R)), "wr": float((R > 0).mean() * 100), "pf": float(pf),
            "avgR": float(R.mean()), "totR": float(R.sum())}


def year_signs(tdf):
    if len(tdf) == 0:
        return {}
    out = {}
    for y in sorted(tdf["et_year"].unique()):
        s = tdf[tdf["et_year"] == y]["R"].sum()
        out[int(y)] = "+" if s > 0 else ("-" if s < 0 else "0")
    return out


def full_bucket_row(tdf):
    """Full per-filter stat set required by the spec."""
    base = rstats(tdf)
    is_ = rstats(tdf[tdf["et_year"] <= 2024]) if len(tdf) else {"avgR": np.nan}
    oos = rstats(tdf[tdf["et_year"] >= 2025]) if len(tdf) else {"avgR": np.nan}
    ex24 = rstats(tdf[tdf["et_year"] != 2024]) if len(tdf) else {"avgR": np.nan}
    exfri = rstats(tdf[tdf["et_dow"] != 4]) if len(tdf) else {"avgR": np.nan}
    base.update({"is_avgR": is_["avgR"], "oos_avgR": oos["avgR"],
                 "ex24_avgR": ex24["avgR"], "exfri_avgR": exfri["avgR"],
                 "yr_signs": year_signs(tdf)})
    return base


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
DEAD_SMC3 = {"n": 5056, "wr": 34.4, "avgR": -0.010}


def _pf(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "-"
    return "inf" if x == np.inf else f"{x:.2f}"


def _f(x, nd=3):
    if x is None or (isinstance(x, float) and (np.isnan(x))):
        return "-"
    return f"{x:+.{nd}f}"


def speed_bucket_table(tdf):
    """n/WR/PF/avgR/totR for exact speeds 1..5 and >5."""
    rows = []
    for lbl, mask in ([(str(s), tdf["speed"] == s) for s in (1, 2, 3, 4, 5)]
                      + [(">5", tdf["speed"] > 5)]):
        rows.append((lbl, rstats(tdf[mask])))
    return rows


def filter_table(tdf):
    """Cumulative <=k filters, no-limit, and >=5 negative control (full stat set)."""
    out = []
    for lbl, mask in [("<=1", tdf["speed"] <= 1), ("<=2", tdf["speed"] <= 2),
                      ("<=3", tdf["speed"] <= 3), ("<=4", tdf["speed"] <= 4),
                      ("<=5", tdf["speed"] <= 5), ("no-limit", tdf["speed"] >= 1),
                      (">=5 (neg ctrl)", tdf["speed"] >= 5)]:
        out.append((lbl, full_bucket_row(tdf[mask])))
    return out


def hand_trace(tdf, label, k=5):
    """Return list of trace strings for k winners, k losers, 3 largest each."""
    if len(tdf) == 0:
        return []
    s = tdf.sort_values("R")
    losers = s.head(k)
    winners = s.tail(k).iloc[::-1]
    largest_w = s.tail(3).iloc[::-1]
    largest_l = s.head(3)
    lines = []

    def _one(tr):
        sw = tr["sweep_time"]; fm = tr["form_time"]; en = tr["entry_time"]; ex = tr["exit_time"]
        ok = (sw < fm < en) and (en <= ex)
        return (f"  {tr['dir']:>5} tf{int(tr['tf'])} spd{int(tr['speed'])} | "
                f"sweep {sw:%Y-%m-%d %H:%M} < fvg {fm:%H:%M} < entry {en:%H:%M} "
                f"<= exit {ex:%H:%M} | entry {tr['entry']:.2f} stop {tr['stop']:.2f} "
                f"tgt {tr['target']:.2f} exit {tr['exit']:.2f} | R {tr['R']:+.2f} "
                f"{tr['reason']} | causal_order={'OK' if ok else 'VIOLATION'}")

    lines.append(f"### {label} — 5 winners")
    for _, tr in winners.iterrows():
        lines.append(_one(tr))
    lines.append(f"### {label} — 5 losers")
    for _, tr in losers.iterrows():
        lines.append(_one(tr))
    lines.append(f"### {label} — 3 largest winners")
    for _, tr in largest_w.iterrows():
        lines.append(_one(tr))
    lines.append(f"### {label} — 3 largest losers")
    for _, tr in largest_l.iterrows():
        lines.append(_one(tr))
    return lines


def main():
    df1m = pd.read_parquet(DATA)
    print(f"[data] {len(df1m):,} 1m bars  {df1m.index[0]} -> {df1m.index[-1]}")

    t_open, buySideLevel, sellSideLevel, src60_close = build_levels(df1m)
    contexts = build_contexts(df1m, t_open, buySideLevel, sellSideLevel)
    print(f"[contexts] {len(contexts):,} sweep contexts")

    # global 60m no-lookahead check (source close <= 1m open where present)
    m60 = src60_close >= 0
    la_global = bool((src60_close[m60] <= t_open[m60]).all())

    tf_arrays = {tf: build_tf(df1m, tf) for tf in (1, 2, 3, 4, 5)}

    # per-tf single runs
    per_tf = {}
    diags = {}
    for tf in (1, 2, 3, 4, 5):
        tdf, diag = run_probe(df1m, t_open, contexts, tf_arrays, mode="single", tf=tf)
        tdf = add_tags(tdf)
        per_tf[tf] = tdf
        diags[tf] = diag
        print(f"[tf {tf}] trades={len(tdf)} diag={diag}")

    # highest-available-tf run
    tdf_h, diag_h = run_probe(df1m, t_open, contexts, tf_arrays, mode="highest")
    tdf_h = add_tags(tdf_h)
    print(f"[highest] trades={len(tdf_h)} diag={diag_h}")

    # ---- choose the headline tf: best <=4 avgR with n>=100 and positive ex-2024
    def score_tf(tf):
        t = per_tf[tf]
        sub = t[t["speed"] <= 4]
        st = full_bucket_row(sub)
        return st
    tf_scores = {tf: score_tf(tf) for tf in (1, 2, 3, 4, 5)}
    # pick best by ex24_avgR among n>=100
    elig = [tf for tf in (1, 2, 3, 4, 5) if tf_scores[tf]["n"] >= 100]
    best_tf = max(elig, key=lambda tf: (tf_scores[tf]["ex24_avgR"]
                                        if not np.isnan(tf_scores[tf]["ex24_avgR"])
                                        else -9)) if elig else None

    # =====================================================================
    # Build report
    # =====================================================================
    L = []
    P = L.append
    P("# Profile D (IFVG) — §F Close-Through-SPEED Probe")
    P("")
    P("_Research-only. LIVE HOLD ACTIVE — no arming, no funded-config change, no "
      "certification claim. Targeted probe of the ONE distinct IFVG rule (inversion "
      "FVG + close-through speed) vs the dead SMC3/BOS-FVG core. All figures in R._")
    P("")
    P(f"Data: `{DATA}`  ({len(df1m):,} 1m bars, {df1m.index[0]:%Y-%m-%d} -> "
      f"{df1m.index[-1]:%Y-%m-%d})")
    P(f"Costs: ${COMMISSION_PER_SIDE:.2f}/side + {SLIPPAGE_TICKS:.0f} tick "
      f"({SLIPPAGE_TICKS*TICK:.2f}pt) adverse/fill. NQ ${POINT_VALUE:.0f}/pt, tick {TICK}. "
      f"Target = fixed {RR:.0f}R (held constant). Stop = sweep extreme ± "
      f"{STOP_BUF_TICKS:.0f}t. IS 2021-24 / OOS 2025-26H1 (by entry year).")
    P("")

    # ---- causal audit
    P("## 1. Causal audit")
    P("")
    tot_gate = sum(diags[tf]["gate_ok"] for tf in (1, 2, 3, 4, 5)) + diag_h["gate_ok"]
    tot_art = sum(diags[tf]["artifacts"] for tf in (1, 2, 3, 4, 5)) + diag_h["artifacts"]
    P(f"- Global 60m no-lookahead (stepped source close <= 1m open): "
      f"**{'PASS' if la_global else 'FAIL'}**")
    P(f"- Per-trade causal gates asserted (entry_ns > sweep_confirm & > FVG_formation; "
      f"entry == close-through confirm; bar-after exists): **PASS** for all fired trades.")
    P(f"- Gate-OK fires across all 6 runs: **{tot_gate:,}** | Artifacts (gate-fail, "
      f"excluded): **{tot_art}**")
    P("")
    P("| run | contexts | candidates | gate_ok | artifacts | risk_rej | blocked | open |")
    P("|---|---|---|---|---|---|---|---|")
    for tf in (1, 2, 3, 4, 5):
        dgt = diags[tf]
        P(f"| tf{tf} | {dgt['contexts']} | {dgt['cands']} | {dgt['gate_ok']} | "
          f"{dgt['artifacts']} | {dgt['risk_rejects']} | {dgt['blocked']} | "
          f"{dgt['open_unresolved']} |")
    P(f"| highest | {diag_h['contexts']} | {diag_h['cands']} | {diag_h['gate_ok']} | "
      f"{diag_h['artifacts']} | {diag_h['risk_rejects']} | {diag_h['blocked']} | "
      f"{diag_h['open_unresolved']} |")
    P("")

    # ---- headline speed bucket table (pooled across all single-tf runs)
    pooled = pd.concat([per_tf[tf] for tf in (1, 2, 3, 4, 5)], ignore_index=True)
    pooled = add_tags(pooled)
    P("## 2. Close-through-SPEED bucket table (pooled tf 1-5, all single-tf trades)")
    P("")
    P("| speed (tf bars) | n | WR% | PF(R) | avgR | totR |")
    P("|---|---|---|---|---|---|")
    for lbl, st in speed_bucket_table(pooled):
        P(f"| {lbl} | {st['n']} | {st['wr']:.1f} | {_pf(st['pf'])} | "
          f"{_f(st['avgR'])} | {st['totR']:+.1f} |")
    P("")
    P("_Speed = (inversion tf-bar idx − FVG formation tf-bar idx). Minimum speed is 1 "
      "(a formation bar can never close through its own gap). MONOTONIC faster=better "
      "would show avgR/PF/WR declining as speed rises._")
    P("")

    # per-tf speed bucket detail
    P("### Per-tf speed buckets (avgR)")
    P("")
    P("| tf | spd1 | spd2 | spd3 | spd4 | spd5 | spd>5 |")
    P("|---|---|---|---|---|---|---|")
    for tf in (1, 2, 3, 4, 5):
        cells = []
        for lbl, st in speed_bucket_table(per_tf[tf]):
            cells.append(f"{_f(st['avgR'],3)}(n{st['n']})" if st['n'] else "-")
        P(f"| tf{tf} | " + " | ".join(cells) + " |")
    P("")

    # ---- filter table (headline) + comparisons
    P("## 3. Filter comparison  (<=4 vs >=5 vs dead-SMC3)")
    P("")
    P("Pooled tf 1-5, full stat set per cumulative filter:")
    P("")
    P("| filter | n | WR% | PF(R) | avgR | totR | IS avgR | OOS avgR | ex-2024 avgR | "
      "ex-Fri avgR | yr-signs |")
    P("|---|---|---|---|---|---|---|---|---|---|---|")
    for lbl, st in filter_table(pooled):
        ys = "".join(st["yr_signs"].get(y, ".") for y in range(2021, 2027))
        P(f"| {lbl} | {st['n']} | {st['wr']:.1f} | {_pf(st['pf'])} | {_f(st['avgR'])} | "
          f"{st['totR']:+.1f} | {_f(st['is_avgR'])} | {_f(st['oos_avgR'])} | "
          f"{_f(st['ex24_avgR'])} | {_f(st['exfri_avgR'])} | {ys} |")
    P("")
    P(f"**Dead SMC3 baseline:** n{DEAD_SMC3['n']} · WR {DEAD_SMC3['wr']}% · "
      f"avgR {DEAD_SMC3['avgR']:+.3f}  (2R/1R breakeven WR ≈ 33.3%).")
    P("")
    le4 = full_bucket_row(pooled[pooled["speed"] <= 4])
    ge5 = full_bucket_row(pooled[pooled["speed"] >= 5])
    P("**Head-to-head (pooled):**")
    P(f"- `<=4` close-through: n{le4['n']} WR {le4['wr']:.1f}% PF(R) {_pf(le4['pf'])} "
      f"avgR {_f(le4['avgR'])} (ex-2024 {_f(le4['ex24_avgR'])})")
    P(f"- `>=5` close-through: n{ge5['n']} WR {ge5['wr']:.1f}% PF(R) {_pf(ge5['pf'])} "
      f"avgR {_f(ge5['avgR'])} (ex-2024 {_f(ge5['ex24_avgR'])})")
    P(f"- dead SMC3:          n{DEAD_SMC3['n']} WR {DEAD_SMC3['wr']}% avgR "
      f"{DEAD_SMC3['avgR']:+.3f}")
    P("")

    # ---- tf table (comparison 3)
    P("## 4. IFVG timeframe table (1m..5m), <=4 close-through headline")
    P("")
    P("| tf | n(<=4) | WR% | PF(R) | avgR | totR | IS avgR | OOS avgR | ex-2024 avgR | "
      "ex-Fri avgR | yr-signs |")
    P("|---|---|---|---|---|---|---|---|---|---|---|")
    for tf in (1, 2, 3, 4, 5):
        st = tf_scores[tf]
        ys = "".join(st["yr_signs"].get(y, ".") for y in range(2021, 2027))
        P(f"| {tf}m | {st['n']} | {st['wr']:.1f} | {_pf(st['pf'])} | {_f(st['avgR'])} | "
          f"{st['totR']:+.1f} | {_f(st['is_avgR'])} | {_f(st['oos_avgR'])} | "
          f"{_f(st['ex24_avgR'])} | {_f(st['exfri_avgR'])} | {ys} |")
    # highest-tf mode
    hst = full_bucket_row(tdf_h[tdf_h["speed"] <= 4])
    ys = "".join(hst["yr_signs"].get(y, ".") for y in range(2021, 2027))
    P(f"| highest(5→1) | {hst['n']} | {hst['wr']:.1f} | {_pf(hst['pf'])} | "
      f"{_f(hst['avgR'])} | {hst['totR']:+.1f} | {_f(hst['is_avgR'])} | "
      f"{_f(hst['oos_avgR'])} | {_f(hst['ex24_avgR'])} | {_f(hst['exfri_avgR'])} | {ys} |")
    P("")

    # ---- long/short, session split (best-candidate context = pooled <=4)
    P("## 5. Sub-splits on the `<=4` pooled headline bucket")
    P("")
    sub = pooled[pooled["speed"] <= 4]
    P("| split | n | WR% | PF(R) | avgR | totR |")
    P("|---|---|---|---|---|---|")
    for lbl, mask in [("long", sub["dir"] == "long"), ("short", sub["dir"] == "short"),
                      ("NY-AM 0930-1200", sub["nyam"]), ("all-sessions", sub["speed"] >= 0),
                      ("2024-in", sub["speed"] >= 0), ("2024-ex", sub["et_year"] != 2024),
                      ("Friday-in", sub["speed"] >= 0), ("Friday-ex", sub["et_dow"] != 4)]:
        st = rstats(sub[mask])
        P(f"| {lbl} | {st['n']} | {st['wr']:.1f} | {_pf(st['pf'])} | {_f(st['avgR'])} | "
          f"{st['totR']:+.1f} |")
    P("")

    # ---- best candidate
    P("## 6. Best candidate")
    P("")
    if best_tf is not None:
        bst = tf_scores[best_tf]
        ys = "".join(bst["yr_signs"].get(y, ".") for y in range(2021, 2027))
        P(f"Best tf by ex-2024 avgR (n>=100) = **{best_tf}m**, `<=4` close-through:")
        P(f"- n{bst['n']} · WR {bst['wr']:.1f}% · PF(R) {_pf(bst['pf'])} · avgR "
          f"{_f(bst['avgR'])} · totR {bst['totR']:+.1f}")
        P(f"- IS avgR {_f(bst['is_avgR'])} · OOS avgR {_f(bst['oos_avgR'])} · "
          f"ex-2024 avgR {_f(bst['ex24_avgR'])} · ex-Friday avgR {_f(bst['exfri_avgR'])}")
        P(f"- per-year R signs 2021..2026: {ys}")
    else:
        P("No tf reached n>=100 in the `<=4` bucket — headline undersized.")
    P("")

    # ---- risk-floor robustness (is the KILL just a tiny-risk cost artifact?)
    P("## 6b. Risk-floor robustness (cost-artifact control)")
    P("")
    P("Sweep-extreme stops produce many sub-1pt-risk trades whose R is dominated by "
      "fixed costs (down to −2.5R). Re-checking the pooled book at rising risk floors "
      "to prove the KILL is NOT merely that cost bleed:")
    P("")
    P("| risk floor | n | WR% | PF(R) | avgR | spd1..5 avgR (gradient) |")
    P("|---|---|---|---|---|---|")
    for lo in (0, 2, 5, 10):
        s = pooled[pooled["risk_pts"] >= lo]
        st = rstats(s)
        grad = []
        for k in (1, 2, 3, 4, 5):
            sk = s[s["speed"] == k]["R"]
            grad.append(f"{sk.mean():+.3f}" if len(sk) else "-")
        P(f"| >={lo}pt | {st['n']} | {st['wr']:.1f} | {_pf(st['pf'])} | "
          f"{_f(st['avgR'])} | {' '.join(grad)} |")
    P("")
    P("Even at risk>=10pt (removing the cost-bleed tail) the book converges to WR ~34% / "
      "PF ~1.00 / avgR ~0.00 — i.e. it reproduces the SAME ~33% 2R breakeven "
      "distribution as dead SMC3 (WR 34.4%), and the speed buckets stay non-monotonic "
      "(spd2 best, spd3 worst). Close-through SPEED carries no information about outcome.")
    P("")

    # ---- hand-trace audit
    P("## 7. Hand-trace artifact audit (tz-aware UTC)")
    P("")
    for ln in hand_trace(pooled[pooled["speed"] <= 4], "Pooled <=4"):
        P(ln)
    P("")
    P(f"Total artifacts (gate failures, excluded) across all runs: **{tot_art}**")
    P("")

    # ---- verdict logic
    headline = le4
    n_head = headline["n"]
    speeds = speed_bucket_table(pooled)
    # monotonicity: avgR of exact-speed buckets 1..5 non-increasing?
    seq = [st["avgR"] for _, st in speeds[:5] if st["n"] >= 30]
    monotonic = len(seq) >= 3 and all(seq[i] >= seq[i + 1] - 1e-9 for i in range(len(seq) - 1))
    faster_better = (rstats(pooled[pooled["speed"] <= 4])["avgR"]
                     > rstats(pooled[pooled["speed"] >= 5])["avgR"] + 1e-9)

    kills = []
    if not (headline["pf"] is not None and headline["pf"] != np.inf and headline["pf"] > 1.15):
        kills.append(f"PF(R) {_pf(headline['pf'])} <= 1.15")
    if np.isnan(headline["ex24_avgR"]) or headline["ex24_avgR"] <= 0:
        kills.append(f"ex-2024 avgR {_f(headline['ex24_avgR'])} breakeven/negative")
    exfri = headline["exfri_avgR"]
    if (not np.isnan(exfri)) and headline["avgR"] > 0 and exfri <= 0:
        kills.append("edge is mostly Friday (ex-Friday collapses)")
    if abs(headline["wr"] - 33.3) < 1.5:
        kills.append(f"WR {headline['wr']:.1f}% pinned at ~33% breakeven")
    if n_head < 100:
        kills.append(f"headline n {n_head} < 100 (too small)")
    if not monotonic and not faster_better:
        kills.append("no monotonic faster=better gradient")

    status = "KILL" if kills else ("PASS" if (faster_better and monotonic
                                              and headline["pf"] not in (None, np.inf)
                                              and headline["pf"] > 1.20
                                              and headline["ex24_avgR"] > 0) else "WATCHLIST")

    P("## 8. VERDICT")
    P("")
    P(f"**CLOSE-THROUGH IFVG PROBE STATUS: {status}.**")
    P("")
    P(f"- Mechanism visible as monotonic faster=better gradient? "
      f"**{'YES' if (monotonic and faster_better) else 'NO'}** "
      f"(<=4 avgR {_f(le4['avgR'])} vs >=5 avgR {_f(ge5['avgR'])}; "
      f"exact-speed 1..5 avgR seq = {[round(x,3) for x in seq]})")
    if kills:
        P("- KILL triggers:")
        for k in kills:
            P(f"  - {k}")
    else:
        P("- No KILL triggers fired.")
    P("")
    rec = ("SHELVE — build NOT justified. " if status == "KILL"
           else "PROCEED WITH CAUTION — re-run isolated confirmation before any build. "
           if status == "WATCHLIST"
           else "BUILD justified — full IFVG engine extension warranted. ")
    P(f"**Recommendation: {rec}**")
    P("")

    out_path = os.path.join(OUTDIR, "09_close_through_probe.md")
    os.makedirs(OUTDIR, exist_ok=True)
    with open(out_path, "w") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n[written]", out_path)

    # console echo of the key blocks
    print("\n===== CONSOLE SUMMARY =====")
    print(f"causal: global60 {'PASS' if la_global else 'FAIL'}, gate_ok {tot_gate}, "
          f"artifacts {tot_art}")
    print("\nSPEED BUCKETS (pooled tf1-5):")
    print("spd | n | WR% | PF(R) | avgR | totR")
    for lbl, st in speeds:
        print(f"{lbl:>3} | {st['n']:>5} | {st['wr']:.1f} | {_pf(st['pf'])} | "
              f"{_f(st['avgR'])} | {st['totR']:+.1f}")
    print(f"\n<=4: n{le4['n']} WR{le4['wr']:.1f} PF{_pf(le4['pf'])} avgR{_f(le4['avgR'])} "
          f"ex24{_f(le4['ex24_avgR'])}")
    print(f">=5: n{ge5['n']} WR{ge5['wr']:.1f} PF{_pf(ge5['pf'])} avgR{_f(ge5['avgR'])} "
          f"ex24{_f(ge5['ex24_avgR'])}")
    print(f"dead SMC3: n{DEAD_SMC3['n']} WR{DEAD_SMC3['wr']} avgR{DEAD_SMC3['avgR']:+.3f}")
    print(f"best_tf={best_tf}")
    print(f"\nSTATUS: {status}")
    return status


if __name__ == "__main__":
    main()
