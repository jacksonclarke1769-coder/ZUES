"""TRAILING 12 MONTHS on a 50K account — Profile B alone (2 MNQ) and Profile A+B together
(A3 + B2 + the deployed -$700 daily stop). Same frozen logic + realistic fills as
replay_ab_dailystop.py (the validated 30-day harness), just over a 12-month window with
monthly breakdowns. Dukascopy NQ CFD 5m (basis-irrelevant: both profiles trade relative levels).

  python3 replay_ab_12mo.py
"""
import os, sys
import numpy as np, pandas as pd
import paper_live, strategy_engine_profileA as E, config
import model01_sweep_mss_fvg as M1
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
from funded_sim import Acct, ACCOUNTS

A_DPP, A_COMM = 6, 4.5     # 3 MNQ ($2/pt/contract * 3) + round-turn commission
B_DPP = 4                  # 2 MNQ
DAILY_STOP = -700.0
B_COST = 0.75              # Profile B frozen cost (points): slippage + commission
WARMUP_DAYS = 450
WINDOW_DAYS = 365
E.BUFFER_DAYS = 70


# --- Profile B frozen logic (verbatim from replay_ab_dailystop.py) ---
def b_entries(df):
    H, L, C, O = df.High.values, df.Low.values, df.Close.values, df.Open.values
    atrv = df["atr"].values; day = df["day"].values; idx = df.index
    ents = []; busy = -1
    for d0, g in df.groupby("day"):
        r = g[g.rth]
        if len(r) < 20: continue
        o_end = r.index[0] + pd.Timedelta(minutes=15)
        orng = r[r.index < o_end]
        if len(orng) < 2: continue
        orh, orl = orng.High.max(), orng.Low.min()
        post = r[r.index >= o_end]
        atr0 = atrv[idx.get_loc(orng.index[-1])]
        if not atr0 or np.isnan(atr0): continue
        broke = False
        for t in post.itertuples():
            if broke: break
            gi = idx.get_loc(t.Index)
            if gi <= busy: continue
            for d, lvl in ((1, orh), (-1, orl)):
                br = (t.Close > lvl) if d > 0 else (t.Close < lvl)
                if not br: continue
                fill = None
                for x in range(gi + 1, min(gi + 7, len(C))):
                    if L[x] <= lvl <= H[x]: fill = x; break
                broke = True
                if fill is None: break
                ents.append(dict(fill=fill, dir=d, entry=lvl, atr=atr0, orh=orh, orl=orl,
                                 day=day[fill], ts=idx[fill])); busy = fill; break
    return ents, (H, L, C, O, df["rth"].values)


def b_exits(ents, arrays, s=1.0, t=1.5, cost=B_COST):
    H, L, C, O, rth = arrays; n = len(C); out = []
    for e in ents:
        f = e["fill"]; d = e["dir"]; entry = e["entry"]; atr = e["atr"]
        if not atr or np.isnan(atr): continue
        stop = entry - d * s * atr; tgt = entry + d * t * atr; mae = 0.0; ex = None
        for j, x in enumerate(range(f, min(f + 24, n))):
            mae = min(mae, (L[x] - entry) * d)
            if d > 0:
                if L[x] <= stop: ex = stop; break
                if H[x] >= tgt: ex = tgt; break
            else:
                if H[x] >= stop: ex = stop; break
                if L[x] <= tgt: ex = tgt; break
            if not rth[x] and x > f: ex = C[x]; break
        if ex is None: ex = C[min(f + 24, n) - 1]
        gross = (ex - entry) * d
        out.append(dict(net=gross - cost, mae=mae, day=pd.Timestamp(e["day"]).normalize(), ts=e["ts"]))
    return pd.DataFrame(out)


print("fetching ~%dd of Dukascopy NQ 5m…" % WARMUP_DAYS, flush=True)
bars = list(paper_live.DukascopyLiveFeed(warmup_days=WARMUP_DAYS).history())

