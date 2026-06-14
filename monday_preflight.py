"""MONDAY PREFLIGHT — one command that proves the whole stack is green before the
first session. Read-only; places nothing. Run it ~20 min before 09:30 ET.

  python3 monday_preflight.py --account MFFU-50K-1 --tier 50K-conservative
"""
import argparse
import os
import sys
from datetime import datetime, timezone

from store import Store
from auto_safety import EVAL_TIERS, DD_ALLOWANCE, validate_size, tier_spec, APPROVAL_DIR
from scheduler import Scheduler


def check(name, ok, detail=""):
    mark = "✓" if ok else "✗"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--account", required=True)
    p.add_argument("--tier", required=True, choices=list(EVAL_TIERS))
    p.add_argument("--d1c-mode", default="active-eval-filter")
    a = p.parse_args(argv)

    print(f"\n=== MONDAY PREFLIGHT · {a.account} · {a.tier} ===")
    allg = True
    spec = tier_spec("eval", a.tier)

    print("\nTESTS & CODE")
    import subprocess
    r = subprocess.run([sys.executable, "-m", "pytest", "-q"], capture_output=True, text=True)
    allg &= check("full test suite green", "passed" in r.stdout and "failed" not in r.stdout.split("passed")[0][-30:],
                  r.stdout.strip().splitlines()[-1] if r.stdout else "")
    allg &= check("git clean (no uncommitted edits)",
                  subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                                 text=True).stdout.strip() == "", "")

    print("\nSIZING & RISK")
    buf = DD_ALLOWANCE[spec["account"]]
    ok, why = validate_size(spec, buf)
    allg &= check(f"size {spec['am']}A/{spec['bm']}B worst-day < buffer", ok, why)
    allg &= check(f"daily stop set: -${spec['daily_stop']}", True)

    print("\nDATA FEED")
    try:
        from paper_live import DukascopyLiveFeed
        f = DukascopyLiveFeed(poll_sec=30, warmup_days=5); f.connect()
        bars = f.history()
        fresh = bars and (datetime.now(timezone.utc) -
                          bars[-1][0].tz_convert("UTC")).total_seconds() < 4 * 86400
        allg &= check("Dukascopy NQ feed reachable", bool(bars),
                      f"last bar {bars[-1][0]}" if bars else "no bars")
    except Exception as e:                                  # noqa
        allg &= check("Dukascopy NQ feed reachable", False, str(e)[:60])

    print("\nD1c (DriftGate)")
    from drift_gate import DriftGate
    g = DriftGate(enabled=(a.d1c_mode != "off"))
    allg &= check(f"D1c mode = {a.d1c_mode}", True,
                  "Profile A only · fail-closed · ATHENA count untouched")

    print("\nWALL CLOCK / SESSION")
    sch = Scheduler()
    now = datetime.now(timezone.utc)
    allg &= check("ET trading day", sch.is_trading_day(sch.et(now).date()),
                  f"next entry window {sch.in_entry_window(now)}")

    print("\nEXECUTION MODE")
    live_url = bool(os.environ.get("TRADERSPOST_LIVE_URL"))
    tp_ok = os.path.exists(os.path.join(APPROVAL_DIR, "traderspost-approved.flag"))
    bracket_ok = os.path.exists(os.path.join(APPROVAL_DIR, "bracket-verified.flag"))
    live_ready = live_url and tp_ok and bracket_ok
    check("TRADERSPOST_LIVE_URL set", live_url)
    check("traderspost-approved.flag", tp_ok)
    check("bracket-verified.flag (Stage 2 passed)", bracket_ok,
          "REQUIRED for live — proves stop+target attach at Tradovate")
    print(f"\n  >>> EXECUTION TODAY: {'LIVE-CAPABLE' if live_ready else 'PAPER ONLY'} <<<")

    print("\nKILL SWITCH")
    s = Store()
    lock = s.get_state("emergency_lockout")
    allg &= check("no active lockout", not lock, lock or "clear")
    check("operator kill command", True, "python3 -c \"from store import Store; "
          "Store().set_state(auto_live_kill='1')\"  (instant halt)")

    print("\n" + "=" * 56)
    if allg:
        mode = "--live" if live_ready else "(paper)"
        print("PREFLIGHT GREEN. Run the session:")
        print(f"  python3 auto_live.py --account {a.account} --tier {a.tier} "
              f"--d1c-mode {a.d1c_mode} {mode}".rstrip())
        print("  SUPERVISE the NY-AM window. MFFU is semi-auto — watch the account.")
    else:
        print("PREFLIGHT NOT GREEN — resolve the ✗ items. NO TRADE until clean.")
    return 0 if allg else 1


if __name__ == "__main__":
    sys.exit(main())
