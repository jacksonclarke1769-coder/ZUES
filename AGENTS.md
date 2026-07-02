# ZEUS — Master Project Instructions (AGENTS.md)

Read this before doing ANYTHING in this repository. It is the contract every model/session works under.
Role split (who plans vs who implements): see `SUBAGENTS.md`. Workflow: see `docs/development_workflow.md`.

## What this repository is

A LIVE automated NQ futures trading bot on real prop-firm capital (Apex 50K eval, TradersPost →
Tradovate). Mistakes here lose real money.

## 🔒 ZEUS Production Machine v2026.07.02 rev b (DLL re-lock) (LOCKED — operator-approved)

**A10 · Exit#3 · D1c ACTIVE_EVAL_FILTER · size-to-risk $1,200 · B OFF · momentum OFF · $550 daily stop**
(pass 58.2% / bust 29.1% / expire 12.7% / median 11d — DLL-honest model; operator confirmed Apex 50K
EOD DLL = $1,000 on 2026-07-02; provenance `reports/apex_validation.json` §dll_recert_selected_machine,
harness `tools_account_size_research.py`). Launch ONLY via `./go-live-recert.sh`. No task may alter
this configuration without a new certification run and explicit operator approval.

⚠ **STALE-PROCESS WARNING:** any `auto_live.py` process started BEFORE 2026-07-02 ~11:00 AWST runs the
OLD machine (SINGLE_1R, B on, momentum flag, MFFU rules, read-back halted) and must NOT be trusted.
Before any live restart the operator must: (1) rotate the Tradovate password (the old one was exposed),
(2) verify the Apex trail on the live dashboard — config assumes $2,500; if it shows $2,000 update
`config.py EVAL.trail_dd` first (DLL $1,000 verified 2026-07-02), (3) confirm the Tradovate
account-manager panel is readable in the :9222 Chrome, (4) start only with `./go-live-recert.sh`.

## Engineering principles (non-negotiable)

1. **Fail closed.** An error path, missing flag, unreadable panel, or unknown config value must BLOCK
   trading, never permit it. A gate failure may only ever cost income — never add risk. If you write an
   `except:` on the order path, the handler must return/block, not continue.
2. **Live must always match certified.** The code that trades is the code that was measured. Any change
   to entries, exits, sizing, filters, or their timing de-certifies the machine until the committed
   harness re-measures it. "It should be roughly the same" is not a measurement.
3. **Never modify strategy logic without measurable evidence.** Evidence = a committed harness run on
   real data with results recorded in `reports/apex_validation.json`. Intuition, memory of old numbers,
   or a plausible argument do not qualify.
4. **Preserve causality.** No decision may use information from at/after the bar it acts on. Signals
   decide on CLOSED bars; fills happen strictly after signals; same-bar entry-vs-target sequencing is
   unprovable at bar resolution and must be resolved conservatively (the 2026-07-02 F1 bug — fill-bar
   target booking — inflated every headline stat; never reintroduce it).
5. **Preserve parity.** Live engines import/mirror the backtest engines. The parity harnesses
   (`test_signal_parity.py`, `tools/check_profile_b_parity.py`, `verify_momentum_parity.py`) must stay
   at 0 mismatches. If your change breaks parity, either fix the change or re-certify — never ship a
   silent divergence.
6. **Small surgical patches.** Before any refactor, check whether a 1–5 line patch does the job. Match
   the surrounding style. Do not rewrite working modules to make them prettier.
7. **Token discipline.** Targeted reads (`grep -n`, `sed -n 'a,bp'`) over whole-file dumps. Read only
   the files the task needs. Never print large files, logs, or data frames into the conversation.
   Minimal tokens never justifies skipping verification.

## Repository conventions

- Live runner: `auto_live.py` (LiveAuto + main loop). Safety: `auto_safety.py`, `runtime_config.py`
  (CONFIGLOCK), `config_defaults.py` (committed defaults — NO secrets), `config.py` (gitignored local).
- Committed simulators/harnesses live in the repo root (`tools_*.py`, `apex_*.py`, `exit_model_*.py`).
  NEVER put a harness in /tmp — results must be reproducible from the repo.
- Approval flags in `evidence/approvals/*.flag` gate live behaviors (EXITLOCK, momentum, TradersPost).
  Creating a flag is an OPERATOR action, never an implementation detail.
- Numbers shown anywhere (dashboard, docs, Telegram) must trace to `reports/apex_validation.json`,
  which must trace to a committed harness (`test_apex_validation_provenance.py` enforces this).
- Secrets come from `.env` (loaded by `env_loader.py`). Never hardcode credentials; never print them.
- Timezones: all session logic is tz-aware `America/New_York` via zoneinfo. Never use naive datetimes
  on the money path.

## Testing expectations

- Full suite (`python3 -m pytest -q`) must be GREEN (0 failed) before any task is "done". ~600 tests,
  ~30s. No skipping.
- Every behavior change ships with a test that would fail on the old behavior. Deliberate behavior
  changes update the old tests WITH a comment citing the reason/audit item.
- Run the smallest relevant test file first, the full suite last.

## Certification rules

- Fills: 1m-truth conventions (`tools_1m_truth_recert.py`) — no same-bar target on the fill bar,
  adverse-first (stop before target) on every bar, real Databento data only.
- **LOOK-AHEAD CANARY (mandatory since 2026-07-02):** every NEW research feature ships with an
  `assert_causal()` test (`lookahead_canary.py`) — poison all data after ts, the value must not
  change — BEFORE its results are believed, certified, or ticketed. Named bug classes it catches:
  F1 (fill-bar target/entry sequencing) and Z (indexing a full-frame resample at "the bucket
  containing ts" — that bucket holds its FINAL close = future data; use `completed_bucket_slope()`
  or completed buckets only). Both classes produced era-consistent, profitable-looking fake edges.
- Comparisons must be paired (same data, same harness, same costs) and ranked on the business axes:
  pass rate, bust rate, expectancy, worst-day/threshold proximity, trade count, era-split robustness —
  never raw PF alone.
- A held-out period must be frozen BEFORE looking at results. An OOS column consulted during selection
  is no longer OOS.
- Old numbers invalidated by a methodology fix are marked INVALID in `apex_validation.json` with a
  root-cause note — never silently overwritten.

## Risk philosophy

- The bust-terminal constraint is the trailing-drawdown cushion; every prospective gate protects it.
- Risk gates SIZE DOWN before they reject, and reject before they ever add exposure.
- The $550 daily stop, the P3 brake, the read-back sentinel, and the flatten guardian are load-bearing
  safety systems: changes to them get the same rigor as strategy changes.
- Never deploy a configuration whose bust rate exceeds its pass rate.

## Required output format

Every task reports in the standard format — see `docs/output_format.md`. No essays, no full-file dumps.

## Definition of "done"

A task is done when ALL of these hold:
1. The stated success criteria of the task are met (see `docs/task_template.md`).
2. Full test suite green; new/updated tests cover the change.
3. No parity, causality, or fail-closed regression.
4. Certification artifacts updated if any measured number changed.
5. The standard output report is delivered, including unresolved risks stated honestly.
6. Nothing outside the task's allowed-files list was modified.
