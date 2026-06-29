"""Feed watchdog + auto-reload self-healer.

Monitors the live data pipe and, when the browser feed FREEZES (Chrome render-throttle stalls the
chart's 1m bar series), automatically recovers it:
    freeze detected -> reload chart tab via CDP -> if still frozen -> relaunch Chrome
with a cooldown, an attempt cap, and a market-hours guard (no thrashing reloads overnight/weekends).

Read-only on trading state. Does NOT place orders or touch strategy/D1c/sizing. A heal causes a brief
feed reset, which the runner's reconnect-tolerant readiness handles (YELLOW -> GREEN). On any
degradation it also writes a SEMI_AUTO_ONLY marker. Supervised live auto stays gated elsewhere.

Run:  python3 feed_watch.py --heal             # monitor + auto-heal, 60s
      python3 feed_watch.py --once             # single check (spot-report, no heal)
"""
import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from store import Store
import heimdall_monitor as H

LOG = "logs/feed-watch.log"
MARKER = "out/heimdall/FEED_DEGRADED.flag"
LAUNCH_SCRIPT = os.path.expanduser("~/trading-team/tools/launch-tv-chrome.sh")
ET = ZoneInfo("America/New_York")

FREEZE_HEAL_S = 300      # last-bar age beyond this (during a session) = frozen -> heal
HEAL_COOLDOWN_S = 180    # min seconds between heal attempts (let a reload take effect)
MAX_HEALS = 3            # attempts before giving up (reload, reload, relaunch) -> then manual


# ----------------------------- pure decision helpers (testable) -----------------------------
def market_likely_open(now_et):
    """NQ trades Globex Sun 18:00 ET -> Fri 17:00 ET, minus the daily 17:00-18:00 maintenance break.
    Returns False when bars legitimately should NOT be flowing (so we don't thrash heals)."""
    wd = now_et.weekday()              # Mon=0 .. Sun=6
    t = now_et.time()
    from datetime import time as _t
    if wd == 5:                        # Saturday
        return False
    if wd == 6 and t < _t(18, 0):      # Sunday before reopen
        return False
    if wd == 4 and t >= _t(17, 0):     # Friday after close
        return False
    if _t(17, 0) <= t < _t(18, 0):     # daily maintenance break
        return False
    return True


def heal_decision(data_age_s, market_open, secs_since_last_heal, attempts,
                  freeze_s=FREEZE_HEAL_S, cooldown_s=HEAL_COOLDOWN_S, max_heals=MAX_HEALS):
    """(do_heal, action). action in {reload, relaunch, no:<reason>}."""
    if not market_open:
        return False, "no:market-closed"
    if (data_age_s or 0) <= freeze_s:
        return False, "no:fresh"
    if secs_since_last_heal < cooldown_s:
        return False, "no:cooldown"
    if attempts >= max_heals:
        return False, "no:exhausted"
    return True, ("reload" if attempts < max_heals - 1 else "relaunch")


# ----------------------------- snapshot -----------------------------
def snapshot(now=None):
    now = now or datetime.now(timezone.utc)
    ds = H.apply_freshness(json.loads(Store().get_state("data_status") or "{}"), now)
    dm = H.deadman_status(now=now)
    hb = H.read_heartbeat() or {}
    state = ds.get("data_state")
    healthy = (state == "GREEN" and bool(ds.get("DATA_READY")) and dm.get("alive")
               and not ds.get("reconnecting") and hb.get("guardian") == "armed")
    return dict(
        healthy=healthy, data_state=state, data_ready=bool(ds.get("DATA_READY")),
        last_bar=ds.get("last_bar"), last_bar_age_s=ds.get("last_bar_age_s"),
        deadman=dm.get("state"), reset_count=ds.get("reset_count"),
        reconnecting=ds.get("reconnecting"), out_of_order=ds.get("out_of_order"),
        gaps=ds.get("gaps"), d1c_mode=hb.get("d1c_mode"), guardian=hb.get("guardian"))


