"""B0/W6 — Recovery & Replay (v2, hardened by the W6 battery). On restart:
rebuild beliefs from the ledger, then reconcile against the broker. BROKER WINS.

v2 additions (battery-driven):
  - fill sweep: broker fills for KNOWN lifecycles that the ledger missed
    (crash between broker fill and local persist, at ANY lifecycle stage)
  - CANCEL_SENT resolution (gone at broker -> CANCEL_CONFIRMED; still working -> nothing)
  - MODIFY_SENT resolution (broker qty matches request -> MODIFY_CONFIRMED)
  - EXIT sweep: ledger-open position, broker flat, with a matching closing fill
    -> EXIT(source=recovery)
  - idempotent: a second recover() appends NOTHING new (except recon re-alerts)

Resolution rules for SENDs with unknown outcome:
  broker shows order working -> ACK · broker shows fill -> ACK+FILL ·
  neither -> REJECT(not_found_at_broker). NEVER resend.
"""
from recon import Reconciler


def _match(items, cl, bmap, key="broker_order_id"):
    return [x for x in items
            if (x.get("cl_ord_id") == cl or bmap.get(str(x.get(key))) == cl)]


def recover(journal, broker, state_view=None, p3_params=None):
    report = dict(resolved=[], beliefs={}, discrepancies=[])
    bmap = journal.broker_map()
    working = list(broker.working_orders())
    fills = list(broker.fills_since(None))

    # ---- 1. resolve ambiguous SENDs from broker truth ----
    for cl in journal.unresolved_sends():
        head = journal.events(cl)[0]
        acct = head["account_id"]
        w = _match(working, cl, bmap)
        f = _match(fills, cl, bmap)
        if w:
            journal.append("ACK", acct, cl, payload=dict(
                broker_order_id=w[0].get("broker_order_id"), source="recovery"))
            report["resolved"].append((cl, "ACK_working_at_broker"))
        elif f:
            journal.append("ACK", acct, cl, payload=dict(
                broker_order_id=f[0].get("broker_order_id"), source="recovery"))
            report["resolved"].append((cl, "FILLED_at_broker"))
            # fill events appended by the sweep below (single code path)
        else:
            journal.append("REJECT", acct, cl, payload=dict(
                reason="not_found_at_broker", source="recovery"))
            report["resolved"].append((cl, "REJECTED_not_found"))
    bmap = journal.broker_map()                      # refresh after resolutions

    # ---- 2. fill sweep: broker fills missing from KNOWN lifecycles ----
    for cl in _known_lifecycles(journal):
        head = journal.events(cl)[0]
        acct, side = head["account_id"], (head["payload"] or {}).get("side")
        if journal.status(cl) in ("rejected", "cancelled", "closed"):
            continue
        led_qty = _ledger_filled_qty(journal, cl)
        brk = _match(fills, cl, bmap)
        seen = _recorded_fill_ids(journal, cl)
        new = [f for f in brk if str(f.get("fill_id")) not in seen]
        brk_qty = sum(f.get("qty", 0) for f in brk)
        if brk_qty > led_qty and new:
            delta = brk_qty - led_qty
            intended = (head["payload"] or {}).get("qty", delta)
            kind = "FILL" if brk_qty >= intended else "PARTIAL_FILL"
            journal.append(kind, acct, cl, payload=dict(
                qty=delta, side=side, px=new[-1].get("px"),
                fill_id=new[-1].get("fill_id"),
                broker_order_id=new[-1].get("broker_order_id"), source="recovery"))
            report["resolved"].append((cl, f"{kind}_swept_qty_{delta}"))

    # ---- 3. CANCEL_SENT / MODIFY_SENT resolution ----
    for cl in _known_lifecycles(journal):
        evs = journal.events(cl)
        acct = evs[0]["account_id"]
        types = [e["event_type"] for e in evs]
        still_working = bool(_match(working, cl, bmap))
        if "CANCEL_SENT" in types and "CANCEL_CONFIRMED" not in types \
                and journal.status(cl) not in ("closed", "cancelled", "rejected"):
            if not still_working and not _match(fills, cl, bmap):
                journal.append("CANCEL_CONFIRMED", acct, cl,
                               payload=dict(source="recovery"))
                report["resolved"].append((cl, "CANCEL_CONFIRMED_swept"))
        if "MODIFY_SENT" in types:
            last_mod = [e for e in evs if e["event_type"] == "MODIFY_SENT"][-1]
            confirmed = any(e["event_type"] == "MODIFY_CONFIRMED"
                            and e["seq"] > last_mod["seq"] for e in evs)
            if not confirmed:
                want = (last_mod["payload"] or {}).get("qty")
                got = [o for o in _match(working, cl, bmap)
                       if want is None or o.get("qty") == want]
                if got:
                    journal.append("MODIFY_CONFIRMED", acct, cl, payload=dict(
                        qty=got[0].get("qty"), source="recovery"))
                    report["resolved"].append((cl, "MODIFY_CONFIRMED_swept"))

    # ---- 4. EXIT sweep: ledger open, broker flat, closing fill present ----
    brk_net = {}
    for p in broker.positions():
        brk_net[p["account_id"]] = brk_net.get(p["account_id"], 0) + p["qty"]
    for (acct, cl), pos in list(journal.open_positions().items()):
        if brk_net.get(acct, 0) == 0:
            closers = [f for f in fills if f.get("closes_cl") == cl]
            if closers:
                journal.append("EXIT", acct, cl, payload=dict(
                    px=closers[-1].get("px"), qty=pos["qty"],
                    fill_id=closers[-1].get("fill_id"),
                    reason="closed_while_disconnected", source="recovery"))
                report["resolved"].append((cl, "EXIT_swept"))

    # ---- 5. rebuild beliefs + grace-free reconciliation ----
    report["beliefs"] = dict(
        open_positions=dict(journal.open_positions().items()),
        open_orders=journal.open_orders(),
    )
    rec = Reconciler(journal, broker, grace_cycles=1)
    report["discrepancies"] = rec.run(state_view=state_view, p3_params=p3_params)
    return report


def _known_lifecycles(journal):
    return [r[0] for r in journal.con.execute(
        "SELECT DISTINCT cl_ord_id FROM ledger"
        " WHERE cl_ord_id IS NOT NULL AND event_type='INTENT'").fetchall()]


def _ledger_filled_qty(journal, cl):
    q = 0
    for e in journal.events(cl):
        if e["event_type"] in ("FILL", "PARTIAL_FILL"):
            q += (e["payload"] or {}).get("qty", 0)
    return q


def _recorded_fill_ids(journal, cl):
    out = set()
    for e in journal.events(cl):
        if e["event_type"] in ("FILL", "PARTIAL_FILL"):
            fid = (e["payload"] or {}).get("fill_id")
            if fid is not None:
                out.add(str(fid))
    return out
