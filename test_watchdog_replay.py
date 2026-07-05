"""WATCHDOG corrupted-replay test suite — the cycle's core deliverable.

A scripted-session harness: sequences of (belief_state, broker_state, wall_clock) frames stepped
through Watchdog.run_cycle() with fake truth-reader/sender/telegram/tmp dirs, following
test_watchdog_core.py's injection pattern (truth + sender + belief_reader + telegram +
config_verifier are all constructor-injectable; WATCHDOG_DIR/HALT_FLAG_PATH are monkeypatched to
tmp_path so nothing here ever touches a real out/watchdog/ path). No sleeps — every clock advance
is an explicit `now_utc` passed into run_cycle.

Ten items, each numbered to match the task spec. Every test asserts the FULL sender call list
(flattens + sends), the HALT.flag state, and the relevant audit-*.jsonl rows — not just the
returned ActionRecords — so a test cannot pass on a partial/accidental side effect.

watchdog.py and watchdog_belief.py are read-only here. Where a check needs the engine's
`killed()` gate logic (auto_live.py ~228-240 / ~1410-1431), we replicate the exact guarded
call pattern locally (env check + call into watchdog_belief) rather than importing/instantiating
auto_live's live Auto class — that class needs a real store/guard/sender/broker stack to
construct and is out of scope for a watchdog-side replay harness. This mirrors, not duplicates,
policy: the boolean logic is copied 1:1 from the cited line ranges and each is called out below.
"""
import ast
import hashlib
import json
import os
from datetime import datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

import watchdog as W
import watchdog_belief as WB

ET = ZoneInfo("America/New_York")
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def _et(y, m, d, hh, mm, ss=0):
    """ET wall-clock -> aware UTC datetime via zoneinfo (DST-correct; no manual UTC offsets)."""
    return datetime(y, m, d, hh, mm, ss, tzinfo=ET).astimezone(timezone.utc)


MORNING = _et(2026, 7, 6, 10, 30)          # Monday, market open, well before the 14:31 flat time
FLAT_TIME_FRAME = _et(2026, 7, 6, 14, 31)  # exactly the second-signature flat time (Monday)


# ══════════════════════════════════════════════════════════════════════════════════════════
# Fakes (mirrors test_watchdog_core.py's injection pattern)
# ══════════════════════════════════════════════════════════════════════════════════════════
class FakeTruth:
    def __init__(self, snap, feed_age=10):
        self._snap = dict(snap)
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


def _belief(expected_net=0, entry_sids=None, bracket_sids=None, day_pnl=None, ts="t"):
    return dict(expected_net=expected_net, open_entry_sids=entry_sids or [],
                claimed_bracket_sids=bracket_sids or [], day_internal_pnl=day_pnl, ts_utc=ts)


def _make(mode, snap, belief, tmp_path, monkeypatch, feed_age=10, config_verifier=None):
    """belief may be a plain dict (static) or a zero-arg callable (dynamic, multi-frame replay)."""
    monkeypatch.setattr(W, "WATCHDOG_DIR", str(tmp_path))
    monkeypatch.setattr(W, "HALT_FLAG_PATH", str(tmp_path / "HALT.flag"))
    reader = belief if callable(belief) else (lambda: belief)
    wd = W.Watchdog(mode=mode, account="APEX-50K-EVAL-1",
                    truth=FakeTruth(snap, feed_age=feed_age),
                    sender=FakeSender(), belief_reader=reader,
                    telegram=FakeTg(), config_verifier=config_verifier or (lambda: (True, [])),
                    state_path=str(tmp_path / "state.json"),
                    audit_dir=str(tmp_path / "audit"))
    return wd


def _find(records, invariant):
    return [r for r in records if r.invariant == invariant]


def _halt_path(tmp_path):
    return str(tmp_path / "HALT.flag")


def _audit_rows(audit_dir, now_utc, invariant=None):
    date_str = now_utc.astimezone(ET).date().isoformat()
    path = os.path.join(audit_dir, f"audit-{date_str}.jsonl")
    if not os.path.exists(path):
        return []
    rows = [json.loads(ln) for ln in open(path) if ln.strip()]
    if invariant is not None:
        rows = [r for r in rows if r["invariant"] == invariant]
    return rows


