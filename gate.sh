#!/usr/bin/env bash
# FUNDED_CONFIG gate — run before any commit that could touch eval- or funded-sizing code.
# Fails closed: any red step aborts the script (set -e).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

echo "== (a) full test suite =="
python3 -m pytest -q

echo "== (b) funded config firewall (named) =="
python3 -m pytest test_funded_config_firewall.py -q

echo "== (c) config_funded_locked.py SHA256 check =="
RECORDED="$(cat evidence/funded_config.sha256)"
ACTUAL="$(shasum -a 256 config_funded_locked.py | awk '{print $1}')"
if [ "$ACTUAL" != "$RECORDED" ]; then
    echo "FUNDED_CONFIG firewall: funded constants changed — requires funded re-certification + operator approval (see config_funded_locked.py header)" >&2
    exit 1
fi

echo "== (d) eval config firewall (named) =="
python3 -m pytest test_eval_config_firewall.py -q

echo "== (e) config_eval_locked.py + live-file SHA256 check =="
# The eval firewall records config_eval_locked.py (self) AND the live files it pins
# (config_defaults.py, auto_safety.py) in evidence/eval_config.sha256 — the same recorded set the
# watchdog CONFIG INTEGRITY invariant recomputes at runtime. shasum -c verifies all three.
shasum -a 256 -c evidence/eval_config.sha256

echo "== gate.sh: ALL CHECKS GREEN =="
