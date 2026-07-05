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

echo "== gate.sh: ALL CHECKS GREEN =="