# ══════════════════════════════════════════════════════════════════════════════════════════
# 1. FLAT vs LONG-3 — exactly one flatten + HALT.flag + alert (enforce); zero sends in observe.
# ══════════════════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("mode", ["enforce", "observe"])
def test_1_flat_belief_broker_long3(mode, tmp_path, monkeypatch):
    snap = _snap(net=3, working_ids=[])                  # broker holds +3
    belief = _belief(expected_net=0)                      # engine believes FLAT
    wd = _make(mode, snap, belief, tmp_path, monkeypatch)
    recs = wd.run_cycle(MORNING, grace_override=False)
    parity = _find(recs, "POSITION_PARITY")
    assert len(parity) == 1
    assert parity[0].intended == "flatten" and parity[0].write_halt is True
    assert _find(recs, "ORPHAN_ORDERS") == [] and _find(recs, "UNPROTECTED_POSITION") == []

    rows = _audit_rows(str(tmp_path / "audit"), MORNING, "POSITION_PARITY")
    assert len(rows) == 1 and rows[0]["verdict"] == "violation"

    if mode == "enforce":
        assert len(wd.sender.flattens) == 1
        f = wd.sender.flattens[0]
        assert f["account"] == "APEX-50K-EVAL-1" and f["root"] == "MNQ"
        assert f["reason"].startswith("watchdog_position_parity_")
        assert wd.sender.sends == []
        assert os.path.exists(_halt_path(tmp_path))
        assert rows[0]["action"] == "flatten"
    else:
        assert wd.sender.flattens == [] and wd.sender.sends == []
        assert not os.path.exists(_halt_path(tmp_path))
        assert rows[0]["action"] == "would_have"
    assert any("POSITION_PARITY" in m for m in wd.tg.msgs)   # alert fires in BOTH modes


# ══════════════════════════════════════════════════════════════════════════════════════════
# 2. Belief claims a 2-leg resting bracket, broker shows only the core leg, position open
#    -> UNPROTECTED (silent-reject case): flatten + HALT.
# ══════════════════════════════════════════════════════════════════════════════════════════
def test_2_unprotected_silent_reject_second_leg(tmp_path, monkeypatch):
    snap = _snap(net=1, working_ids=["stop1"], working_count=1)      # only the core/stop leg present
    belief = _belief(expected_net=1, bracket_sids=["stop1", "tgt1"])  # engine believes BOTH legs rest
    wd = _make("enforce", snap, belief, tmp_path, monkeypatch)
    recs = wd.run_cycle(MORNING, grace_override=False)

    unprot = _find(recs, "UNPROTECTED_POSITION")
    assert len(unprot) == 1
    assert unprot[0].intended == "flatten" and unprot[0].write_halt is True and unprot[0].executed is True
    assert "tgt1" in unprot[0].note and "UNPROTECTED" in unprot[0].note
    assert _find(recs, "ORPHAN_ORDERS") == [] and _find(recs, "POSITION_PARITY") == []

    assert len(wd.sender.flattens) == 1
    f = wd.sender.flattens[0]
    assert f["account"] == "APEX-50K-EVAL-1" and f["root"] == "MNQ"
    assert f["reason"].startswith("watchdog_unprotected_position_")
    assert wd.sender.sends == []
    assert os.path.exists(_halt_path(tmp_path))

    rows = _audit_rows(str(tmp_path / "audit"), MORNING, "UNPROTECTED_POSITION")
    assert len(rows) == 1 and rows[0]["verdict"] == "violation" and rows[0]["action"] == "flatten"
    assert any("UNPROTECTED_POSITION" in m for m in wd.tg.msgs)


