# CONFIGLOCK — Version-Controlled Official Exit Model
_2026-06-21 · config safety fix · no live · suite 365→378 green_

## The problem
`config.py` (which held `EXIT_MODEL = "EXIT3_FIXED_PARTIAL"`) is **gitignored**, and `auto_live.py`
fell back to `getattr(config, "EXIT_MODEL", "SINGLE_TARGET")`. A fresh clone / future session with no
local config would silently route **SINGLE_TARGET** — reintroducing the exact mismatch EXITLOCK caught.
Same risk for `config.exit3_split` and the locally-corrected `trade_results.csv` ($1,400 row).

## 1. Files changed
| File | Change |
|---|---|
| **`config_defaults.py`** (NEW, committed) | `EXIT_MODEL`, `EXIT_MODEL_ALLOWED`, `EXIT_MODEL_RESEARCH_ONLY`, `EXECUTION_MODES`, and `exit3_split()` — the version-controlled source of truth (no secrets) |
| **`runtime_config.py`** (NEW, committed) | `resolve_exit_model(mode)` — committed default → optional local override → fail-closed validation |
| `auto_live.py` | uses `resolve_exit_model(self.mode)`; no more `"SINGLE_TARGET"` fallback; CONFIGLOCK error → fail-closed (no send) + ARGUS exitlock row |
| `bridge_traderspost.py` | `build_entry_exit3` uses `config_defaults.exit3_split` (was gitignored `config.exit3_split`) |
| `trade_results.py` | `is_realised(note)` classifier; `by_day` counts realised only if fill-backed; `record_resolved` marks modeled rows `fill_backed=False` |
| `tools/exit3_dryrun_proof.py`, `tools/exit3_paper_path_proof.py` | display via `resolve_exit_model` (no hard `config.EXIT_MODEL` dep) |
| `test_configlock.py` (NEW) | 13 tests |
| `test_trade_results.py` | updated: modeled rows are now hypothetical (intended) |

## 2. Where the official EXIT_MODEL now lives
**`config_defaults.py` (committed).** `config.py` may still override locally, but the safe default is
version-controlled and travels with every clone.

## 3. If `config.py` is missing → `EXIT3_FIXED_PARTIAL`
`resolve_exit_model` catches the import failure / missing attr / empty value and returns the committed
default. **A fresh clone resolves Exit #3, never single-target.** (Proven: `test_missing_exit_model_*`.)

## 4. If `config.py` says `SINGLE_TARGET` → **fail closed**
For `live`/`paper`/`controlled`, `resolve_exit_model` raises `ConfigLockError` ("CONFIGLOCK: unsafe exit
model blocked — 'SINGLE_TARGET' is research-only"). `auto_live` catches it, sends nothing, logs an ARGUS
exitlock row. SINGLE_TARGET is allowed ONLY in `research`/`test` mode (for comparison). (`test_single_target_blocked_for_live`, `test_single_target_allowed_in_research`.)

## 5. If `config.py` has an unknown model → **fail closed**
Any value not in `EXIT_MODEL_ALLOWED` raises `ConfigLockError` for execution. (`test_unknown_model_blocked_for_live`.)

## 6. Proof no live path defaults to single-target
`grep getattr.*EXIT_MODEL.*SINGLE_TARGET` over the live code → **none**. `test_no_single_target_fallback_in_live_code`
guards the source. `resolve_exit_model('paper')` prints `EXIT3_FIXED_PARTIAL`.

## 7. Dashboard/calendar synthetic-P&L protection (code-level, fresh-clone safe)
`trade_results.is_realised(note)`: a row is **realised only if its note proves a fill/resolution**
("fill-backed"/"broker fill"/…); modeled / pending / synthetic / "TP hit (gross)" / blank → **hypothetical**.
`by_day` sums realised vs hypothetical separately; `/api/calendar` consumes it. So even **without** the
locally-corrected CSV, the old +$1,400 synthetic row classifies as hypothetical → realised P&L $0.
(`test_synthetic_1400_row_is_hypothetical`, `test_modeled_rows_are_hypothetical`, `test_fill_backed_row_is_realised`.)

## 8. Emergency flatten never blocked
`resolve_exit_model` is only called on the entry-build path. Flatten/cancel never call it →
`test_flatten_not_blocked_by_unsafe_config` (build_flatten works with SINGLE_TARGET config active).

## 9. Test result
`test_configlock.py` **13/13** · **full suite 378 passed, 0 failed.** Dry-run + parity PASS.

## 10. Safe to push?
**Yes — after the commit below.** The repo now guarantees `EXIT3_FIXED_PARTIAL` on a fresh clone and
fails closed on any unsafe override. (Push still awaits operator go-ahead per the brief.)
