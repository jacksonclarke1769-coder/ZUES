"""FlattenGuardian — wall-clock EOD + kill auto-flatten for the live engine.

Feed-INDEPENDENT by construction: a daemon thread checks the wall-clock Scheduler on its own
timer, so a stale/dead bar feed cannot leave a live position open past the flatten time
(THOR #1 kill path). On each tick it:
  * fires the bridge flatten (cancel working orders THEN exit) once per ET trading date at/after
    the session flatten time (14:30, or 12:45 on half days) — Profile A's flat-by rule, and
  * fires a kill-flatten the first time a lockout / operator kill / daily-loss stop is seen.

Fire-once survives restart (Scheduler fired-state persisted in the store). Does NOT change
Profile A/B/D1c logic — it only closes positions + cancels orders via the proven bridge path.

DB objects (Journal holds a persistent, thread-bound connection) are built INSIDE the guardian
thread via `build`; tests inject sender/store and call tick() directly on one thread.
"""
import json
import os
import threading
from datetime import datetime, timezone

from scheduler import Scheduler
from flatten import LOCK_KEY
from heimdall_monitor import write_heartbeat, HEARTBEAT_PATH


def _utcnow():
    return datetime.now(timezone.utc)


class FlattenGuardian:
    def __init__(self, account, *, build=None, sender=None, store=None, journal=None,
                 scheduler=None, poll_sec=20, root="MNQ", clock=_utcnow,
                 heartbeat_path=HEARTBEAT_PATH, hb_meta=None):
        self.account = account
        self.heartbeat_path = heartbeat_path
        self.hb_meta = hb_meta or {}
        self._build = build              # callable -> (sender, store, journal), run in-thread
        self.sender = sender
        self.store = store
        self.j = journal
        self.sched = scheduler or Scheduler()
        self.poll = poll_sec
        self.root = root
        self.clock = clock
        self._stop = threading.Event()
        self._thread = None
        self._kill_date = None           # ET date we've already kill-flattened
        if self.store is not None:
            self._restore()

    # ---- fire-once persistence (survives restart) ----
    def _restore(self):
        try:
            self.sched.restore_fired(json.loads(self.store.get_state("auto_flatten_fired") or "[]"))
        except Exception:
            pass

    def _persist_fired(self, now):
        try:
            self.store.set_state(auto_flatten_fired=json.dumps(self.sched.fired_today(now)))
        except Exception:
            pass

    def _ensure(self):
        if self.sender is None and self._build is not None:
            self.sender, self.store, self.j = self._build()
            self._restore()

    # ---- kill detection (same conditions as the live loop, read from the store) ----
    def _killed(self, et_date):
        if self.store.get_state(LOCK_KEY):
            return "emergency lockout"
        if self.store.get_state("auto_live_kill"):
            return "operator kill switch"
        try:
            from auto_safety import DailyGuard
            if DailyGuard(self.store).is_stopped(self.account, et_date):
                return "daily loss stop"
        except Exception:
            pass
        return None

    def _flatten(self, reason):
        res = self.sender.flatten(self.account, root=self.root,
                                  reason=f"{reason}-{int(self.clock().timestamp())}")
        c = res.get("cancel", {}); e = res.get("exit", {})
        print("[guardian] AUTO-FLATTEN (%s) -> cancel:%s | exit:%s" %
              (reason, c.get("reason", "sent"), e.get("reason", "sent")), flush=True)
        if self.j is not None:
            try:
                self.j.append("STATE_ASSERT", self.account,
                              payload=dict(action="auto_flatten", reason=reason, ok=res.get("ok")))
            except Exception:
                pass
        return res

    def _heartbeat(self, now):
        """Write the process heartbeat. Feed health is mirrored from the store's data_status."""
        ds = {}
        try:
            ds = json.loads(self.store.get_state("data_status") or "{}")
        except Exception:
            pass
        fields = dict(self.hb_meta)
        fields.update(
            pid=os.getpid(), account=self.account, guardian="armed",
            data_state=ds.get("data_state"), data_ready=ds.get("DATA_READY"),
            last_bar=ds.get("last_bar"), last_bar_age_s=ds.get("last_bar_age_s"),
            reset_count=ds.get("reset_count"), reconnecting=ds.get("reconnecting"),
            last_webhook=self.store.get_state("bridge_last_result"),
            flatten_fired=self.store.get_state("auto_flatten_fired"))
        write_heartbeat(fields, self.heartbeat_path, now)

    def tick(self):
        """One wall-clock check. Idempotent / fire-once per ET date. Always writes the heartbeat."""
        now = self.clock()
        et_date = self.sched.et(now).date().isoformat()
        if self.sched.flatten_due(now):
            self._flatten("EOD")
            self._persist_fired(now)
        kill = self._killed(et_date)
        if kill and self._kill_date != et_date:
            self._kill_date = et_date
            self._flatten("KILL:%s" % kill)
        self._heartbeat(now)

    def _run(self):
        self._ensure()
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as ex:
                print("[guardian] error: %s" % ex, flush=True)
            self._stop.wait(self.poll)

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True, name="flatten-guardian")
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
