# FORK A — PHASE 3 BUILD: surface-at-MSS emission for Profile A

**Branch:** `model01-surface-mss` (bot repo). **Status:** BUILT + verified, DEFAULT-OFF, NOT armed,
NOT pushed. **Date:** 2026-07-13.
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
- **Realtime-selection parity: 556/581 stateless → 568/581** when the bot's flat-since bar is threaded
  (the no-overlap rule). Residual 13 (2.2%) are multi-sweep co-confirmation ordering differences vs
  `run()`'s backtest loop — causally clean, benign.
- **Honest fillable PF (BUILT path, emit-at-k):** 1.30 on the reproduced population (568, no-overlap;
  1.2965 stateless), vs the 1.35 selection-perfected sim ceiling; durable **IS ≈ 1.18** unchanged.
- **Suite:** 968 passed, 1 skipped (962 baseline + 6 new surface-mode guards) — all green.

**Blunt verdict:** the rebuild WORKS — causally clean, emits at k before the fill, and delivers the
rescued edge (1.18 durable / ~1.30–1.35 sim) into a live-emittable form. The build revealed a benign
selection nuance (which liquidity sweep is paired when several co-confirm the same MSS bar), fixable
by threading the bot's flat-since bar; it is not look-ahead and does not change the causality verdict.
The one true unresolved gate remains **N≥30 live OTE-limit fills** (out of scope, unchanged).

---

## 1. What was built

| File | Change |
|---|---|
| `surface_at_mss.py` (new) | `latest_mss_emission(feats, params)` — realtime emit: on the rolling buffer whose last row is the just-closed bar, detect a Profile-A OTE setup whose MSS confirms on THAT bar and return its resting-limit entry/stop/target. Delegates detection to frozen `model01._detect`; copies run()'s fixed_rr entry/stop/target + risk guards + ny_am session filter (matching how the 581 were selected in `classify_signals.py:94`). Also `scan_all_mss_emissions` (offline image of the stream). |
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

**(b) Realtime selection — 556/581 stateless, 568/581 no-overlap.** When several liquidity sweeps
co-confirm the SAME MSS bar, which one gets emitted depends on scan ordering:

| Selection rule | Match vs 581 | PF (matched) | sumR |
|---|---|---|---|
| stateless (scan whole W_MSS window, first sweep with MSS==last) — current default | **556** (95.7%) | 1.2965 | 72.27 |
| no-overlap (scan from the bot's flat-since bar = `start_bar`) | **568** (97.8%) | 1.3036 | 75.12 |
| selection-perfected ceiling (certified stream, all 581) | 581 | 1.3507 | 86.78 |

**Why the gap, and why it is benign.** `model01.run()` pairs a sweep with an MSS via its ascending
scan **plus no-overlap** — it advances `i` past each taken trade's *realized exit bar*, so it never
evaluates sweeps that fell inside a prior open position. That exit bar is FUTURE information relative
to the MSS instant, so **no realtime emitter can reproduce run()'s pairing from price alone.** The
fix that IS realtime-valid: pass the bar the bot became FLAT (one past its last position's exit — a
PAST fact the bot knows) as `start_bar`. That recovers 12 of the 25 divergences (556→568). The
residual 13 (2.2%, gaps mostly ==1) are finer ordering interactions with run()'s reject-and-jump
sequence; reproducing them exactly would require mirroring run()'s full loop and is not worth the
coupling. Every divergence is a *different valid Profile-A OTE setup at the same bar* (correct
direction, causally clean, emit-at-k) — a choice of which liquidity level's OTE to rest, **not** a
look-ahead or a phantom. `latest_mss_emission` now accepts `start_bar` so the live bot can thread its
flat-since bar; default (stateless) is the conservative 556-parity behaviour.

## 4. Honest fillable PF (BUILT path, actual emit bar = k)

Emit-at-k rests the OTE limit at the mss_bar close, so the first fillable bar is `mss_bar+1` — the
**same** bar `model01.run()`'s own fill loop starts at (`range(mss_bar+1, …)`). The BUILT path
therefore fills at the identical historical fill bars, and the certified 8-tick-honest, 1m-truth
`R` stream **is** the fillable stream for the emitted signals:

- **Reproduced population (no-overlap, 568 signals): PF 1.3036, +75.12R.** Stateless (556): PF 1.2965,
  +72.27R. Selection-perfected ceiling (all 581): PF **1.3507**, +86.78R.
- The real emit-bar timing (k) does **not** erode the edge — the erosion vs 1.35 is the ~2–4% of
  signals where the built path emits a *different* (unscored-here) valid setup, not a lost or degraded
  fill. The k+1 counterfactual (naive `run()` reuse) would be the real eroder — losing the 184
  gap==1/fill==mss+1 fills — and the build specifically avoids it by emitting at k.

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
- **Full suite green: 968 passed, 1 skipped** (`python3 -m pytest -q`; 962 pre-existing tests
  unchanged + 6 new surface-mode canaries). The 962 originals exercise only the certified path and
  stay green → A-detection parity is preserved and default-off behaviour is unchanged.

## BLOCKED / out of scope (unchanged from Fork A)

- **N≥30 live OTE-limit fills** — the decisive fill-quality proof. Not buildable offline.
- **Live config note (flagged, not fixed):** the certified 581 were built at `slip_ticks=8`; the live
  `PROFILE_A` dict uses the default `slip_ticks=2` (a pre-existing repo choice shared by the existing
  certified_gate path, not introduced here). The surface algorithm is parametrised identically; this
  slip delta should be reconciled before any arming, but it is orthogonal to the emission rebuild.
- **No-overlap / one-position gating** is enforced by the bot (position guard + `acted_ts`), not by
  the emit scan; the raw surface stream can propose a setup while a prior limit still rests — the bot
  suppresses it, exactly as today.
- **Flat-since threading (follow-up integration, not blocking):** to lift realtime-selection parity
  556→568/581, the bot should pass its flat-since bar as `latest_mss_emission(..., start_bar=…)`. The
  hook is built and defaults off (stateless). This is a benign selection improvement, not a causality
  or arming prerequisite.

**Nothing armed. Nothing pushed. Branch `model01-surface-mss` only.**

---
Artifacts: `surface_at_mss.py`, `strategy_engine_profileA.py` (mode wiring),
`test_surface_at_mss_canary.py`; harnesses `research/fork_a/{build_surface_mss_verify,fast_parity,
optimized_parity}.py`; data `reports/fork_a/03_*.{csv,json}`.
