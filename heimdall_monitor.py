"""HEIMDALL heartbeat + dead-man monitor.

The live process proves it is ALIVE by writing a heartbeat (atomically) on a timer. The dead-man
reads that heartbeat and reports OK / WARN / RED by age. A frozen process, crashed runner, or
silent stall stops the heartbeat -> dead-man RED -> dashboard red + entries blocked.

Heartbeat = liveness of the PROCESS; the `data_state` field inside it = liveness of the FEED.
The two are distinct: a stale feed still updates the heartbeat (process alive) but reports
data_state RED; a frozen process stops the heartbeat entirely.
"""
import json
import os
from datetime import datetime, timezone

HEARTBEAT_PATH = "out/heimdall/heartbeat.json"
WARN_S = 60        # heartbeat older than this -> WARN (a few missed ~20s ticks)
RED_S = 180        # heartbeat older than this -> RED (process likely frozen/crashed)


def write_heartbeat(fields, path=HEARTBEAT_PATH, now=None):
    """Atomically write the heartbeat. `fields` is a dict; `ts` is stamped here."""
    now = now or datetime.now(timezone.utc)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = dict(fields)
    data["ts"] = now.isoformat()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)        # atomic swap — readers never see a half-written file
    return data


def read_heartbeat(path=HEARTBEAT_PATH):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def entry_ready(data_state, deadman):
    """(ok, reason) for routing a NEW entry. Blocks unless data is GREEN and the dead-man is alive.
    data_state = (state, reason) tuple from the feed; deadman = deadman_status() dict."""
    st, why = data_state
    if st != "GREEN":
        return False, "data %s (%s)" % (st, why)
    if not deadman.get("alive"):
        return False, "dead-man %s" % deadman.get("reason")
    return True, "ok"


def deadman_status(path=HEARTBEAT_PATH, now=None, warn_s=WARN_S, red_s=RED_S):
    """{state: OK|WARN|RED, age_s, reason, alive}. alive=False on WARN? No — alive=False only on
    RED/missing (the condition that must block entries + turn the dashboard red)."""
    now = now or datetime.now(timezone.utc)
    hb = read_heartbeat(path)
    if not hb or "ts" not in hb:
        return dict(state="RED", age_s=None, reason="no heartbeat (dead-man missing)", alive=False)
    try:
        ts = datetime.fromisoformat(hb["ts"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = (now - ts).total_seconds()
    except Exception:
        return dict(state="RED", age_s=None, reason="bad heartbeat timestamp", alive=False)
    if age > red_s:
        return dict(state="RED", age_s=round(age), reason="heartbeat stale %ds" % int(age), alive=False)
    if age > warn_s:
        return dict(state="WARN", age_s=round(age), reason="heartbeat lagging %ds" % int(age), alive=True)
    return dict(state="OK", age_s=round(age), reason="fresh", alive=True)
