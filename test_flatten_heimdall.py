"""W4/W5 battery: emergency flatten single-path lifecycle + lockout persistence;
HEIMDALL metric computation + every alert tier triggers at its threshold."""
import pytest
from datetime import datetime, timedelta, timezone
from journal import Journal
from flatten import EmergencyFlatten, LOCK_KEY
from heimdall import Heimdall, BLACK, RED, ORANGE, YELLOW
from store import Store


class FakeBrokerActions:
    def __init__(self):
        self._positions = []
        self.calls = []
        self.fail_close = 0          # close_position failures before success
    def positions(self):
        return list(self._positions)
    def cancel_all(self, acct):
        self.calls.append(("cancel_all", acct))
    def close_position(self, acct):
        self.calls.append(("close", acct))
        if self.fail_close > 0:
            self.fail_close -= 1
            return
        self._positions = [p for p in self._positions if p["account_id"] != acct]


@pytest.fixture
def env(tmp_path):
    j = Journal(str(tmp_path / "j.db"))
    s = Store(str(tmp_path / "s.db"))
    b = FakeBrokerActions()
    return j, s, b


def test_flatten_happy_path_ends_locked(env):
    j, s, b = env
    b._positions = [dict(account_id="A1", qty=4)]
    ef = EmergencyFlatten(j, b, s)
    r = ef.trigger("CHECK2_NAKED_POSITION", account_id="A1")
    assert r["flat"] and ("cancel_all", "A1") in b.calls and ("close", "A1") in b.calls
    assert ef.locked() and "CHECK2_NAKED_POSITION" in ef.locked()
    stages = [e["payload"]["stage"] for e in j.export(account_id="A1")[0]["events"]
              if e["event_type"] == "EMERGENCY_FLATTEN"] if j.export(account_id="A1") else []
    n = j.con.execute("SELECT COUNT(*) FROM ledger WHERE event_type='EMERGENCY_FLATTEN'").fetchone()[0]
    assert n == 3                                    # triggered, verified, lockout


def test_flatten_retries_until_flat(env):
    j, s, b = env
    b._positions = [dict(account_id="A1", qty=4)]
    b.fail_close = 2                                 # first 2 closes do nothing
    ef = EmergencyFlatten(j, b, s, verify_attempts=4)
    r = ef.trigger("CHECK1_POSITION_MISMATCH", account_id="A1")
    assert r["flat"] and r["attempts"] >= 2


def test_flatten_verify_failure_still_locks(env):
    j, s, b = env
    b._positions = [dict(account_id="A1", qty=4)]
    b.fail_close = 99                                # position never closes
    ef = EmergencyFlatten(j, b, s, verify_attempts=2)
    r = ef.trigger("CHECK3_UNKNOWN_FILL", account_id="A1")
    assert not r["flat"]
    assert ef.locked()                               # lockout regardless
    bad = j.con.execute("SELECT COUNT(*) FROM ledger WHERE payload_json LIKE '%VERIFY_FAILED%'").fetchone()[0]
    assert bad == 1


def test_flatten_all_targets_union_of_broker_and_ledger(env):
    j, s, b = env
    b._positions = [dict(account_id="A2", qty=2)]
    cl = j.intent("A1", "A", "A", "t", "entry", dict(side="Buy", qty=4))
    j.append("SEND", "A1", cl); j.append("ACK", "A1", cl)
    j.append("FILL", "A1", cl, payload=dict(qty=4, side="Buy"))
    ef = EmergencyFlatten(j, b, s)
    r = ef.trigger("operator", account_id="ALL")
    assert set(r["accounts"]) == {"A1", "A2"}


def test_lockout_survives_restart_and_requires_note(env):
    j, s, b = env
    ef = EmergencyFlatten(j, b, s)
    ef.trigger("test_reason", account_id="A1")
    s2 = Store(s.path)                               # "restart"
    ef2 = EmergencyFlatten(j, b, s2)
    assert ef2.locked()
    with pytest.raises(ValueError):
        ef2.operator_clear("ok")                     # note too short: refused
    assert ef2.operator_clear("false positive: broker maintenance window, verified flat manually")
    assert ef2.locked() is None
    n = j.con.execute("SELECT COUNT(*) FROM ledger WHERE payload_json LIKE '%lockout_cleared%'").fetchone()[0]
    assert n == 1                                    # the clearance is journaled


# ---------------- HEIMDALL ----------------

def now():
    return datetime(2026, 6, 11, 14, 0, tzinfo=timezone.utc)


def test_snapshot_and_clean_state_quiet(env):
    j, s, _ = env
    h = Heimdall(j, s)
    snap = h.snapshot(now=now(), heartbeat_ts=now() - timedelta(seconds=30),
                      feed_last_bar_ts=now() - timedelta(seconds=25),
                      last_signal_ts=dict(A=now() - timedelta(days=2),
                                          B=now() - timedelta(days=1)),
                      in_session=True)
    assert h.evaluate(snap) == []                    # healthy system is silent


@pytest.mark.parametrize("kw,tier,name", [
    (dict(heartbeat_ts=lambda n: n - timedelta(seconds=400)), RED, "heartbeat_dead"),
    (dict(heartbeat_ts=lambda n: n - timedelta(seconds=200)), ORANGE, "heartbeat_stale"),
    (dict(feed_last_bar_ts=lambda n: n - timedelta(seconds=60), in_session=True),
     YELLOW, "feed_lagging"),
    (dict(feed_last_bar_ts=lambda n: n - timedelta(seconds=400), in_session=True),
     ORANGE, "feed_stale_failover"),
    (dict(feed_last_bar_ts=lambda n: n - timedelta(seconds=1000), in_session=True,
          has_open_position=True), RED, "feed_dead_with_position"),
    (dict(last_signal_ts=lambda n: dict(A=n - timedelta(days=8))), YELLOW, "A_quiet"),
    (dict(last_signal_ts=lambda n: dict(A=n - timedelta(days=13))), ORANGE, "A_silent"),
    (dict(last_signal_ts=lambda n: dict(B=n - timedelta(days=4))), YELLOW, "B_quiet"),
    (dict(daily_trades=lambda n: {"A1": 3}), RED, "trade_cap_breach_A1"),
])
def test_each_alert_fires_at_threshold(env, kw, tier, name):
    j, s, _ = env
    h = Heimdall(j, s)
    resolved = {k: (v(now()) if callable(v) else v) for k, v in kw.items()}
    snap = h.snapshot(now=now(), **resolved)
    alerts = h.evaluate(snap)
    assert any(a[0] == tier and a[1] == name for a in alerts), alerts


def test_recon_unknowns_black_and_lockout_black(env):
    j, s, _ = env
    j.append("RECON_ALERT", "A1", payload=dict(check="CHECK3_UNKNOWN_FILL", tier="BLACK"))
    s.set_state(emergency_lockout="2026|A1|test|flat=True")
    h = Heimdall(j, s)
    snap = h.snapshot(now=now())
    tiers = {a[1]: a[0] for a in h.evaluate(snap)}
    assert tiers.get("recon_unknowns") == BLACK
    assert tiers.get("lockout_active") == BLACK


def test_p3_braked_yellow_and_cushion_reported(env):
    j, s, _ = env
    h = Heimdall(j, s)
    sv = {"M1": dict(balance=146_500.0, floor=145_500.0, p3_braked=True)}
    snap = h.snapshot(now=now(), state_view=sv)
    assert snap["p3"]["M1"]["cushion"] == 1000.0
    assert any(a[1] == "p3_braked_M1" for a in h.evaluate(snap))
