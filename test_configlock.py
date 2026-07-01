"""CONFIGLOCK — the official exit model is version-controlled and fail-closed. The committed
default is SINGLE_1R (promoted 2026-07-01): a fresh clone / missing EXIT_MODEL resolves to it for
paper, but LIVE fails SAFE to EXIT3_FIXED_PARTIAL without single-1r-approved.flag; a SINGLE_TARGET
or unknown local override RAISES for live/paper; synthetic P&L never shows as realised."""
import sys
import types
import os

import pytest

import runtime_config as RC
from runtime_config import resolve_exit_model, ConfigLockError
import config_defaults as CD
import trade_results as TR

_REAL = sys.modules.get("config")


def _fake_config(monkeypatch, exit_model="__MISSING__"):
    m = types.ModuleType("config")
    if exit_model != "__MISSING__":
        m.EXIT_MODEL = exit_model
    monkeypatch.setitem(sys.modules, "config", m)


# ---- 1 — missing config / missing attr -> committed default (SINGLE_1R); live fail-safe to EXIT3 ----
def test_missing_exit_model_is_safe(monkeypatch):
    _fake_config(monkeypatch, "__MISSING__")               # config exists but has no EXIT_MODEL
    monkeypatch.setattr(CD, "single1r_live_ok", lambda mode, approval_dir=None: mode == "paper")  # no live approval
    assert resolve_exit_model("live") == "EXIT3_FIXED_PARTIAL"   # SINGLE_1R default, no flag -> fail-safe
    assert resolve_exit_model("paper") == "SINGLE_1R"           # paper (dry-run) = the committed default

def test_empty_or_none_exit_model_is_safe(monkeypatch):
    monkeypatch.setattr(CD, "single1r_live_ok", lambda mode, approval_dir=None: mode == "paper")
    _fake_config(monkeypatch, "")
    assert resolve_exit_model("live") == "EXIT3_FIXED_PARTIAL"
    _fake_config(monkeypatch, None)
    assert resolve_exit_model("paper") == "SINGLE_1R"

def test_config_import_failure_is_safe(monkeypatch):
    # simulate no importable config at all -> committed default, live still fail-safe to EXIT3
    monkeypatch.setitem(sys.modules, "config", None)       # import config -> None attr access guarded
    monkeypatch.setattr(CD, "single1r_live_ok", lambda mode, approval_dir=None: mode == "paper")
    assert resolve_exit_model("live") == "EXIT3_FIXED_PARTIAL"


# ---- 3,4 — unsafe overrides fail closed for execution ----
def test_single_target_blocked_for_live(monkeypatch):
    _fake_config(monkeypatch, "SINGLE_TARGET")
    for mode in ("live", "paper", "controlled"):
        with pytest.raises(ConfigLockError):
            resolve_exit_model(mode)

def test_unknown_model_blocked_for_live(monkeypatch):
    _fake_config(monkeypatch, "WEIRD_MODE")
    with pytest.raises(ConfigLockError):
        resolve_exit_model("live")
    with pytest.raises(ConfigLockError):
        resolve_exit_model("paper")


# ---- 5 — SINGLE_TARGET allowed ONLY in research ----
def test_single_target_allowed_in_research(monkeypatch):
    _fake_config(monkeypatch, "SINGLE_TARGET")
    assert resolve_exit_model("research") == "SINGLE_TARGET"


# ---- 6 — no live bridge path defaults to SINGLE_TARGET (source guard) ----
def test_no_single_target_fallback_in_live_code():
    src = open(os.path.join(os.path.dirname(__file__), "auto_live.py")).read()
    assert 'getattr(_cfg, "EXIT_MODEL", "SINGLE_TARGET")' not in src
    assert 'resolve_exit_model' in src                      # the safe resolver is used


# ---- 7 — emergency flatten never blocked by CONFIGLOCK ----
def test_flatten_not_blocked_by_unsafe_config(monkeypatch):
    _fake_config(monkeypatch, "SINGLE_TARGET")             # unsafe override active
    import bridge_traderspost as BP
    p, err = BP.build_flatten(account="MFFU-50K-1", reason="t")
    assert err is None and p["action"] == "exit"           # flatten builds regardless of exit model


# ---- 2,10 — live/paper still builds Exit #3 two-leg + parity ----
def test_exit3_two_leg_still_built(monkeypatch):
    _fake_config(monkeypatch, "EXIT3_FIXED_PARTIAL")
    assert resolve_exit_model("live") == "EXIT3_FIXED_PARTIAL"
    import bridge_traderspost as BP
    legs, err = BP.build_entry_exit3(account="A", strategy="A", setup="s", signal_ts="t",
                                     side="short", qty=3, entry=30654.83, stop=30771.5,
                                     target=30421.49)
    assert err is None and len(legs) == 2
    win = sum(TR.pnl_from_r(L["r_target"], 30654.83, 30771.5, L["qty"]) for L in legs)
    assert round(win) == 1167                               # parity, not $1,400


# ---- 8,9 — synthetic P&L never realised (fresh-clone safe, code-level) ----
def test_synthetic_1400_row_is_hypothetical(tmp_path):
    p = str(tmp_path / "tr.csv")
    # the EXACT old synthetic row pattern (note carries no fill proof)
    TR.record("2026-06-16", "paper", "MFFU-50K-1", "A", "short", 3, 1400.0,
              note="paper · Profile A NY-AM short · TP hit (gross)", fill_backed=True, path=p)
    day = TR.by_day(p)["2026-06-16"]
    assert day["pnl"] == 0.0                                # NOT realised
    assert day["hypothetical_pnl"] == 1400.0

def test_modeled_rows_are_hypothetical(tmp_path):
    p = str(tmp_path / "tr.csv")
    TR.record("2026-06-16", "live", "X", "A", "short", 3, 900.0,
              note="modeled · pending broker recon · +1.50R gross", fill_backed=False, path=p)
    assert TR.by_day(p)["2026-06-16"]["pnl"] == 0.0

def test_fill_backed_row_is_realised(tmp_path):
    p = str(tmp_path / "tr.csv")
    TR.record("2026-06-16", "live", "X", "A", "short", 3, 900.0,
              note="broker fill confirmed", fill_backed=True, path=p)
    assert TR.by_day(p)["2026-06-16"]["pnl"] == 900.0
    assert TR.by_day(p)["2026-06-16"]["hypothetical_pnl"] == 0.0

def test_is_realised_classifier():
    assert TR.is_realised("fill-backed · +1.5R") is True
    assert TR.is_realised("HYPOTHETICAL · whatever") is False
    assert TR.is_realised("modeled · pending") is False
    assert TR.is_realised("TP hit (gross)") is False
    assert TR.is_realised("") is False                      # no proof -> not realised
