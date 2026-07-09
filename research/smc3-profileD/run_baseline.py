"""
SMC3 baseline run — full 5y NQ 1m, default Config.  Prints the funnel, the
closed-trade table, per-year + IS/OOS, sample trades, the no-lookahead
assertion result, and writes BASELINE.md.  No optimization — baseline only.
"""
from __future__ import annotations
import time
import numpy as np
import pandas as pd
from smc3_engine import (Config, run_backtest, per_year, window_stats,
                         COMMISSION_PER_SIDE, SLIPPAGE_TICKS, POINT_VALUE, TICK)

DATA = "/Users/jacksonclarke/trading-team/data/real_futures/NQ_databento_1m_5y.parquet"
OUT = "/Users/jacksonclarke/trading-team/backtests/zeus-occ-optimize/smc3/BASELINE.md"


def fmt_pf(pf):
    return "inf" if pf == np.inf else f"{pf:.3f}"


def main():
    df = pd.read_parquet(DATA)
    cfg = Config()
    t = time.time()
    r = run_backtest(df, cfg)
    elapsed = time.time() - t
    m = r.metrics
    py = per_year(r.trades)
    is_w = window_stats(r.trades, 2021, 2024)
    oos_w = window_stats(r.trades, 2025, 2026)

    # PF/WR lookahead flags
    flags = []
    if m.get("pf", 0) not in (np.inf,) and m.get("pf", 0) > 2.5:
        flags.append(f"OVERALL PF {m['pf']:.2f} > 2.5")
    if m.get("win_pct", 0) > 70:
        flags.append(f"OVERALL WR {m['win_pct']:.1f}% > 70%")
    for y, s in py.items():
        if s["pf"] not in (np.inf,) and isinstance(s["pf"], float) and s["pf"] > 2.5:
            flags.append(f"{y} PF {s['pf']:.2f} > 2.5")
        if s["wr"] > 70:
            flags.append(f"{y} WR {s['wr']:.1f}% > 70%")

    L = []
    P = L.append
    P("# SMC3 Baseline — HTF Sweep -> 5M Confirm -> 1M Entry (NQ 1m, 5y)\n")
    P(f"Data: `{DATA}`")
    P(f"Span: {df.index.min()} -> {df.index.max()}  ({len(df):,} 1m bars)")
    P(f"Run time: {elapsed:.1f}s   |   engine: `smc3_engine.py`  (default Config)\n")

    P("## No-lookahead assertion")
    P(f"- Global stepped-source check (all 60m/5m values close <= 1m open): "
      f"**{'PASS' if r.lookahead_ok else 'FAIL'}**")
    if len(r.trades):
        P(f"- Per-fired-trade source-bar check (60m & 5m source close <= trigger "
          f"open): **{'PASS' if bool(r.trades['lookahead_ok'].all()) else 'FAIL'}** "
          f"({int(r.trades['lookahead_ok'].sum())}/{len(r.trades)} trades)")
    P(f"- 1m pivots use left=right={cfg.triggerPivotLen} (confirmed {cfg.triggerPivotLen} "
      f"bars late); 5m {cfg.confirmPivotLen}/{cfg.confirmPivotLen}; 60m "
      f"{cfg.htfPivotLen}/{cfg.htfPivotLen}. Entry = trigger-bar CLOSE.\n")

    P("## Funnel (cross-check vs Pine stats table)")
    f = r.funnel
    P("| stage | count |")
    P("|---|---|")
    P(f"| HTF sweeps (60m sweep+reclaim events) | {f['htf_sweeps']:,} |")
    P(f"| 5m confirms (latch transitions) | {f['confirms_5m']:,} |")
    P(f"| 1m triggers (trigger-true bars) | {f['triggers_1m']:,} |")
    P(f"| valid trades (fired, risk OK) | {f['valid_trades']:,} |")
    P(f"| risk rejects (fired, risk invalid) | {f['risk_rejects']:,} |")
    P(f"| open at data end (excluded from stats) | {f['open_at_end']} |")
    P("")
    P("_Funnel definitions: sweeps = 1m bars where longSweep|shortSweep set/refresh "
      "context; confirms = 5m-latch false->true transitions; triggers = 1m bars where "
      "(longTrigger|shortTrigger) true (includes bars while a position is open / before "
      "flat); valid+rejects counted only on flat, in-session trigger attempts._\n")

    P("## Closed-trade stats (full 5y)")
    P("| metric | value |")
    P("|---|---|")
    P(f"| n (closed) | {m['n']} |")
    P(f"| win % | {m['win_pct']:.2f}% |")
    P(f"| PF | {fmt_pf(m['pf'])} |")
    P(f"| net $ | {m['net_dollars']:,.0f} |")
    P(f"| avg $/trade | {m['avg_dollars']:,.1f} |")
    P(f"| avg winner | {m['avg_win']:,.1f} |")
    P(f"| avg loser | {m['avg_loss']:,.1f} |")
    P(f"| total R | {m['total_R']:.1f} |")
    P(f"| avg R | {m['avg_R']:.3f} |")
    P(f"| maxDD $ | {m['maxdd_dollars']:,.0f} |")
    P(f"| median hold (min) | {m['median_hold_min']:.0f} |")
    P("")
    P(f"_Costs: commission ${COMMISSION_PER_SIDE:.2f}/side (${COMMISSION_PER_SIDE*2:.2f} "
      f"round-trip) + {SLIPPAGE_TICKS:.0f} tick ({SLIPPAGE_TICKS*TICK:.2f}pt) adverse "
      f"slippage entry & exit.  NQ point=${POINT_VALUE:.0f}._\n")

    P("## Per calendar year")
    P("| year | n | WR% | PF | net$ |")
    P("|---|---|---|---|---|")
    for y, s in py.items():
        P(f"| {y} | {s['n']} | {s['wr']:.1f} | {fmt_pf(s['pf'])} | {s['net']:,.0f} |")
    P("")

    P("## IS (2021-2024) vs OOS (2025-2026 H1)")
    P("| window | n | WR% | PF | net$ | totalR | maxDD$ |")
    P("|---|---|---|---|---|---|---|")
    for name, w in (("IS 2021-24", is_w), ("OOS 2025-26H1", oos_w)):
        if w.get("n", 0):
            P(f"| {name} | {w['n']} | {w['win_pct']:.1f} | {fmt_pf(w['pf'])} | "
              f"{w['net_dollars']:,.0f} | {w['total_R']:.1f} | {w['maxdd_dollars']:,.0f} |")
        else:
            P(f"| {name} | 0 | - | - | - | - | - |")
    P("")

    P("## Sample trades (faithfulness eyeball)")
    P("| entry_time (UTC) | dir | entry | stop | target | exit | R | reason | hold_min |")
    P("|---|---|---|---|---|---|---|---|---|")
    if len(r.trades):
        idxs = list(range(min(5, len(r.trades))))
        for k in idxs:
            tr = r.trades.iloc[k]
            P(f"| {tr['entry_time']:%Y-%m-%d %H:%M} | {tr['dir']} | {tr['entry']:.2f} | "
              f"{tr['stop']:.2f} | {tr['target']:.2f} | {tr['exit']:.2f} | {tr['R']:.2f} | "
              f"{tr['reason']} | {tr['hold_min']:.0f} |")
    P("")

    P("## Faithfulness notes")
    P("- **Multi-TF stepping (no lookahead):** 60m/5m values read via searchsorted "
      "(side='right') on the closed-HTF-bar close-time array vs the 1m OPEN time — "
      "mirrors request.security(lookahead_off). A 60m bar becomes readable only on "
      "the 1m bar opening at its close.")
    P("- **Pivot confirmation lag:** ta.pivothigh/low(L,R) confirmed R bars late "
      "(60m 3/3 = 3h, 5m/1m 2/2). 'Last confirmed pivot' = valuewhen carry-forward.")
    P("- **Entry = trigger-bar CLOSE** (process_orders_on_close=true). Exits simulated "
      "on 1m bars STARTING THE BAR AFTER entry; stop-first when one bar spans both.")
    P("- **Costs** applied to every fill: 1-tick adverse slippage on entry & exit + "
      "$2.50/side commission. Target hits land ~+1.93..1.99R, stops ~-1.0..-1.25R "
      "(tight-risk trades pay proportionally more cost) — visible in the samples.")
    P("- **One position at a time**; a valid fire consumes its context; invalid-risk "
      "triggers are counted (risk_rejects) but do NOT consume context (can retry).")
    P(f"- **R vs $ divergence:** total R = {m['total_R']:.1f} (NEGATIVE) while net $ = "
      f"{m['net_dollars']:,.0f} (positive). Fixed 1-contract sizing lets a few "
      "wide-stop winners dominate raw dollars, but on a risk-normalized (1R-per-trade) "
      "basis expectancy is slightly negative (avg R "
      f"{m['avg_R']:+.3f}/trade). Honest read: no robust edge, essentially a coin-flip "
      "around the 2R/1R breakeven.")
    P("- **1 trade still open** at data end, excluded from closed-trade stats.\n")

    P("## Lookahead / plausibility flags")
    if flags:
        for fl in flags:
            P(f"- FLAG: {fl}")
    else:
        P("- None. No config window shows PF>2.5 or WR>70%.")
    wr = m["win_pct"]
    P(f"- 2R/1R structure => breakeven WR ~= 33.3%. Observed WR = {wr:.1f}% "
      f"({'below' if wr < 33.3 else 'above'} breakeven), consistent with PF "
      f"{fmt_pf(m['pf'])}.\n")

    txt = "\n".join(L)
    with open(OUT, "w") as fh:
        fh.write(txt + "\n")

    # ---- console echo ----
    print(txt)
    print("\n[written]", OUT)


if __name__ == "__main__":
    main()