def _reasons(s, prev_last_bar):
    r = []
    if s["data_state"] != "GREEN":
        r.append("data_state=%s" % s["data_state"])
    if not s["data_ready"]:
        r.append("DATA_READY=false")
    if s["deadman"] != "OK":
        r.append("dead-man=%s" % s["deadman"])
    if s["reconnecting"]:
        r.append("reconnecting")
    if s["guardian"] != "armed":
        r.append("guardian=%s" % s["guardian"])
    if (s.get("out_of_order") or 0) > 0:
        r.append("out_of_order=%s" % s["out_of_order"])
    if prev_last_bar is not None and s["last_bar"] == prev_last_bar and (s.get("last_bar_age_s") or 0) > 240:
        r.append("bars not advancing (frozen %ss)" % s.get("last_bar_age_s"))
    return r


def _log(line):
    os.makedirs(os.path.dirname(LOG) or ".", exist_ok=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


# ----------------------------- heal actions -----------------------------
def heal_reload_tab():
    """Reload the TradingView chart page via CDP — re-initialises the chart widget + data sub."""
    try:
        from tv_feed import _CDP
        c = _CDP(); c.connect()
        try:
            c.eval("location.reload()")     # ws may drop as the page reloads; that's expected
        except Exception:
            pass
        c.close()
        return True
    except Exception as e:
        _log("    heal: tab reload error: %s" % e)
        return False


def heal_relaunch_chrome():
    """Heavier recovery: kill the :9222 Chrome and relaunch it (anti-throttle flags) via the script."""
    try:
        subprocess.run("pkill -f 'remote-debugging-port=9222'", shell=True, timeout=10)
        time.sleep(3)
        subprocess.run([LAUNCH_SCRIPT], timeout=60)
        return True
    except Exception as e:
        _log("    heal: chrome relaunch error: %s" % e)
        return False


def run(interval=60, once=False, heal=False):
    prev_last_bar = None
    last_heal = datetime(1970, 1, 1, tzinfo=timezone.utc)
    attempts = 0
    while True:
        now = datetime.now(timezone.utc)
        s = snapshot(now)
        reasons = _reasons(s, prev_last_bar)
        tag = "OK   " if (s["healthy"] and not reasons) else "ALERT"
        _log("%s %s | state=%s ready=%s last_bar=%s age=%ss dm=%s resets=%s oo=%s d1c=%s guardian=%s" % (
            now.strftime("%H:%M:%SZ"), tag, s["data_state"], s["data_ready"], s["last_bar"],
            s["last_bar_age_s"], s["deadman"], s["reset_count"], s["out_of_order"],
            s["d1c_mode"], s["guardian"]))
        if reasons:
            os.makedirs(os.path.dirname(MARKER) or ".", exist_ok=True)
            with open(MARKER, "w") as f:
                f.write("SEMI_AUTO_ONLY %s — %s\n" % (now.isoformat(), "; ".join(reasons)))
        elif os.path.exists(MARKER):
            # Feed is healthy again — clear the stale degraded marker so the dashboard/preflight
            # don't keep reading a false SEMI_AUTO_ONLY state forever (write-on-degrade was never cleared).
            os.remove(MARKER)
            _log("    feed healthy — cleared %s" % MARKER)

        # --- auto-heal ---
        if heal:
            if s["healthy"]:
                if attempts:
                    _log("    heal: feed RECOVERED to GREEN after %d attempt(s)" % attempts)
                    attempts = 0
            else:
                mo = market_likely_open(now.astimezone(ET))
                do, action = heal_decision(s["last_bar_age_s"], mo,
                                           (now - last_heal).total_seconds(), attempts)
                if do:
                    attempts += 1
                    last_heal = now
                    if action == "reload":
                        _log("    HEAL #%d: reloading chart tab (frozen %ss)" % (attempts, s["last_bar_age_s"]))
                        heal_reload_tab()
                    else:
                        _log("    HEAL #%d: relaunching Chrome (reload did not resume bars)" % attempts)
                        heal_relaunch_chrome()
                elif action == "no:exhausted":
                    _log("    HEAL EXHAUSTED after %d attempts — MANUAL INTERVENTION needed; SEMI_AUTO_ONLY" % attempts)

        prev_last_bar = s["last_bar"]
        if once:
            return s
        time.sleep(interval)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--interval", type=int, default=60)
    p.add_argument("--once", action="store_true")
    p.add_argument("--heal", action="store_true", help="auto-recover a frozen browser feed")
    a = p.parse_args()
    run(interval=a.interval, once=a.once, heal=a.heal)