# --- Profile A (3 MNQ) ---
# Build the engine buffer DIRECTLY over the FULL history (bypass add_bar's rolling
# BUFFER_DAYS trim, which is a live-only window). feats over the full buffer + M1.run is
# the canonical Profile A backtest the live engine wraps.
NY = "America/New_York"
eng = E.ProfileAEngine(config.STRAT)
_idx, _data = [], []
for ts, o, h, l, c in bars:
    t = pd.Timestamp(ts)
    t = t.tz_convert(NY) if t.tzinfo else t.tz_localize("UTC").tz_convert(NY)
    _idx.append(t); _data.append([o, h, l, c, 0])
buf = pd.DataFrame(_data, index=pd.DatetimeIndex(_idx),
                   columns=["Open", "High", "Low", "Close", "Volume"])
eng.buf = buf[~buf.index.duplicated(keep="last")].sort_index()
feats = eng._features()
trA = M1.run(feats, "NQ", {**E.PROFILE_A, "slip_ticks": 8})
trA = trA[trA.session == "ny_am"].copy()
trA["ts"] = pd.to_datetime(trA["date"].astype(str))
fi = feats.index
trA["ft"] = trA["fill_bar"].apply(lambda b: fi[int(b)] if 0 <= int(b) < len(fi) else pd.NaT)
trA["pnl"] = trA.r_result * (trA.entry - trA.stop).abs() * A_DPP - A_COMM
trA["mae"] = trA.mae_r * (trA.entry - trA.stop).abs() * A_DPP

# --- Profile B (2 MNQ) on the same bars ---
df = pd.DataFrame([(ts, o, h, l, c) for ts, o, h, l, c in bars],
                  columns=["ts", "Open", "High", "Low", "Close"]).set_index("ts")
et = df.index.tz_convert("America/New_York")
mins = et.hour * 60 + et.minute
df["rth"] = (mins >= 570) & (mins < 960)
df["day"] = et.normalize().tz_localize(None)
pc = df.Close.shift(1)
trng = pd.concat([df.High - df.Low, (df.High - pc).abs(), (df.Low - pc).abs()], axis=1).max(axis=1)
df["atr"] = trng.rolling(14).mean()
ents, arrays = b_entries(df)
trB = b_exits(ents, arrays)
if len(trB):
    trB["pnl"] = trB.net * B_DPP
    trB["maed"] = trB.mae * B_DPP

# --- trailing 12-month window ---
last = eng.buf.index.max().normalize().tz_localize(None)
start = last - pd.Timedelta(days=WINDOW_DAYS)

rows = []
for _, t in trA.iterrows():
    d = pd.Timestamp(t.ts).normalize()
    if start <= d <= last:
        rows.append(dict(day=d, ft=t.ft, pnl=t.pnl, src="A"))
for _, t in (trB.iterrows() if len(trB) else []):
    d = pd.Timestamp(t.day).normalize()
    if start <= d <= last:
        rows.append(dict(day=d, ft=t.ts, pnl=t.pnl, src="B"))
R = pd.DataFrame(rows)
R["ft"] = pd.to_datetime(R["ft"], utc=True, errors="coerce")
R = R.sort_values(["day", "ft"]).reset_index(drop=True)
R["month"] = R["day"].dt.to_period("M")


def daily_pnl(sub, apply_stop):
    """Per-day P&L; if apply_stop, halt NEW entries once the day's realised P&L <= -$700."""
    out = []
    for d, g in sub.groupby("day"):
        cum = 0.0; na = nb = 0; trades = []
        for _, r in g.iterrows():
            if apply_stop and cum <= DAILY_STOP:
                break
            trades.append(r.pnl); cum += r.pnl
            if r.src == "A": na += 1
            else: nb += 1
        out.append(dict(day=d, pnl=sum(trades), n=len(trades), na=na, nb=nb, trades=trades))
    return pd.DataFrame(out)


