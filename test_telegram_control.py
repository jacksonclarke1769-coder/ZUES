"""Telegram remote control — owner-only auth, correct dispatch, fail-safe, offset acking."""
import pytest
from telegram_control import TelegramControl


class Resp:
    status_code = 200
    def __init__(self, payload): self._p = payload
    def json(self): return self._p


def _updates(*msgs):
    """Build a getUpdates payload; each msg = (update_id, chat_id, text)."""
    return {"result": [{"update_id": uid, "message": {"chat": {"id": cid}, "text": txt}}
                       for (uid, cid, txt) in msgs]}


def _getter(payload):
    calls = {"n": 0, "params": []}
    def get(url, params=None, timeout=None):
        calls["n"] += 1; calls["params"].append(params)
        return Resp(payload if calls["n"] == 1 else {"result": []})   # serve once, then empty
    return get, calls


def test_noop_when_unconfigured():
    c = TelegramControl(token=None, chat_id=None)
    assert not c.enabled and c.poll() == []


def test_owner_command_dispatched():
    get, _ = _getter(_updates((10, "123", "/health")))
    c = TelegramControl(token="TOK", chat_id="123", getter=get)
    c.on("health", lambda args: "HEALTH OK")
    out = c.poll()
    assert out == [("health", "HEALTH OK")] and c.seen == 1


def test_non_owner_ignored_silently():
    get, _ = _getter(_updates((11, "999", "/flatten")))   # stranger
    c = TelegramControl(token="TOK", chat_id="123", getter=get)
    hit = {"n": 0}
    c.on("flatten", lambda args: hit.__setitem__("n", hit["n"] + 1) or "done")
    assert c.poll() == [] and hit["n"] == 0 and c.ignored == 1   # never dispatched


def test_offset_advances_past_acked_updates():
    get, calls = _getter(_updates((42, "123", "/ping")))
    c = TelegramControl(token="TOK", chat_id="123", getter=get)
    c.on("ping", lambda a: "pong")
    c.poll(); c.poll()
    assert calls["params"][1]["offset"] == 43          # second poll asks only for >42


def test_args_and_group_suffix():
    get, _ = _getter(_updates((1, "123", "/status@ZUESNQ_bot now")))
    c = TelegramControl(token="TOK", chat_id="123", getter=get)
    seen = {}
    c.on("status", lambda args: seen.update(a=args) or "ok")
    c.poll()
    assert seen["a"] == ["now"]                          # @botname stripped, args parsed


def test_unknown_command_replies_help_hint():
    get, _ = _getter(_updates((1, "123", "/wat")))
    c = TelegramControl(token="TOK", chat_id="123", getter=get)
    assert "try /help" in c.poll()[0][1]


def test_handler_exception_is_caught():
    def boom(args): raise ValueError("nope")
    get, _ = _getter(_updates((1, "123", "/flatten")))
    c = TelegramControl(token="TOK", chat_id="123", getter=get)
    c.on("flatten", boom)
    cmd, reply = c.poll()[0]
    assert cmd == "flatten" and "failed" in reply and "ValueError" in reply   # swallowed, reported


def test_poll_network_error_never_raises():
    def get(url, params=None, timeout=None): raise ConnectionError("down")
    c = TelegramControl(token="TOK", chat_id="123", getter=get)
    assert c.poll() == []          # swallowed
