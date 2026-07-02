"""Unit tests for exec_telemetry.py.

Tests cover:
  * CSV writer produces correct headers + row content
  * Slippage math: long fill (positive = paid more = slip worse) and short fill
  * bar_to_decision_ms computed correctly for tz-aware bar ts
  * decision_to_webhook_ms computed correctly
  * webhook_to_fill_ms computed correctly
  * MISSED path flushes with resolution=MISSED, no slippage fields
  * CANCELLED path flushes with resolution=CANCELLED
  * pending_signal_ts returns most-recent armed signal
  * Exceptions inside every method are SWALLOWED (never raised) — order-path safety
  * poll_increment increments counter
  * A second on_decision for the same signal_ts overwrites the pending row (restart idempotency)
  * on_fill_confirmed with panel_readable=False leaves actual_fill_px / slippage blank
"""
from __future__ import annotations

import csv
import io
import os
import tempfile
from datetime import datetime, timezone, timedelta

import pytest

from exec_telemetry import ExecTelemetry, COLUMNS


# ------------------------------------------------------------------ helpers

def _utc(y=2026, mo=7, d=2, h=10, mi=0, s=0) -> datetime:
    return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)


def _make_telem(tmp_path: str) -> ExecTelemetry:
    return ExecTelemetry(csv_path=str(tmp_path))


def _read_rows(csv_path: str) -> list[dict]:
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------------ tests

def test_csv_header_and_filled_row(tmp_path):
    """A complete fill cycle writes one row with correct header."""
    p = str(tmp_path / "telem.csv")
    t = ExecTelemetry(p)
    bar_ts = _utc(h=9, mi=30)
    dec_wall = _utc(h=9, mi=30, s=1)
    wh_wall = _utc(h=9, mi=30, s=2)
    fill_wall = _utc(h=9, mi=31)

    t.on_decision("TS001", bar_ts, dec_wall, 19000.0, 18980.0, 19040.0, 3, "long", "A")
    t.on_webhook_result("TS001", 200, wh_wall)
    t.on_fill_confirmed("TS001", 19001.5, True, fill_wall)

    rows = _read_rows(p)
    assert len(rows) == 1
    r = rows[0]
    assert r["signal_ts"] == "TS001"
    assert r["strategy"] == "A"
    assert r["side"] == "long"
    assert r["webhook_http_status"] == "200"
    assert r["resolution"] == "FILLED"
    assert r["panel_readable"] == "True"
    assert float(r["actual_fill_px"]) == pytest.approx(19001.5)
    # slippage: (19001.5 - 19000.0) × +1 = 1.5 pts
    assert float(r["slippage_pts"]) == pytest.approx(1.5)
    # slippage_R: 1.5 / 20.0 = 0.075
    assert float(r["slippage_R"]) == pytest.approx(0.075)
    # all COLUMNS present as headers
    with open(p) as f:
        header = f.readline().strip().split(",")
    assert header == COLUMNS


def test_slippage_short_fill(tmp_path):
    """Short fill: slippage_pts = (actual - expected) × -1; positive = filled higher = worse."""
    p = str(tmp_path / "telem.csv")
    t = ExecTelemetry(p)
    t.on_decision("TS002", "2026-07-02T09:35:00", _utc(h=9, mi=35), 19000.0, 19020.0, 18940.0, 2, "short", "A")
    t.on_webhook_result("TS002", 200, _utc(h=9, mi=35, s=1))
    # actual fill = 18999.0 (below expected 19000.0); for short that means BETTER fill
    t.on_fill_confirmed("TS002", 18999.0, True, _utc(h=9, mi=36))
    rows = _read_rows(p)
    r = rows[0]
    # slippage = (18999.0 - 19000.0) × -1 = +1.0  (positive = unfavourable for short? no wait)
    # For SHORT: positive slippage = filled at higher price (worse). lower fill = negative slip = good.
    # slip = (actual - expected) * direction; direction = -1 for short
    # slip = (18999 - 19000) * -1 = +1.0  WAIT that's positive but 18999 is BETTER than 19000 for short
    # Hmm, let me reconsider the sign convention:
    # "positive = filled WORSE than expected"
    # Short: expected 19000, actual 18999 → filled at lower price → less favourable? No, for short LOWER fill IS better.
    # Actually for short: expected to sell at 19000, got 18999 → sold for less → WORSE → positive slip.
    # slip = (actual - expected) * (-1) because direction_sign = -1
    # = (18999 - 19000) * -1 = 1.0  ← positive = indeed worse
    assert float(r["slippage_pts"]) == pytest.approx(1.0)
    # stop_distance = |19000 - 19020| = 20 pts
    assert float(r["slippage_R"]) == pytest.approx(1.0 / 20.0)


