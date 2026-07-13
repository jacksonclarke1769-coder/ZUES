# FORK A — PHASE 3 BUILD: surface-at-MSS emission for Profile A

**Branch:** `model01-surface-mss` (bot repo). **Status:** BUILT + verified, DEFAULT-OFF, NOT armed,
NOT pushed. **Date:** 2026-07-13.

> **UPDATE 2026-07-13 — sweep-selection parity defect FIXED → full 581/581.** The realtime-selection
> gap below (556/581 stateless) is resolved. `latest_mss_emission` now REPLAYS `run()`'s exact
> sequential scan — it resumes at the no-overlap free bar and advances past earlier setups with
> `run()`'s own reject-jumps (`i = mss_bar+1` on no-fill, `i = fill+1` on the risk guards) — so it
> pairs the SAME liquidity sweep `run()` does. The free bar is self-derived from the frozen
> `model01.run()` trade timeline (`_anchor_from_run`), so the stateless live path and the truncation
> canary both reproduce it with no caller state. **Full 581 parity = 581/581 match-at-k, sweep_ok all
> true, all emit at k** (`reports/fork_a/03_fast_parity_summary.json`). Own look-ahead canary stays
> CLEAN (20/20 emit-at-k, causally ≤ mss, via the self-contained internal path). Suite 968 passed / 1
> skipped; default-off path unchanged. **Honest fillable PF on the now-matched 581 = 1.3507
> (+86.78R, WR 44.8%).** The k-vs-k+1 timing held: every setup still emits at k (no k+1 regression).
> Detection math (`model01_sweep_mss_fvg.py`/`primitives.py`) and all protected files untouched.
**Scope guarantee:** the change moves WHEN/HOW the signal is emitted. It does NOT touch the detection
math — `model01_sweep_mss_fvg.py`, `primitives.py`, `config_*_locked.py`, EXITLOCK, watchdog,
bridge send path are all unmodified. Sweep/MSS/displacement/OTE detection is delegated **verbatim**
to the frozen `model01._detect()`; the OTE entry/stop/target/risk formulas are copied byte-for-byte
out of `model01.run()`.

---

## VERDICT — the rebuild WORKS and is causally clean; it revealed one BENIGN (non-look-ahead) nuance

The surface-at-MSS path emits the Profile-A OTE resting-limit at the **MSS bar's own close (k)**,
using **only bars ≤ mss_bar**. The build did **not** reveal a look-ahead, and the emission math
reproduces the certified 581 entry/stop/target/direction **exactly (581/581)**. It **did** reveal —
and resolve — the k-vs-k+1 realtime timing question (the task's named key uncertainty), and it
surfaced a second, **benign** finding: a stateless emit scan diverges from `run()`'s no-overlap
*sweep-pairing* on a few percent of bars (a selection nuance, not a causality or math error).

- **OWN CANARY (decisive): CLEAN.** For every verified signal, feeding the *realtime engine* data
  truncated at the mss_bar close makes it emit the identical signal on that bar. No post-MSS
  dependency exists in the BUILT code.
- **Real emit bar = k (mss_bar close), for all gaps** — including the 446/581 (77%) gap==1 setups.
- **Emission-math parity: 581/581 EXACT** — given `run()`'s sweep, the built formulas reproduce every
  certified entry/stop/target/direction to the cent (`refsweep_reproducible = 581`).
- **Realtime-selection parity: 581/581 (FIXED 2026-07-13).** Was 556 stateless / 568 with flat-since;
  the scanner now replays `run()`'s exact scan (no-overlap free bar + `run()`'s reject-jumps), pairing
  `run()`'s sweep for all 581 — `sweep_ok` true on every signal, `mismatch = 0`, `all_emit_at_k = true`.
- **Honest fillable PF (BUILT path, emit-at-k):** **1.3507 (+86.78R, WR 44.8%) on the matched 581**
  (= the selection-perfected certified stream, now reproduced end-to-end); durable **IS ≈ 1.18**
  unchanged. (Pre-fix: 1.2965 on the 556-matched subset.)
- **Suite:** 968 passed, 1 skipped (962 baseline + 6 new surface-mode guards) — all green.

