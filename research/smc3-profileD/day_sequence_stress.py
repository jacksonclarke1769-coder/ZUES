"""
Stress test the top rows (by ex-2024 avgR) from the day-sequence filter
battery: 2x/3x costs, flat -0.01/-0.02/-0.03R slippage, winner-fill
90%/85% degradation. Writes reports/ifvg_optimisation/09_day_sequence_stress.md
"""
from __future__ import annotations
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "..")
from engine import load_data                        # noqa: E402
from smc3_engine import run_backtest, Config         # noqa: E402
from day_sequence_filters import (load, replay, metrics, build_rules, N_BASE)

DATA = "/Users/jacksonclarke/trading-team/data/real_futures/NQ_databento_1m_5y.parquet"
OUT_MD = "/Users/jacksonclarke/trading-team/backtests/zeus-occ-optimize/smc3/reports/ifvg_optimisation/09_day_sequence_stress.md"

BASE_COST_DOLLARS = 15.0   # $5 RT commission + $10 (2 ticks @ $20/pt = 0.5pt) slippage
POINT_VALUE = 20.0

TOP_N = 5


def ex2024_avgR(sub: pd.DataFrame) -> float:
    if len(sub) == 0:
        return np.nan
    yr = sub["entry_time"].dt.tz_convert("UTC").dt.year
    m = sub.loc[yr != 2024, "R"]
    return m.mean() if len(m) else np.nan


def pf_r(sub: pd.DataFrame) -> float:
    gw = sub.loc[sub.R > 0, "R"].sum()
    gl = -sub.loc[sub.R < 0, "R"].sum()
    return gw / gl if gl > 0 else np.inf


def apply_cost_mult(sub: pd.DataFrame, risk: pd.DataFrame, mult: float) -> pd.DataFrame:
    s = sub.merge(risk[["entry_time", "risk_pts"]], on="entry_time", how="left")
    extra_dollars = (mult - 1) * BASE_COST_DOLLARS
    extra_R = extra_dollars / (s["risk_pts"] * POINT_VALUE)
    s["R"] = s["R"] - extra_R
    return s


def apply_flat_slip(sub: pd.DataFrame, flat: float) -> pd.DataFrame:
    s = sub.copy()
    s["R"] = s["R"] - flat
    return s


def apply_winner_fill(sub: pd.DataFrame, fill: float) -> pd.DataFrame:
    s = sub.copy()
    s["R"] = np.where(s["R"] > 0, s["R"] * fill, s["R"])
    return s


def main():
    full = load()
    df = load_data(DATA)
    eng_t = run_backtest(df, Config(useSession=True, sessStart="09:30", sessEnd="12:00")).trades
    eng_t = eng_t[eng_t.reason.isin(["target", "stop"])]
    risk = eng_t[["entry_time", "risk_pts"]]
    rules = dict(build_rules())

    res = pd.read_csv(
        "/Users/jacksonclarke/trading-team/backtests/zeus-occ-optimize/smc3/reports/ifvg_optimisation/09_day_sequence_filters.csv"
    )
    top = res.sort_values("ex2024", ascending=False).head(TOP_N)

    lines = []
    P = lines.append
    P("# 09 — Stress test: top rows by ex-2024 avgR\n")
    P("Method: cost stress recomputes R by subtracting `(cost_mult-1) x $15 "
      "(baseline $5 RT commission + $10 = 2-tick slippage) / (risk_pts x $20/pt)` "
      "from every trade's R (extra $ cost converted to R via the trade's own risk). "
      "Flat-slippage stress subtracts a fixed R amount from every trade. "
      "Winner-fill degradation multiplies ONLY winning trades' R by the fill "
      "factor (expected-value method — MFE not available in this ledger, so this "
      "approximates 'some winners get a worse fill / clipped early' rather than "
      "literally re-drawing a subset of winners).\n")
    P("| rule | scenario | n | avgR | ex2024_avgR | PF(R) | dies? |")
    P("|---|---|---|---|---|---|---|")

    for _, r in top.iterrows():
        name = r["rule"]
        rule_fn = rules[name]
        sub = replay(full, rule_fn)
        base_ex2024 = ex2024_avgR(sub)

        scenarios = {
            "baseline": sub,
            "2x costs": apply_cost_mult(sub, risk, 2.0),
            "3x costs": apply_cost_mult(sub, risk, 3.0),
            "-0.01R flat slip": apply_flat_slip(sub, 0.01),
            "-0.02R flat slip": apply_flat_slip(sub, 0.02),
            "-0.03R flat slip": apply_flat_slip(sub, 0.03),
            "90% winner fill": apply_winner_fill(sub, 0.90),
            "85% winner fill": apply_winner_fill(sub, 0.85),
        }
        for scen, s in scenarios.items():
            ex = ex2024_avgR(s)
            dies = "DIES" if (scen != "baseline" and pd.notna(ex) and ex <= 0) else (
                "-" if scen != "baseline" else "(ref)")
            P(f"| {name} | {scen} | {len(s)} | {s['R'].mean():+.4f} | "
              f"{ex:+.4f} | {pf_r(s):.3f} | {dies} |")

    with open(OUT_MD, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"[written] {OUT_MD}")
    print("\n".join(lines[:20]))


if __name__ == "__main__":
    main()
