"""
Lookahead self-test (shift-invariance): truncating the future must not change
past signals. For each TF, build detector context on the full buffered window
and on a truncated copy (last N 1m bars dropped); every candidate confirmed
more than a safety margin before the truncation point must be byte-identical
(idx, direction, mode, entry_price, stop_price) between the two runs. Abort the
survey if any detector fails.
"""
import sys
import numpy as np
import pandas as pd

from common import load_1m
from survey_engine import build_tf_context

TRUNCATE_1M_BARS = 8000     # dropped from the end
MARGIN_BARS_SIGNAL_TF = 200  # safety margin in signal-TF bars (>> 100-bar breaker/IFVG window)


def _key_set(cand: pd.DataFrame, cutoff_ts):
    if cand is None or not len(cand):
        return set()
    sub = cand[cand["conf_ts"] < cutoff_ts]
    keys = set()
    for r in sub.itertuples(index=False):
        keys.add((round(float(r.entry_price), 4), round(float(r.stop_price), 4),
                   int(r.direction), r.mode, r.conf_ts))
    return keys


def run():
    df1m = load_1m()
    all_ok = True
    for tf in (1, 5, 15):
        ctx_full = build_tf_context(df1m, tf)
        df1m_trunc = df1m.iloc[:-TRUNCATE_1M_BARS]
        ctx_trunc = build_tf_context(df1m_trunc, tf)
        trunc_end_ts = df1m_trunc.index[-1]
        margin = pd.Timedelta(minutes=tf * MARGIN_BARS_SIGNAL_TF)
        cutoff = trunc_end_ts - margin
        for concept in ctx_full["candidates"]:
            kf = _key_set(ctx_full["candidates"][concept], cutoff)
            kt = _key_set(ctx_trunc["candidates"][concept], cutoff)
            ok = kf == kt
            status = "OK" if ok else "FAIL"
            if not ok:
                all_ok = False
                missing_in_trunc = kf - kt
                extra_in_trunc = kt - kf
                print(f"[{status}] tf={tf} concept={concept} full={len(kf)} trunc={len(kt)} "
                      f"missing_in_trunc={len(missing_in_trunc)} extra_in_trunc={len(extra_in_trunc)}")
                for x in list(missing_in_trunc)[:3]:
                    print("   missing:", x)
                for x in list(extra_in_trunc)[:3]:
                    print("   extra:  ", x)
            else:
                print(f"[{status}] tf={tf} concept={concept} n_compared={len(kf)}")
    if not all_ok:
        print("LOOKAHEAD SELF-TEST FAILED — ABORT")
        sys.exit(1)
    print("LOOKAHEAD SELF-TEST: ALL DETECTORS PASS (shift-invariant)")


if __name__ == "__main__":
    run()
