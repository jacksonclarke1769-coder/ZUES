# ZEUS Standard Development Workflow

Every non-trivial change moves through three gates. Roles are defined in `../SUBAGENTS.md`; the
engineering contract is `../AGENTS.md`. Trivial changes (docs, log wording) may skip to a single
Sonnet pass but still report in the standard format.

## Phase 1 — Fable: plan

1. **Inspect** — targeted reads of the files in scope (grep/sed ranges, not full dumps).
2. **Analyse** — root cause, constraints (fail-closed, parity, certification impact), alternatives.
3. **Produce an implementation specification** using `task_template.md`, containing at minimum:
   - the Problem and the intended behavior after the change
   - Scope with explicit **Files allowed** / **Files forbidden**
   - exact patch locations where known (`file.py:func` / line anchors)
   - Success criteria + the Verification commands (which tests, which harness)
   - whether the change de-certifies anything (and if so, the re-certification plan)

A spec that would require Sonnet to make a statistical or architectural choice is not finished.

## Phase 2 — Sonnet: implement

1. Implement the specification exactly. Surgical patches; match surrounding style.
2. Run the smallest relevant tests, then the FULL suite (`python3 -m pytest -q`). Fix implementation
   bugs until green.
3. Write/update tests named in the spec (a behavior change needs a test that fails on old behavior).
4. Report in the standard output format (`output_format.md`).
5. On any ambiguity or boundary (see the stop rule in `SUBAGENTS.md`): STOP, report
   `BLOCKED — decision needed`, hand back to Fable. Do not guess.

## Phase 3 — Fable: review

1. **Review the diff** against the spec — every changed file, nothing outside allowed-files.
2. **Verify correctness** — rerun key tests/harnesses; check fail-closed direction on every new error
   path; check parity/causality where touched; check certification artifacts updated if numbers moved.
3. **Approve or reject.**
   - Approve → task is done (per the Definition of Done in `AGENTS.md`).
   - Reject → return to Phase 2 with a delta-spec (what to change, why). Two rejects on the same task
     mean the spec was inadequate: go back to Phase 1.

## Escalation map

| Situation | Handled by |
|---|---|
| Spec ambiguity, failing behavioral test, forbidden-file need | Sonnet → STOP → Fable |
| Live incident, money-path bug, certification question | Fable (immediately) |
| Anything requiring an approval flag, `.env`, or arming live | OPERATOR only |

## Why this split

Fable reasoning is expensive and is what prevents de-certification, look-ahead, and fail-open bugs.
Sonnet implementation is cheap and fast. The spec is the interface: everything above it is Fable's,
everything below it is Sonnet's, and the review gate makes the split safe.