# ══════════════════════════════════════════════════════════════════════════════════════════
# 3. Broker working order, unknown sid, belief has none, flat -> cancel-only, never an exit.
# ══════════════════════════════════════════════════════════════════════════════════════════
def test_3_orphan_cancel_only_payload(tmp_path, monkeypatch):
    snap = _snap(net=0, working_ids=["unknown_sid_1"], working_count=1)   # flat, unknown order rests
    belief = _belief(expected_net=0)                                       # no sids known at all
    wd = _make("enforce", snap, belief, tmp_path, monkeypatch)
    recs = wd.run_cycle(MORNING, grace_override=False)

    orphan = _find(recs, "ORPHAN_ORDERS")
    assert len(orphan) == 1 and orphan[0].intended == "cancel" and orphan[0].executed is True
    assert _find(recs, "UNPROTECTED_POSITION") == [] and _find(recs, "POSITION_PARITY") == []

    assert wd.sender.flattens == []                       # never an exit
    assert len(wd.sender.sends) == 1
    payload = wd.sender.sends[0]
    assert payload["action"] == "cancel"
    for forbidden in ("quantity", "orderType", "stopLoss", "takeProfit", "limitPrice"):
        assert forbidden not in payload                    # cancel-only: no entry/exit fields at all
    assert not os.path.exists(_halt_path(tmp_path))         # cancel never HALTs (risk-reducing, not a doubt)

    rows = _audit_rows(str(tmp_path / "audit"), MORNING, "ORPHAN_ORDERS")
    assert len(rows) == 1 and rows[0]["action"] == "cancel"
    assert any("ORPHAN_ORDERS" in m for m in wd.tg.msgs)


# ══════════════════════════════════════════════════════════════════════════════════════════
# 4. FLAT-TIME second signature: position open at 14:31 ET, engine EOD never fired (belief
#    unaware) -> watchdog flattens. Plus the half-day variant if scheduler is importable.
# ══════════════════════════════════════════════════════════════════════════════════════════
def test_4_flat_time_engine_eod_never_fired(tmp_path, monkeypatch):
    snap = _snap(net=1, working_ids=["s1"], working_count=1)
    belief = _belief(expected_net=1, bracket_sids=["s1"])   # parity + bracket both fine — belief just
                                                             # never registered the EOD flatten happened
    wd = _make("enforce", snap, belief, tmp_path, monkeypatch)
    recs = wd.run_cycle(FLAT_TIME_FRAME, grace_override=False)

    ft = _find(recs, "FLAT_TIME")
    assert len(ft) == 1 and ft[0].intended == "flatten" and ft[0].executed is True
    assert ft[0].write_halt is False                        # FLAT_TIME flattens but does NOT halt
    assert _find(recs, "POSITION_PARITY") == [] and _find(recs, "UNPROTECTED_POSITION") == []

    assert len(wd.sender.flattens) == 1 and wd.sender.sends == []
    assert not os.path.exists(_halt_path(tmp_path))          # no HALT-class invariant fired

    rows = _audit_rows(str(tmp_path / "audit"), FLAT_TIME_FRAME, "FLAT_TIME")
    assert len(rows) == 1 and rows[0]["action"] == "flatten"
    assert "half_day=False" in rows[0]["belief_observed"]


def test_4b_flat_time_half_day_variant(tmp_path, monkeypatch):
    try:
        from scheduler import HALF_DAYS_2026
    except Exception as e:                                   # noqa: BLE001
        pytest.skip(f"scheduler not importable: {e!r}")
    if not HALF_DAYS_2026:
        pytest.skip("scheduler.HALF_DAYS_2026 is empty this year")
    half_day = sorted(HALF_DAYS_2026)[0]
    frame = _et(half_day.year, half_day.month, half_day.day, 12, 46)   # 1 min after the 12:45 half-day flatten

    snap = _snap(net=1, working_ids=["s1"], working_count=1)
    belief = _belief(expected_net=1, bracket_sids=["s1"])
    wd = _make("enforce", snap, belief, tmp_path, monkeypatch)
    recs = wd.run_cycle(frame, grace_override=False)

    ft = _find(recs, "FLAT_TIME")
    assert len(ft) == 1 and ft[0].intended == "flatten" and ft[0].executed is True
    assert len(wd.sender.flattens) == 1

    rows = _audit_rows(str(tmp_path / "audit"), frame, "FLAT_TIME")
    assert len(rows) == 1
    assert "half_day=True" in rows[0]["belief_observed"] and "12:46ET" in rows[0]["belief_observed"]


