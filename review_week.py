"""WEEKLY STRATEGY-FIDELITY REVIEW — the gate for buying the next funded account.

Operator rule (2026-06-28): we buy a new Apex funded account each week *as long as the week's
trades reflected the strategy* — win or lose. This tool answers exactly that, by joining two
independent live records the bot already writes:

  1. trade_results.csv      -> every RESOLVED live trade (modeled P&L; `confirmed` once eye-checked)
  2. logs/live_engine_decisions/*.jsonl  -> EVERY engine decision (signal fired / blocked + reason)

FIDELITY = every live trade maps to a clean engine `signal`/`live_send` row (rule-based, not a
rogue/manual entry), and the blocks are legitimate gate reasons. P&L is irrelevant to the verdict.

Usage:
    python3 review_week.py --account APEX-50K-1                 # last 7 days
    python3 review_week.py --account APEX-50K-1 --since 2026-06-22 --until 2026-06-28
    python3 review_week.py --account APEX-50K-1 --json          # machine-readable (for the dashboard)
"""
import argparse, glob, json, os
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

import trade_results

DLOG_GLOB = "logs/live_engine_decisions/*.jsonl"
SIGNAL_ACTIONS = {"signal", "live_send"}          # a rule-based entry the engine decided to take
PAPER_ACTIONS = {"paper_signal"}                  # engine signalled but in paper mode (not live)


def _d(s):
    return datetime.fromisoformat(str(s)[:10]).date() if s else None


def load_decisions(since, until, account):
    """Return engine decisions in [since, until] for the account, split signals vs blocks."""
    signals, blocks = [], []
    for fp in sorted(glob.glob(DLOG_GLOB)):
        for ln in open(fp):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if account and (r.get("account") or "") != account:
                continue
            # prefer the engine bar date (what session it belongs to), fall back to wall clock
            d = _d(r.get("bar_ts") or r.get("timestamp_et") or r.get("timestamp_utc"))
            if d is None or d < since or d > until:
                continue
            act = (r.get("final_action") or "").strip()
            row = {"date": d.isoformat(), "profile": r.get("profile") or "A",
                   "side": r.get("side"), "entry": r.get("entry"), "stop": r.get("stop"),
                   "action": act, "reason": r.get("reason") or r.get("blocked_stage")}
            if act in SIGNAL_ACTIONS or act in PAPER_ACTIONS:
                signals.append(row)
            elif act == "blocked" or r.get("blocked_stage"):
                blocks.append(row)
    return signals, blocks


def review(account, since, until):
    trades = [t for t in trade_results.live_trades(account=account)
              if since.isoformat() <= t["date"] <= until.isoformat()]
    signals, blocks = load_decisions(since, until, account)

    # FIDELITY: every live trade should have >=1 engine signal on the same day+profile.
    sig_keys = Counter((s["date"], (s["profile"] or "A").upper()) for s in signals)
    off_strategy = []
    for t in trades:
        key = (t["date"], (t["strategy"] or "A").upper())
        if sig_keys.get(key, 0) <= 0:
            off_strategy.append(t)        # a live trade with NO matching engine signal = rogue/manual

    by_day = defaultdict(lambda: {"trades": 0, "pnl": 0.0, "pending": 0})
    for t in trades:
        e = by_day[t["date"]]
        e["trades"] += 1
        e["pnl"] += t["pnl"]
        e["pending"] += 0 if t["confirmed"] else 1

    block_reasons = Counter((b.get("reason") or "unknown") for b in blocks)
    live_sigs = sum(1 for s in signals if s["action"] in SIGNAL_ACTIONS)
    paper_sigs = sum(1 for s in signals if s["action"] in PAPER_ACTIONS)
    pending = sum(1 for t in trades if not t["confirmed"])

    fidelity_ok = (len(off_strategy) == 0) and (paper_sigs == 0)
    return {
        "account": account, "since": since.isoformat(), "until": until.isoformat(),
        "trades": trades, "n_trades": len(trades),
        "modeled_pnl": round(sum(t["pnl"] for t in trades), 2),
        "pending_confirm": pending,
        "engine_signals_live": live_sigs, "engine_signals_paper": paper_sigs,
        "blocks": dict(block_reasons), "n_blocks": len(blocks),
        "off_strategy": off_strategy,
        "by_day": {d: {**v, "pnl": round(v["pnl"], 2)} for d, v in sorted(by_day.items())},
        "fidelity_ok": fidelity_ok,
        "verdict": ("GREEN-LIGHT: trades reflected the strategy -> OK to buy next funded account"
                    if fidelity_ok else
                    "HOLD: review needed before buying next account"),
    }


def _print(rep):
    print(f"\n================ WEEKLY FIDELITY REVIEW · {rep['account']} ================")
    print(f"  window : {rep['since']} -> {rep['until']}")
    print(f"  live trades taken : {rep['n_trades']}   ·   modeled P&L: ${rep['modeled_pnl']:,.2f}"
          f"   ·   {rep['pending_confirm']} still pending eye-confirm")
    print(f"  engine signals    : {rep['engine_signals_live']} live"
          + (f"  ⚠ {rep['engine_signals_paper']} PAPER (bot not in live mode!)" if rep['engine_signals_paper'] else ""))
    if rep["by_day"]:
        print("  by day:")
        for d, v in rep["by_day"].items():
            tag = f"  ({v['pending']} pending)" if v["pending"] else ""
            print(f"    {d}  {v['trades']} trade(s)  ${v['pnl']:+,.2f}{tag}")
    if rep["blocks"]:
        print(f"  no-trade blocks   : {rep['n_blocks']} total")
        for r, n in sorted(rep["blocks"].items(), key=lambda x: -x[1]):
            print(f"    {n:>3}×  {r}")
    if rep["off_strategy"]:
        print(f"  ⚠ OFF-STRATEGY TRADES (no matching engine signal — investigate):")
        for t in rep["off_strategy"]:
            print(f"    {t['date']}  {t['strategy']} {t['direction']} x{t['contracts']}  ${t['pnl']:+,.2f}  — {t['note'][:70]}")
    print(f"\n  >>> {rep['verdict']}")
    print(f"  (fidelity is win/lose-blind: it only checks every trade was a rule-based engine signal)\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True, help="e.g. APEX-50K-1")
    ap.add_argument("--since", help="YYYY-MM-DD (default: 7 days before --until)")
    ap.add_argument("--until", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of the printed report")
    a = ap.parse_args()
    until = _d(a.until) or date.today()
    since = _d(a.since) or (until - timedelta(days=7))
    rep = review(a.account, since, until)
    if a.json:
        print(json.dumps(rep, indent=2))
    else:
        _print(rep)


if __name__ == "__main__":
    main()
