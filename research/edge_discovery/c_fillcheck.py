"""
FILL-REALISM check for family C (vol-gated MR fade), LIMIT-ENTRY variant.

The primary harness (c_volgated_mr.py) uses MARKET entry at next-bar open -- no fill
optimism. A fade is *naturally* a resting LIMIT at the band, which fills at a BETTER
price than a market entry. The artifact risk: assuming the limit fills when price only
touches (not trades through) it, on a stale signal. This module verifies fills honestly
on REAL 1m Databento bars: price must trade THROUGH the limit, and stop/target are then
walked adverse-first on 1m. Reports FILL RATE and honest PF.

Levels for the 1m bars inside 5m interval (i+1) use bar i's CLOSED vwap/atr -> causal.
Tested on the best-looking gate (atrpct low-vol) to see if better limit entries flip the
sub-1.0 verdict. If even the optimistically-priced limit fade stays PF<1, the limit
route offers no rescue.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
import apex_eval_eod_databento as DB
import tools_vpc_1m_truth as T
import c_volgated_mr as C

RT_COST = 0.75


def run():
    print("loading 5m + 1m real Databento...", flush=True)
    df5 = DB.load_databento_5m()
    feats = C.features(df5)
    d1 = T.load_1m_rth()
    d1 = d1[d1.index >= C.YR_START].copy()
    d1["date"] = d1.index.normalize()
    d1by = {d: g for d, g in d1.groupby("date")}

    CFGS = [  # (band_k, stop_atr, tgt_mode, gate, thr)
        (2.0, 1.5, "vwap", "atrpct", 0.40),
        (2.5, 2.0, "vwap", "atrpct", 0.40),
        (2.0, 1.5, "vwap", "off",    None),
    ]
    slot_min, slot_max, max_trades = 6, 66, 2

    for (bk, sa, tm, gate, thr) in CFGS:
        n_signals = 0; n_filled = 0; trades = []
        for day, g in feats.groupby("date"):
            g = g.sort_values("slot").reset_index(drop=True)
            g1 = d1by.get(day)
            if g1 is None or len(g1) == 0:
                continue
            i1 = g1.index.values; H1 = g1.high.values; L1 = g1.low.values; C1 = g1.close.values
            V = g.vwap.values; A = g.atr.values; Cl = g.Close.values
            t5 = g.index.values
            busy_until_ts = None; taken = 0
            for i in range(len(g) - 1):
                if not (slot_min <= i <= slot_max):
                    continue
                if taken >= max_trades:
                    break
                if np.isnan(A[i]) or A[i] <= 0 or np.isnan(V[i]):
                    continue
                if not C.gate_pass(g.iloc[i], gate, thr):
                    continue
                # direction only if bar i is EXTENDED beyond band at close (same trigger as primary)
                upper = V[i] + bk * A[i]; lower = V[i] - bk * A[i]
                if Cl[i] > upper:
                    d = -1; limit = upper
                elif Cl[i] < lower:
                    d = 1; limit = lower
                else:
                    continue
                n_signals += 1
                # 1m window: from start of NEXT 5m bar forward to EOD
                t_next = t5[i + 1]
                a1 = int(np.searchsorted(i1, t_next, side="left"))
                if busy_until_ts is not None:
                    a1 = max(a1, int(np.searchsorted(i1, busy_until_ts, side="right")))
                if a1 >= len(i1):
                    continue
                # find first 1m bar that trades THROUGH the limit (adverse selection: fade fills
                # only if price continues to the band). short: high>=limit ; long: low<=limit
                fill_j = None
                for j in range(a1, len(i1)):
                    if d == -1 and H1[j] >= limit:
                        fill_j = j; break
                    if d == 1 and L1[j] <= limit:
                        fill_j = j; break
                if fill_j is None:
                    continue                      # NON-FILL (honest)
                n_filled += 1
                entry = limit
                target = V[i]
                stop = entry - sa * A[i] if d == 1 else entry + sa * A[i]
                exit_px = None
                for j in range(fill_j, len(i1)):
                    if d == 1:
                        if L1[j] <= stop: exit_px = stop; break         # adverse first
                        if H1[j] >= target: exit_px = target; break
                    else:
                        if H1[j] >= stop: exit_px = stop; break
                        if L1[j] <= target: exit_px = target; break
                if exit_px is None:
                    exit_px = C1[-1]
                pnl = d * (exit_px - entry) - RT_COST
                trades.append(dict(date=day, d=d, pnl=pnl))
                busy_until_ts = i1[j] if exit_px is not None else i1[-1]
                taken += 1
        tr = pd.DataFrame(trades)
        fill_rate = (n_filled / n_signals * 100) if n_signals else 0
        s = C.stats(tr)
        tr["yr"] = pd.to_datetime(tr.date).dt.year if len(tr) else []
        is_pf = C.pf_of(tr[pd.to_datetime(tr.date) < C.IS_END]) if len(tr) else np.nan
        oos_pf = C.pf_of(tr[pd.to_datetime(tr.date) >= C.IS_END]) if len(tr) else np.nan
        print(f"\ncfg band_k={bk} stop_atr={sa} tgt={tm} gate={gate} thr={thr}")
        print(f"  signals={n_signals} filled={n_filled} FILL_RATE={fill_rate:.1f}%  "
              f"(non-fill risk={100-fill_rate:.1f}%)")
        print(f"  HONEST-1m-LIMIT: n={s['n']} PF={s['pf']:.3f} WR={s['wr']:.3f} "
              f"net={s['net']:+.1f}pt  IS_PF={is_pf:.3f} OOS_PF={oos_pf:.3f}")


if __name__ == "__main__":
    run()
