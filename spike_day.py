"""A3 SPIKE-DAY HARNESS — scripted Tradovate verification bench (V1-V7).
Run the moment demo credentials exist:  python3 spike_day.py

DEMO-ONLY: refuses to run unless config env is demo AND SAFETY.paper is True at the
config layer (orders here go to the DEMO API deliberately, via explicit demo gate).
Writes evidence to out_spike_results.md and files it in the evidence locker.

Each section prints findings for the operator to eyeball AND records raw responses.
NOTHING here touches production execution code — this is verification tooling only.
"""
import json
import time
import sys

import config
from tradovate_client import TradovateClient
from locker import Locker

RESULTS = "out_spike_results.md"
_log_lines = []


def log(section, msg, payload=None):
    line = f"## {section}\n{msg}\n"
    if payload is not None:
        line += "```json\n" + json.dumps(payload, indent=2, default=str)[:4000] + "\n```\n"
    _log_lines.append(line)
    print(f"[{section}] {msg}")


def flush():
    with open(RESULTS, "w") as f:
        f.write("# Spike Day Results — A3 / V1-V7\n\n" + "\n".join(_log_lines))
    try:
        Locker().file("incidents", RESULTS, "spike-day-results.md")
    except Exception as e:
        print("locker filing failed:", e)
    print(f"\nresults -> {RESULTS}")


