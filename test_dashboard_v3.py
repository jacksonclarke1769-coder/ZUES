"""Tests for ZEUS MISSION DECK — dashboard v3.

Covers:
- /api/validation returns valid JSON from reports/apex_validation.json
- /api/heartbeat returns JSON with freshness_s and stale fields
- /api/exec_telemetry returns JSON (graceful when file absent)
- /v3 and /v3/ serve index.html
- /v3/<path> serves static assets (e.g. app.js, vendor/three.module.js)
- dashboard-v3/index.html exists and contains required structure
- No new write endpoints added (SAFETY rule unchanged)
"""
import json
import os
import shutil
import pytest

ROOT = os.path.dirname(os.path.abspath(__file__))
V3_DIR = os.path.join(ROOT, "dashboard-v3")


# ─── FIXTURES ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os as _os
    _os.makedirs("data", exist_ok=True)
    # Copy reports dir so /api/validation can read apex_validation.json
    reports_src = os.path.join(ROOT, "reports")
    if os.path.isdir(reports_src):
        shutil.copytree(reports_src, "reports")
    # Copy heartbeat so /api/heartbeat can read it
    hb_src = os.path.join(ROOT, "out", "heimdall", "heartbeat.json")
    if os.path.exists(hb_src):
        _os.makedirs("out/heimdall", exist_ok=True)
        shutil.copy(hb_src, "out/heimdall/heartbeat.json")
    # Copy dashboard-v3 so static route works
    if os.path.isdir(V3_DIR):
        shutil.copytree(V3_DIR, "dashboard-v3")
    # Copy dashboard for base routes
    dash_src = os.path.join(ROOT, "dashboard")
    if os.path.isdir(dash_src):
        shutil.copytree(dash_src, "dashboard")
    import zeus_server
    zeus_server.CFG["demo"] = False
    return zeus_server.APP.test_client()


# ─── /api/validation ──────────────────────────────────────────────────────────

def test_validation_returns_json(client):
    r = client.get("/api/validation")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, dict)


def test_validation_has_required_keys(client):
    r = client.get("/api/validation")
    data = r.get_json()
    # Must have the basic provenance keys
    for key in ("verified", "rule", "data", "harness"):
        assert key in data, f"missing key: {key}"


def test_validation_has_eval_deployed(client):
    r = client.get("/api/validation")
    data = r.get_json()
    ev = data.get("eval_deployed") or data.get("dll_recert_selected_machine")
    assert ev is not None, "no eval numbers in validation"


def test_validation_no_fabricated_numbers(client):
    """86% / 87% are documented fabrications — must not appear as current values."""
    r = client.get("/api/validation")
    data = r.get_json()
    # These should only appear in the retired_fabrications block (never as current)
    fab = data.get("retired_fabrications", {})
    assert fab.get("eval_pass_pct") == 86, "86% should be in retired_fabrications"


# ─── /api/heartbeat ───────────────────────────────────────────────────────────

def test_heartbeat_returns_json(client, tmp_path):
    r = client.get("/api/heartbeat")
    # May be 200 (file present) or 503 (absent) — both must return JSON
    data = r.get_json()
    assert isinstance(data, dict)


def test_heartbeat_has_freshness_fields(client):
    r = client.get("/api/heartbeat")
    data = r.get_json()
    # freshness_s and stale MUST be present regardless of file existence
    assert "freshness_s" in data, "freshness_s missing"
    assert "stale" in data, "stale missing"
    assert isinstance(data["stale"], bool)


def test_heartbeat_freshness_is_numeric_or_null(client):
    r = client.get("/api/heartbeat")
    data = r.get_json()
    fs = data.get("freshness_s")
    assert fs is None or isinstance(fs, (int, float))


# ─── /api/exec_telemetry ──────────────────────────────────────────────────────

def test_exec_telemetry_returns_json(client):
    r = client.get("/api/exec_telemetry")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, dict)


def test_exec_telemetry_has_rows(client):
    r = client.get("/api/exec_telemetry")
    data = r.get_json()
    assert "rows" in data
    assert isinstance(data["rows"], list)


def test_exec_telemetry_graceful_when_absent(client, tmp_path, monkeypatch):
    """Endpoint must return 200 with empty rows when telemetry file is absent."""
    r = client.get("/api/exec_telemetry")
    # File absent (no out/exec/ in tmp_path) → still 200 with rows=[]
    assert r.status_code == 200
    data = r.get_json()
    assert data["rows"] == [] or isinstance(data["rows"], list)


# ─── /v3 STATIC ROUTES ────────────────────────────────────────────────────────

def test_v3_index_served(client):
    r = client.get("/v3")
    assert r.status_code == 200
    assert b"ZEUS MISSION DECK" in r.data


def test_v3_slash_index_served(client):
    r = client.get("/v3/")
    assert r.status_code == 200
    assert b"ZEUS MISSION DECK" in r.data


def test_v3_app_js_served(client):
    r = client.get("/v3/app.js")
    assert r.status_code == 200
    assert len(r.data) > 100


def test_v3_three_module_served(client):
    r = client.get("/v3/vendor/three.module.js")
    assert r.status_code == 200
    assert len(r.data) > 100_000  # three.js is large


# ─── FILE EXISTENCE CHECKS ────────────────────────────────────────────────────

