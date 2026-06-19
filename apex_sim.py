"""APEX funded-rules SIM — does the frozen Profile A survive Apex's unrealized trailing drawdown?

SIM / RESEARCH ONLY. No live wiring, no orders. Dukascopy NQ CFD PROXY (label: proxy). Uses the
real frozen Profile A (model01) trade stream, fed through the Apex trailing-threshold model
(funded_rules.ApexAcct) for 50K / 100K / 150K. Rolling-start evals (start an eval at every signal)
so the result is robust to entry timing, not one lucky path.

Per-trade Apex risk uses model01's mfe_r/mae_r (favourable/adverse excursion) -> the give-back
breach is modelled. NOTE: this is a per-trade approximation (slightly OPTIMISTIC vs the true tick
path, which could breach on an intra-trade dip-below-floor that then recovers to a positive close).

  python3 apex_sim.py
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

import strategy_engine_profileA as E      # import FIRST: puts model01 on sys.path
import model01_sweep_mss_fvg as M1
import config
import paper_live
import funded_rules as FR

NY = "America/New_York"
DPP = 2.0            # MNQ $/point/contract
CONTRACTS = 3       # Profile A A3 baseline (Apex 50K/100K/150K allow 10/14/17 — scaling up scales risk)
WARMUP_DAYS = 1500  # ~4y proxy


def profile_a_trades():
    bars = list(paper_live.DukascopyLiveFeed(warmup_days=WARMUP_DAYS).history())
    eng = E.ProfileAEngine(config.STRAT)
    idx, data = [], []
    for ts, o, h, l, c in bars:
        t = pd.Timestamp(ts)
        t = t.tz_convert(NY) if t.tzinfo else t.tz_localize("UTC").tz_convert(NY)
        idx.append(t); data.append([o, h, l, c, 0])
    buf = pd.DataFrame(data, index=pd.DatetimeIndex(idx),
                       columns=["Open", "High", "Low", "Close", "Volume"])
    eng.buf = buf[~buf.index.duplicated(keep="last")].sort_index()
    feats = eng._features()
    tr = M1.run(feats, "NQ", {**E.PROFILE_A, "slip_ticks": 8})
    tr = tr[tr.session == "ny_am"].copy()
    tr["ts"] = pd.to_datetime(tr["date"].astype(str))
    tr = tr.sort_values("ts").reset_index(drop=True)
    rows = []
    for _, t in tr.iterrows():
        risk = abs(float(t["entry"]) - float(t["stop"]))
        if risk <= 0:
            continue
        usd = risk * DPP * CONTRACTS
        rows.append(dict(ts=t["ts"], day=pd.Timestamp(t["ts"]).normalize(),
                         pnl=float(t["r_result"]) * usd,
                         mfe=float(t["mfe_r"]) * usd,           # >= 0
                         mae=float(t["mae_r"]) * usd))          # <= 0
    return rows, (eng.buf.index.min(), eng.buf.index.max())


def eval_from(trades, start, spec):
    """Simulate one Apex eval starting at trade index `start`. Returns (outcome, n_trades, giveback)."""
    a = FR.ApexAcct(spec)
    for k in range(start, len(trades)):
        t = trades[k]
        pre_locked = a.locked
        a.apply_trade(t["pnl"], mfe=max(0.0, t["mfe"]), mae=min(0.0, t["mae"]))
        if a.passed:
            return "PASS", k - start + 1, False
        if a.breached:
            # give-back breach = the killing trade ran favourable but we still breached
            giveback = t["mfe"] > abs(t["pnl"]) and t["pnl"] <= 0
            return "BREACH", k - start + 1, giveback
    return "INCOMPLETE", len(trades) - start, False


def last_n_months(trades, asof, months=12, size="50K"):
    """How many Apex evals of `size` would have resolved in the trailing window:
      - sequential: start an eval, on PASS/BREACH immediately start the next (account throughput),
      - rolling: pass rate over every possible start (robust to entry timing).
    """
    asof = pd.Timestamp(asof)
    asof = asof.tz_localize(None) if asof.tzinfo else asof
    cut = asof - pd.DateOffset(months=months)
    w = [t for t in trades if pd.Timestamp(t["ts"]) >= cut]
    spec = FR.APEX_ACCOUNTS[size]
    i = 0; passes = breaches = 0; cycles = []
    while i < len(w):
        outcome, n, gb = eval_from(w, i, spec)
        if outcome == "INCOMPLETE":
            cycles.append(("INCOMPLETE", n, gb)); break
        passes += (outcome == "PASS"); breaches += (outcome == "BREACH")
        cycles.append((outcome, n, gb)); i += n
    starts = range(0, max(1, len(w) - 10))
    roll = [eval_from(w, s, spec) for s in starts]
    rn = len(roll)
    rp = sum(1 for o in roll if o[0] == "PASS")
    rb = sum(1 for o in roll if o[0] == "BREACH")
    return dict(size=size, window=(cut.date(), pd.Timestamp(asof).date()), n_trades=len(w),
                seq_pass=passes, seq_breach=breaches, cycles=cycles,
                roll_pass_pct=round(100 * rp / rn, 1), roll_breach_pct=round(100 * rb / rn, 1), roll_n=rn)


def run():
    print(f"generating Profile A trades (proxy, ~{WARMUP_DAYS}d, {CONTRACTS} MNQ)…", flush=True)
    trades, (t0, t1) = profile_a_trades()
    span = f"{t0.date()} -> {t1.date()}"
    print(f"  {len(trades)} Profile A NY-AM trades · {span}", flush=True)
    starts = range(0, max(1, len(trades) - 10))    # need room for an eval to resolve
    lines = []
    summary = []
    for size in ("50K", "100K", "150K"):
        spec = FR.APEX_ACCOUNTS[size]
        outcomes = [eval_from(trades, s, spec) for s in starts]
        n = len(outcomes)
        npass = sum(1 for o in outcomes if o[0] == "PASS")
        nbreach = sum(1 for o in outcomes if o[0] == "BREACH")
        ninc = sum(1 for o in outcomes if o[0] == "INCOMPLETE")
        gbreach = sum(1 for o in outcomes if o[0] == "BREACH" and o[2])
        pass_trades = [o[1] for o in outcomes if o[0] == "PASS"]
        med = int(np.median(pass_trades)) if pass_trades else None
        row = dict(size=size, start_points=n, pass_pct=round(100 * npass / n, 1),
                   breach_pct=round(100 * nbreach / n, 1), incomplete_pct=round(100 * ninc / n, 1),
                   giveback_breach_pct=round(100 * gbreach / max(1, nbreach), 1),
                   median_trades_to_pass=med, trailing=spec["trailing"], target=spec["target"])
        summary.append(row)
        print(f"  Apex {size}: PASS {row['pass_pct']}% · BREACH {row['breach_pct']}% "
              f"(give-back {row['giveback_breach_pct']}% of breaches) · "
              f"median {med} trades to pass · trailing ${spec['trailing']} target ${spec['target']}",
              flush=True)
    write_report(span, summary, len(trades))
    return summary


def write_report(span, summary, n_trades):
    os.makedirs("reports", exist_ok=True)
    R = ["# Apex Funded-Rules Sim — Profile A under Apex trailing drawdown\n",
         "**SIM / RESEARCH ONLY · Dukascopy NQ CFD PROXY · numbers VERIFY vs your Apex contract.**\n",
         f"- Trade stream: {n_trades} frozen Profile A NY-AM trades · {span} · {CONTRACTS} MNQ.\n",
         "- Method: rolling-start Apex evals (an eval started at every signal) through the unrealized "
         "trailing-threshold model (`funded_rules.ApexAcct`). Per-trade give-back via model01 mfe_r/mae_r.\n",
         "- Apex model: threshold trails the unrealized peak by `trailing`, locks at start+$100; "
         "no daily limit; 30% consistency for payout.\n\n",
         "| Apex size | Trailing | Target | Eval PASS % | BREACH % | give-back share of breaches | median trades→pass |\n",
         "|---|--:|--:|--:|--:|--:|--:|\n"]
    for r in summary:
        R.append(f"| {r['size']} | ${r['trailing']:,} | ${r['target']:,} | {r['pass_pct']}% | "
                 f"{r['breach_pct']}% | {r['giveback_breach_pct']}% | {r['median_trades_to_pass']} |\n")
    R.append("\n**Caveat:** per-trade approximation is slightly optimistic vs the true tick path "
             "(an intra-trade dip below the locked floor that recovers to a positive close would breach "
             "in reality but not here). At larger Apex contract sizes (10/14/17) breach risk scales up "
             "roughly with size. Proxy data — reproduce on CME before trusting. Apex = SEMI-AUTO ONLY "
             "(confirm-to-trade), so any live use runs the human-in-the-loop path, never auto-execute.\n")
    open("reports/apex-funded-sim.md", "w").write("".join(R))


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
