"""Telegram notifier — fail-safe, no-op when unconfigured, correct payloads, never raises."""
import pytest
from telegram_notify import Telegram


class FakeResp:
    status_code = 200
    text = ""


def _capture():
    sent = {}
    def poster(url, json=None, timeout=None):
        sent["url"] = url
        sent["body"] = json
        return FakeResp()
    return sent, poster


def test_noop_when_unconfigured(monkeypatch):
    # isolate the operator's shell env — the constructor falls back to TELEGRAM_* when args are None
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    t = Telegram(token=None, chat_id=None)
    assert not t.enabled
    assert t.send("hi") is False and t.signal("A", "long", 4, 1, 2, 3, "live") is False


def test_signal_payload_live():
    sent, poster = _capture()
    t = Telegram(token="TOK", chat_id="123", poster=poster)
    assert t.enabled
    ok = t.signal("B", "short", 2, 29603.0, 29664.5, 29510.7, "live")
    assert ok and t.sent == 1
    assert "/botTOK/sendMessage" in sent["url"]
    body = sent["body"]
    assert body["chat_id"] == "123" and body["parse_mode"] == "HTML"
    assert "Profile B" in body["text"] and "SHORT" in body["text"]
    assert "29603" in body["text"] and "29664" in body["text"] and "LIVE" in body["text"]


def test_outcome_payload_marks_modeled():
    sent, poster = _capture()
    t = Telegram(token="TOK", chat_id="123", poster=poster)
    t.outcome("A", "long", 2.0, 369.0, "target", "live")
    txt = sent["body"]["text"]
    assert "✅" in txt and "+2.00R" in txt and "$+369" in txt
    assert "modeled" in txt.lower() and "tradovate" in txt.lower()   # never claims confirmed


def test_outcome_loss_emoji():
    sent, poster = _capture()
    t = Telegram(token="TOK", chat_id="123", poster=poster)
    t.outcome("B", "short", -1.0, -246.0, "stop", "live")
    assert "❌" in sent["body"]["text"] and "-1.00R" in sent["body"]["text"]


def test_send_never_raises():
    def boom(url, json=None, timeout=None):
        raise ConnectionError("network down")
    t = Telegram(token="TOK", chat_id="123", poster=boom)
    assert t.send("x") is False and t.failed == 1     # swallowed, counted, no exception


def test_non_200_counts_as_failure():
    class Bad:
        status_code = 403
        text = "forbidden"
    t = Telegram(token="TOK", chat_id="123", poster=lambda *a, **k: Bad())
    assert t.send("x") is False and t.failed == 1


def test_health_card_live():
    sent, poster = _capture()
    t = Telegram(token="TOK", chat_id="123", poster=poster)
    t.health("live", "MFFU-50K-1", "50K-balanced",
             {"Sizing": "A 4 MNQ + B 2 MNQ", "D1c": "ACTIVE_EVAL_FILTER ✅", "Data": "✅ GREEN"})
    txt = sent["body"]["text"]
    assert "LIVE" in txt and "MFFU-50K-1" in txt and "A 4 MNQ" in txt
    assert "ACTIVE_EVAL_FILTER" in txt and "NY-AM" in txt


def test_health_card_paper():
    sent, poster = _capture()
    t = Telegram(token="TOK", chat_id="123", poster=poster)
    t.health("paper", "MFFU-50K-1", "50K-balanced", {"Data": "GREEN"})
    assert "PAPER" in sent["body"]["text"]


def test_heartbeat():
    sent, poster = _capture()
    t = Telegram(token="TOK", chat_id="123", poster=poster)
    t.heartbeat("11:42 ET", "GREEN", 0, 1, 2, "OK")
    txt = sent["body"]["text"]
    assert "ARES alive" in txt and "11:42 ET" in txt and "✅ GREEN" in txt
    assert "Trades today: 1 (A:0 B:1)" in txt and "blocked: 2" in txt


def test_heartbeat_red_data():
    sent, poster = _capture()
    t = Telegram(token="TOK", chat_id="123", poster=poster)
    t.heartbeat("12:00 ET", "RED", 0, 0, 0, "WARMUP")
    assert "🔴 RED" in sent["body"]["text"]


def test_label_prefix():
    sent, poster = _capture()
    t = Telegram(token="TOK", chat_id="123", label="MFFU-50K-1", poster=poster)
    t.signal("A", "long", 4, 1.0, 2.0, 3.0, "paper")
    assert "MFFU-50K-1" in sent["body"]["text"] and "PAPER" in sent["body"]["text"]
