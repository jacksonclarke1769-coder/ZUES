"""ARES 50K eval, LAST 30 DAYS, the DEPLOYED config: Profile A3 + Profile B2 + the -$700 daily stop.

A = frozen model01 (NY-AM OTE), 3 MNQ, realistic 2pt-slip fills + $comm.
B = frozen Profile B v1 (NY 15m OR break -> limit retest, E1 1.0/1.5 ATR, 0.75pt cost), 2 MNQ.
Daily stop = halt NEW entries once the day's realised P&L <= -$700 (ARES control).
MFFU eval rules via funded_sim.Acct (+$3k target, $2k EOD-trailing DD w/ intraday-MAE breach,
50% single-day consistency, min 2 days). Same recent Dukascopy data as the size sweep.
"""
import os, sys
import numpy as np, pandas as pd
import paper_live, strategy_engine_profileA as E, config
import model01_sweep_mss_fvg as M1
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
from funded_sim import Acct, ACCOUNTS

A_DPP, A_COMM = 6, 4.5     # 3 MNQ
B_DPP = 4                  # 2 MNQ ($2/pt/contract * 2)
DAILY_STOP = -700.0
B_COST = 0.75             # Profile B frozen cost (points)
E.BUFFER_DAYS = 70


# --- Profile B frozen logic (copied from profileB_validation to avoid import side effects) ---
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


# --- recent bars (same source as the size sweep) ---
bars = list(paper_live.DukascopyLiveFeed(warmup_days=72).history())

# --- Profile A (3 MNQ) ---
eng = E.ProfileAEngine(config.STRAT)
for ts, o, h, l, c in bars:
    eng.add_bar(ts, o, h, l, c)
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

# --- 30-day window ---
last = eng.buf.index.max().normalize().tz_localize(None); start = last - pd.Timedelta(days=30)

rows = []
for _, t in trA.iterrows():
    d = pd.Timestamp(t.ts).normalize()
    if start <= d <= last:
        rows.append(dict(day=d, ft=t.ft, pnl=t.pnl, mae=t.mae, src="A"))
for _, t in (trB.iterrows() if len(trB) else []):
    d = pd.Timestamp(t.day).normalize()
    if start <= d <= last:
        rows.append(dict(day=d, ft=t.ts, pnl=t.pnl, mae=t.maed, src="B"))
R = pd.DataFrame(rows)
R["ft"] = pd.to_datetime(R["ft"], utc=True, errors="coerce")
R = R.sort_values(["day", "ft"]).reset_index(drop=True)


def build_days(apply_stop):
    days = []
    for d, g in R.groupby("day"):
        cum = 0.0; lst = []; na = nb = 0; stopped = False
        for _, r in g.iterrows():
            if apply_stop and cum <= DAILY_STOP:
                stopped = True; break
            lst.append((r.pnl, r.mae, 0.0)); cum += r.pnl
            if r.src == "A": na += 1
            else: nb += 1
        days.append((d, lst, na, nb, stopped))
    return days


def run_eval(days, label):
    acc = Acct(ACCOUNTS["50K"])
    traj = []; result = None
    for d, lst, na, nb, stopped in days:
        r = acc.day(lst)
        daypnl = sum(x[0] for x in lst)
        traj.append((d, na, nb, daypnl, acc.bal, stopped))
        if r in ("PASS", "BREACH"):
            result = r; break
    peak = max(b for _, _, _, _, b, _ in traj) if traj else 50000
    end = acc.bal
    maxdd = max((peak_so_far - b) for peak_so_far, b in
                _running_peak([b for *_, b, _ in traj])) if traj else 0
    return acc, traj, result, end, peak, maxdd


def _running_peak(bals):
    pk = 50000.0
    for b in bals:
        pk = max(pk, b); yield (pk, b)


nA = ((trA.ts >= start) & (trA.ts <= last)).sum()
nB = (len(trB) and ((pd.to_datetime(trB.day) >= start) & (pd.to_datetime(trB.day) <= last)).sum()) or 0
print(f"=== ARES 50K eval · {start.date()} -> {last.date()} (30d) · A3+B2 · realistic fills ===")
print(f"signals in window: Profile A = {nA}, Profile B = {nB}\n")

for label, stop in [("A3+B2, NO daily stop", False), ("A3+B2 + -$700 DAILY STOP (deployed)", True)]:
    days = build_days(stop)
    acc, traj, result, end, peak, maxdd = run_eval(days, label)
    stops = sum(1 for *_, s in traj if s)
    biggest = max((dp for *_, dp, _, _ in [(t[0], t[1], t[2], t[3], t[4]) for t in traj]), default=0)
    print(f"--- {label} ---")
    print(f"{'date':12}{'A':>3}{'B':>3}{'day P&L':>10}{'balance':>11}{'  stop?':>8}")
    for d, na, nb, dp, bal, stopped in traj:
        print(f"{str(d.date()):12}{na:>3}{nb:>3}{dp:>10.0f}{bal:>11,.0f}{('  STOP' if stopped else ''):>8}")
    prof = end - 50000
    status = result or ("in eval (no pass)")
    cons = (acc.maxday <= 0.5 * prof) if prof > 0 else None
    print(f"  result: {status} · end ${end:,.0f} (profit ${prof:+,.0f}) · peak ${peak:,.0f} · maxDD ${maxdd:,.0f}")
    print(f"  biggest day ${acc.maxday:,.0f} ({(100*acc.maxday/prof) if prof>0 else 0:.0f}% of profit; consistency<=50% {'OK' if cons else 'FAIL'}) · daily-stop fired {stops} day(s)")
    print(f"  target $3,000 -> {'PASSED' if status=='PASS' else ('BREACH' if status=='BREACH' else f'short ${max(0,3000-prof):,.0f}')}\n")
