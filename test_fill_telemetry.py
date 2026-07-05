"""Tests for fill_telemetry.py — observation-only fill-quality recorder.

Coverage (the mandatory set from the build spec):
  * Replay: decision -> send -> resting -> 3 bars (2 touching) -> fill on 2nd touch, exact event
    sequence incl. touch_seq and touch-WITHOUT-fill on touch 1.
  * Broken-logger (MANDATORY): a queue that raises on every enqueue -> no exception reaches the
    caller, the order-flow function returns normally, and a warning is printed.
  * Queue-full: put_nowait path increments `dropped` and never blocks (time-bounded).
  * Restart: a new instance the same ET day appends to the same valid JSONL file.
  * Scrub: the raw account id never appears in a written file (only account_tag does).

Sizing-forensics coverage (schema v2, added 2026-07-05):
  * DECISION carries qty_formula/qty_cap/qty_submitted with correct values, schema bumped to 2.
  * ORDER_SENT carries per-leg qty_submitted + qty_submitted_total.
  * FILL_CONFIRMED carries qty_filled, partial_fill, and time_to_fill_s (via a controllable fake
    clock so the assertion is exact, not a flaky real-time sleep) + its poll-granularity caveat.
  * Broken-logger (MANDATORY, extended): an exception raised strictly INSIDE a new field's
    computation (qty_formula coercion, time_to_fill_s from a corrupted registry entry) still fails
    open — no exception reaches the caller, order flow completes, a warning is printed.
"""
from __future__ import annotations

import json
import os
import queue
import time
from datetime import datetime, timezone

import pytest

import fill_telemetry as ft_module
from fill_telemetry import FillTelemetry, account_tag, NY


# ------------------------------------------------------------------ helpers

def _et_date() -> str:
    return datetime.now(timezone.utc).astimezone(NY).date().isoformat()


def _long_leg(level=19000.0, stop=18980.0, target=19040.0, qty=1, sid="ZB-testcore", acct="ACC"):
    """A single core (entry_tp2) leg shaped like build_entry_exit3 output for a qty=1 long."""
    payload = {"ticker": "MNQ", "action": "buy", "quantity": qty, "orderType": "limit",
               "limitPrice": level, "stopLoss": {"type": "stop", "stopPrice": stop},
               "takeProfit": {"limitPrice": target},
               "extras": {"signalId": sid, "account": acct}}   # raw account lives here — must NOT be written
    return dict(role="entry_tp2", qty=qty, r_target=2.0, target=target, payload=payload)


def _result_ok(role="entry_tp2", qty=1):
    return dict(ok=True, reason="sent", legs=[dict(role=role, qty=qty, sent=True, status=200)])


def _read(base_dir) -> list[dict]:
    path = os.path.join(base_dir, f"{_et_date()}.jsonl")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(ln) for ln in f if ln.strip()]


# ------------------------------------------------------------------ replay

def test_replay_sequence_and_touch_seq(tmp_path):
    """Full episode: DECISION, ORDER_SENT, TOUCH#1, (non-touch bar), TOUCH#2, FILL_CONFIRMED."""
    d = str(tmp_path / "ft")
    t = FillTelemetry(base_dir=d)
    acct = "ACC-REPLAY"
    sid = "ZB-replaycore"

    t.on_decision(strategy="A", side="long", signal_ts="TS100", account=acct,
                  intended_price=19000.0, submitted_price=19000.0, stop=18980.0, target=19040.0,
                  qty=1, d1c=dict(mode="ACTIVE_EVAL_FILTER", status="GREEN", allowed=True, drift=0.1),
                  decision_wall_ts="2026-07-05T13:30:00+00:00", bar_ts="2026-07-05T09:30:00")
    t.on_order_sent(strategy="A", side="long", signal_ts="TS100", account=acct,
                    legs=[_long_leg(sid=sid, acct=acct)], result=_result_ok())
    # bar 1 — trades THROUGH the 19000 limit (low 18999) -> TOUCH #1, filled_yet False
    t.on_bar("b1", 19002.0, 19003.0, 18999.0, 19001.0)
    # bar 2 — stays ABOVE the limit (low 19001) -> NO touch
    t.on_bar("b2", 19002.0, 19004.0, 19001.0, 19003.0)
    # bar 3 — trades through again (low 18998) -> TOUCH #2; fill confirmed just after
    t.on_bar("b3", 19001.0, 19002.0, 18998.0, 18999.0)
    t.on_fill_confirmed(account=acct, expected=1, broker=1)

    t.flush(); t.close()
    rows = _read(d)
    events = [r["event"] for r in rows]
    assert events == ["DECISION", "ORDER_SENT", "TOUCH", "TOUCH", "FILL_CONFIRMED"]

    dec = rows[0]
    assert dec["intended_price"] == pytest.approx(19000.0)
    assert dec["submitted_price"] == pytest.approx(19000.0)
    assert dec["d1c"]["mode"] == "ACTIVE_EVAL_FILTER"

    sent = rows[1]
    assert sent["role"] == "entry_tp2" and sent["send_ok"] is True and sent["limit"] == pytest.approx(19000.0)

    touches = [r for r in rows if r["event"] == "TOUCH"]
    assert [r["touch_seq"] for r in touches] == [1, 2]
    assert all(r["filled_yet"] is False for r in touches)          # crown jewel: touch WITHOUT fill at record time
    assert touches[0]["low"] == pytest.approx(18999.0)

    fill = rows[-1]
    assert fill["prior_touch_count"] == 2                          # fill-time-vs-touch-time is derivable
    assert fill["expected"] == 1 and fill["broker"] == 1 and fill["poll_s"] == 20


