# Fork-A Independent Adversarial Cross-Audit — surface-at-MSS emission

Auditor: independent cross-auditor (read-only, no code/main touched). Branch `model01-surface-mss` @ `1b52906`.
Mandate: REFUTE the "581/581 causally-clean" claim. New artifacts (this branch, read-only):
`research/fork_a/causal_anchor_parity.py`, `reports/fork_a/04_causal_anchor_parity.{csv,json}`, this file.

## TOP-LINE VERDICT: CAUSALLY-CLEAN-CONFIRMED

The primary defect I set out to exploit — that the headline 581/581 (`fast_parity.py:59`) feeds a
**full-frame-derived** anchor `start_bar=free_by_mss.get(mss_bar)` (built at `fast_parity.py:45-49`
from `M1.run(feats,...)` over the UN-truncated frame) and thereby BYPASSES the new causal
`_anchor_from_run()` — is real as a *test-methodology* gap, but it does **not** change the result.
I re-ran the parity through the truly-causal internal path (`start_bar=None`, forcing
`_anchor_from_run` to compute the anchor from the truncated slice `feats.iloc[:mss_bar+1]`) for all
581 certified Profile-A signals. It reproduces the headline exactly, and the emissions are
byte-identical to the override path.

## PRIMARY TASK — causal-anchor parity (start_bar=None), ALL 581

`research/fork_a/causal_anchor_parity.py` calls
`surface_at_mss.latest_mss_emission(feats.iloc[:mss_bar+1], PARAMS, start_bar=None)` per signal.
Result (`reports/fork_a/04_causal_anchor_parity_summary.json`):

| metric | causal path (start_bar=None) | claimed override (03_fast_parity) |
|---|---|---|
| n | 581 | 581 |
| match_at_k | **581** | 581 |
| mismatch | **0** | 0 |
| no_emit | **0** | 0 |
| all_emit_at_k | **true** | true |
| sweep_match | **581** | 581 |
| gap1 / gap≥2 matched | 446 / 135 | 446 / 135 |
| honest_fill PF / sumR / WR | 1.3507 / 86.779 / 0.4475 | 1.3507 / 86.779 / 0.4475 |

Cross-check of the per-signal emission columns (causal CSV vs `03_fast_parity.csv`):
`max |Δentry|+|Δstop|+|Δtarget| = 0.0` across all 581; 0 signals differ. The full-frame override
anchor and the truncated-slice `_anchor_from_run` yield the **same** free bar and the **same** paired
sweep for every certified signal. The override was a speed shortcut, not a correctness crutch: the
production/live path (which uses `start_bar=None`) independently reproduces the certified result.

**This is the decisive finding**: the live engine calls the causal path, and the causal path is
581/581. The rescue is NOT dependent on the full-frame anchor.

## PER-ITEM ADVERSARIAL FINDINGS

**1. Causality of `_anchor_from_run` — PASS (structurally airtight).**
`surface_at_mss.py:143` calls `M1.run(feats, "NQ", params, realtime=True)` where `feats` is the
caller's slice. On the parity/live path the slice is `feats.iloc[:mss_bar+1]`, a frame that
*physically contains no bar with index > mss_bar* — `run()` cannot index past the array it is given,
so no post-MSS read is possible even in principle. The detection math it drives (`_detect`,
model01 lines 375-442) reads only `l[max(0,i-2):i+1]`, `sh_at[i]/sl_at[i]` (line 401), `c[k]` for
`k∈[i+1,mss_bar]` (406-408), `h[i:mss_bar+1]`/`l[i:mss_bar+1]` (417), and `fdir[j]/fmid[j]` for
`j∈[i,mss_bar]` (420-422) — every index ≤ mss_bar. The emission formulas
(`surface_at_mss.py:103-110`: entry `ez + d*SLIP`, stop `sweep_px ± BUFFER`, target
`entry + d*rr*risk`) consume only `ez`, `sweep_px` from that setup. No value in the emission depends
on a bar > mss_bar.

