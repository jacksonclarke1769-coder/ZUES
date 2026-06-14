"""PROMETHEUS order-flow workstream — Tradovate DOM/depth collector.

Records NQ depth-of-market snapshots to daily CSVs in ~/trading-team/data/orderflow/
(ts_utc, contract, bid/ask px+size for 10 levels). This builds the dataset Division 1
(order flow) needs — depth history cannot be bought retroactively at retail.

STATUS: frame parser is tested offline (--selftest + test_dom_collector.py).
Live loop is UNTESTED until the Tradovate key arrives (it reuses tradovate_client auth).
Collector is read-only market data: it cannot place, modify, or cancel anything.

Usage:
  python3 dom_collector.py --selftest          # offline parser check (no network)
  python3 dom_collector.py --symbol NQ         # live collection (requires credentials)
"""
import argparse, csv, json, os, time
from datetime import datetime, timezone

OUTDIR = os.path.expanduser("~/trading-team/data/orderflow")
LEVELS = 10
MD_WS = "wss://md.tradovateapi.com/v1/websocket"


# ----------------------------- frame parsing (pure, tested) -----------------------------
def parse_frame(raw):
    """SockJS-style frame -> list of DOM dicts. 'a[...]' carries events; 'h'/'o' -> []."""
    if not raw or raw[0] in ("o", "h"):
        return []
    if raw[0] != "a":
        return []
    out = []
    for msg in json.loads(raw[1:]):
        if isinstance(msg, dict) and msg.get("e") == "md":
            out.extend(msg.get("d", {}).get("doms", []))
    return out


def flatten_dom(dom, levels=LEVELS):
    """DOM dict -> flat row (ts_utc, contract_id, b1_px..bN_px, b1_sz.., a1_px.., a1_sz..)."""
    row = {"ts_utc": dom.get("timestamp") or datetime.now(timezone.utc).isoformat(),
           "contract_id": dom.get("contractId")}
    bids = sorted(dom.get("bids", []), key=lambda x: -x["price"])[:levels]
    asks = sorted(dom.get("offers", []), key=lambda x: x["price"])[:levels]
    for i in range(levels):
        b = bids[i] if i < len(bids) else {}
        a = asks[i] if i < len(asks) else {}
        row[f"b{i+1}_px"] = b.get("price"); row[f"b{i+1}_sz"] = b.get("size")
        row[f"a{i+1}_px"] = a.get("price"); row[f"a{i+1}_sz"] = a.get("size")
    return row


def csv_path(now=None):
    """Daily rotation: path recomputed at every flush -> new file each UTC day."""
    now = now or datetime.now(timezone.utc)
    return os.path.join(OUTDIR, f"NQ_dom_{now:%Y%m%d}.csv")


def evidence_log(msg, path=None):
    """Append-only operator evidence trail for collector start/stop/flush events."""
    path = path or os.path.join(OUTDIR, "collector_log.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} {msg}\n")


def append_rows(rows, path=None):
    if not rows:
        return 0
    path = path or csv_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if new:
            w.writeheader()
        w.writerows(rows)
    return len(rows)


# ----------------------------- selftest (offline) -----------------------------
SAMPLE = ('a[{"e":"md","d":{"doms":[{"contractId":123,"timestamp":"2026-06-12T14:31:00Z",'
          '"bids":[{"price":24750.25,"size":12},{"price":24750.0,"size":31}],'
          '"offers":[{"price":24750.5,"size":9},{"price":24750.75,"size":22}]}]}}]')


def selftest():
    doms = parse_frame(SAMPLE)
    assert len(doms) == 1, doms
    row = flatten_dom(doms[0])
    assert row["b1_px"] == 24750.25 and row["b1_sz"] == 12
    assert row["a1_px"] == 24750.5 and row["a2_sz"] == 22
    assert row["b3_px"] is None                      # sparse book pads with None
    assert parse_frame("h") == [] and parse_frame("o") == []
    print("selftest OK — parser + flattener behave; live loop awaits credentials")


# ----------------------------- live loop (untested until key arrives) -------------------
def live(symbol):
    import websocket                                  # pip install websocket-client
    from tradovate_client import TradovateClient
    import config
    cli = TradovateClient(config.TRADOVATE, config.HOSTS)
    cli.authenticate()
    contract = cli.resolve_front_month(symbol)
    ws = websocket.create_connection(MD_WS, timeout=30)
    assert ws.recv()[0] == "o"
    ws.send(f"authorize\n1\n\n{cli.access_token}")
    ws.recv()
    ws.send(f'md/subscribeDOM\n2\n\n{json.dumps({"symbol": contract["id"]})}')
    print(f"collecting DOM for {symbol} (contract {contract['id']}) -> {csv_path()}")
    evidence_log(f"START symbol={symbol} contract={contract['id']}")
    buf = []
    last_flush = time.time()
    written = 0
    try:
        while True:
            raw = ws.recv()
            if raw and raw[0] == "h":
                ws.send("[]")                         # heartbeat reply keeps stream alive
                continue
            for dom in parse_frame(raw):
                buf.append(flatten_dom(dom))
            if time.time() - last_flush > 5 and buf:
                written += append_rows(buf)           # csv_path() inside -> daily rotation
                buf = []; last_flush = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        # SAFE SHUTDOWN: flush remaining rows, close socket, leave evidence
        if buf:
            written += append_rows(buf)
        try:
            ws.close()
        except Exception:
            pass
        evidence_log(f"STOP rows_written={written}")
        print(f"\nsafe shutdown — {written} rows written, evidence logged")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--symbol", default="NQ")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    else:
        live(a.symbol)
