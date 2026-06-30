"""RETEST-LIMIT vs MARKET-FILL — Profile B (ORB) entry model, real Databento.
Retest (current/validated): on a close beyond the OR level, wait <=6 bars for price to RETEST the level;
  fill at the level, else NO TRADE (the 2026-06-30 miss). Better entry, fewer trades.
Market (chase): on the breakout close, fill at the NEXT bar OPEN every time. Worse entry, more trades.
Same 1-ATR stop / 1.5-ATR target exit in both. Compares B's own stats AND the deployed A10/B5/mm6 eval
pass-rate (B-fill swapped only; A retest + momentum held constant). Full 5y + last 12mo."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod as EOD
import apex_eval_eod_databento as DB
import funded_rules as FR

SPEC = FR.APEX_ACCOUNTS["50K"]
DPP, BCOST = H.DPP, H.B_COST


def b_events_fill(df5, mode):
    """mode='retest' (=H.b_events) or 'market' (fill next-bar-open on the breakout, always)."""
    df = df5.copy()
    et = df.index.tz_convert(H.NY); mins = et.hour * 60 + et.minute
    df["rth"] = (mins >= 570) & (mins < 960)
    df["day"] = et.normalize().tz_localize(None)
    pc = df.Close.shift(1)
    trng = pd.concat([df.High - df.Low, (df.High - pc).abs(), (df.Low - pc).abs()], axis=1).max(axis=1)
    df["atr"] = trng.rolling(14).mean()
    O, Hi, L, C = df.Open.values, df.High.values, df.Low.values, df.Close.values
    atrv = df["atr"].values; idx = df.index; n = len(C)
    ev = []; ntr = nwin = 0; sumR = 0.0
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
                if mode == "retest":
                    fill = None
                    for x in range(gi + 1, min(gi + 7, n)):
                        if L[x] <= lvl <= Hi[x]:
                            fill = x; break
                    if fill is None:
                        break
                    entry = lvl
                else:                                     # market: fill next-bar OPEN, always
                    if gi + 1 >= n:
                        break
                    fill = gi + 1; entry = O[fill]
                stop = entry - d * 1.0 * atr0; tgt = entry + d * 1.5 * atr0
                risk = abs(entry - stop) or 1e-9
                ex = None; mfe = 0.0; mae = 0.0
                for x in range(fill, min(fill + 24, n)):
                    mfe = max(mfe, (Hi[x] - entry) * d if d > 0 else (entry - L[x]) * d)
                    mae = min(mae, (L[x] - entry) * d if d > 0 else (entry - Hi[x]) * d)
                    if d > 0:
                        if L[x] <= stop: ex = stop; break
                        if Hi[x] >= tgt: ex = tgt; break
                    else:
                        if Hi[x] >= stop: ex = stop; break
                        if L[x] <= tgt: ex = tgt; break
                    if not df["rth"].values[x] and x > fill: ex = C[x]; break
                if ex is None:
                    ex = C[min(fill + 24, n) - 1]
                gross = (ex - entry) * d
                R = gross / risk
                ntr += 1; sumR += R; nwin += (R > 0)
                ev.append(dict(ts=idx[fill], src="B", pnl=(gross - BCOST) * DPP * H.B_SIZE,
                               mfe=max(0.0, mfe) * DPP * H.B_SIZE, mae=min(0.0, mae) * DPP * H.B_SIZE))
                break
    return ev, dict(trades=ntr, wr=100 * nwin / max(1, ntr), totR=sumR)


def eval_pass(ev, lo=None):
    if lo is not None:
        ev = [e for e in ev if pd.Timestamp(e["ts"]) >= lo]
    ev = H.apply_daily_stop(ev)
    st = EOD.day_starts(ev)
    p, b, x, m = EOD.summarize([EOD.eval_eod(ev, s, SPEC) for s in st])
    return p, len(st)


def main():
    print("loading real Databento…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    A = H.a_events(df5); Mm = H.m_events(df5)
    sc = {"A": 10, "B": 5, "M": 6}
    scl = lambda e: dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*sc[e["src"]],
                         mfe=e["mfe"]*sc[e["src"]], mae=e["mae"]*sc[e["src"]])
    end = df5.index.max(); yr1 = end - pd.Timedelta(days=365)
    print(f"\n  {'B fill mode':>14} | {'B trades':>8} {'B win%':>7} {'B totR':>7} | {'eval pass% (5y)':>15} {'eval pass% (12mo)':>17}")
    print("  " + "-" * 78)
    for mode in ("retest", "market"):
        bev, bs = b_events_fill(df5, mode)
        ev = [scl(e) for e in (A + bev + Mm)]
        p5, n5 = eval_pass(ev)
        p1, n1 = eval_pass(ev, lo=yr1)
        print(f"  {mode:>14} | {bs['trades']:>8} {bs['wr']:>6.1f}% {bs['totR']:>7.0f} | "
              f"{p5:>14.1f}% {p1:>16.1f}%")
    print("\n  [retest = current/validated · market = chase next-bar-open every signal]")
    print("  Memory's prior verdict: chasing the break = -30R net-neg. This re-tests it head-to-head.")


if __name__ == "__main__":
    main()