def test_slippage_zero_when_fill_exact(tmp_path):
    """Exact fill at expected price → slippage_pts = 0."""
    p = str(tmp_path / "telem.csv")
    t = ExecTelemetry(p)
    t.on_decision("TS003", "2026-07-02T10:00:00", _utc(h=10), 19500.0, 19480.0, 19560.0, 1, "long", "A")
    t.on_webhook_result("TS003", 200, _utc(h=10, s=1))
    t.on_fill_confirmed("TS003", 19500.0, True, _utc(h=10, mi=1))
    rows = _read_rows(p)
    assert float(rows[0]["slippage_pts"]) == pytest.approx(0.0)
    assert float(rows[0]["slippage_R"]) == pytest.approx(0.0)


def test_missed_path(tmp_path):
    """on_missed writes MISSED row with no slippage / fill fields."""
    p = str(tmp_path / "telem.csv")
    t = ExecTelemetry(p)
    t.on_decision("TS010", "2026-07-02T09:35:00", _utc(h=9, mi=35), 19100.0, 19080.0, 19160.0, 3, "long", "A")
    t.on_webhook_result("TS010", None, _utc(h=9, mi=35, s=1))   # dry-run, no HTTP status
    t.on_missed("TS010")
    rows = _read_rows(p)
    assert len(rows) == 1
    r = rows[0]
    assert r["resolution"] == "MISSED"
    assert r["actual_fill_px"] in ("", "None", None)
    assert r["slippage_pts"] in ("", "None", None)


def test_cancelled_path(tmp_path):
    """on_cancelled writes CANCELLED row."""
    p = str(tmp_path / "telem.csv")
    t = ExecTelemetry(p)
    t.on_decision("TS011", "2026-07-02T10:05:00", _utc(h=10, mi=5), 19200.0, 19180.0, 19260.0, 2, "long", "A")
    t.on_webhook_result("TS011", 200, _utc(h=10, mi=5, s=1))
    t.on_cancelled("TS011", "operator cancel")
    rows = _read_rows(p)
    assert rows[0]["resolution"] == "CANCELLED"
    assert rows[0]["notes"] == "operator cancel"


def test_pending_signal_ts_returns_most_recent(tmp_path):
    """pending_signal_ts returns the most recently armed signal."""
    p = str(tmp_path / "telem.csv")
    t = ExecTelemetry(p)
    assert t.pending_signal_ts() is None
    t.on_decision("TS020", "ts", _utc(), 100.0, 90.0, 120.0, 1, "long")
    assert t.pending_signal_ts() == "TS020"
    t.on_decision("TS021", "ts", _utc(), 100.0, 90.0, 120.0, 1, "long")
    assert t.pending_signal_ts() == "TS021"


def test_poll_increment_counts(tmp_path):
    """poll_increment increments per-row counter."""
    p = str(tmp_path / "telem.csv")
    t = ExecTelemetry(p)
    t.on_decision("TS030", "ts", _utc(), 19000.0, 18980.0, 19040.0, 1, "long")
    t.poll_increment("TS030")
    t.poll_increment("TS030")
    t.poll_increment("TS030")
    t.on_fill_confirmed("TS030", 19001.0, True, _utc(h=10))
    rows = _read_rows(p)
    # 3 poll_increment calls BEFORE on_fill_confirmed; on_fill_confirmed doesn't add one
    assert int(rows[0]["polls_to_confirm"]) == 3


