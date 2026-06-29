#!/usr/bin/env bash
# Launch the dedicated TradingView feed Chrome (CDP :9222, anti-throttle, persistent login profile).
#
# Thin delegator to the single source of truth at ~/trading-team/tools/launch-tv-chrome.sh.
# The previous standalone version omitted --user-data-dir, so `open -na "Google Chrome"` collided with
# the operator's already-running main Chrome (default-profile lock) and --remote-debugging-port was
# silently ignored — CDP never came up (root cause, 2026-06-29). The canonical launcher passes a
# separate --user-data-dir, so it spawns a genuine 2nd instance alongside the main Chrome and binds CDP.
set -uo pipefail
exec bash "$HOME/trading-team/tools/launch-tv-chrome.sh" "$@"
