# TASK: W — repository-wide knowledge reconciliation (single source of truth)

ROLE: Sonnet implement
DE-CERTIFIES: no (documentation + display strings only)

## Problem
Pre-2026-07-02 machine descriptions (SINGLE_1R default, A10/B5/mm6 = 21 MNQ, Profile A+B+momentum,
pass 57.5/59.8/63.1/86%, funded $2.4k/mo · 80% lock · $19-22k EV, MFFU-as-firm) survive across
runbooks, reports and the dashboard. The single source of truth is now:

**ZEUS Production Machine v2026.07.02** — A10 · Exit#3 · D1c ACTIVE_EVAL_FILTER · size-to-risk
$1,600 · B OFF · momentum OFF · $550 daily stop · eval pass 57.7% / bust 17.7% (1m-truth) · funded
~$12.6-12.8k lifetime/PA ladder-capped (A4-A5, ~16mo median). Canonical definition: AGENTS.md
"🔒 THE SELECTED MACHINE" section; numbers: reports/apex_validation.json.

## Scope
Rule of treatment (apply consistently):
- **Historical artifacts** (anything in reports/ dated pre-2026-07-02, B1_DESIGN.md,
  RUNBOOK_SINGLE1R.md, MONDAY_GOLIVE.md, MONDAY_SESSION.md, KEY_ARRIVAL.md if stale): do NOT rewrite
  content. PREPEND this exact banner (adjusting nothing else):

  > ⛔ **OBSOLETE (pre-2026-07-02 machine).** This document describes a configuration/certification
  > that was INVALIDATED by the 2026-07-02 audit (5m fill-bar look-ahead) and superseded by
  > **ZEUS Production Machine v2026.07.02** — see `AGENTS.md` §"THE SELECTED MACHINE" and
  > `reports/apex_validation.json`. Kept for historical reference only.

- **Living operator docs** (README.md, RULEBOOK.md, ADD_ACCOUNT.md, OPERATOR_RUNBOOK.md,
  docs/ARES_DAILY_CHECKLIST.md, docs/ARES_KILL_SWITCH.md, docs/STAGE_A_PAPER_SOAK_RUNBOOK.md,
  HEIMDALL.md): find each stale machine reference (grep terms below) and UPDATE it in place to the
  v2026.07.02 machine (or delete the stale clause if it's incidental). Where a doc teaches an
  obsolete procedure (e.g. STAGE_A launch recipe with --profile-momentum / momentum-qty / B lanes),
  correct the command to the go-live-recert.sh form. Keep edits surgical.

- **Dashboard display constants** (`zeus_server.py` ~lines 219-235 status payload ONLY — strings
  and literal numbers, NO logic): the funded dict still shows lock_pct=80, income_mo=2412,
  lock="+$2.6k floor-lock", lock_days=51 and renders phase1/phase2 from the tier table (A4/B2/mm2
  etc.). Replace with the funded_40 recert truth: recommended A4-A5 · lifetime E[paid] ~$12.6-12.8k
  ladder-capped (6 payouts) · median ~16mo · bust ~0% observed · provenance apex_funded_40.py +
  reports/apex_validation.json "funded_40_recert" · note "tier-table B/mm lanes NOT re-certified —
  funded plan pending final sizing decision". Do NOT touch the tier table itself or any code path.
  Also scan dashboard/ static assets for stale figures (grep terms) and fix text only.

- **AGENTS.md**: retitle the lock section heading to
  "🔒 ZEUS Production Machine v2026.07.02 (LOCKED — operator-approved)" so the version name is
  canonical; content unchanged.

Grep terms (case-insensitive) to sweep with: `A10/B5`, `B5/mm6`, `mm6`, `21 MNQ`, `63.1`, `59.8`,
`57.5`, `86%`, `SINGLE_1R`, `single@1R`, `Profile A + B`, `A + B (ORB)`, `momentum lane`,
`PARTIAL_1R`, `A3/B2`, `A4/B2`, `income_mo`, `2412`, `19,419`, `22.1k`, `MFFU` (only where it
describes THIS bot's firm/plan — MFFU as historical research context may stay).
EXCLUDE from edits: docs/tickets/, reports/full-audit-2026-07-02.md, reports/phase3_sweep*,
reports/apex_funded_40*, reports/apex_validation.json, AGENTS.md history mentions (already framed
as history), test files, and ALL production .py except the zeus_server.py display block. Python
docstrings/comments in production code: LEAVE (code is certified as-committed; comments citing
history are not operator-facing truth claims).

## Files allowed
- All *.md in repo root, docs/, reports/ (banner-only for historical), dashboard/ text assets,
  zeus_server.py (display constants in the status dict ONLY)

## Files forbidden
- Any other .py, config*.py, evidence/, .env*, tests, docs/tickets/

## Success criteria
- A final `grep -rniE "<terms>" --include="*.md" .` (excluding tickets/full-audit/EXCLUDE list)
  shows every remaining hit is either (a) under an OBSOLETE banner, (b) inside AGENTS.md/audit
  history framing, or (c) an explicit "superseded/INVALID" statement.
- Dashboard /api status payload contains no pre-recert funded figures.
- Full suite green (zeus_server tests may assert old constants — update those assertions with a
  citation comment if so).

## Verification
- The final grep sweep output (include in report), `python3 -m pytest -q` → 0 failed.

## Exit criteria
Standard report listing: every stale reference found (file:line), treatment applied per file,
and the final-grep proof. Nothing outside allowed files.
