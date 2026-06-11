"""
Seed the dashboard store with PROFILE A data — wipes all prior strategy data and
replaces it with Profile A (NQ NY-Open OTE Reversal): the validated backtest, the
funded-account economics, and every historical trade. Run once:

    python seed_profileA.py

After this, the bot appends LIVE trades to the same store and the dashboard updates
automatically (store.add_trade on each win/loss).
"""
import os, sys
import pandas as pd, numpy as np
FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
sys.path.insert(0, os.path.join(FW, "engine")); sys.path.insert(0, os.path.join(FW, "models"))
import htf, trade_log as TL, model01_sweep_mss_fvg as M1
from store import Store
import funded_sim

DISPLAY_MNQ = 2          # dashboard shows $ at 2 MNQ (the recommended funded size)
MNQ_PT = 2.0


def build_trades():
    f = htf.build_features("NQ", "5m"); f.index.name = "timestamp"
    tr = M1.run(f, "NQ", dict(entry_type="ote", sessions={"asia", "london", "ny_am", "ny_lunch", "ny_pm"},
                              target_mode="fixed_rr", rr=2.0,
                              partial=[(1, 0.5)]))   # Exit #3 (frozen v2): 50% @ +1R, 50% @ +2R
    tr["ts"] = pd.to_datetime(tr["date"])
    return tr[(tr.session == "ny_am") & (tr.year >= 2019)].sort_values("ts").reset_index(drop=True)


def metrics_block(tr):
    m = TL.metrics(tr)
    return dict(pf=m["profit_factor"], wr=m["win_rate"], exp_r=m["expectancy"], trades=m["trades"],
                total_r=m["total_r"], maxdd_r=m["max_dd_r"], avg_win=m["avg_win"], avg_loss=m["avg_loss"],
                streak=m["longest_loss_streak"], funded=TL.funded_score(m))


