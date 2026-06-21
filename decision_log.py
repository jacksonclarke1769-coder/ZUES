"""ARGUS — append-only live-engine decision logger.

One JSONL row per engine decision point so a ZERO-TRADE session is provable:
the engine checked, no setup existed (or a candidate was rejected/blocked), and
nothing was silently missed. Rows land in logs/live_engine_decisions/<ET-date>.jsonl.

HARD RULES (enforced here):
  * never logs webhook URLs / tokens / keys / secrets (key + value scrub)
  * a logging failure NEVER raises into the engine and NEVER affects a send
    (every public call is wrapped fail-safe and returns None on error)
  * append-only; one valid JSON object per line
"""
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SCHEMA_VERSION = 1
LOG_DIR = "logs/live_engine_decisions"
NY = ZoneInfo("America/New_York")
EXIT_MODEL = "EXIT3_FIXED_PARTIAL"

FINAL_ACTIONS = {
    "no_signal", "candidate_rejected", "data_blocked", "d1c_blocked", "ares_blocked",
    "exitlock_blocked", "paper_signal", "live_send", "skipped", "error",
}
_SECRET_HINTS = ("url", "token", "apikey", "api_key", "key", "secret", "webhook", "password", "auth")


def _scrub(d):
    """Drop secret-ish keys entirely; redact any URL-looking value. Defense in depth."""
    out = {}
    for k, v in d.items():
        if any(h in str(k).lower() for h in _SECRET_HINTS):
            continue
        if isinstance(v, str) and ("http://" in v or "https://" in v):
            v = "[redacted]"
        out[k] = v
    return out


class DecisionLogger:
    def __init__(self, account, mode, session_id, profile="A", feed_source=None,
                 engine_timeframe="5m", log_dir=LOG_DIR):
        self.account = account
        self.mode = mode
        self.session_id = session_id
        self.profile = profile
        self.feed_source = feed_source
        self.engine_timeframe = engine_timeframe
        self.log_dir = log_dir

    # ---- core (fail-safe) ----
    def log(self, final_action, **fields):
        try:
            if final_action not in FINAL_ACTIONS:
                fields.setdefault("rejection_reason", f"bad_final_action:{final_action}")
                final_action = "error"
            utc = datetime.now(timezone.utc)
            et = utc.astimezone(NY)
            row = dict(
                schema_version=SCHEMA_VERSION, session_id=self.session_id,
                timestamp_utc=utc.isoformat(), timestamp_et=et.isoformat(),
                account=self.account, mode=self.mode, profile=self.profile,
                feed_source=self.feed_source, engine_timeframe=self.engine_timeframe,
                exit_model=EXIT_MODEL, final_action=final_action)
            row.update(fields)
            row = _scrub(row)
            os.makedirs(self.log_dir, exist_ok=True)
            path = os.path.join(self.log_dir, et.date().isoformat() + ".jsonl")
            with open(path, "a") as fh:
                fh.write(json.dumps(row, default=str) + "\n")
            return path
        except Exception:                          # noqa: BLE001 — NEVER raise into the engine
            return None

    # ---- convenience row builders ----
    def no_signal(self, bar_ts, **ds):
        return self.log("no_signal", bar_ts=str(bar_ts), candidate_detected=False, **ds)

    def candidate_rejected(self, *, bar_ts, side, reason, entry=None, stop=None, target=None, **ds):
        return self.log("candidate_rejected", bar_ts=str(bar_ts), candidate_detected=True,
                        side=side, rejection_reason=reason, entry_price=entry,
                        stop_price=stop, tp2_target=target, **ds)

    def blocked(self, gate, *, bar_ts, side, reason, **ds):
        """gate in {data, d1c, ares, exitlock} -> final_action <gate>_blocked."""
        fa = f"{gate}_blocked"
        return self.log(fa, bar_ts=str(bar_ts), candidate_detected=True, side=side,
                        rejection_reason=reason, **ds)

    def signal(self, *, bar_ts, side, entry, stop, qty_total, tp1_qty, tp1_target,
               tp2_qty, tp2_target, signal_id_base, webhook_sent, traderspost_status=None,
               live=False, **ds):
        return self.log("live_send" if live else "paper_signal",
                        bar_ts=str(bar_ts), candidate_detected=True, side=side,
                        entry_price=entry, stop_price=stop, qty_total=qty_total,
                        tp1_qty=tp1_qty, tp1_target=tp1_target, tp2_qty=tp2_qty,
                        tp2_target=tp2_target, signal_id_base=signal_id_base,
                        webhook_intended=True, webhook_sent=webhook_sent,
                        traderspost_status=traderspost_status, **ds)
