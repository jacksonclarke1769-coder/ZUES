# TASK: X — DLL-aware risk-budget re-lock ($1,600 → $1,200) [BLOCKED ON OPERATOR VERIFICATION]

ROLE: Sonnet implement (AFTER operator verifies + approves)
DE-CERTIFIES: yes — replaces the locked budget with the DLL-honest certified value

## Problem
Account-size research (tools_account_size_research.py, 2026-07-02) modeled the Apex 4.0 EOD eval's
$1,000 Daily Loss Limit honestly (day force-flattened when marked open loss touches −DLL). Under it,
the locked $1,600 budget lets a single A trade's excursion cross the DLL — Apex cuts deep-pullback
winners at −$1k. Result: budget $1,200 DOMINATES $1,600 (pass 58.2% vs 51.9%, bust 29.1% vs 40.5%,
E[$/attempt] $7,040 vs $5,341). The v2026.07.02 certification did not model the DLL at all.

## OPERATOR GATE (must complete BEFORE implementation)
1. Verify on the live Apex contract/dashboard whether the 50K EOD eval enforces a $1,000 DLL
   (help-center sources say yes for 4.0 EOD; the account vintage is ~June 2026).
2. If DLL confirmed → approve this ticket. If NO DLL (legacy account) → CLOSE this ticket; the
   $1,600 lock stands.

## Scope (after approval)
- config_defaults.py: A_RISK_BUDGET_USD 1600 → 1200, with a comment citing the DLL recert.
- AGENTS.md lock section + OPERATOR_RUNBOOK banner + go-live-recert.sh echo text + zeus_server
  display constants: update machine line to "size-to-risk $1,200" and the certified numbers to the
  DLL-honest row (pass 58.2 / bust 29.1 / exp 12.7 / med 11d — reports/account_size_research JSON).
- reports/apex_validation.json: add the DLL-recert block; mark the DLL-free 57.7/17.7 row as
  superseded (methodology note: DLL unmodeled).
- Tests asserting 1600/57.7 updated with citation comments. Full suite green.

## Files forbidden
- Strategy engines, auto_live logic (the budget is a config constant), evidence/, .env

## Success criteria / Verification
- grep shows no remaining "1,600"-as-current-lock claims; suite green; provenance test green.
