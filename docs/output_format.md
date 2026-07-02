# ZEUS Standard Output Format

Every task — implementation, audit, research, review — reports in EXACTLY this shape. Compact: no
essays, no full-file dumps, no unexplained jargon. Diffs summarized, not pasted wholesale.

```text
PHASE: <which task/phase this report covers>
STATUS: <✅ complete | ❌ failed | BLOCKED — decision needed>

FILES CHANGED:
<comma-separated list; "(new)" for created files; "none (read-only)" for research>

PATCH SUMMARY:
<per file or per fix: WHAT changed and WHY, 1-3 lines each. Cite file:line or function anchors.>

TESTS RUN:
<exact commands, smallest-first then full suite>

RESULTS:
<pass counts, harness outputs, measured numbers. If numbers changed: OLD -> NEW, and note the
 certification artifact updated. If a previously-published number is now invalid, SAY SO.>

UNRESOLVED RISKS:
<numbered, honest, specific. "none" only if truly none. Include: deviations from spec (with the
 operator/reviewer decision needed), residual gaps, anything time-sensitive.>

NEXT STEP:
<the single concrete next action, and whose it is (Fable / Sonnet / OPERATOR).>
```

## Rules

- **STATUS is honest.** Tests failing = ❌ or BLOCKED, never "mostly done". A skipped verification is
  a lie of omission.
- **Numbers carry provenance.** Any measured figure names the harness that produced it. Dashboard/doc
  numbers trace to `reports/apex_validation.json`.
- **BLOCKED reports** state the exact decision needed and the options considered — they are the
  Sonnet→Fable handoff artifact (see the stop rule in `../SUBAGENTS.md`).
- **Secrets never appear** in reports (no URLs with tokens, no credentials, no account numbers beyond
  the account label).
