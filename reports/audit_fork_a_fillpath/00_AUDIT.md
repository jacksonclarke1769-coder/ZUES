# Retroactive fill-path audit — FORK-A walker vs the same-bar cancellation bug class

Date: 2026-07-20 · Auditor: Fable (main session) · Scope: verification only, no strategy change,
no emit-at-fill build, no arming. LIVE HOLD remains ACTIVE.

Cross-links: survey incident vault `AUDIT-20260720-0941` (ICT concept survey v1 retraction,
survey fix commit 652fdbf); FORK-A verdict commit `235907c`
(`reports/inc_20260707_recert/01_CAUSAL_FORK_VERDICT.md`); recert lineage `d87692a`.

## Verdict: **FORK A — VERIFIED-STANDS**

The walker behind the 188-winner / +80.9R / PF 2.617 causal-fork verdict already implements the
correct same-bar convention, implemented it at the time the verdict was computed, and its ledger
contains the instant-loss population whose absence was the survey bug's fingerprint. The
emit-at-fill premise survives the mechanical fill-path audit.

## Step 1 — which walker produced the verdict

`tools_1m_truth_recert.py::walk_1m` (lines 72–113), driven by
`databento_emission_replay.py` (line 217: `T1M.walk_1m(...)`), loading via the certified
single-vendor path (`apex_eval_eod_databento.load_databento_5m` + `RD.load_1m`).

- It is **NOT shared** with the ICT survey's engine (`backtests/zeus-ict-2026-07/concept_survey/
  survey_engine.py`, a fresh build). The survey bug neither originated in nor was fixed into
  this walker; the survey fix 652fdbf touched only the survey harness.
- Git: the correct convention entered at commit `1ef27cd` ("Full audit → repair → 1m-truth
  recertification"), which **is an ancestor of** verdict commit `235907c`; `walk_1m` is
  byte-unchanged from `1ef27cd` through current HEAD (`git log 1ef27cd..235907c --
  tools_1m_truth_recert.py` → empty; `git diff 235907c HEAD -- tools_1m_truth_recert.py` →
  empty). The 188-winner audit therefore ran on the post-fix walker.

## Step 2 — same-bar regression tests against this walker

New permanent test file: `tests/test_fork_a_fill_convention.py` (4 tests, all pass; suite-style
FakeMap over the M1Map interface):

1. Same-bar entry+stop (long): **filled-then-stopped, −1.50R booked** (includes A_SLIP penalty —
   stricter than the −1R minimum the convention requires). Not cancelled, not skipped. PASS.
2. Same-bar entry+stop (short): symmetric. PASS.
3. Fill bar touching entry AND target: target **not** credited on the fill bar (walk_1m line
   100–101, the "F1 fix": `if x == fill_i: continue` placed AFTER the stop check). PASS.
4. Later ambiguous bar touching both stop and target: stop-first. PASS.

Code-level confirmation: `walk_1m` line 96–99 — "stop first — including on the 1m fill bar
itself" — the stop check precedes the fill-bar `continue`, so the instant-loss case is
structurally bookable. There is no pre-fill cancellation-on-invalidation path in this walker at
all (entry/stop/target are fixed by the certified signal; the only no-fill case is the limit
literally never trading, which is outcome-neutral).

## Step 2.3 — physical-impossibility check on the real ledger

`research/atlas/profile_a_edge/outputs/signals_583_classified.csv` (the canonical classified
583-signal stream, 1m-truth R):

- Full-stop losses (R ≤ −0.95): **234 / 583 = 40.1%** of the population. The survey artifact's
  fingerprint (~0% fill-bar stop breaches) is **absent**.
- mae_r ≤ −1.0 on 299 signals — adverse excursion beyond the stop distance is observed and
  recorded, i.e. the walker sees and books the paths the survey bug deleted.
- Note: `reports/inc_20260707_recert/emission_replay_raw_full.csv` carries the emission
  classification but its `r_1mtruth` column is empty (708 rows, all NaN) — economics live in the
  classified CSV / recert JSONs, not that file. Documented to prevent a future false alarm.

## Step 3 — partition re-derivation

No discrepancy found in Step 2, so no re-run required. Re-derived from the canonical stream as a
consistency check: DELAYED = 187 signals, 111 winners, **+79.41R, PF 2.587** — matching
EMIT-001's `g4_g5_economics.json` (delayed_187 PF 2.587) exactly. The verdict-era figures
(189 suppressed / +80.91R / PF 2.617 / "188/188 recoverable") reconcile via PAE-001's later,
stricter classification which moved 2 of the 189 out of DELAYED (1 UNREACHABLE,
1 POST-ENTRY-DEPENDENT) — i.e. the small numeric drift between 235907c and the canonical stream
is a documented reclassification, not an error.

## Step 4 — fill-path pre-gate coverage across walkers

Audited against this bug class as of 2026-07-20:

| Walker | Status |
| --- | --- |
| `concept_survey/survey_engine.py` | FIXED + regression-tested (652fdbf, test_fill_sequencing.py) |
| `tools_1m_truth_recert.walk_1m` (FORK-A / recert / honest-numbers lineage) | **VERIFIED CLEAN (this audit)** + tests/test_fork_a_fill_convention.py |
| VPC execution lane streaming engine | Previously adversarially certified incl. same-bar defects (F2/F3 class, registry VPC-LANE round 2) — treated as covered |

UNCHECKED against this specific bug class (flagged for future audits, in priority order of how
load-bearing their ledgers are):

1. `tools_1m_truth_recert.walk_5m` (b_streams' 5m walker — Profile B numbers)
2. `apex-bot-share/models/model01_sweep_mss_fvg._simulate` (frozen core's own simulator)
3. `research/honest_numbers/fill_verify.py` (honest-scoreboard fill placement)
4. `backtests/zeus-occ-optimize/engine.py` and `smc3/smc3_engine.py`
5. `backtests/zeus-ict-causal-v04/mirror.py::scan_exit`
6. `nq-chart 2/backend/pine.py` strategy emulator (local chart app)

Standing rule (from AUDIT-20260720-0941, now extended): any NEW walker must pass a same-bar
fill-convention regression + a ledger-level instant-loss-population check BEFORE its numbers
feed any statistical gate or decision.