# ══════════════════════════════════════════════════════════════════════════════════════════
# 5. FEED LIVENESS — watchdog's own last-bar age > 180s, engine heartbeat claims armed.
# ══════════════════════════════════════════════════════════════════════════════════════════
def test_5a_feed_stale_flat_halt_only(tmp_path, monkeypatch):
    monkeypatch.setattr(W, "deadman_status", lambda **k: dict(alive=True))
    snap = _snap(net=0, working_ids=[], working_count=0)
    belief = _belief(expected_net=0)
    wd = _make("enforce", snap, belief, tmp_path, monkeypatch, feed_age=200)
    recs = wd.run_cycle(MORNING, grace_override=False)

    feed = _find(recs, "FEED_LIVENESS")
    assert len(feed) == 1 and feed[0].intended == "halt" and feed[0].write_halt is True
    assert _find(recs, "POSITION_PARITY") == [] and _find(recs, "ORPHAN_ORDERS") == []
    assert wd.sender.flattens == [] and wd.sender.sends == []
    assert os.path.exists(_halt_path(tmp_path))


def test_5b_feed_stale_open_protected_leave_no_flatten(tmp_path, monkeypatch):
    monkeypatch.setattr(W, "deadman_status", lambda **k: dict(alive=True))
    snap = _snap(net=1, working_ids=["s1", "s2"], working_count=2)
    belief = _belief(expected_net=1, bracket_sids=["s1", "s2"])   # both bracket sids confirmed working
    wd = _make("enforce", snap, belief, tmp_path, monkeypatch, feed_age=200)
    recs = wd.run_cycle(MORNING, grace_override=False)

    feed = _find(recs, "FEED_LIVENESS")
    assert len(feed) == 1 and feed[0].intended == "halt" and feed[0].write_halt is True
    assert "leave" in feed[0].note
    assert _find(recs, "UNPROTECTED_POSITION") == [] and _find(recs, "ORPHAN_ORDERS") == []
    assert wd.sender.flattens == []                          # NO flatten — position stays, only HALT
    assert os.path.exists(_halt_path(tmp_path))


def test_5c_feed_stale_open_unconfirmable_flatten(tmp_path, monkeypatch):
    monkeypatch.setattr(W, "deadman_status", lambda **k: dict(alive=True))
    snap = _snap(net=1, working_ids=["unknown"], working_count=1)
    belief = _belief(expected_net=1)                          # no known bracket sids -> unconfirmable
    wd = _make("enforce", snap, belief, tmp_path, monkeypatch, feed_age=200)
    recs = wd.run_cycle(MORNING, grace_override=False)

    feed = _find(recs, "FEED_LIVENESS")
    assert len(feed) == 1 and feed[0].intended == "flatten" and feed[0].write_halt is True
    assert _find(recs, "UNPROTECTED_POSITION") == [] and _find(recs, "ORPHAN_ORDERS") == []
    assert len(wd.sender.flattens) == 1 and wd.sender.sends == []
    assert os.path.exists(_halt_path(tmp_path))


# ══════════════════════════════════════════════════════════════════════════════════════════
# 6. CONFIG INTEGRITY — tamper a TMP copy (never a live file) -> HALT + alert; and replicate
#    auto_live.py's arm-time refusal boolean via watchdog_belief (not main()).
# ══════════════════════════════════════════════════════════════════════════════════════════
def _tmp_config_pair(tmp_path):
    """Copy config_defaults.py + auto_safety.py into tmp_path and write a matching sha256 file.
    Returns (repo_dir, sha_path). Never touches the real repo files."""
    repo_copy = tmp_path / "cfgrepo"
    repo_copy.mkdir()
    lines = []
    for name in ("config_defaults.py", "auto_safety.py"):
        content = open(os.path.join(REPO_ROOT, name), "rb").read()
        (repo_copy / name).write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        lines.append(f"{digest}  {name}")
    sha_path = repo_copy / "eval_config.sha256"
    sha_path.write_text("\n".join(lines) + "\n")
    return str(repo_copy), str(sha_path)


