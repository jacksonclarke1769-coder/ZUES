"""
Telegram REMOTE CONTROL — inbound commands TO the live bot (the other half of telegram_notify).

telegram_notify pushes signals/outcomes/heartbeat OUT. This polls getUpdates and lets the OWNER
text commands IN: read-only (/health /status /ping /journal /help) + control (/stop /resume /flatten).

SECURITY: only messages whose chat id == TELEGRAM_CHAT_ID are honoured — anyone else who finds the
bot is silently ignored (no reply, no dispatch). Control commands DO NOT invent a new code path:
they flip the SAME `auto_live_kill` store flag the guardian/operator already use, so a Telegram
/stop is identical to a local kill. Fail-safe: a poll/handler error is swallowed, never breaks the
engine loop. No-op (enabled=False) unless token+chat_id+requests are all present.
"""
from __future__ import annotations

import os

try:
    import requests                      # bot already depends on it (certifi TLS)
except ImportError:                      # pragma: no cover
    requests = None

API = "https://api.telegram.org/bot{token}/getUpdates"

HELP = ("<b>ARES commands</b>\n"
        "/health — full health card\n"
        "/status — quick state (trades, data, P&amp;L)\n"
        "/ping — alive?\n"
        "/journal — last trade &amp; why\n"
        "/stop — HALT new entries (stays in any open trade)\n"
        "/flatten — flatten everything NOW + halt\n"
        "/resume — clear the halt\n"
        "/help — this list")


class TelegramControl:
    """Owner-authenticated inbound command poller. Handlers are injected by the bot via .on()."""

    def __init__(self, token=None, chat_id=None, getter=None):
        self.token = token if token is not None else os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = str(chat_id if chat_id is not None else (os.environ.get("TELEGRAM_CHAT_ID") or ""))
        self.enabled = bool(self.token and self.chat_id and requests)
        self._get = getter or (requests.get if requests else None)
        self._offset = None              # ack cursor — never re-process an update
        self.handlers = {}               # cmd(str) -> fn(args:list[str]) -> reply:str
        self.seen = self.ignored = 0     # owner cmds dispatched / non-owner msgs rejected

    def on(self, cmd, fn):
        self.handlers[cmd] = fn
        return self

    def _fetch(self):
        params = {"timeout": 0}
        if self._offset is not None:
            params["offset"] = self._offset
        r = self._get(API.format(token=self.token), params=params, timeout=10)
        return (r.json() or {}).get("result", []) if getattr(r, "status_code", 200) == 200 else []

    def poll(self):
        """Pull new updates, AUTH by chat id, dispatch. Returns [(cmd, reply), ...] for the bot to send."""
        if not self.enabled:
            return []
        try:
            updates = self._fetch()
        except Exception as e:                                # noqa: BLE001 — control polling never breaks trading
            print(f"[tg-control] poll failed: {type(e).__name__}: {e}", flush=True)
            return []
        out = []
        for u in updates:
            self._offset = u.get("update_id", 0) + 1          # ack even non-owner msgs so they don't replay
            msg = u.get("message") or u.get("edited_message") or {}
            chat = str((msg.get("chat") or {}).get("id", ""))
            text = (msg.get("text") or "").strip()
            if chat != self.chat_id:                          # AUTH: owner only — silent on others
                self.ignored += 1
                continue
            if not text.startswith("/"):
                continue
            parts = text.split()
            cmd = parts[0].lstrip("/").split("@")[0].lower()  # tolerate /stop@ZUESNQ_bot in groups
            args = parts[1:]
            fn = self.handlers.get(cmd)
            try:
                reply = fn(args) if fn else f"unknown command /{cmd} — try /help"
            except Exception as e:                            # noqa: BLE001 — a bad handler must not halt polling
                reply = f"⚠ /{cmd} failed: {type(e).__name__}: {e}"
            self.seen += 1
            out.append((cmd, reply))
        return out
