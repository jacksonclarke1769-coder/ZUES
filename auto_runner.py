"""ARES AUTO — deployment runner. Orchestrates mode + account + sizing + guards + D1c
gate + live latches. FAILS CLOSED: dry-run by default, paper before live, live refused
unless EVERY latch is green.

  python3 auto_runner.py --mode eval   --account MFFU-50K-1 --tier 50K-conservative
  python3 auto_runner.py --mode funded --account MFFU-150K-1 --tier 150K
  flags: --dry-run (default) | --paper | --live

Hard rejection conditions enforced here:
  * --account is REQUIRED (no silent default)
  * --live needs the full live-latch set (approval, smoke, B1, firm rules, dashboard green)
  * ARES sizing cannot run on a funded account
  * worst-day at chosen size must be < available drawdown buffer, else BLOCK
  * daily stop is persistent (a restart cannot bypass a stopped day)
  * D1c production is locked unless explicitly approved
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from store import Store
from auto_safety import (tier_spec, validate_size, DailyGuard, D1cGate, live_latches,
                         DD_ALLOWANCE, broker_smoke)
from ares_mode import account_phase, current_mode

ET = ZoneInfo("America/New_York")


def et_date():
    return datetime.now(timezone.utc).astimezone(ET).date().isoformat()


def available_buffer(store, account, acct_class):
    """equity - trailing floor for a registered account; full DD allowance for a fresh one."""
    for a in json.loads(store.get_state("zeus_accounts") or "[]"):
        if a.get("name") == account:
            return a.get("balance", 0) - a.get("floor", 0)
    return DD_ALLOWANCE.get(acct_class)        # fresh eval: full buffer


def resolve_plan(args, store):
    """Build the full execution plan + every gate status. Returns (plan, blockers[])."""
    blockers = []
    spec = tier_spec(args.mode, args.tier)
    acct_class = spec["account"]
    phase = account_phase(store, args.account)

    # ARES-on-funded rail
    if args.mode == "eval" and phase == "FUNDED":
        blockers.append(f"REFUSED: {args.account} is FUNDED — eval/ARES sizing forbidden")
    if args.mode == "funded" and phase == "EVAL":
        blockers.append(f"note: {args.account} still in EVAL — funded mode premature")

    # worst-day vs buffer
    buf = available_buffer(store, args.account, acct_class)
    ok_size, why = validate_size(spec, buf)
    if not ok_size:
        blockers.append(f"SIZE BLOCK: {why}")

    # daily guard (persistent, restart-proof)
    guard = DailyGuard(store)
    gstate = guard.state(args.account, et_date())
    if guard.is_stopped(args.account, et_date()):
        blockers.append(f"DAILY STOP already hit today ({gstate['pnl']:+.0f}) — "
                        "no new entries until next ET day (restart cannot bypass)")

    # D1c gate (defensive Profile-A filter; never adds trades / changes size)
    d1c_req = getattr(args, "d1c_mode", "shadow").upper().replace("-", "_")
    store.set_state(d1c_requested_mode=d1c_req)
    acct_type = "funded" if args.mode == "funded" else "eval"
    gate = D1cGate(store)
    d1c = gate.status(acct_type)
    d1c["account_type"] = acct_type
    if d1c_req == "PRODUCTION_FUNDED" and not gate.prod_approved():
        blockers.append("D1c PRODUCTION_FUNDED requested without promotion approval "
                        "(needs approve-d1c-production + athena-allows-d1c + gate-test flags)")
    if d1c_req == "ACTIVE_EVAL_FILTER" and acct_type == "funded":
        blockers.append("D1c ACTIVE_EVAL_FILTER is eval-only — forbidden on a funded "
                        "account (use staged funded rollout, see d1c-funded-rollout.md)")

    # execution route (TradersPost bridge replaces blocked Tradovate API)
    execution = getattr(args, "execution", "none")
    webhook_mode = getattr(args, "webhook_mode", "dry-run")
    if execution == "traderspost" and webhook_mode == "live":
        import os as _os
        if not _os.path.exists(_os.path.join("evidence/approvals",
                                             "traderspost-approved.flag")):
            blockers.append("bridge LIVE webhook requested without traderspost-approved.flag")

    # execution-mode latches
    exec_mode = "live" if args.live else ("paper" if args.paper else "dry-run")
    live_ok, live_fails = (True, [])
    if exec_mode == "live":
        live_ok, live_fails = live_latches(args.account, store,
                                           dashboard_green=args.dashboard_green)
        if not live_ok:
            blockers += [f"LIVE LATCH: {f}" for f in live_fails]

    plan = dict(
        account=args.account, account_class=acct_class, phase=phase,
        mode=args.mode, tier=args.tier, size=f"A{spec['am']}/B{spec['bm']}",
        daily_stop=spec["daily_stop"], available_buffer=buf,
        worst_day=spec["worst_day"], size_ok=ok_size,
        exec_mode=exec_mode, d1c=d1c, daily_guard=gstate,
        live_latches_ok=live_ok, live_failures=live_fails, execution=execution,
        webhook_mode=webhook_mode,
        current_mode=current_mode(store, args.account), et_date=et_date())
    return plan, blockers


def main(argv=None):
    p = argparse.ArgumentParser(description="ARES AUTO deployment runner (fail-closed)")
    p.add_argument("--mode", required=True, choices=["eval", "funded"])
    p.add_argument("--account", required=True)          # NO silent default
    p.add_argument("--tier", required=True)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--paper", action="store_true")
    g.add_argument("--live", action="store_true")
    p.add_argument("--dashboard-green", action="store_true",
                   help="assert dashboard safety green (real check wired in B1)")
    p.add_argument("--d1c-mode", default="shadow",
                   choices=["off", "shadow", "active-eval-filter", "production-funded"],
                   help="D1c defensive Profile-A filter mode (default shadow)")
    p.add_argument("--execution", default="none",
                   choices=["none", "traderspost"],
                   help="execution route (default none = decision-only)")
    p.add_argument("--webhook-mode", default="dry-run",
                   choices=["dry-run", "test", "live"], help="bridge webhook mode")
    args = p.parse_args(argv)

    store = Store()
    plan, blockers = resolve_plan(args, store)

    print("=" * 64)
    print(f"ARES AUTO RUNNER · {plan['exec_mode'].upper()}")
    print("=" * 64)
    for k in ("account", "account_class", "phase", "mode", "tier", "size",
              "daily_stop", "available_buffer", "worst_day", "current_mode", "et_date"):
        print(f"  {k:18}: {plan[k]}")
    print(f"  size_ok           : {plan['size_ok']}")
    print(f"  D1c               : {plan['d1c']['mode']} (requested {plan['d1c']['requested']}, "
          f"acct {plan['d1c']['account_type']})")
    print(f"  D1c role          : blocks/suspends Profile A only · never B · never size")
    print(f"  execution route   : {plan['execution']} · webhook {plan['webhook_mode']}")
    print(f"  daily_guard       : {plan['daily_guard']}")
    if plan["exec_mode"] == "live":
        print(f"  live_latches_ok   : {plan['live_latches_ok']}")
        for f in plan["live_failures"]:
            print(f"      - {f}")

    if blockers:
        print("\n*** NO TRADE — blockers ***")
        for b in blockers:
            print(f"  ✗ {b}")
        print("\nFAIL CLOSED. Resolve every blocker before retrying.")
        return 2

    if plan["exec_mode"] == "dry-run":
        print("\n✓ DRY-RUN OK — plan is valid and safe. No orders placed (by design).")
        print("  To execute: re-run with --paper (then --live once latches are green).")
        return 0
    if plan["exec_mode"] == "paper":
        print("\n✓ PAPER latches OK. Paper execution engine wiring is the B2 deliverable;")
        print("  the safety/orchestration layer above is validated and ready to drive it.")
        return 0
    print("\n✓ LIVE latches OK — but live execution requires the B1 runner (not built).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