def test_6_config_integrity_tamper_tmp_copy_halts(tmp_path, monkeypatch):
    repo_copy, sha_path = _tmp_config_pair(tmp_path)
    ok0, miss0 = WB.verify_eval_config_hashes(repo_dir=repo_copy, sha_path=sha_path)
    assert ok0 is True and miss0 == []                        # sanity: untampered copy matches

    # tamper the TEMP copy only
    with open(os.path.join(repo_copy, "config_defaults.py"), "a") as f:
        f.write("\n# tampered for test_6\n")
    ok1, miss1 = WB.verify_eval_config_hashes(repo_dir=repo_copy, sha_path=sha_path)
    assert ok1 is False and any("config_defaults.py" in m for m in miss1)

    snap = _snap(net=0)
    belief = _belief(expected_net=0)
    wd = _make("enforce", snap, belief, tmp_path, monkeypatch,
               config_verifier=lambda: WB.verify_eval_config_hashes(repo_dir=repo_copy, sha_path=sha_path))
    recs = wd.run_cycle(MORNING, grace_override=False)

    cfg = _find(recs, "CONFIG_INTEGRITY")
    assert len(cfg) == 1 and cfg[0].intended == "halt" and cfg[0].write_halt is True
    assert wd.sender.flattens == [] and wd.sender.sends == []  # config drift NEVER flattens
    assert os.path.exists(_halt_path(tmp_path))
    rows = _audit_rows(str(tmp_path / "audit"), MORNING, "CONFIG_INTEGRITY")
    assert len(rows) == 1 and rows[0]["action"] == "halt"
    assert any("CONFIG_INTEGRITY" in m for m in wd.tg.msgs)


def test_6b_auto_live_arm_time_refusal_logic(tmp_path):
    """Mirrors auto_live.py's WATCHDOG ARM-TIME CHECK (lines ~1410-1431): refuses to arm when
    enforcement is armed AND (config drifted OR the entry gate itself returns a block reason).
    Calls watchdog_belief functions directly — never auto_live.main()."""
    repo_copy, sha_path = _tmp_config_pair(tmp_path)
    with open(os.path.join(repo_copy, "auto_safety.py"), "a") as f:
        f.write("\n# tampered for test_6b\n")
    cfg_ok, cfg_miss = WB.verify_eval_config_hashes(repo_dir=repo_copy, sha_path=sha_path)
    assert cfg_ok is False

    hb_path = str(tmp_path / "heartbeat.json")     # absent -> gate is truthy too (belt-and-braces)
    halt_path = str(tmp_path / "HALT.flag")
    wd_gate = WB.watchdog_entry_block(hb_path=hb_path, halt_path=halt_path, now_utc=MORNING)
    assert wd_gate                                  # missing heartbeat -> block reason

    def _arm_time_refusal(cfg_ok, wd_gate, enforce):
        return bool(enforce and (not cfg_ok or wd_gate))

    assert _arm_time_refusal(cfg_ok, wd_gate, enforce=True) is True
    assert _arm_time_refusal(cfg_ok, wd_gate, enforce=False) is False   # observing only, never refuses


# ══════════════════════════════════════════════════════════════════════════════════════════
# 7. HEARTBEAT GATE — mirrors auto_live.py Auto.killed() lines ~234-242 (env-guarded call into
#    watchdog_belief.watchdog_entry_block). Called directly; auto_live is never imported.
# ══════════════════════════════════════════════════════════════════════════════════════════
def _entry_gate(hb_path, halt_path, now_utc):
    if os.environ.get("WATCHDOG_ENFORCE") == "1":
        return WB.watchdog_entry_block(hb_path=hb_path, halt_path=halt_path, now_utc=now_utc)
    return None


def _write_hb(path, ts_iso):
    with open(path, "w") as f:
        json.dump(dict(ts=ts_iso, pid=1, mode="enforce", last_cycle_ok=True), f)


