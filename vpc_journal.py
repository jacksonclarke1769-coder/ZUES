"""
VPC lane telemetry / journals — ADDITIVE, fail-open (observational only).

Four append-only JSONL journals, one row per event, mirroring the repo's existing
`logs/journal/<date>.jsonl` convention (see trade_journal.py) and Profile A/B's store discipline:
  * signal      — every raw VPC trigger the engine emitted (side, stop_dist, atr, ts_signal)
  * fill_intent — every entry we intended to route (post-gate, sized qty, entry/stop payload sid)
  * missed_fill — a signal that did NOT become a fill (gate block, cap, budget, kill, disarmed)
  * rejection   — a payload/build/send rejection (fail-closed builder returned an error)

FAIL-OPEN: a journalling error NEVER raises into the engine/order path — it prints loudly (the
same lesson as trade_journal's ARGUS note) and returns. These journals are for observation and the
paper shadow; they gate nothing.
"""
import json
import os
from datetime import datetime, timezone

VPC_JOURNAL_DIR = "logs/vpc"
_KINDS = ("signal", "fill_intent", "missed_fill", "rejection")


def _utcnow():
    return datetime.now(timezone.utc).isoformat()


class VpcJournal:
    def __init__(self, account, mode, path_dir=VPC_JOURNAL_DIR, today=None):
        self.account = account
        self.mode = mode
        self.path_dir = path_dir
        self._today = today                 # test hook; None -> derive per-write

    def _path(self, kind):
        day = self._today or datetime.now(timezone.utc).date().isoformat()
        return os.path.join(self.path_dir, kind, f"{day}.jsonl")

    def _write(self, kind, row):
        """Append one JSONL row; fail-open (never raises)."""
        try:
            if kind not in _KINDS:
                raise ValueError(f"unknown VPC journal kind {kind!r}")
            path = self._path(kind)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            rec = dict(ts_log=_utcnow(), account=self.account, mode=self.mode,
                       profile="V", kind=kind, **row)
            with open(path, "a") as f:
                f.write(json.dumps(rec, default=str) + "\n")
            return path
        except Exception as e:              # noqa: BLE001 — fail-open, but LOUD
            print(f"[vpc-journal] ⚠ WRITE FAILED ({kind}): {e!r} — EVENT NOT RECORDED", flush=True)
            return None

    # -- the four observational journals -----------------------------------------------------------
    def signal(self, sig):
        return self._write("signal", dict(
            side=sig.get("side"), direction=sig.get("direction"), stop_dist=sig.get("stop_dist"),
            ts_signal=sig.get("ts_signal"), slot=sig.get("slot"), atr=sig.get("atr"),
            vwap=sig.get("vwap"), emission_mode=sig.get("emission_mode")))

    def fill_intent(self, *, ts_signal, side, qty, entry, stop, signal_id, why=""):
        return self._write("fill_intent", dict(
            ts_signal=ts_signal, side=side, qty=qty, entry=entry, stop=stop,
            signal_id=signal_id, why=why))

    def missed_fill(self, *, ts_signal, side, reason):
        return self._write("missed_fill", dict(ts_signal=ts_signal, side=side, reason=reason))

    def rejection(self, *, ts_signal, side, stage, error):
        return self._write("rejection", dict(ts_signal=ts_signal, side=side, stage=stage, error=error))
