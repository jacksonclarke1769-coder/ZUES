# TASK: AB — GitHub cleanup + beginner onboarding (docs/DX only)

ROLE: Sonnet implement. DE-CERTIFIES: no. Docs + setup script ONLY — zero trading/strategy/risk/config-value changes.

## Truth source (use these numbers verbatim; they trace to reports/apex_validation.json)
Machine = ZEUS Rev B (v2026.07.02b): Profile A ONLY · Exit#3 · D1c ACTIVE_EVAL_FILTER · Apex 50K EOD ·
size-to-risk $1,200 eval budget · B OFF · momentum OFF · HTF-skip INVALIDATED/off · NO Single-1R ·
NO MFFU · NO 150K. Certified eval: pass 58.2% / bust 29.1% / expire 12.7% / median ~11d.
Funded (model): $480 budget / A4 · ~$12.7k lifetime/account · ~15-16mo life · ~$785/mo gross ·
20-acct fleet ~$16-17k/mo gross · eval→first-payout ~53-58% · funded→first-payout ~91-100% (model).
Label clearly: CERTIFIED (eval numbers, from harnesses) vs MODEL-BASED (funded/fleet) vs
NEEDS-LIVE-VALIDATION (fill quality, actual payouts). Launch is ONLY ./go-live-recert.sh.

## Deliverables
1. README.md — FULL REWRITE (current one describes the ancient "NQ Liq-Session" strategy — DELETE that,
   it's wrong). Beginner-friendly GitHub homepage with the 15 sections from the operator brief:
   what ZEUS is · what it trades · locked machine · certified eval numbers · funded model numbers ·
   architecture overview · safety philosophy · setup · using Claude Code · what NOT to touch ·
   folder structure · common commands · operator checklist · research status · historical-docs
   disclaimer. Non-coder must understand it. Numbers labeled certified/model/needs-validation.
2. setup-zeus.sh (new, executable) — one-command safe setup: check Python 3.11+, create venv if
   missing, pip install -r requirements.txt, verify folders (out/, logs/, evidence/approvals/,
   dashboard-v3/), copy .env.example -> .env ONLY if missing (never overwrite; never write real
   secrets), verify AGENTS.md/CLAUDE.md/SUBAGENTS.md exist, run a SAFE smoke test
   (python3 -m pytest -q tools_doc_consistency… or a tiny import check — NOT the full trading path),
   print next steps. MUST NOT: start live trading, send webhooks, connect broker, place orders,
   touch live config, print secrets. Guard: refuse if run as root; never echo .env contents.
3. docs/GETTING_STARTED.md — total-beginner: install Git, clone, install Python, install Claude Code,
   open Terminal in the project, run ./setup-zeus.sh, start Claude Code safely, how to ask questions
   without changing trading logic, how to avoid live mode, how to know setup worked. Plain English.
4. docs/CLAUDE_CODE_GUIDE.md — opening Claude Code; what AGENTS.md/CLAUDE.md/SUBAGENTS.md mean;
   Fable(plan/research/review) vs Sonnet(implement) roles; when to use each; how to ask for docs vs
   research vs implementation; how to avoid accidental live changes; 4-5 example SAFE prompts.
5. docs/SAFETY.md — never commit secrets; never run live scripts without operator approval; machine
   is locked; no old configs; no undocumented launches; no manual production risk-value edits; no
   pushing unreviewed changes; how to spot a dangerous command; what to do if unsure.
6. docs/COMMANDS.md — commands grouped SAFE / RESTRICTED (go-live-recert.sh, auto_live.py,
   feed_watch.py, deadman_watch.py --live, webhook senders) / DANGEROUS (order-placing, .env edits,
   killing live processes). Beginner explanation each.
7. CONTRIBUTING.md — change flow, branch naming, commit style (cite AGENTS.md), running tests,
   requesting Fable review, Sonnet scope limits, no-production-without-approval, no-strategy-without-
   certification. Reference docs/development_workflow.md + task_template.md.
8. Banner the 2 stale living docs: prepend an OBSOLETE banner (same style as reports/) to
   docs/ARES_DAILY_CHECKLIST.md and docs/ARES_KILL_SWITCH.md pointing to AGENTS.md + README as truth.
9. test_doc_consistency.py (new) — assert tools_doc_consistency.main() returns 0 (docs consistent),
   and a unit test that a synthetic living doc with "SINGLE_1R" and no banner IS flagged.

## Files allowed
README.md, CONTRIBUTING.md, setup-zeus.sh (new), docs/GETTING_STARTED.md, docs/CLAUDE_CODE_GUIDE.md,
docs/SAFETY.md, docs/COMMANDS.md, docs/ARES_DAILY_CHECKLIST.md, docs/ARES_KILL_SWITCH.md (banner only),
test_doc_consistency.py (new). Read-only refs: AGENTS.md, SUBAGENTS.md, docs/*, reports/apex_validation.json.

## Files forbidden
Any .py except test_doc_consistency.py · config*.py · .env* · strategy/exec/risk code · tools_doc_consistency.py
(mine, don't edit) · evidence/approvals/ · production docs already correct (OPERATOR_RUNBOOK banner, etc).

## Success criteria / Verification
- `python3 tools_doc_consistency.py` exits 0 (your README/docs introduce ZERO new stale refs; the 2
  ARES docs banner-exempted). `bash -n setup-zeus.sh` OK. `./setup-zeus.sh` runs safe with no orders/
  webhooks/secrets (test in a scratch dir or with a dry guard). Full suite `python3 -m pytest -q` green.
- README shows the Rev B numbers exactly; no "NQ Liq-Session"/Single-1R/MFFU/150K as current.