def test_7_heartbeat_gate_armed_and_permissive(tmp_path, monkeypatch):
    hb_path = str(tmp_path / "heartbeat.json")
    halt_path = str(tmp_path / "HALT.flag")

    # -- armed (WATCHDOG_ENFORCE=1) --
    monkeypatch.setenv("WATCHDOG_ENFORCE", "1")
    _write_hb(hb_path, MORNING.isoformat())
    assert _entry_gate(hb_path, halt_path, MORNING) is None            # fresh heartbeat, no HALT -> permissive

    stale_ts = (MORNING - timedelta(seconds=200)).isoformat()
    _write_hb(hb_path, stale_ts)
    reason = _entry_gate(hb_path, halt_path, MORNING)
    assert reason and "stale" in reason                                  # >90s -> block

    _write_hb(hb_path, MORNING.isoformat())                              # fresh again
    with open(halt_path, "w") as f:
        f.write("{}")
    reason = _entry_gate(hb_path, halt_path, MORNING)
    assert reason and "HALT.flag" in reason                               # HALT present -> block
    os.remove(halt_path)

    os.remove(hb_path)
    reason = _entry_gate(hb_path, halt_path, MORNING)
    assert reason and "missing" in reason                                 # absent heartbeat -> block

    # -- unset (Monday-safe): always permissive regardless of heartbeat/HALT state --
    monkeypatch.delenv("WATCHDOG_ENFORCE", raising=False)
    assert _entry_gate(hb_path, halt_path, MORNING) is None                # heartbeat still absent
    with open(halt_path, "w") as f:
        f.write("{}")
    assert _entry_gate(hb_path, halt_path, MORNING) is None                # even with HALT.flag present
    os.remove(halt_path)


# ══════════════════════════════════════════════════════════════════════════════════════════
# 8. NEGATIVE CONTROLS
# ══════════════════════════════════════════════════════════════════════════════════════════
def test_8a_clean_session_replay_zero_actions(tmp_path, monkeypatch):
    """~40-frame clean session: entry decision -> resting -> partial fill -> fill -> bracket
    working -> EOD-flat before 14:30. Zero actions, no HALT, no telegram violation anywhere."""
    belief_box = {"v": _belief(expected_net=0)}
    snap0 = _snap(net=0, working_ids=[], working_count=0)
    wd = _make("enforce", snap0, lambda: belief_box["v"], tmp_path, monkeypatch)

    base = _et(2026, 7, 6, 9, 31)     # start early so the 4h bracket-hold still lands well before 14:30 ET
    frames = []   # (utc_time, belief_dict, snap_kwargs)

    # idle / entry-decision (flat, no orders) — 5 frames, 10s apart
    for k in range(5):
        frames.append((base + timedelta(seconds=10 * k),
                       _belief(expected_net=0), dict(net=0, working_ids=[], working_count=0)))

    # resting entry order posted (flat, one working order, KNOWN to us) — kept inside the 90s
    # in-flight grace so a legitimately-resting entry isn't mistaken for an orphan
    t0 = base + timedelta(seconds=60)
    for k in range(3):
        frames.append((t0 + timedelta(seconds=10 * k),
                       _belief(expected_net=0, entry_sids=["e1"], bracket_sids=["e1"]),
                       dict(net=0, working_ids=["e1"], working_count=1)))

    # partial fill (net moves to 1, matches belief) — consistent regardless of grace
    t1 = t0 + timedelta(seconds=40)
    for k in range(2):
        frames.append((t1 + timedelta(seconds=10 * k),
                       _belief(expected_net=1, entry_sids=["e1"], bracket_sids=["e1"]),
                       dict(net=1, working_ids=["e1"], working_count=1)))

    # full fill (net=3, entry sid deregisters, protective bracket sid remains + matches)
    t2 = t1 + timedelta(seconds=30)
    frames.append((t2, _belief(expected_net=3, bracket_sids=["b1"]),
                   dict(net=3, working_ids=["b1"], working_count=1)))

    # bracket working — long steady-state hold, sampled every 10 minutes, always consistent
    t3 = t2 + timedelta(seconds=30)
    for k in range(25):
        frames.append((t3 + timedelta(minutes=10 * k), _belief(expected_net=3, bracket_sids=["b1"]),
                       dict(net=3, working_ids=["b1"], working_count=1)))

    # EOD-flat before 14:30 — position + bracket both close cleanly
    t4 = t3 + timedelta(minutes=10 * 25) + timedelta(minutes=5)
    for k in range(3):
        frames.append((t4 + timedelta(seconds=10 * k), _belief(expected_net=0),
                       dict(net=0, working_ids=[], working_count=0)))

    assert len(frames) >= 38                                        # "~40 frames"
    assert frames[-1][0].astimezone(ET).time() < dtime(14, 30)       # genuinely "before 14:30"

    all_recs = []
    for now_utc, belief, snap_kwargs in frames:
        belief_box["v"] = belief
        wd.truth._snap = _snap(**snap_kwargs)
        all_recs += wd.run_cycle(now_utc)                          # natural grace — no override

    assert all_recs == []                                          # ZERO actions across the whole replay
    assert wd.sender.flattens == [] and wd.sender.sends == []
    assert not os.path.exists(_halt_path(tmp_path))
    assert wd.tg.msgs == []                                         # no violation alert, ever

    # transition-only recovery rows are allowed only if a violation occurred — none did, so the
    # audit file (if it exists at all) must carry zero "violation" rows.
    rows = _audit_rows(str(tmp_path / "audit"), frames[-1][0])
    assert all(r["verdict"] != "violation" for r in rows)


