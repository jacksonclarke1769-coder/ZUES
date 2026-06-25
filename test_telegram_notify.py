"""Telegram notifier — fail-safe, no-op when unconfigured, correct payloads, never raises."""
import json
import pytest
from telegram_notify import Telegram


class FakeResp:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _capture():
    sent = {}
    def opener(req, timeout=None):
        sent["url"] = req.full_url
        sent["body"] = json.loads(req.data.decode())
        return FakeResp()
    return sent, opener


def test_noop_when_unconfigured():
    t = Telegram(token=None, chat_id=None)
    assert not t.enabled
    assert t.send("hi") is False and t.signal("A", "long", 4, 1, 2, 3, "live") is False


def test_signal_payload_live():
    sent, opener = _capture()
    t = Telegram(token="TOK", chat_id="123", opener=opener)
    assert t.enabled
    ok = t.signal("B", "short", 2, 29603.0, 29664.5, 29510.7, "live")
    assert ok and t.sent == 1
    assert "/botTOK/sendMessage" in sent["url"]
    body = sent["body"]
    assert body["chat_id"] == "123" and body["parse_mode"] == "HTML"
    assert "Profile B" in body["text"] and "SHORT" in body["text"]
    assert "29603" in body["text"] and "29664" in body["text"] and "LIVE" in body["text"]


def test_outcome_payload_marks_modeled():
    sent, opener = _capture()
    t = Telegram(token="TOK", chat_id="123", opener=opener)
    t.outcome("A", "long", 2.0, 369.0, "target", "live")
    txt = sent["body"]["text"]
    assert "✅" in txt and "+2.00R" in txt and "$+369" in txt
    assert "modeled" in txt.lower() and "tradovate" in txt.lower()   # never claims confirmed


def test_outcome_loss_emoji():
    sent, opener = _capture()
    t = Telegram(token="TOK", chat_id="123", opener=opener)
    t.outcome("B", "short", -1.0, -246.0, "stop", "live")
    assert "❌" in sent["body"]["text"] and "-1.00R" in sent["body"]["text"]


def test_send_never_raises():
    def boom(req, timeout=None):
        raise ConnectionError("network down")
    t = Telegram(token="TOK", chat_id="123", opener=boom)
    assert t.send("x") is False and t.failed == 1     # swallowed, counted, no exception


def test_label_prefix():
    sent, opener = _capture()
    t = Telegram(token="TOK", chat_id="123", label="MFFU-50K-1", opener=opener)
    t.signal("A", "long", 4, 1.0, 2.0, 3.0, "paper")
    assert "MFFU-50K-1" in sent["body"]["text"] and "PAPER" in sent["body"]["text"]
