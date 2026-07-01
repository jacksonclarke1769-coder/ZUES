"""SINGLE_1R exit model — the DEFAULT since 2026-07-01, look-ahead-clean (certified 2026-06-30).
Proves: SINGLE_1R is the default; +1R target geometry; live flag-gate fail-safe to the RETAINED EXIT3;
full-qty OSO with TP at +1R (no +2R misfire); paper routes it; live needs the flag."""
import sys, types
import pytest
import config_defaults as CD
import runtime_config as RC
import bridge_traderspost as BP


def test_default_exit_model_is_single1r(monkeypatch):
    # SINGLE_1R promoted to the default 2026-07-01 (eval pass 63.1 vs 59.3%, funded E[payout] +23.7%)
    assert CD.EXIT_MODEL == "SINGLE_1R"
    assert RC.resolve_exit_model("paper") == "SINGLE_1R"            # paper routes the default
    monkeypatch.setattr(CD, "single1r_live_ok", lambda mode, approval_dir=None: False)
    assert RC.resolve_exit_model("live") == "EXIT3_FIXED_PARTIAL"   # live w/o flag -> fail-safe (EXIT3 retained)
    assert CD.SAFE_FALLBACK_EXIT_MODEL == "EXIT3_FIXED_PARTIAL"     # the decoupled safe fallback


def test_single1r_target_long_short():
    assert CD.single1r_target(100.0, 90.0, "long") == 110.0    # R=10 long  -> entry + R
    assert CD.single1r_target(100.0, 110.0, "short") == 90.0   # R=10 short -> entry - R


def test_single1r_live_gate(tmp_path):
    assert CD.single1r_live_ok("paper") is True                # paper (dry-run) always ok
    d = tmp_path / "approvals"; d.mkdir()
    assert CD.single1r_live_ok("live", str(d)) is False        # live, flag ABSENT
    (d / CD.SINGLE_1R_APPROVAL_FLAG).write_text("ok")
    assert CD.single1r_live_ok("live", str(d)) is True         # live, flag PRESENT


def _fake_config(exit_model):
    m = types.ModuleType("config"); m.EXIT_MODEL = exit_model; return m


def test_resolve_single1r_paper_selects(monkeypatch):
    monkeypatch.setitem(sys.modules, "config", _fake_config("SINGLE_1R"))
    assert RC.resolve_exit_model("paper") == "SINGLE_1R"       # paper routes it (dry-run)


def test_resolve_single1r_live_failsafe_without_flag(monkeypatch):
    monkeypatch.setitem(sys.modules, "config", _fake_config("SINGLE_1R"))
    monkeypatch.setattr(CD, "single1r_live_ok", lambda mode, approval_dir=None: False)
    assert RC.resolve_exit_model("live") == "EXIT3_FIXED_PARTIAL"   # FAIL-SAFE to frozen model


def test_resolve_single1r_live_routes_with_flag(monkeypatch):
    monkeypatch.setitem(sys.modules, "config", _fake_config("SINGLE_1R"))
    monkeypatch.setattr(CD, "single1r_live_ok", lambda mode, approval_dir=None: True)
    assert RC.resolve_exit_model("live") == "SINGLE_1R"


def test_single1r_oso_proof():
    """DRY-RUN OSO PROOF: single@1R builds ONE full-qty bracket, takeProfit at exactly +1R, shared stop."""
    entry, stop = 20000.0, 19900.0                             # R = 100, long
    tgt = CD.single1r_target(entry, stop, "long")
    assert tgt == 20100.0
    payload, err = BP.build_entry(account="X", strategy="A", setup="t",
                                  signal_ts="2026-06-30T10:00:00-04:00", side="long", qty=10,
                                  entry=entry, stop=stop, target=tgt, r_target=1.0)
    assert err is None
    assert payload["quantity"] == 10                           # FULL qty (no partial split)
    assert payload["takeProfit"]["limitPrice"] == 20100.0      # +1R  (NOT the +2R = 20200 misfire)
    assert payload["stopLoss"]["stopPrice"] == 19900.0         # shared -1R stop
    assert payload["extras"]["r_target"] == 1.0


def test_single1r_is_not_the_2R_misfire():
    entry, stop = 20000.0, 19900.0
    t1r = CD.single1r_target(entry, stop, "long")              # 20100
    t2r = entry + 2 * abs(entry - stop)                        # 20200 = what the old else->2R would send
    assert t1r == 20100.0 and t1r != t2r


def test_requested_override_is_gated(monkeypatch):
    """--exit-model launch override goes through the SAME gates as config.EXIT_MODEL."""
    assert RC.resolve_exit_model("paper", requested="SINGLE_1R") == "SINGLE_1R"           # paper ok (real gate)
    monkeypatch.setattr(CD, "single1r_live_ok", lambda mode, approval_dir=None: True)
    assert RC.resolve_exit_model("live", requested="SINGLE_1R") == "SINGLE_1R"            # live + flag
    monkeypatch.setattr(CD, "single1r_live_ok", lambda mode, approval_dir=None: False)
    assert RC.resolve_exit_model("live", requested="SINGLE_1R") == "EXIT3_FIXED_PARTIAL"  # live, no flag -> fail-safe
    with pytest.raises(RC.ConfigLockError):                     # research-only override still raises
        RC.resolve_exit_model("live", requested="SINGLE_TARGET")
    with pytest.raises(RC.ConfigLockError):                     # unknown override still raises
        RC.resolve_exit_model("live", requested="NONSENSE")
