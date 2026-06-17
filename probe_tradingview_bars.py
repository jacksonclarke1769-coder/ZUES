"""Probe the live TradingView CDP feed before a live run: bars advancing, fresh, no dup/out-of-order.
Read-only (no orders, no strategy). PASS only if NQ/MNQ, fresh (<5m), monotonic, and advancing.

  python3 probe_tradingview_bars.py --duration 120
"""
import argparse
import time

import pandas as pd

from tv_feed import _CDP, _read_bars_js, _CHART

NY = "America/New_York"


def snap(c, n=8):
    sym = c.eval(_CHART + ".symbol()")
    res = c.eval(_CHART + ".resolution()")
    raw = c.eval(_read_bars_js(n))
    bars = [pd.Timestamp(int(r[0]), unit="s", tz="UTC").tz_convert(NY) for r in (raw or [])]
    return sym, res, bars


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--duration", type=int, default=120, help="seconds to watch for a new bar (0=snapshot only)")
    p.add_argument("--symbol", default="")
    a = p.parse_args(argv)

    c = _CDP(); c.connect()
    sym, res, bars = snap(c)
    if not bars:
        print("PROBE: FAIL — no bars from chart"); c.close(); return 1
    now = pd.Timestamp.now("UTC").tz_convert(NY)
    last = bars[-1]
    age = (now - last).total_seconds()
    dup = len(bars) != len(set(bars))
    ooo = any(bars[i] >= bars[i + 1] for i in range(len(bars) - 1))
    print(f"symbol={sym} res={res}m | latest bar {last.strftime('%H:%M')} age={age:.0f}s | dup={dup} ooo={ooo}")

    advanced = age < 120
    if a.duration > 0 and not advanced:
        t0 = time.time()
        while time.time() - t0 < a.duration:
            time.sleep(20)
            _, _, b2 = snap(c)
            if b2 and b2[-1] > last:
                advanced = True
                print(f"  bar advanced -> {b2[-1].strftime('%H:%M')}")
                break
    c.close()

    is_nq = "NQ" in str(sym).upper()
    ok = is_nq and (not dup) and (not ooo) and age < 300 and advanced
    print("checks: NQ=%s fresh(<300s)=%s monotonic=%s advancing=%s" %
          (is_nq, age < 300, (not dup and not ooo), advanced))
    print("PROBE:", "PASS ✓" if ok else "CHECK — do NOT go live")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
