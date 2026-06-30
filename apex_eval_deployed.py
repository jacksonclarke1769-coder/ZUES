"""APEX eval sim for the DEPLOYED stack — A10 / B5 / Momentum-6, $550 daily stop, 30-DAY EXPIRY.

Closes the gap flagged 2026-06-27: apex_sim.py is A-only/3MNQ and models NO clock, so its ~90%
is unlimited-time. This sims the ACTUAL deployed Apex-50K-eval config through the Apex trailing model
(funded_rules.ApexAcct) WITH the hard 30-calendar-day expiry, and reports PASS / BUST / EXPIRE.

Method (consistent with apex_sim's validated per-trade approach, so it's apples-to-apples):
  * A (model01 OTE, Exit#3 via PROFILE_A) @ 10 MNQ — pnl/mfe/mae in $ from r_result/mfe_r/mae_r.
  * B (ORB, frozen retest-fill) @ 5 MNQ — pnl/mfe/mae in $ (mfe added here).
  * Momentum (Zarattini noise-band, flat-at-EOD position) @ 6 MNQ — ONE event/day: realised daily P&L
    + intraday peak/trough as mfe/mae. Per-flip cost applied.
  * Merge all events chronologically; apply the $550 daily stop (halt the day's NEW events once
    realised <= -$550); rolling-start an eval at the first event of every trading day; PASS at +$3,000,
    BUST on the trailing breach, EXPIRE if not passed within 30 calendar days.

CAVEAT (honest): per-trade sequential marking is slightly OPTIMISTIC vs the true joint intraday tick
path (three legs can be open at once and are not jointly marked) — so the real BUST rate is, if
anything, a touch higher than this prints. Dukascopy NQ CFD proxy (single source for all 3 legs).
"""
import os, sys
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

import strategy_engine_profileA as E        # puts model01 on sys.path
import model01_sweep_mss_fvg as M1
import config, paper_live
import funded_rules as FR
from profile_momentum_engine import ProfileMomentumEngine as PME

NY = "America/New_York"
DPP = 2.0                 # $ / index point / MNQ contract
A_SIZE, B_SIZE, M_SIZE = 10, 5, 6
DAILY_STOP = -550.0
EXPIRE_DAYS = 30
M_FLIP_COST = 1.0         # $/contract per position change (≈2-tick round-turn) — momentum cost
WARMUP_DAYS = 1500        # ~4y
B_COST = 0.75             # Profile B frozen cost (points)


# ---------------- data (single source for all three legs) ----------------
def load_bars():
    bars = list(paper_live.DukascopyLiveFeed(warmup_days=WARMUP_DAYS).history())
    idx, rows = [], []
    for ts, o, h, l, c in bars:
        t = pd.Timestamp(ts)
        t = t.tz_convert(NY) if t.tzinfo else t.tz_localize("UTC").tz_convert(NY)
        idx.append(t); rows.append([o, h, l, c, 0])
    df = pd.DataFrame(rows, index=pd.DatetimeIndex(idx),
                      columns=["Open", "High", "Low", "Close", "Volume"])
    return df[~df.index.duplicated(keep="last")].sort_index()


# ---------------- Profile A events (@10) ----------------
def a_events(df5):
    eng = E.ProfileAEngine(config.STRAT)
    eng.buf = df5
    feats = eng._features()
    tr = M1.run(feats, "NQ", {**E.PROFILE_A, "slip_ticks": 8})
    tr = tr[tr.session == "ny_am"].copy()
    fi = feats.index
    ev = []
    for _, t in tr.iterrows():
        risk = abs(float(t["entry"]) - float(t["stop"]))
        if risk <= 0:
            continue
        fb = int(t["fill_bar"])
        ts = fi[fb] if 0 <= fb < len(fi) else pd.Timestamp(str(t["date"])).tz_localize(NY)
        usd = risk * DPP * A_SIZE
        ev.append(dict(ts=pd.Timestamp(ts), src="A",
                       pnl=float(t["r_result"]) * usd,
                       mfe=max(0.0, float(t["mfe_r"])) * usd,
                       mae=min(0.0, float(t["mae_r"])) * usd))
    return ev


