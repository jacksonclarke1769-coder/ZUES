"""
SMC3 Stage-2 Task A — parameter robustness (coarse, R-based, anti-overfit).

Sweep ONE axis at a time around the default Config (all other params at default).
For each cell report: n, WR, total R, avg R/trade, PF($), IS avgR vs OOS avgR,
and the per-year avgR sign (how many of the 6 calendar years have positive avgR).

KEY OUTPUT: is there ANY cell with
    (a) positive total R in BOTH IS (2021-24) and OOS (2025-26H1), AND
    (b) positive avg R in >=5 of 6 years ?
If yes -> candidate edge region.  If no cell clears the bar -> stated plainly.

R is the headline everywhere.  R = net_dollars / (risk_pts * $20) per trade, so it
is already normalized to each trade's own initial risk and is comparable across
rrTarget / stopMode cells.  Dollars/PF($) are secondary notes.
"""
from __future__ import annotations
import time
import numpy as np
import pandas as pd
from dataclasses import replace

from smc3_engine import Config, run_backtest, compute_metrics

DATA = "/Users/jacksonclarke/trading-team/data/real_futures/NQ_databento_1m_5y.parquet"
OUT = "/Users/jacksonclarke/trading-team/backtests/zeus-occ-optimize/smc3/STAGE2.md"

IS_YEARS = (2021, 2022, 2023, 2024)
OOS_YEARS = (2025, 2026)
ALL_YEARS = (2021, 2022, 2023, 2024, 2025, 2026)


def _fmt_pf(pf):
    if pf is None:
        return "-"
    return "inf" if pf == np.inf else f"{pf:.3f}"


def window_R(tdf: pd.DataFrame, years) -> dict:
    """total/avg R + n + WR + PF($) restricted to a set of calendar (exit) years."""
    if tdf is None or len(tdf) == 0:
        return {"n": 0, "totR": 0.0, "avgR": np.nan, "wr": np.nan, "pf": None}
    yrs = tdf["exit_time"].dt.year
    sub = tdf[yrs.isin(years)]
    if len(sub) == 0:
        return {"n": 0, "totR": 0.0, "avgR": np.nan, "wr": np.nan, "pf": None}
    R = sub["R"].to_numpy()
    d = sub["net_dollars"].to_numpy()
    gp = d[d > 0].sum(); gl = -d[d < 0].sum()
    pf = gp / gl if gl > 0 else (np.inf if gp > 0 else np.nan)
    return {
        "n": int(len(sub)),
        "totR": float(R.sum()),
        "avgR": float(R.mean()),
        "wr": float((d > 0).mean() * 100),
        "pf": float(pf) if pf not in (np.inf,) and not (isinstance(pf, float) and np.isnan(pf)) else pf,
    }


def per_year_avgR(tdf: pd.DataFrame) -> dict:
    """{year: avgR} over calendar exit years present."""
    out = {}
    if tdf is None or len(tdf) == 0:
        return out
    yrs = tdf["exit_time"].dt.year
    for y in ALL_YEARS:
        sub = tdf[yrs == y]
        if len(sub):
            out[y] = float(sub["R"].mean())
    return out


def cell_report(tag: str, cfg: Config, df: pd.DataFrame) -> dict:
    r = run_backtest(df, cfg)
    tdf = r.trades
    m = r.metrics
    isw = window_R(tdf, IS_YEARS)
    oosw = window_R(tdf, OOS_YEARS)
    pyr = per_year_avgR(tdf)
    pos_years = sum(1 for y in ALL_YEARS if pyr.get(y, -1) > 0)
    n_years = sum(1 for y in ALL_YEARS if y in pyr)
    clears = (isw["totR"] > 0) and (oosw["totR"] > 0) and (pos_years >= 5)
    return {
        "tag": tag,
        "n": m.get("n", 0),
        "wr": m.get("win_pct", np.nan),
        "totR": m.get("total_R", np.nan),
        "avgR": m.get("avg_R", np.nan),
        "pf": m.get("pf", np.nan),
        "is_totR": isw["totR"], "is_avgR": isw["avgR"], "is_n": isw["n"],
        "oos_totR": oosw["totR"], "oos_avgR": oosw["avgR"], "oos_n": oosw["n"],
        "pyr": pyr, "pos_years": pos_years, "n_years": n_years,
        "clears": clears, "la_ok": r.lookahead_ok,
    }


