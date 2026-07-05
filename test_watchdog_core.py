"""WATCHDOG smoke tests — prove invariants A / B / C fire the right ACTION in enforce mode and
only `would_have` (nothing sent, no HALT.flag) in observe mode, using fake panel/belief/sender
injections. The full 9-invariant suite comes from another agent; these lock the injection seams
(truth-reader + sender are constructor-injectable) and the enforce/observe polarity.
"""
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

import watchdog as W

ET = ZoneInfo("America/New_York")
MORNING = datetime(2026, 7, 6, 14, 30, tzinfo=timezone.utc)   # 10:30 ET Mon — market open, before flat time
AFTER_FLAT = datetime(2026, 7, 6, 18, 40, tzinfo=timezone.utc)  # 14:40 ET Mon — past the 14:31 flat time


class FakeTruth:
    def __init__(self, snap, feed_age=10):
        self._snap = snap
        self._feed_age = feed_age
    def snapshot(self):
        return dict(self._snap)
    def last_bar_age_s(self, now_utc):
        return self._feed_age


class FakeSender:
    def __init__(self):
        self.flattens = []
        self.sends = []
    def flatten(self, account, root="MNQ", reason="emergency"):
        self.flattens.append(dict(account=account, root=root, reason=reason))
        return dict(ok=True)
    def send(self, payload, **k):
        self.sends.append(payload)
        return dict(sent=True)


class FakeTg:
    def __init__(self):
        self.msgs = []
    def send(self, text):
        self.msgs.append(text)
        return True


def _snap(net=0, working_ids=None, working_count=None, equity=None):
    working_ids = working_ids or []
    if working_count is None:
        working_count = len(working_ids)
    return dict(account="APEXTEST", net=net, working_ids=working_ids,
                working_count=working_count, equity=equity, nonflat=(net != 0))


def _make(mode, snap, belief, tmp_path, monkeypatch, feed_age=10):
    # redirect HALT.flag / dir so a test never writes a real out/watchdog/HALT.flag
    monkeypatch.setattr(W, "WATCHDOG_DIR", str(tmp_path))
    monkeypatch.setattr(W, "HALT_FLAG_PATH", str(tmp_path / "HALT.flag"))
    wd = W.Watchdog(mode=mode, account="APEX-50K-EVAL-1",
                    truth=FakeTruth(snap, feed_age=feed_age),
                    sender=FakeSender(), belief_reader=lambda: belief,
                    telegram=FakeTg(), config_verifier=lambda: (True, []),
                    state_path=str(tmp_path / "state.json"),
                    audit_dir=str(tmp_path / "audit"))
    return wd


def _find(records, invariant):
    return [r for r in records if r.invariant == invariant]


# ── A. POSITION PARITY ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("mode,executed", [("enforce", True), ("observe", False)])
def test_parity_mismatch(mode, executed, tmp_path, monkeypatch):
    snap = _snap(net=1, working_ids=[])                 # broker holds +1
    belief = dict(expected_net=0, open_entry_sids=[], claimed_bracket_sids=[], day_internal_pnl=None,
                  ts_utc="t")                            # engine believes FLAT
    wd = _make(mode, snap, belief, tmp_path, monkeypatch)
    recs = _find(wd.run_cycle(MORNING, grace_override=False), "POSITION_PARITY")
    assert len(recs) == 1
    r = recs[0]
    assert r.intended == "flatten" and r.write_halt is True and r.executed is executed
    halt_exists = os.path.exists(str(tmp_path / "HALT.flag"))
    if mode == "enforce":
        assert len(wd.sender.flattens) == 1 and halt_exists
    else:
        assert wd.sender.flattens == [] and not halt_exists   # observe: NOTHING sent, no HALT written


# ── B. ORPHAN ORDERS (flat-with-orders → cancel) & UNPROTECTED (open, no bracket → flatten) ──
@pytest.mark.parametrize("mode,executed", [("enforce", True), ("observe", False)])
def test_orphan_cancel(mode, executed, tmp_path, monkeypatch):
    snap = _snap(net=0, working_count=1)                # flat but a working order lingers
    belief = dict(expected_net=0, open_entry_sids=[], claimed_bracket_sids=[], day_internal_pnl=None,
                  ts_utc="t")
    wd = _make(mode, snap, belief, tmp_path, monkeypatch)
    recs = _find(wd.run_cycle(MORNING, grace_override=False), "ORPHAN_ORDERS")
    assert len(recs) == 1 and recs[0].intended == "cancel" and recs[0].executed is executed
    if mode == "enforce":
        assert len(wd.sender.sends) == 1 and wd.sender.flattens == []   # cancel-only, never an exit
    else:
        assert wd.sender.sends == []


@pytest.mark.parametrize("mode,executed", [("enforce", True), ("observe", False)])
def test_unprotected_flatten(mode, executed, tmp_path, monkeypatch):
    snap = _snap(net=1, working_count=0)                # position open, NO working bracket
    belief = dict(expected_net=1, open_entry_sids=[], claimed_bracket_sids=[], day_internal_pnl=None,
                  ts_utc="t")
    wd = _make(mode, snap, belief, tmp_path, monkeypatch)
    recs = _find(wd.run_cycle(MORNING, grace_override=False), "UNPROTECTED_POSITION")
    assert len(recs) == 1 and recs[0].intended == "flatten" and recs[0].write_halt is True
    assert recs[0].executed is executed
    if mode == "enforce":
        assert len(wd.sender.flattens) == 1
    else:
        assert wd.sender.flattens == []