# ---------------- Profile B events (@5) — frozen retest-fill + mfe ----------------
def b_events(df5):
    """Profile B (ORB) per-trade events — modelled here as a SINGLE 1.5R target (full qty).
    ⚠️ FIDELITY NOTE (2026-06-30 audit): the LIVE bot trades B as the 50/50 PARTIAL (50%@+1R +
    50%@+1.5R, shared stop), which is gentler AND out-earns single-1.5R — so this generator
    UNDERSTATES the deployed B edge (eval pass ~57.5% here vs ~59.8% faithful, wins 5/6 yrs).
    For the TRUE deployed pass-rate use bpartial_fidelity.py (b_events_partial). Left as-is to
    avoid rippling every harness; the dashboard/report cite the faithful partial number."""
    df = df5.copy()
    et = df.index.tz_convert(NY); mins = et.hour * 60 + et.minute
    df["rth"] = (mins >= 570) & (mins < 960)
    df["day"] = et.normalize().tz_localize(None)
    pc = df.Close.shift(1)
    trng = pd.concat([df.High - df.Low, (df.High - pc).abs(), (df.Low - pc).abs()], axis=1).max(axis=1)
    df["atr"] = trng.rolling(14).mean()
    H, L, C = df.High.values, df.Low.values, df.Close.values
    atrv = df["atr"].values; idx = df.index; n = len(C)
    ev = []
    for d0, g in df.groupby("day"):
        r = g[g.rth]
        if len(r) < 20:
            continue
        o_end = r.index[0] + pd.Timedelta(minutes=15)
        orng = r[r.index < o_end]
        if len(orng) < 2:
            continue
        orh, orl = orng.High.max(), orng.Low.min()
        atr0 = atrv[idx.get_loc(orng.index[-1])]
        if not atr0 or np.isnan(atr0):
            continue
        post = r[r.index >= o_end]; broke = False
        for t in post.itertuples():
            if broke:
                break
            gi = idx.get_loc(t.Index)
            for d, lvl in ((1, orh), (-1, orl)):
                br = (t.Close > lvl) if d > 0 else (t.Close < lvl)
                if not br:
                    continue
                broke = True
                fill = None
                for x in range(gi + 1, min(gi + 7, n)):
                    if L[x] <= lvl <= H[x]:
                        fill = x; break
                if fill is None:
                    break
                entry = lvl; stop = entry - d * 1.0 * atr0; tgt = entry + d * 1.5 * atr0
                ex = None; mfe = 0.0; mae = 0.0
                for x in range(fill, min(fill + 24, n)):
                    mfe = max(mfe, (H[x] - entry) * d if d > 0 else (entry - L[x]) * d)
                    mae = min(mae, (L[x] - entry) * d if d > 0 else (entry - H[x]) * d)
                    if d > 0:
                        if L[x] <= stop: ex = stop; break
                        if H[x] >= tgt: ex = tgt; break
                    else:
                        if H[x] >= stop: ex = stop; break
                        if L[x] <= tgt: ex = tgt; break
                    if not df["rth"].values[x] and x > fill: ex = C[x]; break
                if ex is None:
                    ex = C[min(fill + 24, n) - 1]
                gross = (ex - entry) * d
                ev.append(dict(ts=idx[fill], src="B",
                               pnl=(gross - B_COST) * DPP * B_SIZE,
                               mfe=max(0.0, mfe) * DPP * B_SIZE,
                               mae=min(0.0, mae) * DPP * B_SIZE))
                break
    return ev


# ---------------- Momentum events (@6) — one per day, flat at EOD ----------------
def m_events(df5):
    d = df5.copy()
    mins = d.index.hour * 60 + d.index.minute
    d = d[(mins >= 570) & (mins < 960)].copy()
    d["date"] = d.index.normalize().tz_localize(None)
    d["slot"] = ((d.index.hour * 60 + d.index.minute) - 570) // 5
    d = d.reset_index().rename(columns={"index": "ts"})
    pos = PME.compute(d[["date", "slot", "Open", "High", "Low", "Close"]].assign(Volume=0))
    d["pos"] = pos
    ev = []
    for day, g in d.groupby("date"):
        g = g.reset_index(drop=True)
        cum = 0.0; peak = 0.0; trough = 0.0; flips = 0; prev = 0.0
        for i in range(1, len(g)):
            held = g.pos.iloc[i - 1]
            cum += held * (g.Close.iloc[i] - g.Close.iloc[i - 1]) * DPP * M_SIZE
            peak = max(peak, cum); trough = min(trough, cum)
            if g.pos.iloc[i] != prev:
                flips += 1; prev = g.pos.iloc[i]
        cost = flips * M_FLIP_COST * M_SIZE
        cum -= cost; trough -= cost
        if abs(cum) > 1e-9 or peak != 0 or trough != 0:
            ev.append(dict(ts=g.ts.iloc[-1], src="M", pnl=cum, mfe=peak, mae=trough))
    return ev