def build_axes():
    base = Config()
    axes = {}

    # --- stopMode ---
    axes["stopMode"] = [
        (f"stopMode={sm}", replace(base, stopMode=sm))
        for sm in ("Recent Swing", "Sweep Extreme", "Wider Of Both")
    ]
    # --- rrTarget ---
    axes["rrTarget"] = [
        (f"rrTarget={rr}", replace(base, rrTarget=rr))
        for rr in (1.0, 1.5, 2.0, 2.5, 3.0)
    ]
    # --- maxStopPoints ---
    axes["maxStopPoints"] = [
        (f"maxStopPoints={ms:.0f}", replace(base, maxStopPoints=float(ms)))
        for ms in (40, 60, 90, 120, 150)
    ]
    # --- 5m confirm ---
    axes["5m_confirm"] = [
        ("5mConfirm=BOS only", replace(base, useBosConfirm=True, useFvgConfirm=False)),
        ("5mConfirm=FVG only", replace(base, useBosConfirm=False, useFvgConfirm=True)),
        ("5mConfirm=both", replace(base, useBosConfirm=True, useFvgConfirm=True)),
    ]
    # --- 1m trigger ---
    axes["1m_trigger"] = [
        ("1mTrigger=BOS only", replace(base, useBosTrigger=True, useFvgTrigger=False)),
        ("1mTrigger=FVG only", replace(base, useBosTrigger=False, useFvgTrigger=True)),
        ("1mTrigger=both", replace(base, useBosTrigger=True, useFvgTrigger=True)),
    ]
    # --- maxSetupBars (contextExpiryBars) ---
    axes["maxSetupBars"] = [
        (f"maxSetupBars={mb}", replace(base, contextExpiryBars=mb))
        for mb in (60, 120, 180, 300)
    ]
    # --- session ---
    axes["session"] = [
        ("session=all 0000-2359", replace(base, useSession=False)),
        ("session=RTH 0930-1600ET", replace(base, useSession=True, sessStart="09:30", sessEnd="16:00")),
        ("session=NY-AM 0930-1200ET", replace(base, useSession=True, sessStart="09:30", sessEnd="12:00")),
    ]
    return axes


