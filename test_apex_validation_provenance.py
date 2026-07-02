"""Guard test: every Apex pass/lock % the operator sees must trace to a COMMITTED harness via
reports/apex_validation.json — never a hand-typed magic number or a deleted /tmp script. This is the
fix for the 2026-06-27 incident where a fabricated 86% (from /tmp/eval_opt.py) reached the dashboard.

Fails if: the provenance file is missing/edited away from committed harnesses, a retired fabrication
(86/87) reappears, or the dashboard's displayed pass/lock % drifts from the source of truth."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROV = os.path.join(HERE, "reports", "apex_validation.json")


def _load():
    with open(PROV) as fh:
        return json.load(fh)


def test_provenance_file_exists_and_is_committed():
    V = _load()
    assert V["data"].lower().find("databento") >= 0, "source data must be the real Databento set"
    assert "eod" in V["rule"].lower(), "drawdown rule must be the confirmed EOD model"
    assert V["harness"], "must cite at least one harness"
    for h in V["harness"]:
        assert not h.startswith("/tmp"), f"harness {h} is ephemeral — must be a committed file"
        assert os.path.exists(os.path.join(HERE, h)), f"cited harness {h} is missing from the repo"


def test_retired_fabrications_do_not_reappear():
    V = _load()
    assert V["eval_deployed"]["pass_pct"] != 86, "the fabricated 86% must not be the eval number"
    assert V["funded_deployed"]["reach_lock_pct"] != 87, "the fabricated 87% must not be the lock number"
    # sane ranges (a faithful EOD model on real data sits well under the old fabrications)
    assert 45 <= V["eval_deployed"]["pass_pct"] <= 75
    assert 50 <= V["funded_deployed"]["reach_lock_pct"] <= 90


def test_dashboard_matches_source_of_truth():
    """The dashboard's displayed numbers must match the provenance file (catches silent drift)."""
    V = _load()
    try:
        import zeus_server
        pb = zeus_server.apex_playbook()
    except Exception as e:                       # pragma: no cover - server deps optional in CI
        import pytest
        pytest.skip(f"zeus_server not importable here: {e}")
    assert abs(pb["eval"]["pass_pct"] - V["eval_deployed"]["pass_pct"]) <= 3, \
        "dashboard eval pass_pct drifted from reports/apex_validation.json — re-run the harness, sync both"
    # W-knowledge-reconciliation 2026-07-02: funded_40_recert model uses PA ladder (no lock step).
    # lock_pct is retained at 80 for dashboard JS compat (apex.js uses f.lock_pct||68 fallback);
    # will be removed when funded sizing finalised. Assertion kept — value still traces to
    # funded_deployed.reach_lock_pct (79.8) in apex_validation.json until funded_40_recert supersedes it.
    assert abs(pb["funded"]["lock_pct"] - V["funded_deployed"]["reach_lock_pct"]) <= 3, \
        "dashboard funded lock_pct drifted from reports/apex_validation.json — re-run the harness, sync both"
    # Also verify the new recert fields are present and reference the right provenance
    assert "funded_40_recert" in pb["funded"]["busts"], \
        "W-knowledge-reconciliation: funded dict must cite funded_40_recert provenance"
    assert pb["funded"]["income_mo"] < 1000, \
        "W-knowledge-reconciliation: income_mo must reflect funded_40_recert (~$785/mo), not old $2,412"
    assert pb["eval"]["pass_pct"] != 86 and pb["funded"]["lock_pct"] != 87
