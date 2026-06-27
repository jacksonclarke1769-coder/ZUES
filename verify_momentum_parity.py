"""
Standalone PARITY check: ProfileMomentumEngine.compute() == the refined backtest signal, on real data.
Proves the live engine's signal math reproduces the validated backtest (z.build + 50d trend filter +
4-bar confirm + time gates slot 3..72) exactly. Run: python3 verify_momentum_parity.py  (needs the backtests repo).
Result on 2026-06-26: 0 mismatches / 94,344 post-warmup bars -> EXACT.
"""
import sys, numpy as np, pandas as pd

sys.path.insert(0, "/Users/jacksonclarke/trading-team/backtests")
sys.path.insert(0, "/Users/jacksonclarke/trading-team/backtests/ict-nq-framework")
import run_d1c_real as RD
import nq_zarattini_5m as z
from nq_momentum_trend_run import add_trend_filter
from profile_momentum_engine import ProfileMomentumEngine as PME


def main():
    d1 = RD.load_1m()
    g = lambda c, h: getattr(d1[c].resample("5min", label="left", closed="left"), h)()
    df = pd.DataFrame({"Open": g("open", "first"), "High": g("high", "max"), "Low": g("low", "min"),
                       "Close": g("close", "last"), "Volume": g("volume", "sum")}).dropna(subset=["Open"])
    mins = df.index.hour*60 + df.index.minute
    df = df[(mins >= 570) & (mins < 960)].copy()
    df["date"] = df.index.normalize().tz_localize(None)
    df["slot"] = ((df.index.hour*60 + df.index.minute) - 570) // 5
    df = df.reset_index(drop=True)

    bd = add_trend_filter(z.build(df.copy(), k=1.0, use_vwap=False), 50)
    s = bd.sig.values; gg = bd.groupby("date").ngroup().values
    conf = np.zeros(len(s))
    for i in range(len(s)):
        if s[i] != 0 and i >= 3 and all(gg[i-j] == gg[i] and s[i-j] == s[i] for j in range(4)):
            conf[i] = s[i]                                   # 4-bar confirm (edge upgrade 2026-06-27)
    slot = bd.slot.values
    backtest = np.where((slot >= 3) & (slot <= 72), conf, 0.0)   # last-entry ~15:30 (slot<=72)

    eng = PME.compute(df)
    days = np.unique(df.date.values)
    mask = np.arange(len(df)) >= (df.date.values < days[60]).sum()    # post warmup
    mm = int((backtest[mask] != eng[mask]).sum())
    print(f"bars compared (post-warmup): {mask.sum()}")
    print(f"mismatches: {mm}  ->  {'EXACT PARITY' if mm == 0 else f'{100*(1-mm/mask.sum()):.3f}% match'}")
    print("signal mix:", dict(zip(*np.unique(eng[mask], return_counts=True))))


if __name__ == "__main__":
    main()
