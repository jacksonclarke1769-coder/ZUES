"""WHY is Thursday the best day? Mechanism dive, real Databento ~5y.
For a breakout strategy the edge comes from DIRECTIONAL follow-through. Measures per weekday:
  MARKET character (NY-AM 09:30-11:30 ET): session range (pts), trend efficiency (|net move|/path),
    realized vol; and TRADE follow-through: avg MFE / MAE (pts) + MFE:MAE ratio from the real A+B events.
Thursday = weekly Initial Jobless Claims 08:30 ET (the recurring macro catalyst) — we test if Thu shows
bigger/cleaner directional moves consistent with that."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB
NY = "America/New_York"; DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]
DPP = H.DPP


def main():
    print("loading real Databento…", flush=True)
    df5 = DB.load_databento_5m()
    et = df5.index.tz_convert(NY); mins = et.hour * 60 + et.minute
    nyam = df5[(mins >= 570) & (mins < 690)].copy()          # 09:30–11:30 ET (the entry window)
    nyam["day"] = nyam.index.tz_convert(NY).normalize()
    nyam["dow"] = nyam.index.tz_convert(NY).dayofweek

    # ---- MARKET character per trading day, then averaged by weekday ----
    rows = {i: {"rng": [], "eff": [], "n": 0} for i in range(5)}
    for day, g in nyam.groupby("day"):
        w = int(g["dow"].iloc[0])
        if w >= 5 or len(g) < 5:
            continue
        rng = g.High.max() - g.Low.min()
        net = abs(g.Close.iloc[-1] - g.Open.iloc[0])
        path = float((g.High - g.Low).sum()) or 1e-9
        rows[w]["rng"].append(rng); rows[w]["eff"].append(net / path); rows[w]["n"] += 1

    print(f"\n  window {df5.index.min().date()} -> {df5.index.max().date()}")
    print("\n========  MARKET CHARACTER by weekday (NY-AM 09:30-11:30 ET)  ========")
    print(f"  {'day':>5} {'days':>5} {'avg range(pt)':>14} {'trend eff.':>11}")
    for i in range(5):
        r = rows[i]
        print(f"  {DOW[i]:>5} {r['n']:>5} {np.mean(r['rng']):>14.1f} {np.mean(r['eff']):>11.3f}")
    print("  [range = session high-low · trend eff = |net move| / sum(bar ranges); higher = trendier/cleaner]")

    # ---- TRADE follow-through per weekday (real A+B events; mfe/mae in $ at size 1 -> pts) ----
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    ev = H.a_events(df5) + H.b_events(df5)
    tr = {i: {"mfe": [], "mae": [], "n": 0} for i in range(5)}
    for e in ev:
        w = pd.Timestamp(e["ts"]).tz_convert(NY).dayofweek
        if w >= 5:
            continue
        tr[w]["mfe"].append(e["mfe"] / DPP); tr[w]["mae"].append(-e["mae"] / DPP); tr[w]["n"] += 1
    print("\n========  TRADE FOLLOW-THROUGH by weekday (A+B, points)  ========")
    print(f"  {'day':>5} {'trades':>7} {'avg MFE':>8} {'avg MAE':>8} {'MFE:MAE':>8}")
    for i in range(5):
        t = tr[i]; mfe = np.mean(t["mfe"]); mae = np.mean(t["mae"]) or 1e-9
        print(f"  {DOW[i]:>5} {t['n']:>7} {mfe:>8.1f} {mae:>8.1f} {mfe/mae:>8.2f}")
    print("  [MFE = how far price runs your way after fill · MAE = worst adverse · ratio>1 = clean follow-through]")
    print("\n  Thu = weekly Initial Jobless Claims 08:30 ET → a recurring directional catalyst into the 09:30 open.")


if __name__ == "__main__":
    main()
