"""Offline tests for the DOM collector's parser/flattener (live loop needs credentials)."""
import os
import dom_collector as dc


def test_parse_md_frame():
    doms = dc.parse_frame(dc.SAMPLE)
    assert len(doms) == 1
    assert doms[0]["contractId"] == 123


def test_heartbeat_and_open_frames_yield_nothing():
    assert dc.parse_frame("o") == []
    assert dc.parse_frame("h") == []
    assert dc.parse_frame("") == []


def test_flatten_orders_levels_and_pads():
    row = dc.flatten_dom(dc.parse_frame(dc.SAMPLE)[0])
    assert row["b1_px"] == 24750.25 and row["b2_px"] == 24750.0   # bids descending
    assert row["a1_px"] == 24750.5 and row["a2_px"] == 24750.75   # asks ascending
    assert row["b10_px"] is None and row["a10_sz"] is None        # sparse padded
    assert row["contract_id"] == 123


def test_append_rows_creates_header_once(tmp_path):
    p = str(tmp_path / "dom.csv")
    row = dc.flatten_dom(dc.parse_frame(dc.SAMPLE)[0])
    assert dc.append_rows([row], p) == 1
    assert dc.append_rows([row], p) == 1
    lines = open(p).read().strip().splitlines()
    assert len(lines) == 3                                        # 1 header + 2 rows
    assert lines[0].startswith("ts_utc,contract_id,b1_px")


def test_collector_has_no_trading_capability():
    """Read-only guarantee: no order/position-mutating API appears anywhere in the module."""
    src = open(dc.__file__).read()
    for forbidden in ("placeOSO", "placeOrder", "place_bracket", "place_market",
                      "liquidate", "cancelOrder", "modifyOrder", "order/"):
        assert forbidden not in src, forbidden


def test_collector_importable_without_credentials():
    """Import + selftest path must never touch network or config credentials."""
    dc.selftest()                                     # raises if parser broken


def test_evidence_log_appends(tmp_path):
    p = str(tmp_path / "log.txt")
    dc.evidence_log("START test", p)
    dc.evidence_log("STOP test", p)
    lines = open(p).read().strip().splitlines()
    assert len(lines) == 2 and "START test" in lines[0] and "STOP test" in lines[1]


def test_daily_rotation_path_changes_with_date():
    from datetime import datetime, timezone
    d1 = datetime(2026, 6, 13, tzinfo=timezone.utc)
    d2 = datetime(2026, 6, 14, tzinfo=timezone.utc)
    assert dc.csv_path(d1) != dc.csv_path(d2)
    assert dc.csv_path(d1).endswith("NQ_dom_20260613.csv")
