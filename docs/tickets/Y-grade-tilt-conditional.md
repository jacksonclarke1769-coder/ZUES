# TASK: Y — grade-tilt sizing overlay [CLOSED 2026-07-02 — DLL CONFIRMED $1,000 by operator]

> ⛔ CLOSED: operator verified the 50K EOD eval carries a fixed $1,000 DLL (help-center table
> $500/$1k/$1.5k/$2k for 25/50/100/150K). Per the decision tree, baseline @$1,200 dominates the
> tilt — ticket X proceeds; this ticket is dead. Kept for the inverse-confluence finding record.

ROLE: Sonnet implement (AFTER operator DLL verification returns "no DLL" AND Fable re-review)
DE-CERTIFIES: yes (sizing overlay changes the certified machine)

## Finding (tools_a_refine.py, 2026-07-02, pre-registered)
Inverse-confluence is the ONLY IS+HO-consistent quality signal in the locked A stream: grade C/D
setups outperform A/B in BOTH eras (WR ~72-77% vs ~52-57%, expR ~0.7-0.9 vs 0.24-0.53). As a sizing
TILT (budget x1.30 for grade C/D, x0.80 for A/B; no trades dropped):
  * NO-DLL world @$1,600: pass 60.0->63.3 (+3.3pp), bust 36.7->32.9 (-3.8pp), IS and HO both improve.
  * DLL world: REJECTED — baseline @$1,200 (ticket X) dominates (58.2/29.1 vs tilt@1600 56.7/35.9;
    tilt@1200 is negative).
So: X (DLL confirmed) -> close this ticket. X (no DLL) -> this is the best-known config.

## Scope (if activated)
- Expose model01's confluence grade on the live signal path (bot.py sig dict) with a parity test
  proving live grade == backtest grade on the full history (0 mismatches — same bar as the parity
  suite), then apply the budget multiplier in auto_live's _risk_gate sizing.
- Full re-certification run + apex_validation.json entry + AGENTS.md/dashboard update.

## Files forbidden until activated: ALL. This ticket is a parked decision, not work.
