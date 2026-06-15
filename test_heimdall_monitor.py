"""Tests for heimdall_monitor — heartbeat write/read, dead-man OK/WARN/RED, entry gate."""
from datetime import datetime, timezone, timedelta

import heimdall_monitor as H


def _now():
    return datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc)


def test_heartbeat_writes_valid_state(tmp_path):
    p = str(tmp_path / "hb.json")
    H.write_heartbeat(dict(pid=123, data_state="GREEN", guardian="armed"), p, now=_now())
    hb = H.read_heartbeat(p)
    assert hb["pid"] == 123 and hb["data_state"] == "GREEN" and hb["guardian"] == "armed"
    assert "ts" in hb


def test_deadman_ok_when_fresh(tmp_path):
    p = str(tmp_path / "hb.json")
    H.write_heartbeat({}, p, now=_now())
    st = H.deadman_status(p, now=_now() + timedelta(seconds=10))
    assert st["state"] == "OK" and st["alive"] is True


def test_deadman_warns_on_missed_heartbeat(tmp_path):
    p = str(tmp_path / "hb.json")
    H.write_heartbeat({}, p, now=_now())
    st = H.deadman_status(p, now=_now() + timedelta(seconds=90))   # > WARN_S(60), < RED_S(180)
    assert st["state"] == "WARN" and st["alive"] is True


def test_deadman_red_on_hard_miss(tmp_path):
    p = str(tmp_path / "hb.json")
    H.write_heartbeat({}, p, now=_now())
    st = H.deadman_status(p, now=_now() + timedelta(seconds=300))  # > RED_S(180)
    assert st["state"] == "RED" and st["alive"] is False
    assert st["age_s"] is not None                                # heartbeat existed -> stalled


def test_deadman_red_when_heartbeat_missing(tmp_path):
    st = H.deadman_status(str(tmp_path / "nope.json"))
    assert st["state"] == "RED" and st["alive"] is False
    assert st["age_s"] is None                                    # never ran -> not present


def test_entry_ready_blocks_on_yellow():
    ok, why = H.entry_ready(("YELLOW", "stabilizing 1/3"), dict(alive=True))
    assert not ok and "YELLOW" in why


def test_entry_ready_blocks_when_deadman_dead():
    ok, why = H.entry_ready(("GREEN", "ok"), dict(alive=False, reason="heartbeat stale 999s"))
    assert not ok and "dead-man" in why


def test_entry_ready_ok_when_green_and_alive():
    ok, why = H.entry_ready(("GREEN", "ok"), dict(alive=True))
    assert ok and why == "ok"


def test_apply_freshness_forces_red_on_frozen_feed():
    # 08:00 ET = 12:00 UTC; at 12:10 UTC the snapshot is 10 min stale -> must read RED
    now = datetime(2026, 6, 15, 12, 10, tzinfo=timezone.utc)
    ds = {"data_state": "GREEN", "DATA_READY": True, "last_bar": "2026-06-15 08:00:00-04:00"}
    out = H.apply_freshness(ds, now=now)
    assert out["data_state"] == "RED" and out["DATA_READY"] is False
    assert out["last_bar_age_s"] >= 300


def test_apply_freshness_keeps_green_when_fresh():
    now = datetime(2026, 6, 15, 12, 1, tzinfo=timezone.utc)   # 1 min after the 08:00 ET bar
    ds = {"data_state": "GREEN", "DATA_READY": True, "last_bar": "2026-06-15 08:00:00-04:00"}
    out = H.apply_freshness(ds, now=now)
    assert out["data_state"] == "GREEN" and out["DATA_READY"] is True


def test_dashboard_red_on_stale_heartbeat(monkeypatch):
    import zeus_server
    monkeypatch.setattr("heimdall_monitor.deadman_status",
                        lambda *a, **k: dict(state="RED", alive=False, age_s=999,
                                             reason="heartbeat stale 999s"))
    d = zeus_server.assemble_state()["deployment"]
    assert d["status"] == "RED" and d["green"] is False     # running process stalled -> RED


def test_dashboard_not_green_when_heartbeat_missing(monkeypatch):
    import zeus_server
    monkeypatch.setattr("heimdall_monitor.deadman_status",
                        lambda *a, **k: dict(state="RED", alive=False, age_s=None,
                                             reason="no heartbeat"))
    d = zeus_server.assemble_state()["deployment"]
    assert d["green"] is False                              # absent heartbeat -> never green
