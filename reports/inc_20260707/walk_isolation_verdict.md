# INC-20260707 — 1m-truth walk isolation — VERDICT: CLEARED (re-cert on the 48 UNBLOCKED)
**Read-only isolation. No fix, no re-cert, no arming. LIVE HOLD ACTIVE.** The question: is the analysis script's broken 1m-truth walk (PF 0.05) the SAME code the certified pipeline uses?

## Step 1 — provenance of both walkers
- **Analysis 1m-truth column**: `analysis_inc0707_missing.py:160-172` `r_1mtruth()` → calls `tools_1m_truth_recert.walk_1m(mp, pos, d, entry, stop, target, partials, ...)` (line 171). `pos` is derived by a **timestamp lookup** `idx5.get_indexer([ets])` / `np.searchsorted(idx5.values, ets.to_datetime64())` (lines 162-164). `mp`/`df5` from `T1M.load_frames()`; but the **trades** (entry/stop/target, fill_instant) come from `htf.build_features("NQ","5m")` — a DIFFERENT frame.
- **Certified re-cert walker**: `tools_1m_truth_recert.a_streams(feats, mp, df5)` (line 117) → `fb = int(t.fill_bar)` (line 128) → `walk_1m(mp, fb, ...)` (line 135). Trades come from `feats`, `mp = M1Map(d1, df5)` — **feats, d1, df5 all from the same `T1M.load_frames()`**. Integer `fill_bar` passed POSITIONALLY — no timestamp lookup, no `to_datetime64`.

## Step 2 — call-graph diff: SHARED FUNCTION, SEPARATE DEFECT
- **Shared node**: `tools_1m_truth_recert.walk_1m` (both call it) and `M1Map`.
- **Disjoint nodes (where they diverge — and where the bug lives)**:
  - Trade *source* frame: analysis = `htf.build_features` (**Dukascopy**, `data/nq/NQ_5m_24h_full.parquet`); certified = `T1M.load_frames` (**Databento**, `NQ_databento_1m_5y.parquet`). **These are different vendors.**
  - Walk *data* frame: analysis walks on Databento (`load_frames`) while its trades were priced on Dukascopy; certified walks on Databento with Databento-priced trades — **single vendor, consistent.**
  - Fill-position derivation: analysis = tz-fragile timestamp lookup; certified = positional integer `fill_bar`.

## Step 3 — ROOT CAUSE (one sentence) + present/absent check
**Root cause:** the analysis script feeds `walk_1m` cross-vendor inputs — trade entry/stop/target priced on Dukascopy (~24596) walked against Databento 1m bars (~24837, a ~241-point basis gap at the same instant) — so the resting limits can't fill (NaN) or resolve as instant stops (−1R), producing PF 0.05; the shared `walk_1m` is faithfully reporting that Dukascopy-priced orders don't fill in Databento bars, it is NOT itself defective.
**Present in the certified walker? ABSENT.** `a_streams` generates AND walks on a single vendor (Databento `load_frames`) using the positional integer `fill_bar` — no vendor mix, no timestamp lookup. Both sub-causes (cross-vendor anchoring + tz-fragile lookup) are structurally absent from the certified path. Verified by reading `a_streams` (line 117-135) and the frame provenance (both = `load_frames`).

## Step 4 — VERDICT: **CLEARED**
The walker FUNCTION is shared, but the DEFECT is not — it lives entirely in the analysis script's Step-3 addition (mixing a Databento 1m-truth walk onto Dukascopy-generated trades). The certified honest stream (PF 1.237/1.361, `tools_sim_parity_check.load_rows`) and the eval/funded sims are all-Databento-consistent and use positional `fill_bar`; they are NOT affected. This is NOT a fifth defect class. **The re-cert on the 48 (through the certified Databento pipeline) is UNBLOCKED.** Discard the analysis script's `r_1mtruth` column.

## Caveats for the re-cert follow-up (NOT blockers, NOT this task)
1. The "48 live-achievable" set was identified in the DUKASCOPY parity world (`test_signal_parity` drives the engine on Dukascopy `load_spine`). The certified re-cert runs on Databento. So the re-cert must **re-measure the freshness-gate emission gap on the certified Databento data** to identify the Databento-native live-achievable subset — do NOT assume the exact same 48 keys transfer across vendors.
2. `analysis_inc0707_missing.py`'s `r_1mtruth` column should be fixed (walk on the same vendor it generates trades from) or the column deleted, before the script is reused.
3. The partition (0 recoverable / 23 irreducible) is UNAFFECTED — it used timestamp arithmetic internal to the Dukascopy parity world, not the cross-vendor walk.
