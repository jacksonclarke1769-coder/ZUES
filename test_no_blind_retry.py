"""Tests for R-no-blind-retry: no blind webhook retry after a send timeout on entry payloads.

Audit R6/A7 — TradersPost has no native dedup; re-posting an entry can double the position.
"""
import json
import os
from unittest.mock import patch, MagicMock

import pytest
import requests

from store import Store
from journal import Journal
import bridge_traderspost as BP
import bridge_sender as BS


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("data", exist_ok=True)
    os.makedirs("evidence/approvals", exist_ok=True)
    os.makedirs("out/ares", exist_ok=True)
    return Store("data/bot.db"), Journal("data/journal.db")


def _entry_payload(**kw):
    base = dict(account="APEX-50K-1", strategy="A", setup="sweep-OTE",
                signal_ts="2026-07-02T09:35:00", side="long", qty=3,
                entry=22050.0, stop=21985.0, target=22180.0, root="MNQ",
                mode_meta=dict(mode="ARES"), d1c_meta=dict(decision="ALLOW"))
    base.update(kw)
    p, err = BP.build_entry(**base)
    assert err is None
    return p


def _exit_payload(account="APEX-50K-1"):
    p, err = BP.build_flatten(account=account, root="MNQ")
    assert err is None
    return p


def _cancel_payload(account="APEX-50K-1"):
    p, err = BP.build_cancel(account=account, strategy="A",
                             signal_ts="2026-07-02T09:35:00", root="MNQ")
    assert err is None
    return p


# R1. Entry payload + ReadTimeout on first post → exactly ONE attempt, sent=False,
#     ledger pending-unverified, reason mentions verification.
def test_r1_entry_read_timeout_no_retry(env):
    s, j = env
    snd = BS.BridgeSender(store=s, journal=j, mode="test", test_url="http://mock")
    p = _entry_payload()
    sid = p["extras"]["signalId"]
    call_count = 0

    def mock_post(url, json=None, timeout=None):
        nonlocal call_count
        call_count += 1
        raise requests.ReadTimeout("read timeout")

    with patch("requests.post", side_effect=mock_post):
        result = snd.send(p, retries=2)

    assert call_count == 1, f"Expected exactly 1 attempt, got {call_count}"
    assert result["sent"] is False
    assert "timeout-unverified" in result["reason"]
    assert "verify" in result["reason"]
    # Ledger must be pending-unverified (not confirmed, not plain pending)
    ledger = json.loads(s.get_state(BS.SENT_KEY) or "{}")
    assert sid in ledger
    assert ledger[sid]["status"] == "pending-unverified"


# R2. Exit payload + ReadTimeout → retried (≥2 attempts), same as today.
def test_r2_exit_read_timeout_retries(env):
    s, j = env
    snd = BS.BridgeSender(store=s, journal=j, mode="test", test_url="http://mock")
    p = _exit_payload()
    call_count = 0

    def mock_post(url, json=None, timeout=None):
        nonlocal call_count
        call_count += 1
        raise requests.ReadTimeout("read timeout")

    with patch("requests.post", side_effect=mock_post):
        result = snd.send(p, retries=2)

    assert call_count >= 2, f"Expected >=2 attempts for exit, got {call_count}"
    assert result["sent"] is False


# R2b. Cancel payload + ReadTimeout → also retried (≥2 attempts).
def test_r2b_cancel_read_timeout_retries(env):
    s, j = env
    snd = BS.BridgeSender(store=s, journal=j, mode="test", test_url="http://mock")
    p = _cancel_payload()
    call_count = 0

    def mock_post(url, json=None, timeout=None):
        nonlocal call_count
        call_count += 1
        raise requests.ReadTimeout("read timeout")

    with patch("requests.post", side_effect=mock_post):
        result = snd.send(p, retries=2)

    assert call_count >= 2, f"Expected >=2 attempts for cancel, got {call_count}"
    assert result["sent"] is False


# R3. ConnectionError on entry → still retried (unchanged behavior).
def test_r3_connection_error_entry_still_retries(env):
    s, j = env
    snd = BS.BridgeSender(store=s, journal=j, mode="test", test_url="http://mock")
    p = _entry_payload(signal_ts="2026-07-02T09:36:00")
    call_count = 0

    def mock_post(url, json=None, timeout=None):
        nonlocal call_count
        call_count += 1
        raise requests.ConnectionError("connection refused")

    with patch("requests.post", side_effect=mock_post):
        result = snd.send(p, retries=2)

    assert call_count >= 2, f"Expected >=2 attempts on ConnectionError, got {call_count}"
    assert result["sent"] is False
    # Ledger must be 'pending' (not pending-unverified) — connection refused = nothing delivered
    sid = p["extras"]["signalId"]
    ledger = json.loads(s.get_state(BS.SENT_KEY) or "{}")
    assert ledger.get(sid, {}).get("status") == "pending"


# R4. is_entry_payload helper classifies correctly (unit test).
def test_r4_is_entry_payload_classification():
    assert BS._is_entry_payload({"action": "buy"}) is True
    assert BS._is_entry_payload({"action": "sell"}) is True
    assert BS._is_entry_payload({"action": "add"}) is True
    assert BS._is_entry_payload({"action": "exit"}) is False
    assert BS._is_entry_payload({"action": "cancel"}) is False
    # Ambiguous / missing action → treated as entry (fail-closed)
    assert BS._is_entry_payload({}) is True
    assert BS._is_entry_payload({"action": "unknown"}) is True
    assert BS._is_entry_payload(None) is True
