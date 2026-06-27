"""Pre-open feed-readiness guard.

Friday 2026-06-26 the live feed only reached GREEN at ~09:40 ET — 10 minutes after the 09:30 open — so
the opening range was malformed and BOTH the Profile B ORB and the Profile MOMENTUM lane silently failed
to arm. This guard makes that failure LOUD and EARLY: in a lead window before the RTH open it checks the
feed and, if it is not GREEN, alerts the operator (escalating) to fix Chrome (:9222, logged-in NQ1! 1m)
*before* the open — and if the open arrives with the feed still not ready, it fires a one-time warning that
the opening-range lanes are compromised for the day.

PURE / TESTABLE: this class makes no I/O and places no orders. It only decides what to say and when.
The caller (auto_live `_process`) sends the returned message via Telegram + logs it. It is advisory:
it NEVER changes sizing, entries, or the existing fail-closed data gate (a RED feed already blocks trades).
"""
from __future__ import annotations

RTH_OPEN_MIN = 9 * 60 + 30          # 09:30 ET


class PreopenGuard:
    def __init__(self, lead_min=10, realert_s=120, open_grace_min=15, open_min=RTH_OPEN_MIN):
        self.lead_min = lead_min            # start checking this many minutes before the open
        self.realert_s = realert_s          # min seconds between repeat "not ready" alerts
        self.open_grace_min = open_grace_min  # stop evaluating this many minutes after the open
        self.open_min = open_min
        self._day = None
        self._reset(None)

    def _reset(self, d):
        self._day = d
        self._confirmed = False             # feed seen GREEN at/after lead-start (ready for the open)
        self._alerted = False               # at least one "not ready" alert sent
        self._last_alert = None             # datetime of last alert (for re-alert throttle)
        self._open_flagged = False          # one-time "open with feed not ready" warning sent

    def evaluate(self, now_et, data_state):
        """Call every tick with naive/aware ET `now` and the feed's data_state ('GREEN'/'YELLOW'/'RED').
        Returns an action dict {kind, msg, ...} to surface (Telegram + log), or None when nothing to do.
        kinds: 'ready' | 'recovered' | 'not_ready' | 'late_open'."""
        if now_et.weekday() >= 5:            # Sat/Sun — futures closed; never alert
            return None
        d = now_et.date()
        if self._day != d:
            self._reset(d)
        mins = now_et.hour * 60 + now_et.minute
        lead_start = self.open_min - self.lead_min
        if mins < lead_start:
            return None                      # too early to care
        green = (data_state == "GREEN")

        # ---- pre-open window: [open-lead, open) ----
        if mins < self.open_min:
            ttl = self.open_min - mins       # minutes to open
            if green:
                if not self._confirmed:
                    self._confirmed = True
                    if self._alerted:
                        return self._act("recovered", now_et,
                                         f"✅ FEED RECOVERED — GREEN with {ttl} min to the 09:30 ET open. "
                                         "ORB + Momentum will arm cleanly.")
                    return self._act("ready", now_et,
                                     f"✅ Feed READY for the open ({ttl} min to 09:30 ET, real-time GREEN).")
                return None
            # not GREEN pre-open -> alert / escalate
            if (not self._alerted) or self._due(now_et):
                self._alerted = True
                self._last_alert = now_et
                return self._act("not_ready", now_et,
                                 f"⚠️ FEED NOT READY — {ttl} min to the 09:30 ET open, data_state={data_state}. "
                                 "Fix NOW: Chrome :9222 must be logged in to TradingView on NQ1! @ 1m, real-time "
                                 "(not Delayed). A late feed kills the ORB + Momentum opening range.")
            return None

        # ---- at/after the open: [open, open+grace] ----
        if mins > self.open_min + self.open_grace_min:
            return None                      # past the grace window; midday feed health is feed_watch's job
        if green:
            if not self._confirmed:          # only just came GREEN, i.e. the open itself was late
                self._confirmed = True
                if self._alerted and not self._open_flagged:
                    self._open_flagged = True
                    return self._act("late_open", now_et,
                                     "🔴 OPEN WAS LATE — feed reached GREEN only after 09:30 ET. The opening "
                                     "range is malformed; treat any ORB / Momentum signal today with caution.")
            return None
        if not self._open_flagged:           # 09:30 reached and feed still not GREEN
            self._open_flagged = True
            return self._act("late_open", now_et,
                             f"🔴 OPEN @ 09:30 ET with feed NOT ready (data_state={data_state}). ORB + Momentum "
                             "opening range compromised today — fix Chrome :9222 (logged-in NQ1! 1m real-time).")
        return None

    # ---- helpers ----
    def _due(self, now_et):
        if self._last_alert is None:
            return True
        return (now_et - self._last_alert).total_seconds() >= self.realert_s

    def _act(self, kind, now_et, msg):
        return dict(kind=kind, msg=msg, et=now_et.strftime("%H:%M ET"))
