"""MONDAY PROOF — TradingView live-bar probe. Connects to the TV CDP feed, pulls the
warmup tail + a few live bars, and verifies the feed is fit for the paper session:
bars advancing, fresh, monotonic timestamps, no duplicates, no out-of-order. READ-ONLY —
no orders, no engine, no sends. Run BEFORE the paper session; if it fails, do not run.

    python3 tools/probe_tradingview_bars.py --duration 180
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=180, help="seconds to watch live bars")
    ap.add_argument("--res", default="1", help="expected resolution (1 = 1m)")
    a = ap.parse_args()
    try:
        from tv_feed import TradingViewFeed
    except Exception as e:                                # noqa: BLE001
        print(f"FAIL: cannot import tv_feed ({e})"); return 2

    try:
        feed = TradingViewFeed(poll_sec=10, warmup=200, expect_res=a.res)
        contract = feed.connect()
    except Exception as e:                                # noqa: BLE001
        print(f"FAIL: CDP connect failed — is Chrome up on :9222 with TradingView loaded? ({e})")
        return 2
    print(f"CDP connected · {contract.get('name')} @ {contract.get('resolution')}m")

    hist = list(feed.history())
    if not hist:
        print("FAIL: no warmup bars returned"); return 2
    ds = feed.data_status() if hasattr(feed, "data_status") else {}
    print(f"warmup bars: {len(hist)} · last {hist[-1][0]} · DATA_READY={ds.get('DATA_READY')} "
          f"· basis {ds.get('basis')}")

    seen = set(t for t, *_ in hist)
    last_ts = hist[-1][0]
    dupes = ooo = fresh = 0
    print(f"watching live bars for {a.duration}s …")
    t0 = time.time()
    for ts, o, h, l, c in feed.live():
        key = ts.isoformat()
        if key in seen:
            dupes += 1
        elif ts <= last_ts:
            ooo += 1
            print(f"  OUT-OF-ORDER: {ts} <= {last_ts}")
        else:
            fresh += 1
            last_ts = ts
            print(f"  bar {ts}  O{o} H{h} L{l} C{c}")
        seen.add(key)
        if time.time() - t0 >= a.duration:
            break

    ok = (fresh >= 1 and dupes == 0 and ooo == 0)
    print(f"\nfresh={fresh} duplicates={dupes} out_of_order={ooo}")
    state = feed.data_state()[0] if hasattr(feed, "data_state") else "?"
    print(f"data_state={state}")
    print("PROBE PASS — bars advancing, monotonic, no dupes" if ok and state == "GREEN"
          else "PROBE FAIL — do NOT run the paper session until this is clean")
    return 0 if (ok and state == "GREEN") else 1


if __name__ == "__main__":
    sys.exit(main())
