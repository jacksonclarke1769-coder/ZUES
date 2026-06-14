"""BRIDGE TEST — fire ONE TradersPost webhook to validate the live path (Test-Plan
Stages 1-2). The webhook URL is read from an ENV VAR (never hardcoded, never in git):
    TRADERSPOST_TEST_URL   (for --mode test)
    TRADERSPOST_LIVE_URL   (for --mode live; also needs traderspost-approved.flag)

Safe by default:
  --ping   : send a benign `exit` on a presumed-FLAT account. Validates auth + routing +
             symbol parsing without opening any position.
  --entry  : send ONE bracket entry. You supply LIVE prices (--price --stop --target).
             This is a REAL order on the eval — use 1 contract, during RTH, watching it.

This is a manual, single-shot operator tool. It does NOT auto-generate signals.
"""
import argparse
import os
import sys

from store import Store
from journal import Journal
import bridge_traderspost as BP
from bridge_sender import BridgeSender


def main(argv=None):
    p = argparse.ArgumentParser(description="single TradersPost webhook test (fail-closed)")
    p.add_argument("--account", required=True)
    p.add_argument("--mode", choices=["test", "live"], default="test")
    p.add_argument("--root", default="MNQ", choices=["MNQ", "NQ"])
    p.add_argument("--symbol", help="override ticker (e.g. explicit contract MNQU2025)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ping", action="store_true", help="benign exit on a flat account")
    g.add_argument("--entry", action="store_true", help="ONE real bracket entry")
    p.add_argument("--side", choices=["long", "short"], default="long")
    p.add_argument("--qty", type=int, default=1)
    p.add_argument("--price", type=float, help="live entry price (required for --entry)")
    p.add_argument("--stop", type=float, help="live stop price (required for --entry)")
    p.add_argument("--target", type=float, help="live target price (required for --entry)")
    p.add_argument("--confirm", action="store_true",
                   help="required to actually fire an --entry (extra human gate)")
    a = p.parse_args(argv)

    url = os.environ.get("TRADERSPOST_TEST_URL" if a.mode == "test"
                         else "TRADERSPOST_LIVE_URL")
    if not url:
        env = "TRADERSPOST_TEST_URL" if a.mode == "test" else "TRADERSPOST_LIVE_URL"
        print(f"REFUSED: ${env} not set. Export your TradersPost strategy webhook URL "
              f"into that env var (do NOT paste it into a file or git).")
        return 2
    if a.symbol:
        BP.TP_SYMBOL[a.root] = a.symbol

    store, j = Store(), Journal()
    sender = BridgeSender(store=store, journal=j, mode=a.mode,
                          test_url=url, live_url=url)

    if a.ping:
        payload, err = BP.build_flatten(account=a.account, root=a.root, reason="bridge-ping")
        print("PING (exit on flat account) — validates routing, opens nothing.")
    else:
        if None in (a.price, a.stop, a.target):
            print("REFUSED: --entry needs --price --stop --target (live prices).")
            return 2
        if not a.confirm:
            print("REFUSED: --entry is a REAL order on the eval. Re-run with --confirm "
                  "once you have eyes on the chart and are ready to manage it.")
            return 2
        payload, err = BP.build_entry(
            account=a.account, strategy="BRIDGE-TEST", setup="manual-stage2",
            signal_ts=f"{a.account}-manual", side=a.side, qty=a.qty,
            entry=a.price, stop=a.stop, target=a.target, root=a.root,
            mode_meta=dict(mode="ARES", test=True))
    if err:
        print(f"FAIL CLOSED — payload not built: {err}")
        return 2

    print("payload:", payload)
    res = sender.send(payload)
    print("result:", res)
    if a.mode == "live" and not res.get("sent"):
        print("(live refused — fix the reason above; the path is fail-closed by design)")
    return 0 if res.get("sent") or a.mode == "test" else 1


if __name__ == "__main__":
    sys.exit(main())