def render_axis(name, cells, L):
    P = L.append
    P(f"### Axis: {name}\n")
    P("| cell | n | WR% | totalR | avgR | PF($) | IS n | IS totR | IS avgR | OOS n | OOS totR | OOS avgR | +yrs/tot | clears? |")
    P("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in cells:
        P(f"| {c['tag']} | {c['n']} | {c['wr']:.1f} | {c['totR']:+.1f} | {c['avgR']:+.4f} | "
          f"{_fmt_pf(c['pf'])} | {c['is_n']} | {c['is_totR']:+.1f} | "
          f"{c['is_avgR']:+.4f} | {c['oos_n']} | {c['oos_totR']:+.1f} | {c['oos_avgR']:+.4f} | "
          f"{c['pos_years']}/{c['n_years']} | {'YES' if c['clears'] else 'no'} |")
    P("")
    # per-year avgR detail
    P("| cell | " + " | ".join(str(y) for y in ALL_YEARS) + " |")
    P("|---|" + "|".join(["---"] * len(ALL_YEARS)) + "|")
    for c in cells:
        row = []
        for y in ALL_YEARS:
            v = c["pyr"].get(y)
            row.append("-" if v is None else f"{v:+.3f}")
        P(f"| {c['tag']} | " + " | ".join(row) + " |")
    P("")


def main():
    df = pd.read_parquet(DATA)
    axes = build_axes()

    L = []
    P = L.append
    P("# SMC3 Stage 2 — Parameter Robustness + Trade Classification\n")
    P("Question: does a real, risk-normalized edge hide in any parameter config or "
      "market-context sub-region, or is SMC3 structurally breakeven?  **R (net$/(risk_pts*$20)) "
      "is the headline; $/PF($) are secondary.**  IS = 2021-24, OOS = 2025-26H1.\n")
    P(f"Data: `{DATA}`  ({len(df):,} 1m bars, {df.index.min():%Y-%m-%d} -> {df.index.max():%Y-%m-%d})\n")
    P("Baseline (default Config): 5056 trades, WR 34.4%, PF($) 1.036, **total R -52.9, "
      "avg R -0.0105**, OOS PF 0.995.\n")

    P("## Task A — parameter robustness (one axis at a time around the default)\n")
    P("Bar for a *candidate edge region*: positive **total R in BOTH IS and OOS** AND "
      "positive **avg R in >=5 of 6 calendar years**.  `clears?` column marks any cell "
      "that meets it.\n")

    all_cells = []
    t0 = time.time()
    for name, specs in axes.items():
        cells = []
        for tag, cfg in specs:
            c = cell_report(tag, cfg, df)
            cells.append(c)
            all_cells.append((name, c))
            print(f"[{time.time()-t0:5.0f}s] {tag:28s} n={c['n']:5d} avgR={c['avgR']:+.4f} "
                  f"IStotR={c['is_totR']:+7.1f} OOStotR={c['oos_totR']:+7.1f} "
                  f"+yrs={c['pos_years']}/{c['n_years']} clears={c['clears']} la={c['la_ok']}")
        render_axis(name, cells, L)

    # ---- summary: any clears? + best cells by OOS avgR ----
    P("## Task A summary\n")
    clearing = [c for _, c in all_cells if c["clears"]]
    if clearing:
        P(f"**{len(clearing)} cell(s) clear the bar** (positive total R in BOTH halves AND "
          ">=5/6 positive-avgR years):\n")
        for c in clearing:
            P(f"- `{c['tag']}` — IS totR {c['is_totR']:+.1f}, OOS totR {c['oos_totR']:+.1f}, "
              f"+yrs {c['pos_years']}/{c['n_years']}, avg R {c['avgR']:+.4f}")
        P("")
    else:
        P("**NO cell clears the bar.** No single-axis parameter configuration produces "
          "positive total R in both IS and OOS with >=5/6 positive-avgR years. "
          "SMC3 has no robust parameter config.\n")

    # best 8 by OOS avgR (n>=100 in OOS to be trustworthy)
    trust = [c for _, c in all_cells if c["oos_n"] >= 100]
    trust.sort(key=lambda c: c["oos_avgR"], reverse=True)
    P("Best cells by **OOS avg R** (OOS n >= 100):\n")
    P("| rank | cell | OOS n | OOS avgR | OOS totR | IS avgR | IS totR | +yrs/tot | clears? |")
    P("|---|---|---|---|---|---|---|---|---|")
    for i, c in enumerate(trust[:8], 1):
        P(f"| {i} | {c['tag']} | {c['oos_n']} | {c['oos_avgR']:+.4f} | {c['oos_totR']:+.1f} | "
          f"{c['is_avgR']:+.4f} | {c['is_totR']:+.1f} | {c['pos_years']}/{c['n_years']} | "
          f"{'YES' if c['clears'] else 'no'} |")
    P("")

    txt = "\n".join(L)
    with open(OUT, "w") as fh:
        fh.write(txt + "\n")
    print("\n[written]", OUT)
    print(f"\nCLEARS: {len(clearing)}   total cells: {len(all_cells)}   time {time.time()-t0:.0f}s")
    # return best for console
    print("\nTop-5 by OOS avgR (OOS n>=100):")
    for c in trust[:5]:
        print(f"  {c['tag']:28s} OOSavgR={c['oos_avgR']:+.4f} ISavgR={c['is_avgR']:+.4f} "
              f"OOStotR={c['oos_totR']:+.1f} IStotR={c['is_totR']:+.1f} +yrs={c['pos_years']}/{c['n_years']}")


if __name__ == "__main__":
    main()
