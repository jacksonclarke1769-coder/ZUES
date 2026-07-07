# Apex Counterparty-Terms Review Checklist

**Cadence: MONTHLY, and MANDATORY before any arming event** (any point where a new eval or
funded account is bought/started, or a certification is (re-)issued against the Apex 4.0
50K ruleset).

This document is the human half of the drift canary in `test_apex_terms_canary.py`. The
canary can only catch **code vs. pinned-snapshot** drift (i.e. someone edited a constant in
`apex_funded_40.py` / `tools_account_size_research.py` without updating the yaml, or vice
versa). It CANNOT catch **snapshot vs. reality** drift — i.e. Apex silently changing a real
rule while the code and the snapshot stay in perfect agreement with each other but both go
stale against the live contract. Catching that requires a human to actually re-read the
source. That is what this checklist is for.

## Forcing-function chain (why this matters)

```
Apex changes a real rule (e.g. trailing DD, ladder cap, consistency %)
        |
        v
Operator re-reads the source, updates evidence/apex_terms/apex_terms.yaml
(new value + confidence + source + snapshot_date), re-hashes apex_terms.sha256
        |
        v
test_apex_terms_canary.py's DRIFT GUARD now compares the NEW pinned value against
every simulator that still hard-codes the OLD number
        |
        v
Every simulator/file that has NOT been updated FAILS the canary immediately
(named constant + both values + both locations — see the assertion messages)
        |
        v
That failure is not a bug to silence — it IS the re-certification trigger. Each
failing file's owning certification (eval cert, funded cert, any live-arming
decision built on that simulator's numbers) must be treated as INVALID until the
file is updated AND re-certified with the new terms.
```

In short: **a terms change is a re-cert event, not just an edit.** The canary makes it
structurally impossible to update one file and forget the other nine (see
`apex_terms.yaml`'s `findings.duplication` list of ~10 files carrying independent literal
copies of these constants) — every un-updated file goes red the moment the snapshot moves.

## What "re-read the source" means today (2026-07-07)

As of this task, **every Apex-rule value in `apex_terms.yaml` is `confidence: UNVERIFIED`
with `source: PENDING`.** No live Apex help-center page or contract document has been read
to confirm any of them — the values were pinned by reading this repo's own docstrings
(which themselves say "help-center-derived — VERIFY against the live contract before
relying on the $ numbers"). The two `funded_value_placeholder` / `eval_fee_placeholder`
entries are not even claimed to be real — they are a stand-in used for one internal
ranking metric.

**Before any arming event, this PENDING state must be resolved for at least the
constants that gate that specific event** (e.g. before starting a new 50K eval: confirm
`profit_target`, `eval_expiry_days`, `bot_daily_stop`/`dll_50k`, `eod_trail`,
`lock_trigger_eod_peak`, `locked_floor`; before a payout sweep: additionally confirm
`payout_ladder`, `payout_floor`, `min_req`, `qual_day`, `qual_n`, `consistency`,
`payout_cadence_days`).

## Monthly / pre-arming checklist

1. Open the live Apex account-rules / help-center page (or current signed contract) for
   the 50K EOD PA product. Record the exact URL/document reference actually used this
   time — do not carry forward a stale or invented citation.
2. For each constant in `apex_terms.yaml`, compare the live source value against the
   pinned `value`. If it holds: bump nothing except the log table below (do NOT bump
   `snapshot_date` for a no-change confirmation — only bump it when a `value` actually
   changes).
3. If ANY value differs:
   a. Update the constant's `value`, `confidence` (drop to a verified state only if you
      have an actual citation — otherwise leave UNVERIFIED but note the new value),
      `source` (the real citation, not PENDING), and top-level `snapshot_date`.
   b. Re-hash: `shasum -a 256 evidence/apex_terms/apex_terms.yaml > evidence/apex_terms/apex_terms.sha256`
   c. Run `python3 -m pytest test_apex_terms_canary.py -q` — expect FAILURES naming every
      file still on the old value. That is correct behavior, not a bug.
   d. File a re-certification task per file that failed (do not silence the canary by
      just editing those files without going through the normal spec → review →
      implement → gate.sh flow for anything touching `config_*`/`strategy_*`/live limits).
4. Re-confirm the `funded_value_placeholder` ($8,000) / `eval_fee_placeholder` ($131)
   are still explicitly marked PLACEHOLDER in the yaml and have not been quietly promoted
   to look authoritative anywhere downstream (dashboards, reports, vault notes).
5. Record the outcome in the log table below.

## Review log

| Date       | Reviewer | Result                                                                 |
|------------|----------|-------------------------------------------------------------------------|
| 2026-07-07 | zeus-implementer (task: apex counterparty-terms canary) | Initial snapshot created. All values transcribed directly from the two canonical source files (`apex_funded_40.py`, `tools_account_size_research.py`) and cross-checked against 8 sibling files — no code-vs-snapshot discrepancy found. **No live Apex source was read** — all entries remain `confidence: UNVERIFIED` / `source: PENDING`. This row is a code-transcription check, NOT a live-terms confirmation; the first real review against the live Apex contract is still outstanding and MANDATORY before any arming decision that relies on these numbers. |

<!-- Add new rows above this line. Never delete history — this log is the audit trail for
     "when did we last actually check this against a live source" separate from "when did
     the code last agree with itself". -->
