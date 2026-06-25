"""
SHADOW OVERLAY — observe-only forward test of the Profile A stop-cap (research finding 2026-06-26).

Research showed: skipping Profile A trades whose stop is wider than ~80pt roughly HALVES the worst-day
tail ($-808 vs $-1,713 @4MNQ) at ~zero expectancy cost. Before trusting a backtest we measure it LIVE.

This records what the cap WOULD do to every resolved trade WITHOUT touching execution — it never blocks,
modifies, or places an order. Profile A trades with stop > cap_pts are flagged 'would-skip'; everything
else is 'kept'. A running tally (this run + the on-disk JSONL across runs) lets us compare the unchanged
live BASELINE vs the cap-filtered book over forward sessions. Cap is Profile A ONLY (the research scope);
Profile B trades are recorded as context and always kept. Fail-safe: any error is swallowed.

CLI:  python3 shadow_overlay.py [path]   -> prints the baseline-vs-capped comparison from the log.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict

DEFAULT_PATH = "logs/shadow/stop_cap.jsonl"
DEFAULT_CAP = 80.0


class ShadowOverlay:
    def __init__(self, cap_pts=DEFAULT_CAP, path=DEFAULT_PATH, notify=None):
        self.cap = float(cap_pts)
        self.path = path
        self.notify = notify
        self.rows = []                  # rows recorded THIS run

    # ---- observe one resolved trade (called from TradeJournal.on_resolved) ----
    def record(self, profile, side, entry, stop, r, pnl, reason, ts):
        try:
            risk = abs(float(entry) - float(stop))
            is_a = str(profile).upper() == "A"
            keep = (risk <= self.cap) if is_a else True       # cap scopes to Profile A only
            row = dict(ts=str(ts), profile=str(profile), side=str(side), risk_pts=round(risk, 2),
                       cap_keep=bool(keep), would_skip=bool(is_a and not keep),
                       r=round(float(r or 0), 3), pnl=round(float(pnl or 0), 2),
                       reason=str(reason), cap_pts=self.cap)
            self.rows.append(row)
            if self.path:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with open(self.path, "a") as f:
                    f.write(json.dumps(row, default=str) + "\n")
            if row["would_skip"]:
                print(f"[shadow] would-SKIP Profile A {side} (stop {risk:.0f}pt > {self.cap:.0f}) "
                      f"— live took it ({r:+.2f}R); cap-book excludes it", flush=True)
            return row
        except Exception as e:                                # noqa: BLE001 — never breaks trading
            print(f"[shadow] record failed: {type(e).__name__}: {e}", flush=True)
            return None

    # ---- compare baseline (all A) vs cap-filtered (A with stop<=cap) ----
    @staticmethod
    def summarize(rows, cap=DEFAULT_CAP):
        a = [x for x in rows if str(x.get("profile", "")).upper() == "A"]
        kept = [x for x in a if x.get("cap_keep", True)]
        skip = [x for x in a if not x.get("cap_keep", True)]

        def agg(rs):
            return dict(n=len(rs), totR=round(sum(x["r"] for x in rs), 2),
                        totUSD=round(sum(x["pnl"] for x in rs), 2))

        def worst_day(rs):
            d = defaultdict(float)
            for x in rs:
                d[str(x["ts"])[:10]] += x["pnl"]
            return round(min(d.values()), 2) if d else 0.0

        base, cb = agg(a), agg(kept)
        return dict(cap_pts=cap, baseline=base, capped=cb,
                    skipped_n=len(skip), skipped_R=round(sum(x["r"] for x in skip), 2),
                    skipped_USD=round(sum(x["pnl"] for x in skip), 2),
                    worst_day_baseline=worst_day(a), worst_day_capped=worst_day(kept))

    def summary(self):
        return self.summarize(self.rows, self.cap)

    # ---- short one-liner for Telegram / heartbeat ----
    def tg_summary(self):
        s = self.summary(); b, c = s["baseline"], s["capped"]
        if b["n"] == 0:
            return f"🧪 <b>Shadow stop-cap ≤{int(self.cap)}pt</b>\nno Profile A trades observed yet"
        return (f"🧪 <b>Shadow stop-cap ≤{int(self.cap)}pt</b> (observe-only, A)\n"
                f"• Baseline (all A): {b['n']} tr · {b['totR']:+.1f}R · ${b['totUSD']:+,.0f} · worst-day ${s['worst_day_baseline']:,.0f}\n"
                f"• Capped book: {c['n']} tr · {c['totR']:+.1f}R · ${c['totUSD']:+,.0f} · worst-day ${s['worst_day_capped']:,.0f}\n"
                f"• Cap would have SKIPPED {s['skipped_n']} (={s['skipped_R']:+.1f}R / ${s['skipped_USD']:+,.0f})")


def load(path=DEFAULT_PATH):
    rows = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
    return rows


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    rows = load(p)
    s = ShadowOverlay.summarize(rows)
    b, c = s["baseline"], s["capped"]
    print(f"\nSHADOW STOP-CAP <= {s['cap_pts']:.0f}pt  (Profile A, observe-only)  ·  {len(rows)} rows in {p}")
    print(f"  BASELINE (all A) : {b['n']:>3} tr · {b['totR']:+7.1f}R · ${b['totUSD']:+10,.0f} · worst-day ${s['worst_day_baseline']:+,.0f}")
    print(f"  CAPPED   (<=cap) : {c['n']:>3} tr · {c['totR']:+7.1f}R · ${c['totUSD']:+10,.0f} · worst-day ${s['worst_day_capped']:+,.0f}")
    print(f"  WOULD-SKIP       : {s['skipped_n']:>3} tr · {s['skipped_R']:+7.1f}R · ${s['skipped_USD']:+10,.0f}")
    if b["n"]:
        dR = c["totR"] - b["totR"]; dWD = s["worst_day_capped"] - s["worst_day_baseline"]
        print(f"  => cap effect: {dR:+.1f}R on total, worst-day {dWD:+,.0f} "
              f"({'safer' if dWD > 0 else 'no tail benefit yet'})")
