"""W5 — HEIMDALL instrumentation layer. Computes the survival metrics from the
journal + store + injected runtime facts, and evaluates them against the HEIMDALL.md
thresholds. Pure functions over data — no broker required; dashboard_server can
serve `snapshot()` JSON directly and the alert list feeds notification channels.
"""
from datetime import datetime, timezone

GREEN, YELLOW, ORANGE, RED, BLACK = "GREEN", "YELLOW", "ORANGE", "RED", "BLACK"


def _age_s(now, ts):
    if ts is None:
        return None
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return max(0.0, (now - ts).total_seconds())


class Heimdall:
    def __init__(self, journal, store, poll_sec=20):
        self.j = journal
        self.store = store
        self.poll = poll_sec

    # ---------------- metrics snapshot ----------------

    def snapshot(self, now=None, heartbeat_ts=None, feed_last_bar_ts=None,
                 last_signal_ts=None, state_view=None, daily_trades=None,
                 has_open_position=False, in_session=False):
        """All runtime facts injected; journal/store facts computed here."""
        now = now or datetime.now(timezone.utc)
        ls = last_signal_ts or {}
        recon_alerts = self._count_events("RECON_ALERT")
        snap = dict(
            ts=now.isoformat(),
            heartbeat_age_s=_age_s(now, heartbeat_ts),
            feed_age_s=_age_s(now, feed_last_bar_ts),
            signal_age_days={k: (None if v is None else _age_s(now, v) / 86400.0)
                             for k, v in ls.items()},
            recon_alerts_24h=recon_alerts["24h"],
            recon_alerts_total=recon_alerts["total"],
            unknown_positions=self._alert_class_count("CHECK1_POSITION_MISMATCH")
                              + self._alert_class_count("CHECK4_UNKNOWN_ORDER"),
            unknown_fills=self._alert_class_count("CHECK3_UNKNOWN_FILL"),
            naked_alerts=self._alert_class_count("CHECK2_NAKED_POSITION"),
            p3=({a: dict(braked=v.get("p3_braked"),
                         cushion=(v.get("balance", 0) - v.get("floor", 0)))
                 for a, v in (state_view or {}).items()}),
            journal=dict(events=self._total_events(), last_seq_ts=self._last_ts()),
            recovery_events=self._recovery_count(),
            emergency_lockout=self.store.get_state("emergency_lockout") or None,
            daily_trades=daily_trades or {},
            has_open_position=has_open_position,
            in_session=in_session,
        )
        return snap

    # ---------------- alert evaluation (HEIMDALL.md thresholds) ----------------

    def evaluate(self, snap):
        alerts = []
        A = alerts.append
        hb = snap["heartbeat_age_s"]
        if hb is not None and hb > 300:
            A((RED, "heartbeat_dead", f"{hb:.0f}s since heartbeat"))
        elif hb is not None and hb > 120:
            A((ORANGE, "heartbeat_stale", f"{hb:.0f}s"))
        fa = snap["feed_age_s"]
        if fa is not None and snap["in_session"]:
            if fa > 900 and snap["has_open_position"]:
                A((RED, "feed_dead_with_position", f"{fa:.0f}s stale, position open"))
            elif fa > 300:
                A((ORANGE, "feed_stale_failover", f"{fa:.0f}s — fail over"))
            elif fa > 2 * self.poll:
                A((YELLOW, "feed_lagging", f"{fa:.0f}s"))
        sa = snap["signal_age_days"]
        a_age, b_age = sa.get("A"), sa.get("B")
        if a_age is not None:
            if a_age > 12:
                A((ORANGE, "A_silent", f"{a_age:.1f} days without an A signal"))
            elif a_age > 7:
                A((YELLOW, "A_quiet", f"{a_age:.1f} days"))
        if b_age is not None and b_age > 3:
            A((YELLOW, "B_quiet", f"{b_age:.1f} days without a B signal"))
        if snap["unknown_positions"] or snap["unknown_fills"]:
            A((BLACK, "recon_unknowns",
               f"pos={snap['unknown_positions']} fills={snap['unknown_fills']}"))
        if snap["naked_alerts"]:
            A((RED, "naked_position_alerts", str(snap["naked_alerts"])))
        if snap["emergency_lockout"]:
            A((BLACK, "lockout_active", snap["emergency_lockout"]))
        for acct, p in (snap["p3"] or {}).items():
            if p["braked"]:
                A((YELLOW, f"p3_braked_{acct}", f"cushion ${p['cushion']:,.0f}"))
        for acct, n in (snap["daily_trades"] or {}).items():
            if n > 2:
                A((RED, f"trade_cap_breach_{acct}", f"{n} trades today"))
        return alerts

    # ---------------- journal-derived internals ----------------

    def _total_events(self):
        return self.j.con.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]

    def _last_ts(self):
        r = self.j.con.execute(
            "SELECT ts_utc FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()
        return r[0] if r else None

    def _count_events(self, etype):
        total = self.j.con.execute(
            "SELECT COUNT(*) FROM ledger WHERE event_type=?", (etype,)).fetchone()[0]
        d24 = self.j.con.execute(
            "SELECT COUNT(*) FROM ledger WHERE event_type=? AND ts_utc >= "
            "datetime('now', '-1 day')", (etype,)).fetchone()[0]
        return dict(total=total, **{"24h": d24})

    def _alert_class_count(self, check_name):
        """24h window — historical drills/incidents must not alarm forever."""
        return self.j.con.execute(
            "SELECT COUNT(*) FROM ledger WHERE event_type='RECON_ALERT' "
            "AND payload_json LIKE ? AND ts_utc >= datetime('now', '-1 day')",
            (f'%{check_name}%',)).fetchone()[0]

    def _recovery_count(self):
        return self.j.con.execute(
            "SELECT COUNT(*) FROM ledger WHERE payload_json LIKE '%\"source\": \"recovery\"%'"
        ).fetchone()[0]
