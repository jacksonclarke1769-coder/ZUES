#!/usr/bin/env bash
# setup-zeus.sh — safe first-time setup for the ZEUS bot repository
#
# WHAT THIS DOES:
#   - Checks Python 3.11+
#   - Creates a virtual environment (if not already present)
#   - Installs Python dependencies from requirements.txt
#   - Verifies required folders exist (creates them if not)
#   - Copies .env.example -> .env ONLY if .env does not already exist
#   - Verifies that the core contract files are present
#   - Runs a lightweight smoke test (doc consistency + import check)
#   - Prints next steps
#
# WHAT THIS DOES NOT DO:
#   - Start the live bot or any live process
#   - Send any webhooks or connect to any broker
#   - Place any orders
#   - Print or write real secrets
#   - Overwrite an existing .env file
#
# SAFE TO RUN repeatedly. Idempotent on a clean or already-setup repo.

set -euo pipefail

# ---------------------------------------------------------------------------
# Guard: refuse to run as root
# ---------------------------------------------------------------------------
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    echo "ERROR: Do not run setup-zeus.sh as root. Use your normal user account." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Resolve repo root (always relative to this script, not $PWD)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "  ZEUS — Safe Setup Script"
echo "  $(date '+%Y-%m-%d %H:%M %Z')"
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# 1. Python version check (3.11+)
# ---------------------------------------------------------------------------
echo "[1/7] Checking Python version..."

PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" &>/dev/null; then
        VERSION=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        MAJOR=${VERSION%%.*}
        MINOR=${VERSION##*.}
        if [[ "$MAJOR" -eq 3 && "$MINOR" -ge 11 ]]; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    echo "ERROR: Python 3.11 or higher is required but was not found." >&2
    echo "  Install Python 3.11+ from https://www.python.org/downloads/" >&2
    exit 1
fi

echo "  Found: $($PYTHON_BIN --version)"

# ---------------------------------------------------------------------------
# 2. Create virtual environment if missing
# ---------------------------------------------------------------------------
echo "[2/7] Checking virtual environment..."

VENV_DIR="$SCRIPT_DIR/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
    echo "  Creating .venv with $PYTHON_BIN..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    echo "  Virtual environment created at .venv/"
else
    echo "  .venv already exists — skipping creation."
fi

# Activate the venv for the rest of this script
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
ACTIVE_PYTHON="$VENV_DIR/bin/python3"

# ---------------------------------------------------------------------------
# 3. Install dependencies
# ---------------------------------------------------------------------------
echo "[3/7] Installing dependencies from requirements.txt..."

if [[ ! -f "$SCRIPT_DIR/requirements.txt" ]]; then
    echo "ERROR: requirements.txt not found. Is this the correct repo?" >&2
    exit 1
fi

"$ACTIVE_PYTHON" -m pip install --quiet --upgrade pip
"$ACTIVE_PYTHON" -m pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
echo "  Dependencies installed."

# ---------------------------------------------------------------------------
# 4. Verify / create required folders
# ---------------------------------------------------------------------------
echo "[4/7] Verifying required folders..."

REQUIRED_DIRS=(
    "out"
    "logs"
    "evidence/approvals"
    "dashboard-v3"
)

for d in "${REQUIRED_DIRS[@]}"; do
    full="$SCRIPT_DIR/$d"
    if [[ ! -d "$full" ]]; then
        mkdir -p "$full"
        echo "  Created: $d/"
    else
        echo "  OK: $d/"
    fi
done

# ---------------------------------------------------------------------------
# 5. Copy .env.example -> .env ONLY if .env does not already exist
# ---------------------------------------------------------------------------
echo "[5/7] Checking .env file..."

ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"

if [[ -f "$ENV_FILE" ]]; then
    echo "  .env already exists — NOT overwriting (your credentials are safe)."
elif [[ -f "$ENV_EXAMPLE" ]]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo "  Copied .env.example -> .env"
    echo "  NEXT: open .env and fill in your real credentials before going live."
else
    echo "  WARNING: .env.example not found. You will need to create .env manually."
    echo "  Required keys: see AGENTS.md § Secrets."
fi
# Never print or log .env contents — not even a "safe" preview.

# ---------------------------------------------------------------------------
# 6. Verify contract files exist
# ---------------------------------------------------------------------------
echo "[6/7] Verifying contract files..."

REQUIRED_FILES=(
    "AGENTS.md"
    "CLAUDE.md"
    "SUBAGENTS.md"
    "config_defaults.py"
    "go-live-recert.sh"
)

MISSING_FILES=()
for f in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$SCRIPT_DIR/$f" ]]; then
        echo "  OK: $f"
    else
        echo "  MISSING: $f"
        MISSING_FILES+=("$f")
    fi
done

if [[ ${#MISSING_FILES[@]} -gt 0 ]]; then
    echo "ERROR: Required files are missing. The repo may be incomplete." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# 7. Smoke test — doc consistency + lightweight import check (no live path)
# ---------------------------------------------------------------------------
echo "[7/7] Running smoke tests..."

echo "  Checking doc consistency..."
if "$ACTIVE_PYTHON" "$SCRIPT_DIR/tools_doc_consistency.py"; then
    echo "  Doc consistency: PASS"
else
    echo "ERROR: Doc consistency check failed. Run:" >&2
    echo "  python3 tools_doc_consistency.py --list" >&2
    exit 1
fi

echo "  Checking core imports (no live trading path)..."
"$ACTIVE_PYTHON" - <<'PYCHECK'
# Verify that the non-live modules import without error.
# This catches missing dependencies and obvious syntax errors.
# It does NOT start the live bot, send webhooks, or connect to any broker.
try:
    import config_defaults           # noqa: F401
    import env_loader                # noqa: F401
    import store                     # noqa: F401
    import market_calendar           # noqa: F401
    print("  Import check: PASS")
except ImportError as e:
    print(f"  Import check: WARNING — {e}")
    print("  This may mean a dependency is missing from requirements.txt.")
    print("  It does NOT block setup; run 'python3 -m pytest -q' for the full picture.")
PYCHECK

# ---------------------------------------------------------------------------
# Done — print next steps
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  Setup complete!"
echo "============================================================"
echo ""
echo "NEXT STEPS:"
echo ""
echo "  1. Fill in .env with your credentials (if you haven't already)."
echo "     Open .env in a text editor — fill in Tradovate login, API key, etc."
echo "     NEVER commit .env to git (it is gitignored)."
echo ""
echo "  2. Run the full test suite to make sure everything is working:"
echo "     source .venv/bin/activate"
echo "     python3 -m pytest -q"
echo "     Expected: 0 failed (a few skipped is fine)."
echo ""
echo "  3. Read the docs before doing anything else:"
echo "     docs/GETTING_STARTED.md  — step-by-step beginner guide"
echo "     docs/CLAUDE_CODE_GUIDE.md — how to use Claude Code safely"
echo "     docs/SAFETY.md            — what never to do"
echo "     AGENTS.md                 — the full engineering contract"
echo ""
echo "  4. Open Claude Code for guided assistance:"
echo "     source .venv/bin/activate"
echo "     claude"
echo ""
echo "  IMPORTANT: Do NOT run go-live-recert.sh or auto_live.py until the"
echo "  operator has completed the pre-launch checklist in README.md."
echo ""
echo "  This script never started the live bot, sent any orders, or"
echo "  connected to any broker. You are safe."
echo ""