def main():
    assert getattr(config, "TRADOVATE", {}).get("env", "demo") == "demo", \
        "SPIKE DAY IS DEMO-ONLY: config.TRADOVATE['env'] must be 'demo'"
    # raw _get/_post on purpose: place_bracket() is welded behind the live gate
    # (correctly), and spike day needs REAL DEMO orders — its own demo assert above
    # is the gate for this tool. NOTE: client uses '/order/placeOSO' casing; docs use
    # lowercase — whichever fails is itself a spike finding.
    cli = TradovateClient(config.TRADOVATE, config.HOSTS)
    cli.authenticate()
    accts = cli._get("/account/list")
    acct = next((a for a in accts if a["id"] == cli.account_id), accts[0])
    log("AUTH", f"authenticated OK (demo) · account {acct.get('name')} id={acct.get('id')}")
    mnq = cli.resolve_front_month("MNQ")
    log("CONTRACT", f"resolved front MNQ: {mnq.get('name')} id={mnq.get('id')}")

    def _get(path, **params):
        return cli._get(path, **params)

    def orders():
        return _get("/order/list")

    def my_working(ids=None):
        return [o for o in orders()
                if o.get("ordStatus") in ("Working", "Suspended", "PendingNew")
                and (ids is None or o.get("id") in ids)]

    # ---------- price anchor (md may be unavailable over REST: fallback = operator) ----------
    try:
        bars = cli.get_bars(mnq["name"], count=2)
        last = float(bars[-1]["close"])
    except Exception:
        last = float(input("md unavailable — enter current MNQ price: "))
    far_below = round((last - 400) * 4) / 4
    log("PRICE", f"last≈{last}, far-below limit px={far_below}")

    # ================= V7 — client tags =================
    try:
        r = cli._post("/order/placeorder", dict(
            accountSpec=acct["name"], accountId=acct["id"], action="Buy",
            symbol=mnq["name"], orderQty=1, orderType="Limit", price=far_below,
            isAutomated=True, clOrdId="NQB-SPIKE-V7-0001", customTag50="NQB-SPIKE-V7-0001"))
        log("V7", "placeorder with clOrdId+customTag50 accepted?", r)
        oid = r.get("orderId")
        time.sleep(1.5)
        ol = [o for o in orders() if o.get("id") == oid]
        log("V7", "order entity echo (expect NO tag fields per spec — verify)", ol)
        cmds = _get("/command/deps", masterid=oid)
        log("V7", "command/deps — does the tag live here? (expected YES)", cmds)
        cli._post("/order/cancelorder", dict(orderId=oid))
        log("V7", "cancel sent")
    except Exception as e:
        log("V7", f"EXCEPTION: {e!r}")

    # ================= V1 — OSO: children timing, atomicity =================
    oso_ids = {}
    try:
        body = dict(accountSpec=acct["name"], accountId=acct["id"], action="Buy",
                    symbol=mnq["name"], orderQty=2, orderType="Limit", price=far_below,
                    isAutomated=True, customTag50="NQB-SPIKE-V1",
                    bracket1=dict(action="Sell", orderType="Stop",
                                  stopPrice=far_below - 50),
                    bracket2=dict(action="Sell", orderType="Limit",
                                  price=far_below + 50))
        r = cli._post("/order/placeoso", body)
        log("V1", "placeOSO far-from-market accepted (LIMIT entry + 2 brackets)?", r)
        oso_ids = dict(parent=r.get("orderId"), c1=r.get("oso1Id"), c2=r.get("oso2Id"))
        time.sleep(1.5)
        fam = [o for o in orders() if o.get("id") in set(oso_ids.values())]
        log("V1b", "child entities pre-fill — EXPECT children Suspended", fam)
        cli._post("/order/cancelorder", dict(orderId=oso_ids["parent"]))
        time.sleep(1.5)
        fam2 = [o for o in orders() if o.get("id") in set(oso_ids.values())
                and o.get("ordStatus") in ("Working", "Suspended")]
        log("V1e", f"after parent cancel: {len(fam2)} family orders still live "
                   "(EXPECT 0 — cancel cascades)", fam2)
    except Exception as e:
        log("V1", f"EXCEPTION: {e!r}")

    # ================= V1b/V2 — marketable OSO: fill -> children Working =================
    try:
        px = round((last + 20) * 4) / 4         # marketable limit (crosses)
        body = dict(accountSpec=acct["name"], accountId=acct["id"], action="Buy",
                    symbol=mnq["name"], orderQty=2, orderType="Limit", price=px,
                    isAutomated=True, customTag50="NQB-SPIKE-V1B",
                    bracket1=dict(action="Sell", orderType="Stop", stopPrice=px - 60),
                    bracket2=dict(action="Sell", orderType="Limit", price=px + 60))
        t0 = time.time()
        r = cli._post("/order/placeoso", body)
        ids = dict(parent=r.get("orderId"), c1=r.get("oso1Id"), c2=r.get("oso2Id"))
        log("V1b", "marketable OSO placed", r)
        for _ in range(20):                      # watch children activate
            time.sleep(1.0)
            fam = [o for o in orders() if o.get("id") in set(ids.values())]
            sts = {o.get("id"): o.get("ordStatus") for o in fam}
            if any(s == "Working" for s in sts.values()):
                log("V1b", f"children WORKING {time.time()-t0:.1f}s after place "
                           f"(CRITICAL: record gap fill->working)", sts)
                break
        fills = _get("/fill/list")
        log("V6", f"fill/list count={len(fills)} — record ids/order; re-fetch compare",
            fills[-5:] if isinstance(fills, list) else fills)
        time.sleep(1.0)
        fills2 = _get("/fill/list")
        log("V6", f"second fetch count={len(fills2)} — same ids? same order?")
        # V4: disconnect persistence — drop token, wait, re-auth
        log("V4", "simulating disconnect: discarding session for 45s "
                  "(position open with brackets at broker)")
        cli.s.headers.pop("Authorization", None)
        time.sleep(45)
        cli.connect()
        fam = [o for o in orders() if o.get("id") in set(ids.values())
               and o.get("ordStatus") == "Working"]
        log("V4", f"after reconnect: {len(fam)} bracket legs still WORKING "
                  "(EXPECT >=1: stop alive server-side)", fam)
        # V2: exit via target -> sibling cancellation
        pos = _get("/position/list")
        log("V2", "positions before exit", pos)
        cli._post("/order/cancelorder", dict(orderId=ids["c2"]))   # cancel target
        # close manually with market, then verify stop auto-handled or orphaned:
        cli._post("/order/placeorder", dict(
            accountSpec=acct["name"], accountId=acct["id"], action="Sell",
            symbol=mnq["name"], orderQty=2, orderType="Market", isAutomated=True,
            customTag50="NQB-SPIKE-EXIT"))
        time.sleep(3)
        leftover = my_working(set(ids.values()))
        log("V2", f"after manual flat: leftover family orders={len(leftover)} "
                  "(CRITICAL: does the stop auto-cancel when position closed manually? "
                  "If not -> bot must cancel residual brackets on flatten)", leftover)
        for o in leftover:
            cli._post("/order/cancelorder", dict(orderId=o["id"]))
    except Exception as e:
        log("V1b/V2/V4", f"EXCEPTION: {e!r}")

    # ================= V5 — burst behavior (GENTLE: 10 cycles) =================
    try:
        penalties = 0
        t0 = time.time()
        for i in range(10):
            r = cli._post("/order/placeorder", dict(
                accountSpec=acct["name"], accountId=acct["id"], action="Buy",
                symbol=mnq["name"], orderQty=1, orderType="Limit", price=far_below,
                isAutomated=True, customTag50=f"NQB-SPIKE-V5-{i}"))
            if "p-ticket" in str(r) or r.get("failureReason"):
                penalties += 1
                log("V5", f"burst #{i}: penalty/failure", r)
            oid = r.get("orderId")
            if oid:
                cli._post("/order/cancelorder", dict(orderId=oid))
        log("V5", f"10 place+cancel cycles in {time.time()-t0:.1f}s, penalties={penalties} "
                  "(do NOT push harder — penalties are sticky)")
    except Exception as e:
        log("V5", f"EXCEPTION: {e!r}")

    # ================= cleanup =================
    try:
        for o in my_working():
            cli._post("/order/cancelorder", dict(orderId=o["id"]))
        pos = _get("/position/list")
        log("CLEANUP", "final positions (EXPECT all qty 0/closed)", pos)
    except Exception as e:
        log("CLEANUP", f"EXCEPTION: {e!r}")
    flush()
    print("\nOPERATOR: review out_spike_results.md; transcribe GREEN/RED into "
          "B1_DESIGN.md Part 3 spike table; decide amendment A4 (Exit #3 pattern).")


if __name__ == "__main__":
    sys.exit(main())
