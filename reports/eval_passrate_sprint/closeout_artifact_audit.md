# Sprint Closeout — Artifact-vs-Verdict Audit (Fable auditor, 2026-07-05)

Decision state audited against: EXECUTIVE_SUMMARY.md, the three DEC drafts, the vault-draft sprint
note, asia_london_extra_lane/summary_matrix.csv, cap_risk_matrix.md, fill_sensitivity.md.

| Verdict element | Artifacts consistent? |
|---|---|
| A10 remains live | ✔ everywhere |
| Cap-15 × $1,000 SIM CONDITIONAL, NOT promoted | ✔ labeled in every mention |
| Telemetry N≥30 required (~late Oct/early Nov) | ✔ |
| Adverse touch-without-fill kill line = **15%** (tightened from 20%; measured break-even 16.4%) | ✔ present in exec summary + DEC draft |
| A20-A40 / raw-E$ maxima REJECTED (fill fragility, k*≈0.0125-0.0163) | ✔ |
| R1 recycle = operator policy candidate (zero-code) | ✔ correctly scoped |
| Holiday-shortened start-week avoidance = operator policy candidate | ✔ |
| Asia/London: all 11 rejected/dead/watched, L6 killed at 1m truth, L1 watch-only | ✔ (summary_matrix rows verified) |
| Funded config unchanged + firewalled | ✔ (preflight hash check) |
| No artifact quotes 58.2% as current truth | ✔ (appears only as retired history where referenced) |
| No artifact describes funded payout as guaranteed | ✔ (model-observed language only) |

Findings: **no contradiction implying code/config drift.** One documentation note: the draft
DEC_DRAFT_eval_sizing.md is terser than the operator's required DEC wording (full promotion-gate
bullet list); the vault DEC will be written with the operator's REQUIRED wording verbatim —
an expansion of the draft, not a conflict.

**ARTIFACT AUDIT: PASS.** Cleared for vault migration and commit.
