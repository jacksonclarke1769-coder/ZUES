# Contributing to ZEUS

ZEUS is a live trading system. Every change has the potential to affect real money.
This document explains the workflow, standards, and limits that keep contributions safe.

Read `AGENTS.md` before contributing — it is the master engineering contract and is
authoritative above everything in this document.

---

## The Three-Gate Workflow

Every non-trivial change moves through three gates. See `docs/development_workflow.md`
for the full specification.

```
Gate 1: Fable PLANS        → produces a written specification (ticket)
Gate 2: Sonnet IMPLEMENTS  → executes the spec exactly, runs tests
Gate 3: Fable REVIEWS      → verifies the diff matches the spec, approves or rejects
```

**Trivial changes** (typos, log wording, doc corrections that do not affect numbers) may
skip to a single Sonnet pass — but still report in the standard format.

**A task is not done** until:
1. Its stated success criteria are met.
2. The full test suite is green (`python3 -m pytest -q`, 0 failed).
3. No parity, causality, or fail-closed regression.
4. Certification artifacts updated if any measured number changed.
5. The standard output report is delivered (`docs/output_format.md`).
6. Nothing outside the task's allowed-files list was modified.

---

## Branch Naming

```
feature/<short-description>      # new capability
fix/<short-description>          # bug fix (root cause already identified)
docs/<short-description>         # documentation only
audit/<short-description>        # look-ahead / parity / certification audit
```

Examples:
```
feature/telegram-daily-summary
fix/d1c-stale-file-handling
docs/funded-model-numbers
audit/profile-a-fill-bar-sequencing
```

---

## Commit Style

Every commit message should cite the engineering contract and describe the *why*, not just
the *what*:

```
fix: D1c suspend path was continue not block (AGENTS.md §fail-closed)

The old code continued to the order path when the d1c_filter returned None.
This violates the fail-closed rule. Changed to return early with a SUSPEND
event, matching the pattern in auto_safety.py.
```

For docs-only commits:
```
docs: rewrite README.md with Rev B certified numbers (ticket AB)
```

For implementation commits from a ticket:
```
impl: ticket AB — beginner onboarding docs + setup-zeus.sh

Implements docs/tickets/AB-onboarding-docs.md exactly.
README.md rewritten; ARES docs bannered; 6 new docs + setup script added.
test_doc_consistency.py added; tools_doc_consistency.py exits 0.
```

---

## Running Tests

Run the smallest relevant test file first, then the full suite:

```bash
# Smallest first (fast feedback)
python3 -m pytest test_d1c_eval.py -v

# Full suite — must be 0 failed before anything is "done"
python3 -m pytest -q

# Additional check for docs changes
python3 tools_doc_consistency.py
```

The full suite takes about 30 seconds. Never skip it before declaring a task done.

---

## Requesting a Fable Review

Fable (the architect role) reviews the diff against the spec before any task counts as done.
To request a review:

1. Deliver the standard output report (`docs/output_format.md`) — paste it into the session.
2. Include: status, files changed, patch summary, test results, unresolved risks.
3. If there are open questions or the spec was ambiguous, say so explicitly. Do not guess.

Two rejections on the same task mean the spec was inadequate — go back to Gate 1.

---

## Sonnet Scope Limits

The implementer (Sonnet) must NOT:

- Redesign architecture (even "locally nicer" structure — implement the spec as written)
- Change strategy logic: entries, exits, stops, targets, filters, sizing, session windows,
  or their timing — under any circumstance not spelled out in the spec
- Reinterpret research findings or "improve" a certified parameter
- Alter certification methodology, harness conventions, or recorded numbers
- Make statistical decisions (choosing configs, reading sweeps, deciding significance)
- Create or delete approval flags, touch `.env`, or arm anything live
- Widen the task's allowed-files list

If Sonnet hits any of these situations, it STOPS and returns `BLOCKED — decision needed`.
That is the correct behaviour. Do not work around it.

---

## No Production Without Approval

Changes to the live machine require:
1. A harness run on real data
2. Results recorded in `reports/apex_validation.json`
3. Explicit operator approval

"It should be roughly the same" is not a measurement. The engineering contract requires
evidence. Any change to entries, exits, sizing, filters, or their timing de-certifies the
machine until the committed harness re-measures it.

---

## No Strategy Without Certification

Before a new strategy feature is believed, certified, or ticketed, it must pass the
look-ahead canary (`lookahead_canary.py`): poison all data after the decision timestamp,
and confirm the signal does not change. This is mandatory since 2026-07-02 — both known
bug classes (F1 fill-bar sequencing and Z resample indexing) produced era-consistent,
profitable-looking fake edges before the canary was required.

---

## Questions

If you are unsure whether a change is in scope, create a Fable planning ticket first.
A ticket that says "I'm considering X — is it safe?" is a perfectly valid starting point.
Guessing at a boundary is the one unforgivable implementation error.
