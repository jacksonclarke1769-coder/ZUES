"""Pytest isolation for production audit artifacts.

Root cause (2026-06-29 refused-send anomaly): `BridgeSender.LOG` is a hardcoded module constant
("out/ares/bridge_webhook_log.csv"), and tests that exercise `send()` without isolating it appended
'refused: exit model not approved/aligned' rows to the LIVE order-audit trail on every `pytest` run.
That trail is the source of truth for what the bot actually sent, so the junk made trade audits
noisy/misleading (it never placed real orders — all refused — but it polluted the record).

This autouse fixture redirects `bridge_sender.LOG` to a per-test tmp file. `_log()` reads the module
global at call time, so the redirect covers both writes and the tests that assert on `bridge_sender.LOG`.
"""
import pytest


@pytest.fixture(autouse=True)
def _isolate_bridge_log(tmp_path, monkeypatch):
    import bridge_sender
    monkeypatch.setattr(bridge_sender, "LOG", str(tmp_path / "bridge_webhook_log.csv"))
    yield