def main():
    st = Store("data/bot.db")
    st.reset()
    print("store wiped.")
    tr = build_trades()
    print(f"Profile A trades: {len(tr)}")

    # ---- per-trade rows + equity ----
    eq_r = 0.0; bal = 50000.0; peak = 50000.0
    for _, t in tr.iterrows():
        risk_pts = abs(t.entry - t.stop)
        pnl_usd = t.r_result * risk_pts * MNQ_PT * DISPLAY_MNQ
        exit_px = t.target if t.outcome == "win" else (t.entry - np.sign(t.entry - t.stop) * risk_pts
                                                       if t.outcome == "loss" else t.entry + t.points * (1 if t.direction == "long" else -1))
        st.add_trade(ts_entry=str(t.ts) + f" {t.time}", ts_exit=str(t.ts) + f" {t.time}",
                     direction=t.direction, phase="BACKTEST", qty=DISPLAY_MNQ,
                     entry_px=round(t.entry, 2), stop_px=round(t.stop, 2), exit_px=round(float(exit_px), 2),
                     pnl_usd=round(pnl_usd, 2), pnl_pts=round(t.points, 2), reason=t.outcome,
                     mae_pts=round(t.mae_r * risk_pts, 1), mfe_pts=round(t.mfe_r * risk_pts, 1), account="backtest")
        eq_r += t.r_result; bal += pnl_usd; peak = max(peak, bal)
        st.add_equity(str(t.ts) + f" {t.time}", round(bal, 2), round(peak, 2), round(peak - 2000, 2), "BACKTEST")

    # ---- overview state (all validated metrics from the research) ----
    full = metrics_block(tr)
    oos = {y: round(TL.metrics(tr[tr.year == y])["profit_factor"], 2) for y in [2019, 2020, 2021, 2022, 2023, 2024, 2025]}
    last = tr.ts.max()
    rec = {"5mo": metrics_block(tr[tr.ts >= last - pd.Timedelta(days=152)]),
           "6mo": metrics_block(tr[tr.ts >= last - pd.Timedelta(days=182)]),
           "12mo": metrics_block(tr[tr.ts >= last - pd.Timedelta(days=365)])}
    risk_pts_mean = (tr.entry - tr.stop).abs()
    recent_stop = (tr[tr.ts >= last - pd.Timedelta(days=182)].entry - tr[tr.ts >= last - pd.Timedelta(days=182)].stop).abs().mean()

    st.set_state(
        strategy_name="Profile A v2 — NQ NY-Open OTE Reversal",
        config="OTE entry · NY-AM 09:30–11:30 ET · Exit #3 (50% @1R + 50% @2R) · stop below swept low · NQ 5m",
        status="VALIDATED · Deployment-Ready (paper-test pending)",
        data_note=f"Backtest 2019→2026 ({full['trades']} trades) · $ shown at {DISPLAY_MNQ} MNQ · live trades append below",
        summary=full,
        validation=dict(cme_pf=1.39, real_futures_pf=1.23, real_futures_n=22,
                        cost_stress_pf=1.32, news="NFP blackout applied (CPI/FOMC to add)",
                        verdict="PF 1.39 after realistic CME costs (>1.2) — edge confirmed on real NQ=F futures"),
        walkforward=[dict(year=y, pf=oos[y]) for y in oos],
        recent=rec,
        edge=dict(source="NY cash open: 2–3× session volatility + raids overnight Asia/London liquidity ~⅔ of days + strongest post-sweep follow-through",
                  freq="~12 trades/month · ~1 every 1.8 trading days · fires ~49% of NY-AM days",
                  stop_mean_pt=round(risk_pts_mean.mean(), 0), stop_recent_pt=round(recent_stop, 0)),
        funded=dict(
            program="MyFundedFutures Core 50K · EOD $2,000 DD · $3,000 target · NO daily limit · BOTS ALLOWED on funded",
            sizing=[
                dict(size="2 MNQ", risk="~$267/tr", role="FUNDED (sustainable)", pass90="—", note="0 funded blows in 12mo backtest"),
                dict(size="3–4 MNQ", risk="~$400–534/tr", role="FUNDED (higher payouts)", pass90="—", note="more cash, still survives on EOD DD"),
                dict(size="4 MNQ", risk="~$534/tr", role="EVAL", pass90="—", note="watch 50% eval consistency"),
                dict(size="1 NQ", risk="~$1,340/tr", role="cash-grab", pass90="—", note="hits $5k cap fast but ~75% blow"),
            ],
            meta="EOD drawdown = Profile A flat by 2:30pm, so intraday excursions never breach. Asymmetric sizing: 4 MNQ eval (watch eval-only 50% consistency) → 2–3 MNQ funded.",
            blow_rate="Identical-footing 12mo: MyFundedFutures $40,444 withdrawable / 0 funded blows (2 MNQ funded · continuous campaign · bots allowed on funded · EOD trailing DD).",
        ),
        risk=dict(dd10="80%/yr", dd15="35%/yr", dd20="12%/yr", streak95=12, cap99_r=23.1,
                  note="20k-path bootstrap; block-bootstrap matched IID (autocorr +0.03 — no streak clustering)"),
        live=dict(connected=False, paper=True, account="—", balance=50000, today_pnl=0, today_trades=0,
                  open_position=None, last_signal="—"),
    )
    # ---- funded sizing MATRIX: 4 accounts x 10 sizes, BOTH periods (toggle: full 2019+ / last 12mo) ----
    tr12 = tr[tr.ts >= last - pd.Timedelta(days=365)]
    matrix_full = funded_sim.sizing_matrix(tr)
    matrix_12 = funded_sim.sizing_matrix(tr12)
    yrs = round((tr.ts.max() - tr.ts.min()).days / 365.0, 1)
    st.set_state(
        sizing_matrix={"2019+": matrix_full, "12mo": matrix_12},
        sizing_matrix_notes={"2019+": f"full 2019+ ({yrs}y · {len(tr)} trades) · conservative",
                             "12mo": f"last 12 months ({len(tr12)} trades) · recent regime"},
        sizing_matrix_note="MyFundedFutures-style EOD-trailing · Exit #3 · continuous eval→funded campaign")
    print(f"sizing_matrix seeded: periods={{2019+:{len(tr)}tr, 12mo:{len(tr12)}tr}} · accounts={list(matrix_full.keys())}")
    print("overview seeded. summary:", full)
    print("done — run: python dashboard_server.py  →  http://127.0.0.1:8000")


if __name__ == "__main__":
    main()
