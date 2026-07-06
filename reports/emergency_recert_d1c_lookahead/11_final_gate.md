# Emergency Re-Cert — Final Gate (2026-07-06)
Commands: bash gate.sh (full 851-test suite incl. the two new D1c timestamp canaries + rewritten
parity/forecaster calibrations; funded + eval firewalls; 4-file SHA256 checks) · independent
funded-hash diff vs pre-cycle recording.
Results: ALL CHECKS GREEN (851 passed, 1 pre-existing deprecation warning) · funded hash
byte-identical to pre-cycle · zero live/config/funded files modified (research tools + tests +
reports only) · LIVE HOLD ACTIVE (go-live-recert.sh untouched, Operator Checklist frozen).
Known warnings: (1) live latest_signal() sibling defect — ticketed, NOT fixed (live hold);
(2) eval_forecast.valid_starts has a pre-existing 1-start boundary difference vs the cert harness
(documented in 09, within calibration tolerance); (3) headline constants in zeus_server/AGENTS/
README remain stale-and-flagged until the operator-approved re-lock (listed in 04).