def test_dashboard_v3_index_html_exists():
    path = os.path.join(V3_DIR, "index.html")
    assert os.path.isfile(path), f"dashboard-v3/index.html missing at {path}"


def test_dashboard_v3_app_js_exists():
    path = os.path.join(V3_DIR, "app.js")
    assert os.path.isfile(path), f"dashboard-v3/app.js missing"


def test_dashboard_v3_three_module_exists():
    path = os.path.join(V3_DIR, "vendor", "three.module.js")
    assert os.path.isfile(path), f"dashboard-v3/vendor/three.module.js missing"
    size = os.path.getsize(path)
    assert size > 100_000, f"three.module.js suspiciously small ({size} bytes)"


def test_dashboard_v3_index_html_structure():
    """index.html must contain required structural elements."""
    path = os.path.join(V3_DIR, "index.html")
    content = open(path).read()
    for token in ("id=\"boot\"", "id=\"spine\"", "id=\"app\"", "id=\"deck\"",
                  "id=\"canvas-3d\"", "app.js", "ZEUS MISSION DECK"):
        assert token in content, f"missing token in index.html: {token}"


def test_dashboard_v3_app_js_endpoints():
    """app.js must reference the server endpoints it fetches from."""
    path = os.path.join(V3_DIR, "app.js")
    content = open(path).read()
    for ep in ("/api/state", "/api/heartbeat", "/api/validation", "/api/exec_telemetry"):
        assert ep in content, f"app.js missing endpoint reference: {ep}"


# ─── ROUTE-COVERAGE + ABSOLUTE-PATH GUARDS (post-incident) ───────────────────
# INCIDENT 2026-07-02: /v3 (no trailing slash) + relative <script src="app.js">
# resolved to /app.js, which the catch-all static route served from dashboard/
# (the OLD v2 app.js). The v3 deck never rendered and the old script's
# j("/api/overview") — not a registered route — got an HTML 404 page every 15s
# (`Unexpected token '<'`). These tests fail on that entire bug class.

import re


def _v3_app_js():
    return open(os.path.join(V3_DIR, "app.js")).read()


def _v3_index_html():
    return open(os.path.join(V3_DIR, "index.html")).read()


def test_every_api_literal_in_app_js_is_a_registered_route():
    """Every /api/... string literal in app.js must exist as a Flask route."""
    import zeus_server
    js = _v3_app_js()
    urls = set(re.findall(r"""['"](/api/[A-Za-z0-9_\-/]+)['"]""", js))
    assert urls, "no /api/ literals found in app.js — regex or file broken"
    routes = {str(r) for r in zeus_server.APP.url_map.iter_rules()}
    for u in urls:
        assert u in routes, f"app.js fetches {u} but zeus_server has no such route"


def test_every_v3_asset_literal_exists_on_disk():
    """Every /v3/... path referenced in app.js or index.html must be a real file."""
    combined = _v3_app_js() + _v3_index_html()
    refs = set(re.findall(r"""['"]/v3/([A-Za-z0-9_\-./]+)['"]""", combined))
    assert refs, "no /v3/ asset references found"
    for rel in refs:
        path = os.path.join(V3_DIR, rel)
        assert os.path.isfile(path), f"referenced /v3/{rel} does not exist on disk"


def test_index_html_uses_absolute_script_src():
    """The module script MUST be loaded via /v3/app.js — a relative src resolves
    against '/' when the page is served at /v3 and loads the OLD dashboard app."""
    html = _v3_index_html()
    assert 'src="/v3/app.js"' in html, "script src must be absolute /v3/app.js"
    assert 'src="app.js"' not in html, "relative script src regression"


def test_app_js_has_no_relative_imports():
    """Relative module specifiers break when the page URL is /v3 (no slash)."""
    js = _v3_app_js()
    assert re.search(r"""(?:from|import\()\s*['"]\.{1,2}/""", js) is None, \
        "app.js contains a relative import — must be absolute /v3/..."


def test_app_js_boot_failure_proofing():
    """Boot hardening invariants: sync skip binding, watchdog, guarded JSON."""
    js = _v3_app_js()
    # skip handler bound at top level (before runBoot is invoked)
    assert "addEventListener('keydown', _skipBoot)" in js
    # hard watchdog exists
    assert re.search(r"setTimeout\(\(\)\s*=>\s*finishBoot\(\),\s*8000\)", js), \
        "8s boot watchdog missing"
    # guarded JSON helper used for all API polling (no bare r.json() on the poll path)
    assert "safeJson" in js
    assert ".json()" not in js, "bare .json() call found — must use safeJson guard"


# ─── SAFETY: no new write endpoints ──────────────────────────────────────────

def test_v3_adds_only_read_endpoints():
    """New v3 API endpoints must be read-only (GET only)."""
    import zeus_server
    new_eps = {"/api/validation", "/api/heartbeat", "/api/exec_telemetry"}
    for rule in zeus_server.APP.url_map.iter_rules():
        if str(rule) in new_eps:
            methods = rule.methods - {"HEAD", "OPTIONS", "GET"}
            assert not methods, f"{rule} has unexpected write methods: {methods}"


def test_v3_routes_not_reachable_as_post(client):
    """v3 endpoints must not accept POST."""
    for ep in ("/api/validation", "/api/heartbeat", "/api/exec_telemetry"):
        r = client.post(ep, json={})
        assert r.status_code in (404, 405), f"{ep} accepted POST (status {r.status_code})"
