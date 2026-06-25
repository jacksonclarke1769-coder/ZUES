"""
TRADE JOURNAL — records every resolved trade for LEARNING, with a 'why it won/lost' narrative.

Beyond the P&L ledger (trade_results) this captures the full context of each trade and classifies it
against the model's VALIDATED forensics (memory: losers = fast whipsaw stops; winners = >2h runners;
'gave-back' = reached +1R then reversed = an exit leak, NOT a bad entry). Writes one JSON line per
trade to logs/journal/<date>.jsonl (structured) + prints the human 'why'.

POST-EXIT WATCH: when a trade STOPS OUT it is watched for `post_exit_bars` more bars; if its target
would have been hit, the entry is updated with 'stopped early — right direction, wrong timing' — the
single most useful learning signal (separates a bad ENTRY from a bad EXIT/timing).
"""
from __future__ import annotations

import json
import os

JOURNAL_DIR = "logs/journal"


def classify(reason, r, reached_1r, reached_2r, hold_bars):
    """Return (tag, why) — the learning label + a one-line human reason, from resolution context."""
    r = float(r or 0.0)
    hold = hold_bars if hold_bars is not None else 99
    if r > 0:
        if reason == "target":
            return ("WIN_CLEAN", f"✅ CLEAN WIN — broke and ran straight to target (+{r:.1f}R). Thesis played out.")
        if reason in ("eod", "timeout", "forced"):
            return ("WIN_RUNNER", f"✅ RUNNER — rode the move to +{r:.1f}R, held to {reason}. The model's edge: the right-tail runner that carries the book.")
        return ("WIN_PARTIAL", f"✅ WIN — banked +{r:.1f}R via {reason}" + (" (hit +1R partial)." if reached_1r else "."))
    # losses
    if reason in ("eod", "timeout", "forced"):
        return ("LOSS_FADE", f"❌ FADE — held to {reason}, closed {r:+.1f}R. Drifted, never resolved to target or stop.")
    # stop-out
    if reached_1r:
        return ("LOSS_GAVEBACK", f"❌ GAVE BACK — reached +1R then reversed into the stop ({r:+.1f}R). An EXIT/timing leak, not a bad entry.")
    if hold <= 3:
        return ("LOSS_WHIPSAW", f"❌ WHIPSAW STOP — reversed within {hold} bars of entry ({r:+.1f}R). The model's #1 loss type: fast chop. One of the small losses the runners pay for.")
    return ("LOSS_WRONG", f"❌ WRONG WAY — stopped, never got going ({r:+.1f}R). Entry thesis failed (bad level / counter-move).")


class TradeJournal:
    def __init__(self, account, mode, path_dir=JOURNAL_DIR, post_exit_bars=78, notify=None, today=None):
        self.account = account
        self.mode = mode
        self.peb = post_exit_bars          # ~90 min on 5m bars
        self.notify = notify
        self._dir = path_dir
        self._today = today                # injectable date string for the filename (tests)
        self.entries = []
        self.watching = []                 # stopped trades pending post-exit review

    def _path(self, ts):
        d = self._today or str(ts)[:10]
        os.makedirs(self._dir, exist_ok=True)
        return os.path.join(self._dir, f"{d}.jsonl")

    def _write(self, rec):
        try:
            with open(self._path(rec["ts"]), "a") as f:
                f.write(json.dumps(rec, default=str) + "\n")
        except Exception as e:                              # noqa: BLE001 — journaling must never break trading
            print(f"[journal] write failed: {e!r}", flush=True)

    # ---- record a resolved trade ----
    def on_resolved(self, profile, side, qty, entry, stop, target, exit_px, reason, r, pnl,
                    ts, reached_1r=False, reached_2r=False, hold_bars=None):
        tag, why = classify(reason, r, reached_1r, reached_2r, hold_bars)
        rec = dict(ts=str(ts), account=self.account, mode=self.mode, profile=profile, side=side,
                   qty=qty, entry=round(float(entry), 2), stop=round(float(stop), 2),
                   target=(round(float(target), 2) if target else None),
                   exit=(round(float(exit_px), 2) if exit_px is not None else None),
                   reason=reason, R=round(float(r or 0), 2), pnl=round(float(pnl or 0), 0),
                   hold_bars=hold_bars, tag=tag, why=why, post_exit=None)
        self.entries.append(rec)
        self._write(rec)
        print(f"[journal] {profile} {side} {reason} {r:+.2f}R — {why}", flush=True)
        if self.notify is not None:
            self.notify.send(f"📓 <b>Journal — Profile {profile} {str(side).upper()}</b>\n{why}")
        if reason == "stop" and target:                     # watch for a post-exit target hit
            d = 1 if str(side).lower() in ("long", "buy") else -1
            self.watching.append(dict(rec=rec, d=d, target=float(target), left=self.peb, n=0))
        return rec

    # ---- advance post-exit watches on each new bar ----
    def on_bar(self, high, low):
        still = []
        for w in self.watching:
            w["n"] += 1; w["left"] -= 1
            hit = (high >= w["target"]) if w["d"] > 0 else (low <= w["target"])
            if hit:
                note = (f"⚠ STOPPED EARLY — target would have hit {w['n']} bars after the stop "
                        f"(right direction, wrong timing). Whipsaw, not a wrong call.")
                w["rec"]["post_exit"] = note
                self._write(dict(w["rec"], _amended=True))
                print(f"[journal] post-exit: {note}", flush=True)
                if self.notify is not None:
                    self.notify.send(f"📓 {note}")
            elif w["left"] > 0:
                still.append(w)
        self.watching = still
