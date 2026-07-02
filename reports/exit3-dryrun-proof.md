> ⛔ **OBSOLETE (pre-2026-07-02 machine).** This document describes a configuration/certification
> that was INVALIDATED by the 2026-07-02 audit (5m fill-bar look-ahead) and superseded by
> **ZEUS Production Machine v2026.07.02** — see `AGENTS.md` §"THE SELECTED MACHINE" and
> `reports/apex_validation.json`. Kept for historical reference only.

# EXIT3 Dry-Run Payload Proof
_2026-06-21 · `tools/exit3_dryrun_proof.py` · no live sends_

EXIT_MODEL = `EXIT3_FIXED_PARTIAL` · account MFFU-50K-1 · 3 MNQ · DRY-RUN

| Leg | Send order | Qty | Limit | Stop | Target | R | signalId |
|---|---|---|---|---|---|---|---|
| ENTRY_TP2 (core) | **first** | 2 MNQ | 30654.75 | **30771.5** | 30421.5 | +2R | ZB-54cb1fe45af0dff8aac2 |
| ENTRY_TP1 (scalp) | second | 1 MNQ | 30654.75 | **30771.5** | 30538.25 | +1R | ZB-bd28e7fea057e35d02b9 |

Checklist:
- ✅ TP1 payload exists · qty = 1 · target = +1R (30538.25)
- ✅ TP2 payload exists · qty = 2 · target = +2R (30421.5, the strategy target)
- ✅ Both legs share the same stop (30771.5)
- ✅ Distinct deterministic signalIds
- ✅ INTEGRITY: legs=2, total_qty=3, shared_stop=YES, distinct_ids=YES
- ✅ NO single full-qty @ 2R payload built
- ✅ No live send (dry-run only)

**PASS.**
