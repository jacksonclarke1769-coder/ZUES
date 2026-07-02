# Using Claude Code with ZEUS

Claude Code is an AI assistant that can read, explain, and help modify the ZEUS codebase.
Because ZEUS runs on real capital, Claude Code is configured with hard limits on what it is
allowed to change. This guide explains how to use it effectively and safely.

---

## Opening Claude Code

In your Terminal, from inside the `nq-liq-bot` folder, with your virtual environment active:

```bash
claude
```

Claude Code will automatically read `AGENTS.md` (the engineering contract), `CLAUDE.md`
(repository-specific instructions), and `SUBAGENTS.md` (the model role split). You do not
need to paste these in or explain them — they are loaded for you.

---

## What the contract files mean

**`AGENTS.md`** — The master engineering contract. It defines the non-negotiable rules that
govern every change to this repository: fail-closed error handling, requiring harness
evidence before any strategy change, preserving causality (no look-ahead bias), and parity
between the live engine and the backtest engine. Read it once carefully. Every Claude Code
session operates under these rules.

**`CLAUDE.md`** — Repository-level instructions that tell Claude Code which model roles to
use for which tasks. It points Claude Code to the key docs (AGENTS.md, SUBAGENTS.md,
development_workflow.md) and reminds it to stop and report `BLOCKED` if it hits anything
ambiguous.

**`SUBAGENTS.md`** — Defines the two-model role split:
- **Fable (architect/planner/auditor)** — makes decisions about what to change, why, and
  how. Does research, certification, and reviews.
- **Sonnet (implementer)** — turns an approved, written specification into code. Does not
  make strategic or statistical decisions. Stops and returns `BLOCKED` if it needs to.

---

## Fable vs Sonnet — when to use each

| Task | Use |
|---|---|
| "Explain how Profile A works" | Either — research question |
| "Is the D1c filter applied before or after sizing?" | Either — factual question |
| "Should we change the stop to 25 points?" | Fable — strategic decision, needs evidence |
| "Run the certification harness and interpret the results" | Fable — statistical reasoning |
| "Implement the change described in ticket XYZ" | Sonnet — implementation against a spec |
| "Fix the import error in test_d1c_eval.py" | Sonnet — mechanical bug with root cause known |
| "Audit auto_live.py for look-ahead bias" | Fable — correctness/certification audit |
| "Add a log line to auto_live.py at line 142" | Sonnet — small mechanical patch |

As a practical rule: if the task involves deciding WHAT to do or WHETHER it is safe, use
Fable (the main session or the `zeus-architect` sub-agent). If the task involves doing a
clearly-specified thing, use Sonnet (the `zeus-implementer` sub-agent).

---

## How to ask questions about the system (safe)

These prompts explore the codebase without changing anything:

```
"Explain what happens step-by-step when auto_live.py receives a Profile A signal."
```

```
"Show me where the D1c filter is applied and what happens if it returns False."
```

```
"What safety gates does auto_safety.py check before allowing an order?"
```

```
"Walk me through the fail-closed path in bridge_traderspost.py — what happens on a timeout?"
```

```
"What are the certified eval numbers for the current machine and where do they come from?"
```

---

## How to ask for research (safe, no live changes)

```
"Read reports/apex_validation.json and summarise the certified eval numbers."
```

```
"Run tools_doc_consistency.py and report any violations."
```

```
"Read the funded_40_recert block in apex_validation.json and explain what A4 means."
```

---

## How to ask for implementation (only against a written spec)

If you have an approved ticket or spec (see `docs/task_template.md`), you can ask the
implementer to execute it:

```
"Implement ticket docs/tickets/AB-onboarding-docs.md exactly as written."
```

```
"Run the full test suite and fix any implementation-level failures."
```

The implementer will STOP and say `BLOCKED — decision needed` if it encounters anything
that requires a strategic or statistical decision. That is the correct behaviour — do not
try to talk it through the block. Escalate to Fable instead.

---

## How to avoid accidental live changes

These are the main ways someone accidentally risks the live machine:

1. **Asking Claude Code to "fix" a strategy parameter.** Never ask "make the stop tighter"
   or "change the profit target." Any strategy logic change requires harness evidence + a
   new certification run. Claude Code should refuse — but do not try to work around it.

2. **Editing `config.py` directly.** Config is gitignored for a reason. The committed
   defaults are in `config_defaults.py`. Only the operator edits `config.py`, and only after
   a verified certification run.

3. **Running `go-live-recert.sh` or `auto_live.py` without operator approval.** These start
   the live bot. They should only be run after the operator pre-launch checklist is complete.

4. **Committing changes without a Fable review.** The workflow is Fable-plan → Sonnet-implement
   → Fable-review. Skipping the review gate puts unverified code into the repo.

5. **Creating approval flags.** Files in `evidence/approvals/` arm live behaviors. Only the
   operator creates them.

If Claude Code asks you to do any of the above without a written spec and operator approval,
say no and escalate.

---

## Recognising a dangerous command

A command is dangerous if it:
- Starts with `python3 auto_live.py` or `./go-live-recert.sh` (live bot)
- Writes to `evidence/approvals/` (approval flags)
- Writes to `.env` (credentials)
- Sends a webhook (curl to TradersPost URLs)
- Contains `--live` on a script you don't recognise

When in doubt, ask: "Is this command safe to run without operator approval?" If you are
unsure, do not run it.

---

## Example safe session

Here is what a safe, productive Claude Code session looks like:

```
You: Explain the three-gate development workflow.

Claude Code: [reads docs/development_workflow.md and explains it]

You: I want to add a Telegram notification when the daily stop is hit. Is that safe?

Claude Code: [explains what files would be touched, notes it needs a Fable spec first]

You: OK, create a Fable plan for that change.

Claude Code (Fable): [writes a ticket using task_template.md with Files allowed/forbidden,
                     patch locations, success criteria, and verification commands]

You: Implement the ticket.

Claude Code (Sonnet): [implements exactly the spec, runs tests, returns the standard report]
```

The plan separates what should change from how it changes. The implementation is mechanical,
verified, and scoped. Nothing outside the allowed-files list is touched.