def summarize(sub, label, apply_stop):
    dd = daily_pnl(sub, apply_stop)
    if not len(dd):
        print(f"\n=== {label}: no trades in window ==="); return
    # per-trade stats (flatten kept trades)
    pnls = [p for row in dd.trades for p in row]
    wins = [p for p in pnls if p > 0]; losses = [p for p in pnls if p < 0]
    n = len(pnls); net = sum(pnls)
    pf = (sum(wins) / abs(sum(losses))) if losses else float("inf")
    winr = 100.0 * len(wins) / n if n else 0
    # equity curve on a 50k account (chronological by day)
    dd = dd.sort_values("day").reset_index(drop=True)
    bal = 50000.0; peak = 50000.0; maxdd = 0.0; cum0 = 0.0; days_to_target = None
    for _, row in dd.iterrows():
        bal += row.pnl; cum0 += row.pnl
        peak = max(peak, bal); maxdd = max(maxdd, peak - bal)
        if days_to_target is None and cum0 >= 3000:
            days_to_target = row.day
    # MFFU eval: run the precise account model over the chronological day stream
    acc = Acct(ACCOUNTS["50K"]); eval_res = None; eval_date = None
    for _, row in dd.iterrows():
        r = acc.day([(p, 0.0, 0.0) for p in row.trades])
        if r in ("PASS", "BREACH"):
            eval_res = r; eval_date = row.day; break

    print(f"\n================ {label} ================")
    print(f"window {start.date()} -> {last.date()}  ·  trading days {len(dd)}")
    nA = int(dd.na.sum()); nB = int(dd.nb.sum())
    print(f"trades: {n}  (A={nA}  B={nB})  ·  win% {winr:.0f}  ·  profit factor {pf:.2f}")
    print(f"NET P&L (12mo): ${net:+,.0f}  ·  avg/trade ${net/n:+,.0f}  ·  avg/day ${net/len(dd):+,.0f}")
    best = dd.loc[dd.pnl.idxmax()]; worst = dd.loc[dd.pnl.idxmin()]
    print(f"best day ${best.pnl:+,.0f} ({best.day.date()})  ·  worst day ${worst.pnl:+,.0f} ({worst.day.date()})")
    print(f"equity 50,000 -> {50000+net:,.0f}  ·  max drawdown ${maxdd:,.0f}")
    # monthly table
    print(f"\n  {'month':9}{'A':>4}{'B':>4}{'days':>6}{'P&L':>11}{'cum P&L':>12}")
    cum = 0.0
    for m, g in dd.assign(month=dd.day.dt.to_period("M")).groupby("month"):
        mp = g.pnl.sum(); cum += mp
        # a/b counts that month
        sm = sub[sub.month == m]
        print(f"  {str(m):9}{int(g.na.sum()):>4}{int(g.nb.sum()):>4}{len(g):>6}{mp:>11,.0f}{cum:>12,.0f}")
    # eval interpretation
    print(f"\n  MFFU 50K eval (start of window): "
          + (f"{eval_res} on {eval_date.date()}" if eval_res else "no pass/breach in window"))
    if days_to_target:
        print(f"  +$3,000 target first reached: {days_to_target.date()}  ·  max DD ${maxdd:,.0f} "
              f"(< $2,000 breach line: {'OK' if maxdd < 2000 else 'BREACHED'})")
    else:
        print(f"  +$3,000 target: not reached cumulatively in window  ·  max DD ${maxdd:,.0f}")


# OUTPUT 1 — Profile B alone (2 MNQ), no daily stop (it's a single-strategy view)
summarize(R[R.src == "B"].copy(), "PROFILE B ALONE  ·  2 MNQ  ·  50K account", apply_stop=False)

# OUTPUT 2 — Profile A + B together (3+2 MNQ) with the deployed -$700 daily stop
summarize(R.copy(), "PROFILE A + B  ·  A3 + B2  ·  -$700 daily stop (deployed)  ·  50K account",
          apply_stop=True)

print("\n[note] Dukascopy NQ CFD 5m, realistic fills (A: 8-tick slip + $comm; B: 0.75pt cost).")
print("[note] Equity/maxDD are the raw strategy curve from $50k (NOT eval-stopped); the eval line")
print("       shows when a fresh MFFU 50K challenge would resolve. Past sim != future / live fills.")