**Blunt verdict:** the rebuild WORKS — causally clean, emits at k before the fill, and delivers the
rescued edge (1.18 durable / 1.35 sim) into a live-emittable form. The selection nuance (which
liquidity sweep is paired when several co-confirm the same MSS bar) is now RESOLVED by replaying
`run()`'s exact scan — full parity is 581/581 with sweep_ok on every signal; it was never look-ahead
and the causality verdict is unchanged. The one true unresolved gate remains **N≥30 live OTE-limit
fills** (out of scope, unchanged).

---

## 1. What was built

| File | Change |
|---|---|
| `surface_at_mss.py` (new) | `latest_mss_emission(feats, params, start_bar=None)` — realtime emit: on the rolling buffer whose last row is the just-closed bar, detect a Profile-A OTE setup whose MSS confirms on THAT bar and return its resting-limit entry/stop/target. Delegates detection to frozen `model01._detect`; copies run()'s fixed_rr entry/stop/target + risk guards + ny_am session filter (matching how the 581 were selected in `classify_signals.py:94`). **Sweep pairing replays run()'s sequential scan** — `_anchor_from_run` reads the no-overlap free bar from the frozen `run()` trade timeline and `_reject_jump` advances past earlier setups with run()'s verbatim reject-jumps (lines 229-250), so it pairs run()'s sweep for all 581. Also `scan_all_mss_emissions` (offline image of the stream). |
| `strategy_engine_profileA.py` | Added `EMISSION_MODE_SURFACE_AT_MSS` + `_latest_signal_surface_mss()`. `latest_signal()` gains ONE early-return guard at the top; every non-surface mode falls through to the **byte-identical** certified_gate / emit_at_fill path. Lazy import of `surface_at_mss` — never touched on the default path. Fail-closed on detection error; broken emit-bar instant escapes via the existing `_derive_fill_instant` invariant. |
| `test_surface_at_mss_canary.py` (new) | 6 regression guards (default never routes to surface; surface emits at mss bar; dedup; no-setup→None; warmup guard; detection-error→fail-closed). |
| `research/fork_a/build_surface_mss_verify.py` (new) | Real-Databento canary/parity harness driving the BUILT realtime path on data truncated at each signal's mss_bar. |

The emission is inert unless an operator constructs
`ProfileAEngine(..., emission_mode="surface_at_mss")`. No live call site passes it.

## 2. OWN CANARY — causally clean, emit-at-k (DECISIVE gate)

Method: for each certified signal, build the **realtime engine's own** feature frame
(`ProfileAEngine._features()`) on the raw 5m buffer **truncated at the mss_bar close**
(`ts ≤ mss_bar`, so `n = mss_bar+1`) and call the surface_at_mss emit. Any look-ahead in feature
construction or detection would surface as a changed/absent emission.

- Every verified signal **emits on the last bar of the truncated buffer**, i.e. at **k = mss_bar**
  (`emit_is_k` true for all), using only bars ≤ mss_bar. `mss_before_fill` (fill_bar > mss_bar)
  holds for all — the resting limit is live ≥1 bar (≥5 min) before every historical fill.
- **No BUILD-REVEALED-LOOKAHEAD.** Entry/stop/target/direction recomputed from ≤mss data match the
  full-history certified values to the cent.

### The k-vs-k+1 realtime finding (the key uncertainty — resolved)

The MSS confirms on bar k's **own close** (`_detect`'s `for k: if c[k] > opp: mss_bar=k; break`) —
no k+1 confirmation candle is needed for the MSS itself. But there is a real streaming subtlety in
the *scan reach*:

- **`model01.run(realtime=True)`'s outer loop is `while i < n-2`.** For the 77% of setups with
  sweep→mss gap==1 (sweep bar `i = mss_bar-1`), that guard cannot reach the sweep bar until the
  buffer contains bar `mss_bar+1` — so **naively reusing run() would emit gap==1 setups at k+1**,
  not k. And 184 of those gap==1 setups fill on the very next bar (`fill_bar == mss_bar+1`): at k+1
  the limit would be placed on the bar it needed to fill on → **too late, unfillable** (≈ +29.7R of
  edge lost, PF would fall from 1.35 to ~1.33).
