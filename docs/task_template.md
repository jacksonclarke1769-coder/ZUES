# ZEUS Task Template

Copy this template for every task/spec. A task missing any section is not ready for implementation.

```markdown
# TASK: <short imperative title>

ROLE: <Sonnet implement | Fable research/audit/review>
DE-CERTIFIES: <no | yes — what, and the re-certification plan>

## Problem
<What is wrong / missing, with evidence (file:line, log lines, harness output).
 What the behavior must be after the change. One paragraph if possible.>

## Scope
<The boundary of the change. What this task deliberately does NOT touch.
 Patch locations where known: file.py:function / line anchors.>

## Files allowed
- <explicit list — the ONLY files that may be modified>

## Files forbidden
- <anything tempting-but-off-limits, e.g. strategy engines, exit models, config_defaults constants>
- Always forbidden without operator action: evidence/approvals/, .env, live process control

## Success criteria
- <observable, checkable statements — "gate returns (False, why, 0) when no size fits">
- <tests that must exist/pass>
- Full suite green (0 failed)

## Verification
- <exact commands: pytest targets, harness runs, grep checks>
- <expected outputs/numbers where applicable>

## Exit criteria
- All success criteria met, verification outputs shown in the report
- Report delivered in docs/output_format.md format, unresolved risks stated
- Nothing outside Files-allowed modified (git diff --stat confirms)
```

## Notes

- **Files allowed/forbidden are enforced by review** — a diff outside the allowed list is an automatic
  reject, even if the change is "obviously fine".
- If, mid-task, the implementation genuinely needs a file not on the list: STOP and return the
  decision (see the stop rule in `../SUBAGENTS.md`).
- For research/audit tasks, "Files allowed" is usually "none (read-only) + new committed harness/report
  files only".