**2. emit-at-k (not k+1) — PASS.** `all_emit_at_k = true`; `k_ok` sum = 581/581 on the causal path
(446 of them gap==1, the exact class run()'s `while i < n-2` right-edge guard would have pushed to
k+1). The surface scanner does NOT reuse run()'s loop for the emit: `latest_mss_emission` runs its
own `while i < last` scan (`surface_at_mss.py:214`) and returns as soon as `setup[5]==last`
(`mss_bar == last`, line 223), so it can and does fire on the MSS bar itself.

**3. DEFAULT-OFF byte-identity — PASS.** `git diff 645c05a~1 645c05a -- strategy_engine_profileA.py`
is purely additive: (a) a new constant `EMISSION_MODE_SURFACE_AT_MSS` added to the `EMISSION_MODES`
set; (b) a new private method `_latest_signal_surface_mss`; (c) a single guard at the top of
`latest_signal()` — `if self.emission_mode == EMISSION_MODE_SURFACE_AT_MSS: return
self._latest_signal_surface_mss()`. No existing line of the default `certified_gate` path is
modified or deleted; when the mode is not surface, the guard is a no-op and control falls through to
the unchanged certified logic. The surface method is fail-closed (warmup guard, `try/except ->
None`, `acted_ts` dedup, `ts > buf.max()` causal net) and lazily imports `surface_at_mss` so the
default path never even imports it. Enforced permanently by
`test_surface_at_mss_canary.py::test_default_mode_never_calls_surface`.

**4. SUITE — PASS (matches claim).** `python3 -m pytest -q` → **968 passed, 1 skipped**, 3 warnings,
165s (I ran it). `test_surface_at_mss_canary.py` → 6 passed. Caveat (not a defect): the canary
tests **mock** `latest_mss_emission`, so they exercise only delivery plumbing (routing, dedup,
warmup, fail-closed) — they provide ZERO validation of the detection math or the causal anchor. That
validation lived only in the 20-signal own-canary until this audit extended it to all 581.

**5. honest_fill arithmetic — PASS (recomputed independently).** From the per-signal `R` column of
`03_fast_parity.csv`: winners 260, losers 321, gross win 334.233R, gross loss 247.454R →
PF = 334.233/247.454 = **1.3507**, sumR = **86.779**, WR = 260/581 = **0.4475**. Exact match to the
summary JSON. Caveat: this PF is the certified 1m-truth R stream of the matched population — it
measures the edge of the signal set *assuming fills occur at the certified levels*; it is not an
independent re-simulation of whether the earlier resting limit fills. The emission parity proves the
order is causally final at k; the fill-timing rescue rests on the class analysis, not this number.

**6. The look-ahead trap (run() pairing on a future exit) — CLOSED.** The concern: run()'s sweep
pick for the setup at `last` could depend on the CURRENT trade's realized `exit_bar` (future), so
matching it would match a look-ahead. It does not. run()'s no-overlap chain resumes at
`i = exit_i + 1` (model01:324) of the PRIOR trade; for every certified signal the prior trade must
have exited strictly before this signal's `sweep_bar (≤ mss_bar)` — otherwise no-overlap would have
skipped the signal entirely and it would not be in the certified set. Hence on `feats.iloc[:mss_bar+1]`
every prior trade completes before `last`, and `run(realtime=True)` RESERVES the current setup (the
`realtime` breaks at model01:194-197 / 240-241) instead of completing it, so the current trade's
future exit is never used to pick its own sweep. `_reject_jump` (surface:149-177) advances only on
earlier setups using their own fill/risk at bars ≤ their fill ≤ last. **Empirical proof**: the
`start_bar=None` path — which derives the anchor purely from the reserved-slice run — returns
`sweep_match = 581/581` and byte-identical emissions. The pairing carries no future information.

## Bottom line
Every refutation angle failed. The `581/581 causally-clean` claim survives independent
reconstruction on the production (start_bar=None) path. The one legitimate criticism — that the
headline test used a full-frame anchor shortcut — is now retired: the causal path gives the identical
581/581 with 0.0 emission delta. Emission causality is confirmed. (The residual, out-of-scope
caveat is fill *realization*, item 5 — the honest_fill PF assumes certified fills; it is an edge
statistic of the signal set, not proof the earlier limit fills. Arming still depends on that
fill-timing evidence, which is the class analysis in reports/fork_a/01-02, not this emission audit.)