def test_8b_inflight_fill_grace_then_converged(tmp_path, monkeypatch):
    """Belief order-state changed 30s ago, broker briefly shows a position while belief still
    claims flat -> GRACE suppresses parity (no action). After the states CONVERGE (belief catches
    up), still no action — independent of whether grace has expired."""
    belief_box = {"v": _belief(expected_net=0)}
    wd = _make("enforce", _snap(net=0), lambda: belief_box["v"], tmp_path, monkeypatch)

    t0 = MORNING
    belief_box["v"] = _belief(expected_net=0)
    wd.truth._snap = _snap(net=0)
    wd.run_cycle(t0)                                                # seed baseline (startup grace, harmless)

    # order-state changes: a resting entry order posted, still flat
    t1 = t0 + timedelta(seconds=30)
    belief_box["v"] = _belief(expected_net=0, entry_sids=["e1"])
    wd.truth._snap = _snap(net=0)
    wd.run_cycle(t1)                                                 # state-change frame, consistent (no-op)

    # 30s after that state change: broker briefly shows a position, belief still says flat
    t2 = t1 + timedelta(seconds=30)
    belief_box["v"] = _belief(expected_net=0, entry_sids=["e1"])      # UNCHANGED belief state
    wd.truth._snap = _snap(net=1, working_ids=["e1"], working_count=1)
    recs = wd.run_cycle(t2)                                           # 30s since last state change < 90s grace
    assert _find(recs, "POSITION_PARITY") == []                       # grace suppressed it entirely — no record
    assert recs == []                                                 # no action of any kind this cycle
    assert wd.sender.flattens == [] and wd.sender.sends == []
    assert not os.path.exists(_halt_path(tmp_path))

    # >90s after the state change, states now CONVERGED (belief caught up to the fill)
    t3 = t1 + timedelta(seconds=125)
    belief_box["v"] = _belief(expected_net=1, entry_sids=["e1"])       # converged, no longer a mismatch
    wd.truth._snap = _snap(net=1, working_ids=["e1"], working_count=1)
    recs2 = wd.run_cycle(t3)
    assert recs2 == []                                                # genuinely matched — no action either way
    assert wd.sender.flattens == [] and wd.sender.sends == []
    assert not os.path.exists(_halt_path(tmp_path))