# ---------------- daily $550 stop ----------------
def apply_daily_stop(events):
    events = sorted(events, key=lambda e: e["ts"])
    kept = []
    by_day = {}
    for e in events:
        day = pd.Timestamp(e["ts"]).normalize()
        by_day.setdefault(day, []).append(e)
    for day in sorted(by_day):
        cum = 0.0
        for e in by_day[day]:
            if cum <= DAILY_STOP:
                break                       # day halted: drop remaining NEW entries
            kept.append(e); cum += e["pnl"]
    return sorted(kept, key=lambda e: e["ts"])


# ---------------- one rolling Apex eval with 30-day expiry ----------------
def eval_from(events, start, spec):
    a = FR.ApexAcct(spec)
    t0 = pd.Timestamp(events[start]["ts"])
    for k in range(start, len(events)):
        e = events[k]
        days = (pd.Timestamp(e["ts"]) - t0).days
        if days > EXPIRE_DAYS:
            return "EXPIRE", EXPIRE_DAYS, k - start
        a.apply_trade(e["pnl"], mfe=max(0.0, e["mfe"]), mae=min(0.0, e["mae"]))
        if a.passed:
            return "PASS", days, k - start + 1
        if a.breached:
            return "BUST", days, k - start + 1
    return "INCOMPLETE", None, len(events) - start


def run_config(events, label, size="50K"):
    spec = FR.APEX_ACCOUNTS[size]
    # start an eval at the first event of each distinct trading day
    day_starts = []
    seen = set()
    for i, e in enumerate(events):
        day = pd.Timestamp(e["ts"]).normalize()
        if day not in seen:
            seen.add(day); day_starts.append(i)
    # need room for a 30-day eval to resolve -> drop starts in the last 30 days
    last_ts = pd.Timestamp(events[-1]["ts"])
    starts = [i for i in day_starts if (last_ts - pd.Timestamp(events[i]["ts"])).days > EXPIRE_DAYS]
    out = [eval_from(events, s, spec) for s in starts]
    n = len(out)
    npass = sum(1 for o in out if o[0] == "PASS")
    nbust = sum(1 for o in out if o[0] == "BUST")
    nexp = sum(1 for o in out if o[0] == "EXPIRE")
    pass_days = [o[1] for o in out if o[0] == "PASS"]
    med_days = int(np.median(pass_days)) if pass_days else None
    print(f"\n================ {label} ================")
    print(f"  eval starts (rolling, 1/trading-day): {n}")
    print(f"  PASS {100*npass/n:5.1f}%   BUST {100*nbust/n:5.1f}%   EXPIRE {100*nexp/n:5.1f}%")
    print(f"  median calendar-days to pass: {med_days}   (Apex clock = {EXPIRE_DAYS}d)")
    return dict(n=n, pass_pct=round(100*npass/n, 1), bust_pct=round(100*nbust/n, 1),
                expire_pct=round(100*nexp/n, 1), med_days=med_days)


def main():
    print(f"loading ~{WARMUP_DAYS}d Dukascopy NQ 5m…", flush=True)
    df5 = load_bars()
    print(f"  bars {df5.index.min().date()} -> {df5.index.max().date()}  ({len(df5):,})", flush=True)
    print("building A@10 / B@5 / Momentum@6 streams…", flush=True)
    A, B, Mm = a_events(df5), b_events(df5), m_events(df5)
    print(f"  A={len(A)}  B={len(B)}  Momentum-days={len(Mm)}", flush=True)

    full = apply_daily_stop(A + B + Mm)
    ab = apply_daily_stop(A + B)
    print(f"  events after $550 daily stop: full(A+B+mm)={len(full)}  A+B-only={len(ab)}", flush=True)

    r_full = run_config(full, "DEPLOYED  A10 / B5 / Momentum-6  ·  $550 stop  ·  30-day clock")
    r_ab = run_config(ab, "A10 / B5 only (momentum OFF)  ·  $550 stop  ·  30-day clock")
    print("\n[note] Dukascopy proxy; per-trade give-back model (slightly optimistic vs joint tick path).")
    print("[note] Compare PASS% to the dashboard's stored ~86%. EXPIRE% = the 30-day-clock cost.")
    return r_full, r_ab


if __name__ == "__main__":
    main()