# ------------------------------------------------------------------ sizing forensics (schema v2)

def test_decision_sizing_fields_and_time_to_fill(tmp_path, monkeypatch):
    """qty_formula/qty_cap/qty_submitted land on DECISION with correct values (schema bumped to 2);
    per-leg qty_submitted + qty_submitted_total land on ORDER_SENT; time_to_fill_s on FILL_CONFIRMED
    reflects the registered ORDER_SENT wall-ts vs the confirm wall-ts, using a controllable fake
    clock so the assertion is exact rather than a flaky real-time sleep."""
    d = str(tmp_path / "ft")
    t = FillTelemetry(base_dir=d)
    acct = "ACC-SIZING"
    sid = "ZB-sizing"

    clock = {"t": 1000.0}
    monkeypatch.setattr(ft_module.time, "time", lambda: clock["t"])

    # auto_live.py computes qty_formula from entry/stop/A_RISK_BUDGET_USD before calling on_decision;
    # here we feed known pre-computed values straight into the recorder.
    t.on_decision(strategy="A", side="long", signal_ts="TS200", account=acct,
                  intended_price=19000.0, submitted_price=19000.0, stop=18980.0, target=19040.0,
                  qty=3, qty_formula=7, qty_cap=5, qty_submitted=3)

    t.on_order_sent(strategy="A", side="long", signal_ts="TS200", account=acct,
                    legs=[_long_leg(sid=sid, acct=acct, qty=3)], result=_result_ok(qty=3))

    clock["t"] = 1000.0 + 2 * 20                    # confirm detected 2 poll-cycles later (poll_s=20)
    t.on_fill_confirmed(account=acct, expected=3, broker=3, poll_s=20)

    t.flush(); t.close()
    rows = _read(d)

    dec = rows[0]
    assert dec["schema"] == 2
    assert dec["qty_formula"] == 7 and dec["qty_cap"] == 5 and dec["qty_submitted"] == 3

    sent = rows[1]
    assert sent["qty_submitted"] == 3 and sent["qty_submitted_total"] == 3

    fill = rows[-1]
    assert fill["qty_filled"] == 3
    assert fill["partial_fill"] is False
    assert fill["time_to_fill_s"] == pytest.approx(40.0)
    assert "poll" in fill["time_to_fill_s_caveat"]


def test_partial_fill_flag_on_mismatched_qty(tmp_path):
    """broker net position short of `expected` -> partial_fill True; qty_filled mirrors broker."""
    d = str(tmp_path / "ft")
    t = FillTelemetry(base_dir=d)
    acct = "ACC-PARTIAL"
    sid = "ZB-partial"

    t.on_order_sent(strategy="A", side="long", signal_ts="TS300", account=acct,
                    legs=[_long_leg(sid=sid, acct=acct, qty=3)], result=_result_ok(qty=3))
    t.on_fill_confirmed(account=acct, expected=3, broker=1)          # only 1 of the expected 3 filled

    t.flush(); t.close()
    rows = _read(d)
    fill = rows[-1]
    assert fill["qty_filled"] == 1
    assert fill["partial_fill"] is True


def test_broken_sizing_fields_never_block_order_flow(tmp_path, capsys):
    """Extends the mandatory broken-logger contract to the NEW schema-v2 fields: an exception raised
    strictly inside a new field's computation (qty_formula coercion; time_to_fill_s subtraction on a
    corrupted registry entry) must still fail open — no exception reaches the caller, order flow
    completes, and a warning is printed for each failure."""
    d = str(tmp_path / "ft")
    t = FillTelemetry(base_dir=d)
    acct = "ACC-BROKENFIELDS"
    sid = "ZB-brokenfields"

    class _Uncoercible:
        """Can't be coerced to int — forces an exception inside on_decision's qty_formula handling,
        not the enqueue path."""
        def __int__(self):
            raise TypeError("cannot coerce qty_formula")

    def fake_order_flow():
        t.on_decision(strategy="A", side="long", signal_ts="TS", account=acct,
                      intended_price=19000.0, submitted_price=19000.0, stop=18980.0, target=19040.0,
                      qty=1, qty_formula=_Uncoercible(), qty_cap=1, qty_submitted=1)
        t.on_order_sent(strategy="A", side="long", signal_ts="TS", account=acct,
                        legs=[_long_leg(sid=sid, acct=acct)], result=_result_ok())
        # corrupt the registered sent_wall_ts so the new time_to_fill_s subtraction raises a TypeError
        with t._reg_lock:
            t._registry[sid]["sent_wall_ts"] = "not-a-number"
        t.on_fill_confirmed(account=acct, expected=1, broker=1)
        return "ORDER_FLOW_OK"

    assert fake_order_flow() == "ORDER_FLOW_OK"                     # no exception reaches the caller
    out = capsys.readouterr().out
    assert "[fill-telem]" in out
    assert "on_decision error" in out
    assert "on_fill_confirmed error" in out
    t.flush(); t.close()