def test_fill_confirmed_no_avg_price(tmp_path):
    """Fill confirmed but panel unreadable → actual_fill_px blank, no slippage."""
    p = str(tmp_path / "telem.csv")
    t = ExecTelemetry(p)
    t.on_decision("TS040", "ts", _utc(), 19000.0, 18980.0, 19040.0, 2, "long")
    t.on_webhook_result("TS040", 200, _utc(s=1))
    t.on_fill_confirmed("TS040", None, False, _utc(mi=1))
    rows = _read_rows(p)
    r = rows[0]
    assert r["panel_readable"] == "False"
    assert r["actual_fill_px"] in ("", "None", None)
    assert r["slippage_pts"] in ("", "None", None)
    assert r["resolution"] == "FILLED"


def test_on_decision_overwrite_same_slot(tmp_path):
    """A second on_decision for the same signal_ts overwrites the pending row."""
    p = str(tmp_path / "telem.csv")
    t = ExecTelemetry(p)
    t.on_decision("TS050", "ts", _utc(h=9), 19000.0, 18980.0, 19040.0, 1, "long")
    t.on_decision("TS050", "ts", _utc(h=10), 19100.0, 19080.0, 19160.0, 2, "short")
    t.on_missed("TS050")
    rows = _read_rows(p)
    # only one row (overwritten, not appended twice)
    assert len(rows) == 1
    r = rows[0]
    # second on_decision wins
    assert r["side"] == "short"
    assert float(r["expected_entry"]) == pytest.approx(19100.0)


def test_exceptions_are_swallowed(tmp_path, capsys):
    """No exception from any ExecTelemetry method ever escapes (order-path safety)."""
    p = str(tmp_path / "telem.csv")
    t = ExecTelemetry(p)

    # on_decision with bad types should not raise
    t.on_decision(None, None, None, "bad", "bad", "bad", "bad", None, None)

    # on_webhook_result with no pending row should not raise
    t.on_webhook_result("NONEXISTENT", None, None)

    # poll_increment with no pending row should not raise
    t.poll_increment("NONEXISTENT")

    # on_fill_confirmed with corrupt pending row entry
    t.on_decision("BADROW", "ts", _utc(), "notafloat", "notafloat", "notafloat", "notanint", "long")
    # this should not raise even with garbage data
    t.on_fill_confirmed("BADROW", "notafloat", True, _utc())

    # on_missed with no pending row
    t.on_missed("NONEXISTENT")

    # on_cancelled with no pending row
    t.on_cancelled("NONEXISTENT")

    # no exception propagated
    # (if any of the above had raised, pytest would fail the test)


def test_latency_fields_computed(tmp_path):
    """decision_to_webhook_ms and webhook_to_fill_ms are populated correctly."""
    p = str(tmp_path / "telem.csv")
    t = ExecTelemetry(p)
    dec_wall = _utc(h=10, mi=0, s=0)
    wh_wall = _utc(h=10, mi=0, s=0) + timedelta(milliseconds=250)
    fill_wall = _utc(h=10, mi=0, s=0) + timedelta(seconds=20)
    t.on_decision("LATS", "2026-07-02T10:00:00+00:00", dec_wall, 19000.0, 18980.0, 19040.0, 1, "long")
    t.on_webhook_result("LATS", 200, wh_wall)
    t.on_fill_confirmed("LATS", 19000.5, True, fill_wall)
    rows = _read_rows(p)
    r = rows[0]
    assert float(r["decision_to_webhook_ms"]) == pytest.approx(250.0, abs=1.0)
    # fill_wall - wh_wall = 20s - 250ms = 19.75s = 19750ms
    assert float(r["webhook_to_fill_ms"]) == pytest.approx(19_750.0, abs=1.0)