# ── C. FLAT-TIME SECOND SIGNATURE ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("mode,executed", [("enforce", True), ("observe", False)])
def test_flat_time_flatten(mode, executed, tmp_path, monkeypatch):
    snap = _snap(net=1, working_ids=["s1"])             # still holding past flat time
    belief = dict(expected_net=1, open_entry_sids=["s1"], claimed_bracket_sids=["s1"],
                  day_internal_pnl=None, ts_utc="t")     # parity ok, brackets present → only FLAT_TIME fires
    wd = _make(mode, snap, belief, tmp_path, monkeypatch)
    recs = wd.run_cycle(AFTER_FLAT, grace_override=False)
    ft = _find(recs, "FLAT_TIME")
    assert len(ft) == 1 and ft[0].intended == "flatten" and ft[0].executed is executed
    # nothing else should have fired (parity matches, bracket present)
    assert _find(recs, "POSITION_PARITY") == [] and _find(recs, "UNPROTECTED_POSITION") == []
    if mode == "enforce":
        assert len(wd.sender.flattens) == 1
    else:
        assert wd.sender.flattens == []


# ── observe never writes a HALT.flag even for a HALT-class invariant ────────────────────────
def test_observe_config_drift_no_halt_written(tmp_path, monkeypatch):
    snap = _snap(net=0)
    belief = dict(expected_net=0, open_entry_sids=[], claimed_bracket_sids=[], day_internal_pnl=None,
                  ts_utc="t")
    wd = _make("observe", snap, belief, tmp_path, monkeypatch)
    wd.config_verifier = lambda: (False, ["config_defaults.py: hash drift"])
    recs = _find(wd.run_cycle(MORNING, grace_override=False), "CONFIG_INTEGRITY")
    assert len(recs) == 1 and recs[0].intended == "halt" and recs[0].executed is False
    assert not os.path.exists(str(tmp_path / "HALT.flag"))


# ── ACTION DEDUP — an action fires ONCE per incident, not every loop cycle ───────────────────
def _mutate_snap(wd, **kw):
    wd.truth._snap.update(kw)


def test_persistent_violation_fires_once(tmp_path, monkeypatch):
    """Wedged case: broker holds +1, belief says FLAT, violation persists → exactly ONE flatten
    send across many cycles (not a fresh webhook every 10s)."""
    snap = _snap(net=1)
    belief = dict(expected_net=0, open_entry_sids=[], claimed_bracket_sids=[], day_internal_pnl=None,
                  ts_utc="t")
    wd = _make("enforce", snap, belief, tmp_path, monkeypatch)
    recs = []
    for k in range(6):                                       # 6 cycles, 10s apart (all < 300s window)
        recs += wd.run_cycle(MORNING + timedelta(seconds=10 * k), grace_override=False)
    parity = _find(recs, "POSITION_PARITY")
    assert len(parity) == 6                                  # a duration row every cycle
    assert sum(1 for r in parity if r.executed) == 1        # but exactly ONE actual send
    assert len(wd.sender.flattens) == 1


def test_recovery_then_reviolation_fires_again(tmp_path, monkeypatch):
    snap = _snap(net=1)
    belief = dict(expected_net=0, open_entry_sids=[], claimed_bracket_sids=[], day_internal_pnl=None,
                  ts_utc="t")
    wd = _make("enforce", snap, belief, tmp_path, monkeypatch)
    wd.run_cycle(MORNING, grace_override=False)                              # violation → fire #1
    _mutate_snap(wd, net=0, nonflat=False)                                   # broker flat → parity recovers
    wd.run_cycle(MORNING + timedelta(seconds=10), grace_override=False)
    _mutate_snap(wd, net=1, nonflat=True)                                    # re-violation
    wd.run_cycle(MORNING + timedelta(seconds=20), grace_override=False)      # fresh transition → fire #2
    assert len(wd.sender.flattens) == 2


def test_backstop_refires_when_broker_still_nonflat(tmp_path, monkeypatch):
    snap = _snap(net=1)                                      # broker keeps re-showing the position
    belief = dict(expected_net=0, open_entry_sids=[], claimed_bracket_sids=[], day_internal_pnl=None,
                  ts_utc="t")
    wd = _make("enforce", snap, belief, tmp_path, monkeypatch)
    wd.run_cycle(MORNING, grace_override=False)                              # fire #1
    wd.run_cycle(MORNING + timedelta(seconds=120), grace_override=False)     # within window → suppressed
    assert len(wd.sender.flattens) == 1
    wd.run_cycle(MORNING + timedelta(seconds=301), grace_override=False)     # >300s, still nonflat → re-fire
    assert len(wd.sender.flattens) == 2


def test_backstop_suppressed_when_broker_flat_but_belief_stale(tmp_path, monkeypatch):
    """A flatten that WORKED leaves the broker flat; a parity break then driven only by a stale
    belief (broker already flat) must NOT re-fire on the backstop."""
    snap = _snap(net=0)                                      # broker FLAT
    belief = dict(expected_net=1, open_entry_sids=[], claimed_bracket_sids=[], day_internal_pnl=None,
                  ts_utc="t")                                # engine belief still says net=1 (stale)
    wd = _make("enforce", snap, belief, tmp_path, monkeypatch)
    wd.run_cycle(MORNING, grace_override=False)              # transition fire(s) once (harmless, broker flat)
    n1 = len(wd.sender.flattens)
    assert n1 >= 1
    wd.run_cycle(MORNING + timedelta(seconds=301), grace_override=False)     # >300s but broker FLAT → no re-fire
    assert len(wd.sender.flattens) == n1
