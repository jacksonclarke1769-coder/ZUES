#!/usr/bin/env bash
# One-line installer for the Apex NQ bot.
#   curl -fsSL https://raw.githubusercontent.com/jacksonclarke1769-coder/ZUES/main/install.sh | bash
# Clones the repo, builds an isolated venv, installs deps, creates config.py, and verifies with the tests.
set -euo pipefail

REPO="${REPO_URL:-https://github.com/jacksonclarke1769-coder/ZUES.git}"
DIR="${1:-apex-bot}"
PY="$(command -v python3 || command -v python || true)"

[ -n "$PY" ] || { echo "❌ Python 3 not found. Install Python 3.11+ first."; exit 1; }
command -v git >/dev/null || { echo "❌ git not found. Install git first."; exit 1; }
[ -e "$DIR" ] && { echo "❌ '$DIR' already exists here. Remove it or pass a different name: ... | bash -s mydir"; exit 1; }

echo "▸ cloning into ./$DIR …"
git clone --depth 1 "$REPO" "$DIR"
cd "$DIR"

echo "▸ creating virtualenv + installing dependencies …"
"$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "▸ creating config.py (your creds go here) …"
cp config.example.py config.py

echo "▸ verifying install (running tests) …"
python3 -m pytest -q

cat <<EOF

✅ Installed in: $(pwd)

NEXT STEPS
  1. Edit config.py  → your Tradovate/Apex creds (env = your live account, not demo)
  2. Start the Chrome :9222 NQ 1m feed (logged in) + set your TradersPost webhook
  3. Start the bot (PAPER first — safe, no real orders):

       cd "$(pwd)"
       source .venv/bin/activate
       python3 auto_live.py --account APEX-50K-1 --tier Apex-50K-eval --profile-momentum

  Full go-live runbook: MONDAY_GOLIVE.md  ·  quickstart: SETUP.md
EOF
