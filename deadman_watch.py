"""O — External dead-man watchdog.

Runs as a SEPARATE process alongside auto_live.py. Polls the heartbeat written by the live bot;
if the heartbeat goes stale while the market is open, alerts the operator (Telegram) then fires an
emergency flatten via its own BridgeSender after a configurable grace period.

State machine per incident:
  OK ──(age > alert_s AND market open)──► ALERT  (telegram once)
     ──(age > flatten_s, still open)───► FLATTEN (bridge once)
     ──► HALTED-INCIDENT (no further action until heartbeat recovers)
     ──(heartbeat fresh again)──────────► OK

Safety:
- market_likely_open guard: never alert/flatten outside market hours.
- Dry-run by default: --live required to actually send webhooks.
- Single-instance lock: two watchdogs cannot coexist (data/deadman_watch.lock).

Usage:
  python3 deadman_watch.py --account APEX-50K-EVAL-1 --live
  python3 deadman_watch.py --account TEST --interval 1 --once   # single poll, test/verify
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import env_loader  # noqa: F401 — loads .env (TRADERSPOST_LIVE_URL, TELEGRAM_*)

from feed_watch import market_likely_open
from heimdall_monitor import read_heartbeat
from instance_lock import InstanceLock, LockHeld
from telegram_notify import Telegram

ET = ZoneInfo("America/New_York")

# ── State constants ──────────────────────────────────────────────────────────
STATE_OK = "OK"
STATE_ALERT = "ALERT"
STATE_FLATTEN = "FLATTEN"
STATE_HALTED = "HALTED-INCIDENT"

# ── Pure decision function (unit-testable without I/O) ───────────────────────

def decide(age_s, market_open, state, *, alert_s=180, flatten_s=420):
    """Pure state transition.

    Args:
        age_s:       heartbeat age in seconds (float/int); None = no heartbeat (treat as ∞).
        market_open: bool — from market_likely_open(now_et).
        state:       current STATE_* constant.
        alert_s:     age threshold to trigger ALERT (default 180s).
        flatten_s:   age threshold to trigger FLATTEN (default 420s).

    Returns:
        (new_state, action) where action ∈ {"none", "alert", "flatten", "recover"}.
    """
    if age_s is None:
        age_s = float("inf")

    # Recovery: heartbeat fresh while we were in an incident → back to OK
    if state in (STATE_ALERT, STATE_HALTED) and age_s <= alert_s and market_open:
        return STATE_OK, "recover"

    # If market closed, hold state but take no action
    if not market_open:
        return state, "none"

    if state == STATE_OK:
        if age_s > alert_s:
            return STATE_ALERT, "alert"
        return STATE_OK, "none"

    if state == STATE_ALERT:
        if age_s <= alert_s:
            return STATE_OK, "recover"
        if age_s > flatten_s:
            return STATE_FLATTEN, "flatten"
        return STATE_ALERT, "none"

    if state == STATE_FLATTEN:
        # Transition immediately to HALTED after one flatten cycle
        return STATE_HALTED, "none"

    if state == STATE_HALTED:
        # Waiting for recovery (handled above in the fresh-heartbeat check)
        return STATE_HALTED, "none"

    # Unknown state — fail safe: treat as OK
    return STATE_OK, "none"


# ── Heartbeat age helper ─────────────────────────────────────────────────────

def _heartbeat_age(path, now_utc):
    """Return age in seconds, or None if missing/unreadable."""
    hb = read_heartbeat(path)
    if not hb or "ts" not in hb:
        return None
    try:
        ts = datetime.fromisoformat(hb["ts"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (now_utc - ts).total_seconds()
    except Exception:
        return None


# ── Watchdog loop ────────────────────────────────────────────────────────────

def run(args):
    tg = Telegram(label="[deadman-watch]")
    live_url = os.environ.get("TRADERSPOST_LIVE_URL") if args.live else None
    mode = "live" if args.live else "dry-run"

    from bridge_sender import BridgeSender
    sender = BridgeSender(mode=mode, live_url=live_url)

    heartbeat_path = args.heartbeat_path or "out/heimdall/heartbeat.json"
    state = STATE_OK

    print(f"[deadman-watch] started account={args.account} mode={mode} "
          f"alert_s={args.alert_s} flatten_s={args.flatten_s} interval={args.interval}",
          flush=True)

    while True:
        now_utc = datetime.now(timezone.utc)
        now_et = now_utc.astimezone(ET)
        age = _heartbeat_age(heartbeat_path, now_utc)
        mopen = market_likely_open(now_et)

        new_state, action = decide(age, mopen, state,
                                   alert_s=args.alert_s, flatten_s=args.flatten_s)

        age_str = f"{age:.0f}s" if age is not None and age != float("inf") else "∞"
        print(f"[deadman-watch] age={age_str} market_open={mopen} "
              f"state={state}→{new_state} action={action}", flush=True)

        if action == "alert":
            msg = (f"⚠️ DEAD-MAN ALERT: auto_live heartbeat stale {age_str} "
                   f"(account={args.account}). Will flatten in "
                   f"{args.flatten_s - args.alert_s}s if not recovered.")
            tg.send(msg)
            print(f"[deadman-watch] ALERT: {msg}", flush=True)

        elif action == "flatten":
            # Fresh reason every firing (timestamp-based) — ensures unique signalId
            reason = f"deadman_emergency_{int(now_utc.timestamp())}"
            print(f"[deadman-watch] FLATTEN firing: account={args.account} reason={reason} "
                  f"mode={mode}", flush=True)
            if args.live:
                res = sender.flatten(args.account, reason=reason)
                ok = res.get("ok", False)
                msg = (f"🚨 DEAD-MAN FLATTEN {'OK' if ok else 'FAILED'}: "
                       f"account={args.account} reason={reason}")
            else:
                res = {"ok": None, "dry_run": True}
                msg = (f"[DRY-RUN] DEAD-MAN FLATTEN: account={args.account} "
                       f"reason={reason} (no webhook sent)")
            tg.send(msg)
            print(f"[deadman-watch] flatten result: {res}", flush=True)

        elif action == "recover":
            msg = (f"✅ DEAD-MAN RECOVERED: heartbeat fresh, account={args.account} "
                   f"state={state}→{new_state}")
            tg.send(msg)
            print(f"[deadman-watch] RECOVERED: {msg}", flush=True)

        state = new_state

        if args.once:
            break
        time.sleep(args.interval)


# ── CLI ──────────────────────────────────────────────────────────────────────

def _build_parser():
    p = argparse.ArgumentParser(description="ZEUS external dead-man watchdog")
    p.add_argument("--account", default="APEX-50K-EVAL-1",
                   help="TradersPost account label (default: APEX-50K-EVAL-1)")
    p.add_argument("--live", action="store_true",
                   help="Send live webhooks (default: dry-run, prints only)")
    p.add_argument("--alert-s", type=int, default=180,
                   help="Heartbeat age (s) that triggers ALERT (default: 180)")
    p.add_argument("--flatten-s", type=int, default=420,
                   help="Heartbeat age (s) that triggers FLATTEN (default: 420)")
    p.add_argument("--interval", type=int, default=30,
                   help="Poll interval seconds (default: 30)")
    p.add_argument("--heartbeat-path", default=None,
                   help="Override heartbeat file path (default: out/heimdall/heartbeat.json)")
    p.add_argument("--once", action="store_true",
                   help="Run a single poll and exit (for manual verification)")
    return p


def main():
    args = _build_parser().parse_args()
    lock = InstanceLock("data/deadman_watch.lock")
    try:
        lock.acquire()
    except LockHeld as e:
        print(f"[deadman-watch] ABORT: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        run(args)
    except KeyboardInterrupt:
        print("\n[deadman-watch] interrupted — exiting cleanly.", flush=True)
    finally:
        lock.release()


if __name__ == "__main__":
    main()
