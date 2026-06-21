"""Profile B PARITY — prove the streaming ProfileBEngine emits the SAME signals as the
validated batch backtest (b_entries/b_exits). Target: 0 mismatches (like Profile A).
Compares per trading day: side, entry level, stop, target. Run:
    python3 tools/check_profile_b_parity.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
sys.path.insert(0, os.path.join(FW, "engine"))
import htf
from strategy_engine_profileB import ProfileBEngine

f = htf.build_features("NQ", "5m"); f.index.name = "timestamp"

# ---------------- BATCH (frozen b_entries/b_exits, verbatim logic) ----------------
df = f[["Open", "High", "Low", "Close"]].copy()
et = df.index
m = et.hour * 60 + et.minute
df["rth"] = (m >= 570) & (m < 960)
df["day"] = pd.DatetimeIndex(et).normalize().tz_localize(None)
pc = df.Close.shift(1)
df["atr"] = pd.concat([df.High - df.Low, (df.High - pc).abs(), (df.Low - pc).abs()],
                      axis=1).max(axis=1).rolling(14).mean()
H, L, C = df.High.values, df.Low.values, df.Close.values
idx = df.index; atrv = df["atr"].values; dayv = df["day"].values

def batch_signals():
    out = {}; busy = -1
    for d0, g in df.groupby("day"):
        r = g[g.rth]
        if len(r) < 20:
            continue
        oe = r.index[0] + pd.Timedelta(minutes=15); orng = r[r.index < oe]
        if len(orng) < 2:
            continue
        orh, orl = orng.High.max(), orng.Low.min(); post = r[r.index >= oe]
        a0 = atrv[idx.get_loc(orng.index[-1])]
        if not a0 or np.isnan(a0):
            continue
        broke = False
        for t in post.itertuples():
            if broke:
                break
            gi = idx.get_loc(t.Index)
            if gi <= busy:
                continue
            for d, lvl in ((1, orh), (-1, orl)):
                if not ((t.Close > lvl) if d > 0 else (t.Close < lvl)):
                    continue
                broke = True
                # SIGNAL = the limit placed at the break (engine's job). The fill-within-6-bars
                # test below is the downstream ORDER layer (limit retest), not the signal.
                out[str(pd.Timestamp(d0).date())] = dict(
                    side="long" if d > 0 else "short", entry=round(float(lvl), 4),
                    stop=round(float(lvl - d * 1.0 * a0), 4), target=round(float(lvl + d * 1.5 * a0), 4))
                for x in range(gi + 1, min(gi + 7, len(C))):
                    if L[x] <= lvl <= H[x]:
                        busy = x; break
                break
    return out

# ---------------- STREAMING (the live engine) ----------------
def stream_signals():
    eng = ProfileBEngine(); out = {}
    O = f["Open"].values; Hh = f["High"].values; Ll = f["Low"].values; Cc = f["Close"].values
    for i, ts in enumerate(f.index):
        eng.add_bar(ts, O[i], Hh[i], Ll[i], Cc[i])
        s = eng.latest_signal()
        if s is not None:
            day = str(pd.Timestamp(s["ts_signal"]).date())
            out[day] = dict(side=s["side"], entry=round(s["entry"], 4),
                            stop=round(s["stop"], 4), target=round(s["target"], 4))
    return out

# days with < 20 RTH bars = data-incomplete (the batch's len(r)>=20 guard; LIVE the data-readiness
# GREEN gate blocks these prospectively). They are a data-quality filter, not a strategy difference.
_rth_count = df[df.rth].groupby("day").size()
INCOMPLETE = {str(d.date()) for d, n in _rth_count.items() if n < 20}

print("running batch + streaming Profile B over full history…", flush=True)
B = batch_signals(); S_raw = stream_signals()
S = {d: v for d, v in S_raw.items() if d not in INCOMPLETE}   # live data-gate equivalent
gap_filtered = sorted(d for d in S_raw if d in INCOMPLETE)
days = sorted(set(B) | set(S))
mismatch = 0; only_b = only_s = side_diff = px_diff = 0
examples = []
for d in days:
    b, s = B.get(d), S.get(d)
    if b and not s: only_b += 1; mismatch += 1; examples.append((d, "only batch", b, s))
    elif s and not b: only_s += 1; mismatch += 1; examples.append((d, "only stream", b, s))
    elif b["side"] != s["side"]:
        side_diff += 1; mismatch += 1; examples.append((d, "side", b, s))
    elif abs(b["entry"] - s["entry"]) > 0.01 or abs(b["stop"] - s["stop"]) > 0.05 \
            or abs(b["target"] - s["target"]) > 0.05:
        px_diff += 1; mismatch += 1; examples.append((d, "price", b, s))

print(f"\nbatch signals: {len(B)}  ·  streaming signals: {len(S)} (complete-data days)  "
      f"·  trading days compared: {len(days)}")
print(f"data-gap days filtered (live data-gate / batch len>=20): {len(gap_filtered)}"
      + (f"  e.g. {gap_filtered[:3]}" if gap_filtered else ""))
print(f"MISMATCHES: {mismatch}  (only-batch {only_b}, only-stream {only_s}, side {side_diff}, price {px_diff})")
for d, kind, b, s in examples[:12]:
    print(f"  {d} [{kind}]  batch={b}  stream={s}")
print("\n" + ("PROFILE B PARITY: 0 MISMATCHES ✓ (streaming == backtest on all complete-data days)"
              if mismatch == 0
              else f"PROFILE B PARITY: {mismatch} MISMATCHES — engine must match the backtest"))
sys.exit(0 if mismatch == 0 else 1)