- **The BUILT scanner avoids this.** It calls the frozen `_detect(i)` directly on the buffer ending
  at `mss_bar` (it is not bound by run()'s right-edge margin), so it reaches `i = mss_bar-1` at
  `n = mss_bar+1` and emits at **k for every gap**. The canary proves this is causally valid: the
  identical entry/stop/target is reproduced from data that physically excludes every bar > mss_bar
  (the `-2` margin in run() is a conservative edge guard, not a causality requirement for the
  already-confirmed opposing swing / frozen impulse leg this setup uses).

### run()-vs-new-scan emit contrast (proves the build is necessary, not cosmetic)

For sampled signals, on a buffer truncated at the mss_bar the certified path
(`model01.run(realtime=True)`, ny_am-filtered) surfaces the trade **never** (it reserves it as a
pending setup and only materialises it at/after the fill bar — the ~44-min lag that made the live
resting limit unfillable). The new scan surfaces it at k. For gap==1 / fill==mss_bar+1 signals the
certified path does **not** surface it even at the fill bar. This is the mechanism Fork A predicted,
now demonstrated in the BUILT code.

## 3. Parity vs certified 581 — and the benign no-overlap finding

Two distinct questions: (a) does the emission **math** reproduce the certified values, and (b) does
the realtime **selection** pick the same sweep `run()` recorded.

**(a) Emission math — 581/581 EXACT.** Forcing the scan to the certified sweep bar and applying the
built entry/stop/target/direction formulas reproduces every one of the 581 to the cent
(`refsweep_reproducible = 581/581`). There is no arithmetic error and no post-MSS dependency; this is
the same result Fork A's verify harness got, now reproduced through the *engine's* code path.

**(b) Realtime selection — 581/581 (FIXED 2026-07-13; was 556 stateless / 568 no-overlap).** When
several liquidity sweeps co-confirm the SAME MSS bar, which one `run()` records depends on its
sequential scan. The evolution of the fix:

| Selection rule | Match vs 581 | PF (matched) | sumR |
|---|---|---|---|
| stateless (first sweep with MSS==last in the W_MSS window) — original build | 556 (95.7%) | 1.2965 | 72.27 |
| no-overlap flat-since only (`start_bar`, ascending-first) | 568 (97.8%) | 1.3036 | 75.12 |
| **run()-scan replay (free bar + reject-jumps) — current** | **581 (100%)** | **1.3507** | **86.78** |

**Root cause and the fix.** `model01.run()` pairs a sweep with an MSS by a *sequential* scan: it
resumes at the no-overlap free bar (one past the last taken trade's realized exit) and then advances
`i` past EARLIER setups with its own reject-jumps (`i = mss_bar+1` when the FVG never fills within
`W_FILL`; `i = fill+1` when the stop is degenerate or > 1.2% of price). The original stateless scan
("first sweep whose MSS==last") ignored both, so on 25/581 it locked onto an EARLIER phantom sweep
`run()` had actually skipped — a different impulse leg → wrong entry/target (e.g. A-0029 entry off
34.7pt). Threading the flat-since free bar alone recovered 12 (the clean no-overlap cases); the other
13 needed the reject-jumps (a rejected setup right before the true sweep jumps `run()`'s `i` past the
phantom). The scanner now **replays `run()`'s scan exactly**: `_anchor_from_run` reads the free bar
from the frozen `run()` trade timeline, and `latest_mss_emission` marches from there applying
`run()`'s verbatim reject-jumps until the first sweep whose MSS confirms at `last` — which IS `run()`'s
pick. This is fully **causal** (every completed prior trade exits strictly before `last`; the current
setup's fill is after `last`, so `run(realtime=True)` reserves it and it is never consulted) and
preserves **emit-at-k** (the march stops AT the MSS-at-`last` detection and emits, never waiting for
the fill). The only active reject-jumps for the Profile-A config are the fill-window and the two risk
guards (all other gates — tier/first-presented/smt/daily-fvg/wdraw/dbias/pd/liquidity-target/
require-draw — are off), so the replay is a small verbatim copy of `run()` lines 229-250, not a fork
of the detection math.

## 4. Honest fillable PF (BUILT path, actual emit bar = k)

Emit-at-k rests the OTE limit at the mss_bar close, so the first fillable bar is `mss_bar+1` — the
**same** bar `model01.run()`'s own fill loop starts at (`range(mss_bar+1, …)`). The BUILT path
therefore fills at the identical historical fill bars, and the certified 8-tick-honest, 1m-truth
`R` stream **is** the fillable stream for the emitted signals:

- **Matched population (581/581 after the parity fix): PF 1.3507, +86.78R, WR 44.8%.** The built path
  now reproduces the full certified stream end-to-end, so its fillable PF equals the selection-perfected
  ceiling. (Pre-fix: 1.2965/+72.27R on the 556 matched; 1.3036/+75.12R on the 568 no-overlap subset.)
- The real emit-bar timing (k) does **not** erode the edge. The k+1 counterfactual (naive `run()`
  reuse) would be the real eroder — losing the gap==1/fill==mss+1 fills — and the build specifically
  avoids it by emitting at k (confirmed: `all_emit_at_k = true` on all 581).

**Durability (from the Fork A verifier, reports/fork_a/02):** the 1.35 is the honest *sim ceiling*,
not a live claim. In-sample (2021-24) PF ≈ **1.18** (the conservative planning number); holdout
(2025-26H1) 1.77 is a 64-trade wide-stop DELAYED pocket that may mean-revert. Fill-fragility stands:
dropping 10/20/30% of limit "touches" that don't fill live → PF 1.22 / 1.08 / 0.94. **The build does
not change this** — it delivers the sim edge into a live-emittable form; the N≥30 live-fill proof
remains the decisive out-of-scope arming gate.

## 5. A-unaffected + suite

- **Default-off is byte-identical.** The only edit to `latest_signal()` is one early-return guard for
  the surface mode; for `certified_gate`/`emit_at_fill` the guard is skipped and the original code
  runs unchanged (`git show` confirms the diff is purely additive above the original body). The
  surface module is lazy-imported only inside the surface branch.
- **Full suite green: 968 passed, 1 skipped** (`python3 -m pytest -q`, re-run after the parity fix;
  962 pre-existing tests unchanged + 6 surface-mode canaries). The 962 originals exercise only the
  certified path and stay green → A-detection parity is preserved and default-off behaviour is unchanged.

## BLOCKED / out of scope (unchanged from Fork A)

- **N≥30 live OTE-limit fills** — the decisive fill-quality proof. Not buildable offline.
- **Live config note (flagged, not fixed):** the certified 581 were built at `slip_ticks=8`; the live
  `PROFILE_A` dict uses the default `slip_ticks=2` (a pre-existing repo choice shared by the existing
  certified_gate path, not introduced here). The surface algorithm is parametrised identically; this
  slip delta should be reconciled before any arming, but it is orthogonal to the emission rebuild.
- **No-overlap / one-position gating** is enforced by the bot (position guard + `acted_ts`), not by
  the emit scan; the raw surface stream can propose a setup while a prior limit still rests — the bot
  suppresses it, exactly as today.
- **Flat-since threading — RESOLVED 2026-07-13.** Realtime-selection parity is now 581/581 with no
  caller state required: `latest_mss_emission` self-derives the no-overlap free bar from the frozen
  `run()` trade timeline (`_anchor_from_run`) and replays `run()`'s reject-jumps. The `start_bar`
  argument is retained as an optional fast-path override (the live bot may pass its real flat-since
  bar, and the `fast_parity` harness precomputes it), but is no longer needed for correctness.

**Nothing armed. Nothing pushed. Branch `model01-surface-mss` only.**

---
Artifacts: `surface_at_mss.py`, `strategy_engine_profileA.py` (mode wiring),
`test_surface_at_mss_canary.py`; harnesses `research/fork_a/{build_surface_mss_verify,fast_parity,
optimized_parity}.py`; data `reports/fork_a/03_*.{csv,json}`.
