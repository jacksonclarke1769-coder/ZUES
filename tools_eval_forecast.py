"""tools_eval_forecast.py — live conditional P(pass) for the active Apex 50K eval.

Reads current state from evidence/eval_campaign.json (operator ground truth; auto-flips to live
read-back), replays the certified per-day P&L stream onto that bankroll + remaining clock, and
prints P(pass)/P(bust)/P(expire), median days-to-target, a pace verdict, and a slippage-sensitivity
table (how much live entry slippage would cost the pass rate — ties to the slip tripwire).

Usage:
    python3 tools_eval_forecast.py                 # today, from eval_campaign.json
    python3 tools_eval_forecast.py --as-of 2026-07-06   # Monday's view
    python3 tools_eval_forecast.py --balance 49404.80 --cushion 1904.80 --days-left 19
    python3 tools_eval_forecast.py --rebuild       # regenerate the certified day cache (~20s, heavy)

The number is only as current as balance_asof in the campaign file. On a big move, refresh that
(or pass --balance/--cushion) before trusting it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_forecast as EF

CAMPAIGN = "evidence/eval_campaign.json"


def _rebuild_cache():
    """Regenerate reports/eval_day_pnl_50k_1200.json from the locked machine (heavy ~20s)."""
    print("rebuilding certified day cache (locked A stream, exit3+D1c, 1m truth)…", flush=True)
    import tools_account_size_research as H
    import run_d1c_real as RD
    import apex_eval_eod_databento as DB
    import config
    import strategy_engine_profileA as E
    from tools_1m_truth_recert import M1Map
    from tools_phase3_config_sweep import a_streams_d1c
    d1_tz = RD.load_1m(); d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m(); mp = M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    rows = a_streams_d1c(eng._features(), mp, d1_tz)["exit3"][0]
    spec = H.SPECS["50K"]
    # deployed tier qty cap (DEC-20260705-1102) — spec max_qty/MAX_A_QTY are research ceilings, not the machine
    days = H.day_rows(H.build_events(rows, 1200, 10), spec["stop"], spec["dll"])
    cache = [{"date": str(d.date()), "real": round(float(r), 2), "trough": round(float(tr), 2)}
             for d, r, tr in days]
    os.makedirs("reports", exist_ok=True)
    json.dump({"machine": "ZEUS v2026.07.02b 50K@1200 cap10", "n_days": len(cache),
               "source": "tools_account_size_research day_rows (exit3+D1c 1m-truth)",
               "days": cache}, open(EF.CACHE_PATH, "w"), indent=0)
    print(f"[saved] {EF.CACHE_PATH} ({len(cache)} day rows)", flush=True)


def _load_campaign():
    try:
        return json.load(open(CAMPAIGN))
    except Exception:  # noqa: BLE001
        return {}


def _slip_haircut(days, tax):
    """Return a copy of the day stream with `tax` dollars removed from each day's realized P&L
    (models ~1 A trade/day of entry slippage; tax≈slipR×$1,200). Trough shifts with it."""
    return [(d, r - tax, tr - tax) for d, r, tr in days]


def main():
    ap = argparse.ArgumentParser(description="Conditional P(pass) for the active Apex 50K eval.")
    ap.add_argument("--rebuild", action="store_true", help="regenerate the certified day cache (heavy)")
    ap.add_argument("--as-of", default=None, help="ISO date to evaluate from (default: today)")
    ap.add_argument("--balance", type=float, default=None, help="override current balance")
    ap.add_argument("--cushion", type=float, default=None, help="override cushion to floor")
    ap.add_argument("--days-left", type=int, default=None, help="override remaining calendar days")
    a = ap.parse_args()

    if a.rebuild:
        _rebuild_cache()
        return

    try:
        days = EF.load_distribution()
    except FileNotFoundError:
        print(f"✗ no day cache at {EF.CACHE_PATH} — run:  python3 tools_eval_forecast.py --rebuild")
        sys.exit(1)

    camp = _load_campaign()
    start = float(camp.get("start_balance", EF.START))
    trail = float(camp.get("trail_dd", EF.TRAIL))
    target_bal = float(camp.get("target_balance", start + EF.TARGET))
    balance = a.balance if a.balance is not None else float(camp.get("current_balance", start))

    # cushion / threshold
    if a.cushion is not None:
        threshold = balance - a.cushion
    else:
        # unlocked default floor = start - trail; a real ratcheted floor comes via --cushion/read-back
        threshold = start - trail
    cushion = balance - threshold

    # days-left from the clock (clock_start + clock_days), measured from as-of
    as_of = date.fromisoformat(a.as_of) if a.as_of else date.today()
    if a.days_left is not None:
        days_left = a.days_left
    else:
        cs = camp.get("clock_start"); cd = int(camp.get("clock_days", EF.EXPIRE_DAYS))
        if cs:
            expiry = date.fromisoformat(cs) + timedelta(days=cd)
            days_left = max(0, (expiry - as_of).days)
        else:
            days_left = EF.EXPIRE_DAYS

    spec = EF.Spec(start=start, trail=trail, target=target_bal - start)
    fc = EF.forecast(days, balance, threshold, days_left, spec)

    # --- report ---
    print("=" * 64)
    print(f"  CONDITIONAL EVAL FORECAST · {camp.get('account_label','APEX-50K-EVAL-1')} · as-of {as_of}")
    print(f"  machine: {camp.get('machine','ZEUS Rev B (v2026.07.02b)')}  ·  method: block-bootstrap replay")
    print("=" * 64)
    print(f"  balance ${balance:,.2f}   floor ${threshold:,.2f}   cushion ${cushion:,.2f}")
    print(f"  target  ${target_bal:,.0f}   to-go ${target_bal-balance:,.2f}   days-left {days_left}")
    print(f"  replayed over {fc['n']} historical continuations")
    print("-" * 64)
    print(f"  P(PASS)    {fc['pass_pct']:>5}%")
    print(f"  P(BUST)    {fc['bust_pct']:>5}%")
    print(f"  P(EXPIRE)  {fc['expire_pct']:>5}%")
    print(f"  median days-to-target (of passes): {fc['median_days_to_pass']}")

    # pace verdict — shared with the dashboard (eval_forecast.pace_verdict), dominant-failure-mode order
    _level, verdict = EF.pace_verdict(fc)
    p = fc["pass_pct"]
    print(f"  VERDICT: {verdict}")
    # honesty line: the conditional number vs the certified headline, and WHY they differ
    print(f"  NOTE: {p}% conditional vs 47.8% certified (cap-10 re-lock 2026-07-05; upper bound) — "
          f"you start down ${start-balance:,.0f} "
          f"(cushion ${cushion:,.0f} vs $2,500), need ${target_bal-balance:,.0f} in {days_left}d not 30. "
          f"The edge is unchanged; the STARTING HANDICAP is the gap.")

    # --- slippage sensitivity (ties to the slip tripwire) ---
    print("-" * 64)
    print("  slippage sensitivity (live entry cost you haven't measured yet):")
    print(f"    {'entry slip':>12}{'~$/trade-day':>14}{'P(pass)':>10}{'P(bust)':>10}")
    for slip_r, tax in [(0.00, 0.0), (0.05, 60.0), (0.10, 120.0), (0.20, 240.0)]:
        fh = EF.forecast(_slip_haircut(days, tax), balance, threshold, days_left, spec)
        print(f"    {slip_r:>11.2f}R{tax:>14,.0f}{fh['pass_pct']:>9}%{fh['bust_pct']:>9}%")
    print("  (assumes ~1 A trade/day; slip_$ = slipR × $1,200. This is why the slip tripwire matters:")
    print("   every 0.05R of unmodeled entry cost visibly moves the pass rate.)")
    print("=" * 64)


if __name__ == "__main__":
    main()