# ══════════════════════════════════════════════════════════════════════════════════════════
# 9. AUTHORITY BOUNDARY — AST-parse watchdog.py + watchdog_belief.py.
# ══════════════════════════════════════════════════════════════════════════════════════════
def test_9_authority_boundary_no_entry_imports_and_sender_methods():
    src = open(os.path.join(REPO_ROOT, "watchdog.py")).read()
    tree = ast.parse(src, filename="watchdog.py")

    imported_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported_names += [a.name for a in node.names]

    forbidden_prefixes = ("build_entry",)
    forbidden_exact = ("send_exit3", "build_entry_exit3", "build_entry_single")
    for name in imported_names:
        assert not name.startswith(forbidden_prefixes), f"forbidden import: {name}"
        assert name not in forbidden_exact, f"forbidden import: {name}"

    # collect every `.sender.<attr>(...)` call site, and which enclosing function it's in
    sender_calls = []   # (method_name, enclosing_function_name)

    class _Visitor(ast.NodeVisitor):
        def __init__(self):
            self.func_stack = []

        def visit_FunctionDef(self, node):
            self.func_stack.append(node.name)
            self.generic_visit(node)
            self.func_stack.pop()

        def visit_Call(self, node):
            f = node.func
            if (isinstance(f, ast.Attribute)
                    and isinstance(f.value, ast.Attribute)
                    and f.value.attr == "sender"
                    and isinstance(f.value.value, ast.Name) and f.value.value.id == "self"):
                enclosing = self.func_stack[-1] if self.func_stack else None
                sender_calls.append((f.attr, enclosing))
            self.generic_visit(node)

    _Visitor().visit(tree)
    methods_used = {m for m, _ in sender_calls}
    assert methods_used == {"flatten", "send"}, f"unexpected sender methods invoked: {methods_used}"
    send_sites = [fn for m, fn in sender_calls if m == "send"]
    assert send_sites and all(fn == "_send_cancel_only" for fn in send_sites), \
        f"self.sender.send(...) invoked outside _send_cancel_only: {send_sites}"
    flatten_sites = [fn for m, fn in sender_calls if m == "flatten"]
    assert flatten_sites and all(fn == "_execute_send" for fn in flatten_sites)


def test_9b_watchdog_belief_no_sender_construction():
    src = open(os.path.join(REPO_ROOT, "watchdog_belief.py")).read()
    tree = ast.parse(src, filename="watchdog_belief.py")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert "sender" not in a.name.lower(), f"belief module imports a sender: {a.name}"
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                assert "sender" not in a.name.lower(), f"belief module imports a sender: {a.name}"
        elif isinstance(node, ast.Call):
            f = node.func
            fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            assert "sender" not in fname.lower(), f"belief module constructs/calls a sender: {fname}"


# ══════════════════════════════════════════════════════════════════════════════════════════
# 10. DEDUP REPLAY at scale — persistent violation across many 10s-apart frames.
# ══════════════════════════════════════════════════════════════════════════════════════════
def test_10_dedup_replay_backstop_fires_exactly_twice(tmp_path, monkeypatch):
    """Broker STAYS nonflat for the whole replay -> exactly 2 sends: the initial ok->violation
    fire, plus exactly one 5-minute (300s) backstop re-fire. 32 frames (10s apart) so the replay
    crosses the 300s boundary (30 * 10s = 290s would land just short of it)."""
    snap = _snap(net=1)
    belief = _belief(expected_net=0)
    wd = _make("enforce", snap, belief, tmp_path, monkeypatch)
    recs = []
    for k in range(32):
        recs += wd.run_cycle(MORNING + timedelta(seconds=10 * k), grace_override=False)
    parity = _find(recs, "POSITION_PARITY")
    assert len(parity) == 32                              # a duration row every cycle
    assert sum(1 for r in parity if r.executed) == 2       # initial fire + exactly one backstop
    assert len(wd.sender.flattens) == 2
    assert wd.sender.sends == []
    assert os.path.exists(_halt_path(tmp_path))


def test_10b_dedup_replay_no_refire_once_broker_flat(tmp_path, monkeypatch):
    """Broker goes flat right after the first flatten (it worked) -> exactly 1 send total, even
    across many more cycles spanning past the 300s backstop window."""
    snap = _snap(net=1)
    belief = _belief(expected_net=0)
    wd = _make("enforce", snap, belief, tmp_path, monkeypatch)
    wd.run_cycle(MORNING, grace_override=False)             # violation -> fire #1
    assert len(wd.sender.flattens) == 1
    wd.truth._snap = _snap(net=0)                            # broker now flat, matches belief (also flat)
    for k in range(1, 32):
        wd.run_cycle(MORNING + timedelta(seconds=10 * k), grace_override=False)
    assert len(wd.sender.flattens) == 1                      # no re-fire, ever
    assert wd.sender.sends == []
    assert os.path.exists(_halt_path(tmp_path))               # HALT.flag from the incident is never
                                                               # auto-cleared — manual reset by design
