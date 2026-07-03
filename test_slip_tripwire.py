"""Tests for the execution slippage tripwire. Spec: docs/specs/slippage_tripwire_spec.md"""
import os
import tempfile

import pytest

from slip_tripwire import evaluate, SlipTripwire
from config_defaults import slip_tripwire_cfg

CFG = slip_tripwire_cfg()


# ---------------------------------------------------------------- pure evaluate()

def test_warmup_no_action_before_min_resolved():
    # Even a catastrophic single fill can't act before warmup_min resolutions.
    slips = [5.0]
    res = ["FILLED"]
    assert evaluate(slips, res, CFG) == (None, "")


def test_clean_fills_no_action():
    slips = [0.0, -0.02, 0.01, 0.0, -0.05, 0.02]   # all at/under model, some better
    res = ["FILLED"] * len(slips)
    action, _ = evaluate(slips, res, CFG)
    assert action is None


def test_creeping_mean_slippage_halts():
    # 6 fills averaging ~0.15R (> 0.10R cap) -> HALT
    slips = [0.12, 0.14, 0.16, 0.13, 0.18, 0.17]
    res = ["FILLED"] * len(slips)
    action, reason = evaluate(slips, res, CFG)
    assert action == "HALT"
    assert "mean entry slippage" in reason


def test_single_fat_print_halts_after_warmup():
    # 5 clean fills then one 0.6R disaster (> single_r_halt 0.50) -> HALT
    slips = [0.0, 0.01, 0.0, -0.01, 0.0, 0.60]
    res = ["FILLED"] * len(slips)
    action, reason = evaluate(slips, res, CFG)
    assert action == "HALT"
    assert "single fill" in reason


def test_single_mid_print_alerts_not_halts():
    # last fill 0.30R: over alert (0.25) but under halt (0.50), mean stays low -> ALERT
    slips = [0.0, 0.0, 0.01, 0.0, -0.02, 0.30]
    res = ["FILLED"] * len(slips)
    action, reason = evaluate(slips, res, CFG)
    assert action == "ALERT"
    assert "single fill" in reason


def test_high_miss_rate_halts():
    # 6 signals, 3 missed (50% > 40% cap); the fills that did happen are clean.
    res = ["FILLED", "MISSED", "FILLED", "MISSED", "FILLED", "MISSED"]
    slips = [0.0, 0.0, 0.01]   # only the FILLED ones produce slips
    action, reason = evaluate(slips, res, CFG)
    assert action == "HALT"
    assert "miss rate" in reason


def test_negative_slippage_never_trips():
    slips = [-0.3, -0.5, -0.2, -0.4, -0.1, -0.6]   # all BETTER than modeled
    res = ["FILLED"] * len(slips)
    assert evaluate(slips, res, CFG) == (None, "")


def test_window_excludes_old_bad_fills():
    # Old bad fills fall out of window_n=10; recent 10 are clean -> no halt.
    slips = [0.9, 0.9, 0.9] + [0.0] * 10
    res = ["FILLED"] * len(slips)
    action, _ = evaluate(slips, res, CFG)
    assert action is None


# ---------------------------------------------------------------- SlipTripwire (stateful)

def _wire(mode, tmp):
    alerts, halts = [], []
    tw = SlipTripwire(CFG, mode=mode,
                      on_alert=lambda m: alerts.append(m),
                      on_halt=lambda r: halts.append(r),
                      event_csv=os.path.join(tmp, "slip_events.csv"))
    return tw, alerts, halts


def test_mode_off_is_noop():
    with tempfile.TemporaryDirectory() as tmp:
        tw, alerts, halts = _wire("off", tmp)
        for _ in range(10):
            tw.observe_fill(1.0)   # would be catastrophic if evaluated
        assert alerts == [] and halts == []
        assert tw.status()["n_resolved"] == 0


def test_alert_mode_never_calls_on_halt():
    with tempfile.TemporaryDirectory() as tmp:
        tw, alerts, halts = _wire("alert", tmp)
        for _ in range(6):
            tw.observe_fill(0.6)   # HALT-worthy every fill
        assert halts == []                 # never latched the sentinel
        assert any("SLIP-TRIPWIRE HALT" in m for m in alerts)
        assert any("alert-only" in m for m in alerts)   # reports what it WOULD do
        assert tw.status()["halted"] is True            # internal latch still records it


def test_halt_mode_calls_on_halt_once():
    with tempfile.TemporaryDirectory() as tmp:
        tw, alerts, halts = _wire("halt", tmp)
        for _ in range(6):
            tw.observe_fill(0.6)
        assert len(halts) == 1             # idempotent — fires exactly once, no spam
        assert "single fill" in halts[0]


def test_halt_event_written_to_csv():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "slip_events.csv")
        tw = SlipTripwire(CFG, mode="halt", event_csv=csv_path)
        for _ in range(6):
            tw.observe_fill(0.6)
        assert os.path.exists(csv_path)
        with open(csv_path) as f:
            body = f.read()
        assert "HALT" in body and "wall_ts" in body


def test_none_slippage_counts_as_resolution_not_fill():
    # panel couldn't price the fill: resolution recorded, but no slip data point.
    with tempfile.TemporaryDirectory() as tmp:
        tw, _, _ = _wire("halt", tmp)
        for _ in range(6):
            tw.observe_fill(None)
        st = tw.status()
        assert st["n_resolved"] == 6 and st["n_fills"] == 0


def test_observe_never_raises_on_bad_input():
    with tempfile.TemporaryDirectory() as tmp:
        tw, _, _ = _wire("halt", tmp)
        # garbage inputs must be swallowed, never propagate into the order path
        assert tw.observe_fill("not-a-number") == (None, "")
        assert tw.observe_fill(float("nan")) is not None  # returns a tuple, doesn't raise


def test_alert_dedupes_identical_reason():
    with tempfile.TemporaryDirectory() as tmp:
        tw, alerts, _ = _wire("alert", tmp)
        # build up to a stable single-fill alert reason repeated
        tw.observe_fill(0.0); tw.observe_fill(0.0); tw.observe_fill(0.0)
        tw.observe_fill(0.0); tw.observe_fill(0.0)
        n_before = len(alerts)
        tw.observe_fill(0.30)   # ALERT
        tw.observe_fill(0.30)   # same reason — should not re-alert
        watch_alerts = [m for m in alerts if "watch" in m]
        assert len(watch_alerts) == 1


# ---------------------------------------------------------------- sentinel slip_halt

def test_sentinel_slip_halt_latches_and_is_idempotent():
    from live_readback import ReadbackSentinel
    msgs = []
    s = ReadbackSentinel("TEST", on_alert=lambda m: msgs.append(m))
    assert s.ready()[0] is True
    s.slip_halt("mean entry slippage 0.14R over last 10 fills")
    ready, why = s.ready()
    assert ready is False
    assert "SLIP-HALT" in why
    assert len(msgs) == 1
    s.slip_halt("another reason")   # idempotent — no second alert, reason unchanged
    assert len(msgs) == 1
    # operator /resume clears it
    s.reset()
    assert s.ready()[0] is True


def test_sentinel_slip_halt_never_flattens():
    # slip_halt must not invoke on_critical/flatten — only halt+alert.
    from live_readback import ReadbackSentinel
    flat = []
    s = ReadbackSentinel("TEST",
                         on_alert=lambda m: None, on_critical=lambda r: flat.append(r))
    s.slip_halt("bad fills")
    assert flat == []