# ------------------------------------------------------------------ broken logger (MANDATORY)

class _BrokenQueue:
    """Raises on every enqueue; get() parks so the writer thread never spins."""
    def put_nowait(self, x):
        raise RuntimeError("boom — enqueue broken")

    def get(self, *a, **k):
        time.sleep(3600)

    def task_done(self):
        pass


def test_broken_logger_never_blocks_order_flow(tmp_path, capsys):
    d = str(tmp_path / "ft")
    t = FillTelemetry(base_dir=d)
    t._q = _BrokenQueue()                                          # every write now raises

    def fake_order_flow():
        """Stand-in for an order-flow function that calls telemetry then returns normally."""
        t.on_decision(strategy="A", side="long", signal_ts="TS", account="ACC",
                      intended_price=19000.0, submitted_price=19000.0, stop=18980.0,
                      target=19040.0, qty=1)
        t.on_order_sent(strategy="A", side="long", signal_ts="TS", account="ACC",
                        legs=[_long_leg()], result=_result_ok())
        t.on_bar("b1", 19002.0, 19003.0, 18999.0, 19001.0)
        t.on_fill_confirmed(account="ACC", expected=1, broker=1)
        t.on_order_resolved(account="ACC", reason="ttl")
        return "ORDER_FLOW_OK"

    # (a) no exception reaches the caller; (b) the function returns normally
    assert fake_order_flow() == "ORDER_FLOW_OK"
    # dropped counter moved (writes were shed, not raised)
    assert t.dropped > 0
    # (c) a warning was printed
    out = capsys.readouterr().out
    assert "[fill-telem]" in out and "enqueue failed" in out


# ------------------------------------------------------------------ queue full

def test_queue_full_increments_dropped_without_blocking(tmp_path):
    d = str(tmp_path / "ft")
    t = FillTelemetry(base_dir=d)
    t.close()                                                      # stop the writer so nothing drains
    t._q = queue.Queue(maxsize=1)
    t._q.put_nowait("occupied")                                    # queue is now FULL

    # register a resting order (ORDER_SENT emit is shed, but registration still happens)
    t.on_order_sent(strategy="A", side="long", signal_ts="TS", account="ACC",
                    legs=[_long_leg()], result=_result_ok())
    before = t.dropped

    start = time.time()
    t.on_bar("b1", 19002.0, 19003.0, 18999.0, 19001.0)            # TOUCH -> put_nowait -> Full
    elapsed = time.time() - start

    assert t.dropped > before                                     # the Full path bumped the counter
    assert elapsed < 1.0                                          # never blocked


# ------------------------------------------------------------------ restart

def test_restart_appends_valid_jsonl(tmp_path):
    d = str(tmp_path / "ft")
    t1 = FillTelemetry(base_dir=d)
    t1.on_decision(strategy="A", side="long", signal_ts="TS1", account="ACC",
                   intended_price=19000.0, submitted_price=19000.0, stop=18980.0, target=19040.0, qty=1)
    t1.flush(); t1.close()

    t2 = FillTelemetry(base_dir=d)                                # new instance, SAME ET day + dir
    t2.on_order_resolved(account="ACC", reason="restart_test")
    t2.flush(); t2.close()

    path = os.path.join(d, f"{_et_date()}.jsonl")
    lines = [ln for ln in open(path).read().splitlines() if ln.strip()]
    assert len(lines) == 2                                        # append continued across restart
    parsed = [json.loads(ln) for ln in lines]                    # every line is valid JSON
    assert parsed[0]["event"] == "DECISION" and parsed[1]["event"] == "ORDER_RESOLVED"


# ------------------------------------------------------------------ scrub

def test_no_raw_account_in_file(tmp_path):
    d = str(tmp_path / "ft")
    acct = "MFFU-50K-SUPERSECRET-999"
    t = FillTelemetry(base_dir=d)
    t.on_decision(strategy="A", side="long", signal_ts="TS", account=acct,
                  intended_price=19000.0, submitted_price=19000.0, stop=18980.0, target=19040.0, qty=1)
    t.on_order_sent(strategy="A", side="long", signal_ts="TS", account=acct,
                    legs=[_long_leg(acct=acct)], result=_result_ok())
    t.on_bar("b1", 19002.0, 19003.0, 18999.0, 19001.0)
    t.on_fill_confirmed(account=acct, expected=1, broker=1)
    t.flush(); t.close()

    content = open(os.path.join(d, f"{_et_date()}.jsonl")).read()
    assert acct not in content                                    # raw account id NEVER written
    assert account_tag(acct) in content                          # only the tag appears
    assert "http://" not in content and "https://" not in content
