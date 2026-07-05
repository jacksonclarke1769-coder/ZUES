# ZEUS bot — Claude Code repository instructions

This is a LIVE trading system on real prop-firm capital. Before doing anything here, read **AGENTS.md**
(engineering contract) and follow it exactly. Role split and workflow:

- **SUBAGENTS.md** — Fable plans/audits/certifies/reviews; Sonnet implements against written specs.
- **docs/development_workflow.md** — the Fable → Sonnet → Fable three-gate workflow.
- **docs/task_template.md** — every task/spec uses this template (Files allowed/forbidden are enforced).
- **docs/output_format.md** — every report uses this exact format.

## Model routing (token discipline)

- Planning, research, audits, certification, statistical decisions, root-cause analysis, reviews →
  main session / `zeus-architect` agent (Fable-class reasoning).
- Implementation against an approved spec, test-running, mechanical fixes, docs → delegate to the
  `zeus-implementer` agent (`.claude/agents/zeus-implementer.md`, runs on Sonnet).
- An implementer that hits ambiguity or a strategy/certification boundary STOPS and returns
  `BLOCKED — decision needed` (the stop rule in SUBAGENTS.md). Never guess at boundaries.

## Hard rules (summary — AGENTS.md is authoritative)

- Fail closed on every error path that could reach an order.
- Live must match certified; strategy logic changes require harness evidence + re-certification.
- Preserve causality (closed-bar decisions, conservative same-bar sequencing) and parity (0 mismatches).
- Small surgical patches; targeted reads (`grep -n` / `sed -n`), never full-file dumps.
- Full suite green (`python3 -m pytest -q`, ~30s) before "done". Numbers trace to
  `reports/apex_validation.json`.
- Never touch `evidence/approvals/`, `.env`, or live process control without explicit operator action.

## Knowledge vault (single source of truth for knowledge — permanent, 2026-07-03)

The Obsidian vault at `~/Documents/Zues` is the ZEUS knowledge base: architecture, research
history, certifications, audits, decisions, runbooks, lessons learned. This repo stays the source
of truth for CODE only. Bootstrap context from the vault (`Home.md` → `START HERE — New Claude
Session.md`), and after any completed task update the vault per its `Vault Conventions.md`
maintenance workflow (research → Research Register, decisions → `08 Decisions/DEC-*`, incidents →
`07 Bugs & Incidents` + Lessons Learned, machine changes → new machine page + supersede). Numbers
in the vault must trace to `reports/apex_validation.json` exactly like numbers here.
