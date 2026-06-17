"""CLI for the FULL-AUTO preflight gate. Reads the live data_status (freshness-corrected) + the
dashboard green state, runs auto_safety.full_auto_preflight, and prints the exact blockers.
Read-only — it never arms anything. Exit 0 = GO, 1 = BLOCKED.

  python3 full_auto_preflight.py --account MFFU-50K-1 [--feed tradingview-1m] [--d1c-mode active-eval-filter]
"""
import argparse
import json

import auto_safety
import zeus_server
from store import Store
from heimdall_monitor import apply_freshness


def main(argv=None):
    p = argparse.ArgumentParser(description="full-auto preflight (read-only)")
    p.add_argument("--account", required=True)
    p.add_argument("--feed", default="tradingview-1m")
    p.add_argument("--tier", default="50K-conservative")
    p.add_argument("--d1c-mode", dest="d1c", default="active-eval-filter")
    p.add_argument("--controlled-tv-full-live-test", "--controlled-tv-live-test",
                   dest="controlled", action="store_true",
                   help="evaluate the SUPERVISED controlled-test gate (allows browser feed) "
                        "instead of the production gate")
    a = p.parse_args(argv)

    ds = apply_freshness(json.loads(Store().get_state("data_status") or "{}"))
    try:
        dgreen = bool(zeus_server.assemble_state()["deployment"].get("green"))
    except Exception:
        dgreen = False
    ok, fails, eff_d1c, summ = auto_safety.full_auto_preflight(
        a.account, a.feed, a.d1c.upper().replace("-", "_"),
        dict(ds, daily_stop=700), store=Store(), dashboard_green=dgreen,
        controlled_test=a.controlled)

    mode = "CONTROLLED TV LIVE TEST" if a.controlled else "PRODUCTION FULL-AUTO"
    print("================ %s PREFLIGHT ================" % mode)
    print("account: %s · feed: %s · dashboard_green: %s" % (a.account, a.feed, dgreen))
    print("data_state: %s · DATA_READY: %s · effective D1c: %s" %
          (ds.get("data_state"), ds.get("DATA_READY"), eff_d1c))
    print("RESULT: %s" % ("FULL AUTO GO" if ok else "BLOCKED"))
    if fails:
        print("blockers:")
        for f in fails:
            print("  ✗ " + f)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
