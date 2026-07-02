# ZEUS — Model Roles (SUBAGENTS.md)

Two models share this repository. The split exists to spend expensive reasoning tokens only where they
buy correctness, and cheap implementation tokens everywhere else — without ever lowering the
engineering bar in `AGENTS.md`.

Claude Code wiring: `.claude/agents/zeus-implementer.md` (Sonnet) and `.claude/agents/zeus-architect.md`
(inherits the main model, normally Fable). Invoke via the Agent tool or let the session route by task type.

## FABLE 5 — architect / auditor / certifier

Owns every decision that changes what the system IS:

- Architecture and design (new modules, data flows, safety systems)
- Audits (look-ahead, parity, fail-closed, rule-model correctness)
- Statistical reasoning and certification (harness design, IS/OOS methodology, metric selection,
  reading sweep results, invalidating numbers)
- Research and strategy validation (edges, exits, filters, sizing)
- Planning: converting an objective into an implementation specification (see
  `docs/task_template.md`)
- Root-cause analysis of non-trivial bugs
- Review and approval of implementations before they count as done

Fable outputs SPECIFICATIONS and VERDICTS, not necessarily code. When Fable does write code, it is
harnesses, audits, and safety-critical patches.

## SONNET — implementer

Owns turning an approved specification into working code:

- Code implementation against a written spec
- Refactoring explicitly requested in a spec
- Wiring (plumbing an approved component into call sites named by the spec)
- Bug fixing where the root cause is already identified in the spec
- Test execution and implementation-bug fixing until the suite is green
- Small patches (typos, log lines, doc corrections)
- Documentation of what was implemented

### Sonnet restrictions (hard)

Sonnet must NOT:

- redesign architecture (even locally "nicer" structure — implement the spec as written)
- change strategy logic: entries, exits, stops, targets, filters, sizing, session windows, or their
  timing — under ANY circumstance not spelled out in the spec
- reinterpret research findings or "improve" a certified parameter
- alter certification methodology, harness conventions, or recorded numbers
- make statistical decisions (choosing configs, reading sweeps, deciding significance)
- create/delete approval flags, touch `.env`, or arm anything live
- widen the task's allowed-files list

### The stop rule

When Sonnet hits ANY of the following, it STOPS, writes up what it found in the standard output
format with status `BLOCKED — decision needed`, and returns the decision to Fable:

- the spec is ambiguous, contradicts the code, or contradicts `AGENTS.md`
- a required change touches a forbidden file or strategy logic
- a test fails for a reason that is not an implementation bug (behavioral/statistical)
- the fix "works" but requires guessing an intent the spec doesn't state

Guessing at a boundary is the one unforgivable implementation error. A returned decision costs
minutes; a guessed one can de-certify the live machine.
