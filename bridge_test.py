"""BRIDGE TEST — fire ONE TradersPost webhook to validate the live path (Test-Plan Stages 1-3).
The webhook URL is read from an ENV VAR (never hardcoded, never in git):
    TRADERSPOST_TEST_URL   (for --mode test)
    TRADERSPOST_LIVE_URL   (for --mode live; also needs traderspost-approved.flag)

Stages (one per run; each saves evidence under evidence/launchlock/traderspost/):
  --ping      Stage 1: benign `exit` on a presumed-FLAT account. Validates auth + routing +
              symbol parsing without opening any position.
  --one-mnq   Stage 2: ONE smallest-size 1-MNQ bracket. qty is HARD-FORCED to 1. Prices from
              --price/--stop/--target, or derived from --ref (resting, non-marketable by default).
              Requires --confirm for a live order. Deterministic signalId → a retry cannot dup it.
  --flatten   Stage 3: flatten/cancel the account (closes the Stage-2 test + cancels working orders).
  --entry     Advanced: arbitrary bracket entry (you supply all prices / qty).

This is a manual, single-shot operator tool. It does NOT auto-generate signals and never changes
Profile A/B/D1c logic.
"""
import argparse
import json
import os
import sys
import time as _t

from store import Store
from journal import Journal
import bridge_traderspost as BP
from bridge_sender import BridgeSender

EVID_DIR = "evidence/launchlock/traderspost"


def save_evidence(stage, payload, res, extra=None):
    os.makedirs(EVID_DIR, exist_ok=True)
    path = os.path.join(EVID_DIR, f"{stage}.json")
    with open(path, "w") as f:
        json.dump({"stage": stage, "ts": int(_t.time()), "payload": payload,
                   "result": res, "extra": extra or {}}, f, indent=2)
    print(f"evidence -> {path}")
    return path


def main(argv=None):
    p = argparse.ArgumentParser(description="single TradersPost webhook test (fail-closed)")
    p.add_argument("--account", required=True)
    p.add_argument("--mode", choices=["test", "live"], default="test")
    p.add_argument("--root", default="MNQ", choices=["MNQ", "NQ"])
    p.add_argument("--symbol", help="override ticker (e.g. explicit contract MNQU2025)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ping", action="store_true", help="Stage 1: benign exit on a flat account")
    g.add_argument("--one-mnq", dest="one_mnq", action="store_true",
                   help="Stage 2: ONE 1-MNQ bracket (qty forced to 1)")
    g.add_argument("--flatten", action="store_true", help="Stage 3: flatten/cancel the account")
    g.add_argument("--entry", action="store_true", help="advanced: arbitrary bracket entry")
    p.add_argument("--side", choices=["long", "short"], default="long")
    p.add_argument("--qty", type=int, default=1)
    p.add_argument("--price", type=float, help="entry/limit price")
    p.add_argument("--stop", type=float, help="stop price")
    p.add_argument("--target", type=float, help="target price")
    p.add_argument("--ref", type=float,
                   help="(--one-mnq) reference price to derive a resting, non-marketable bracket")
    p.add_argument("--tag", default="stage2",
                   help="(--one-mnq) deterministic signalId tag; vary to run a fresh test")
    p.add_argument("--confirm", action="store_true",
                   help="required to actually fire a live --one-mnq/--entry (extra human gate)")
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
    sender = BridgeSender(store=store, journal=j, mode=a.mode, test_url=url, live_url=url)

    stage = None
    if a.ping:
        stage = "stage1-ping"
        payload, err = BP.build_flatten(account=a.account, root=a.root,
                                        reason=f"bridge-ping-{int(_t.time())}")  # fresh id each run
        print("Stage 1 PING (exit on flat account) — validates routing, opens nothing.")
    elif a.flatten:
        stage = "stage3-flatten"
        payload, err = BP.build_flatten(account=a.account, root=a.root,
                                        reason=f"stage3-flatten-{int(_t.time())}")
        print("Stage 3 FLATTEN — closes position + cancels working orders on the account.")
    elif a.one_mnq:
        stage = "stage2-1mnq"
        # derive a controlled, NON-marketable resting bracket from --ref if explicit prices absent
        price, stop, target = a.price, a.stop, a.target
        if None in (price, stop, target):
            if a.ref is None:
                print("REFUSED: --one-mnq needs --price/--stop/--target, or --ref to derive them.")
                return 2
            if a.side == "long":              # rest BELOW market so it does not fill immediately
                price = a.ref - 30.0; stop = price - 20.0; target = price + 40.0
            else:                              # rest ABOVE market
                price = a.ref + 30.0; stop = price + 20.0; target = price - 40.0
            print(f"derived resting bracket from ref {a.ref}: entry {price} stop {stop} target {target}")
        if a.mode == "live" and not a.confirm:
            print("REFUSED: live --one-mnq is a REAL order. Re-run with --confirm once you have "
                  "eyes on the chart and are ready to manage it.")
            return 2
        payload, err = BP.build_entry(
            account=a.account, strategy="BRIDGE-TEST", setup="stage2-1mnq",
            signal_ts=f"{a.account}-{a.tag}",          # deterministic -> retry is dedup-blocked
            side=a.side, qty=1,                         # HARD-FORCED smallest size
            entry=price, stop=stop, target=target, root="MNQ",
            mode_meta=dict(mode="ARES", test=True, stage="stage2-1mnq"))
        print("Stage 2 ONE 1-MNQ bracket (qty forced to 1).")
    else:  # --entry (advanced)
        stage = "entry"
        if None in (a.price, a.stop, a.target):
            print("REFUSED: --entry needs --price --stop --target.")
            return 2
        if a.mode == "live" and not a.confirm:
            print("REFUSED: live --entry is a REAL order. Re-run with --confirm.")
            return 2
        payload, err = BP.build_entry(
            account=a.account, strategy="BRIDGE-TEST", setup="manual-entry",
            signal_ts=f"{a.account}-manual", side=a.side, qty=a.qty,
            entry=a.price, stop=a.stop, target=a.target, root=a.root,
            mode_meta=dict(mode="ARES", test=True))

    if err:
        print(f"FAIL CLOSED — payload not built: {err}")
        return 2

    print("payload:", json.dumps(payload))
    res = sender.send(payload)
    print("result:", res)
    save_evidence(stage, payload, res, extra=dict(mode=a.mode, account=a.account))
    if a.mode == "live" and not res.get("sent"):
        print("(live refused — fix the reason above; the path is fail-closed by design)")
    return 0 if res.get("sent") or a.mode == "test" else 1


if __name__ == "__main__":
    sys.exit(main())
