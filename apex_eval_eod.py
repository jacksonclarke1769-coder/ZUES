"""APEX eval — EOD drawdown rule (corrected 2026-06-27 per operator).

The earlier harness (apex_eval_deployed.py) used INTRADAY trailing: the threshold ratchets on the
unrealized tick high (mark(bal+mfe)) -> give-back busts. Operator confirms the eval is EOD drawdown:
  * threshold updates only at the DAILY CLOSE, from the end-of-day BALANCE (not the intraday high),
  * ratchets up on new EOD-balance highs, locks at start+$100 once an EOD balance hits start+trail+100,
  * during the session, if LIVE equity (balance + open unrealized loss) TOUCHES the threshold -> fail.
So intraday DOWNSIDE still liquidates, but intraday UPSIDE no longer ratchets the floor. Much gentler.

This reruns the deployed config + sizing grid under BOTH rules side by side so the rule's impact is explicit.
Streams generated once at size 1 (apex_eval_deployed generators), rescaled per config; $550 daily stop fixed.
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import apex_eval_deployed as H
import funded_rules as FR

SPEC = FR.APEX_ACCOUNTS["50K"]
EXPIRE_DAYS = 30
DAILY_STOP = -550.0
CONFIGS = [(14, 7, 8), (12, 6, 7), (10, 5, 6), (8, 4, 5), (6, 3, 4),
           (5, 3, 3), (4, 2, 2), (4, 2, 0), (3, 2, 0), (2, 1, 0)]


def eval_eod(ev, start, spec):
    """EOD-drawdown eval: threshold ratchets on END-OF-DAY balance highs only; intraday checks
    the DOWNSIDE (bal + trade MAE) against the day's fixed threshold; no intraday upside ratchet."""
    sb, tr, tg = spec["start"], spec["trailing"], spec["target"]
    lock = sb + 100.0
    thr = sb - tr; bal = sb; peak_eod = sb; locked = False
    t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0
    for i in range(start, len(ev)):
        e = ev[i]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if (ts - t0).days > EXPIRE_DAYS:
            return "EXPIRE", EXPIRE_DAYS
        if cur is None:
            cur = day
        if day != cur:                                   # EOD rollover: ratchet on prior day's CLOSE
            peak_eod = max(peak_eod, bal)
            if not locked:
                thr = max(thr, peak_eod - tr)
                if peak_eod - tr >= lock:
                    thr = lock; locked = True
            cur = day; dreal = 0.0
        if dreal <= DAILY_STOP:                           # $550 daily stop: no new entries
            continue
        if bal + min(0.0, e["mae"]) <= thr:              # intraday DOWNSIDE liquidation
            return "BUST", (ts - t0).days
        bal += e["pnl"]; dreal += e["pnl"]
        if bal >= sb + tg:                                # hit the profit target
            return "PASS", (ts - t0).days
    return "INCOMPLETE", None


def eval_eod_closeonly(ev, start, spec):
    """PURE-EOD (close-only): breach checked ONLY at the daily close on EOD balance — NO intraday
    liquidation. This is the too-lenient model that likely produced the stored 86%."""
    sb, tr, tg = spec["start"], spec["trailing"], spec["target"]
    lock = sb + 100.0
    thr = sb - tr; bal = sb; peak_eod = sb; locked = False
    t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0
    for i in range(start, len(ev)):
        e = ev[i]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if (ts - t0).days > EXPIRE_DAYS:
            return "EXPIRE", EXPIRE_DAYS
        if cur is None:
            cur = day
        if day != cur:
            if bal <= thr:                                # only the CLOSE can fail you
                return "BUST", (ts - t0).days
            peak_eod = max(peak_eod, bal)
            if not locked:
                thr = max(thr, peak_eod - tr)
                if peak_eod - tr >= lock:
                    thr = lock; locked = True
            cur = day; dreal = 0.0
        if dreal <= DAILY_STOP:
            continue
        bal += e["pnl"]; dreal += e["pnl"]
        if bal >= sb + tg:
            return "PASS", (ts - t0).days
    return "INCOMPLETE", None


def day_starts(ev):
    seen, starts = set(), []
    last = pd.Timestamp(ev[-1]["ts"])
    for i, e in enumerate(ev):
        d = pd.Timestamp(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - pd.Timestamp(e["ts"])).days > EXPIRE_DAYS:
            starts.append(i)
    return starts


def summarize(out):
    n = len(out)
    p = sum(1 for o in out if o[0] == "PASS")
    b = sum(1 for o in out if o[0] == "BUST")
    x = sum(1 for o in out if o[0] == "EXPIRE")
    pd_ = [o[1] for o in out if o[0] == "PASS"]
    return 100*p/n, 100*b/n, 100*x/n, (int(np.median(pd_)) if pd_ else None)


def main():
    print("generating unit streams…", flush=True)
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    df5 = H.load_bars()
    base = H.a_events(df5) + H.b_events(df5) + H.m_events(df5)
    print(f"  unit events: {len(base)}", flush=True)

    print(f"\n  Apex 50K · $2.5k trail / $3k target · $550 daily stop · 30-day clock  ·  PASS% by rule")
    print(f"  {'A/B/mm':>10}{'MNQ':>5}  |  {'INTRADAY-trail':>14}  |  {'EOD (real: close-set + intraday-liq)':>36}  |  {'pure-EOD (close-only)':>22}")
    print("  " + "-" * 96)
    for (a, b, m) in CONFIGS:
        sc = {"A": a, "B": b, "M": m}
        ev = [dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*sc[e["src"]],
                   mfe=e["mfe"]*sc[e["src"]], mae=e["mae"]*sc[e["src"]]) for e in base if sc[e["src"]] > 0]
        ev = H.apply_daily_stop(ev)
        starts = day_starts(ev)
        ip, ib, _, _ = summarize([H.eval_from(ev, s, SPEC) for s in starts])           # intraday trail (old)
        ep, eb, ex, emd = summarize([eval_eod(ev, s, SPEC) for s in starts])           # EOD real (correct)
        cp, cb, cx, _ = summarize([eval_eod_closeonly(ev, s, SPEC) for s in starts])   # pure EOD (lenient)
        star = " <-DEPLOYED" if (a, b, m) == (10, 5, 6) else ""
        print(f"  {f'{a}/{b}/{m}':>10}{a+b+m:>5}  |  {ip:>11.1f}%   |  "
              f"PASS {ep:>5.1f}  BUST {eb:>5.1f}  EXP {ex:>4.1f}  med {emd or 0:>2}  |  {cp:>18.1f}%{star}")
    print("\n  [note] INTRADAY-trail = my first harness (wrong rule). EOD-real = threshold set at close, BUT")
    print("         intraday equity still liquidates if it touches it (your own description). pure-EOD = close-only")
    print("         (no intraday liquidation) — the too-lenient model that ~reproduces the stored 86%.")


if __name__ == "__main__":
    main()
