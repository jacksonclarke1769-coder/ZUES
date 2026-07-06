# D1c Attachment Timestamp Look-Ahead — Honest Stream Regeneration

INC-20260706-1141. Regenerated via the standard pipeline: `tools_1m_truth_recert.A_PARAMS["exit3"]`
model params, `strategy_engine_profileA.ProfileAEngine._features()` (full real Databento history via
`apex_eval_eod_databento.load_databento_5m`), `model01_sweep_mss_fvg.run` (FROZEN, unchanged),
the FIXED `run_d1c_real.attach_drift(tr, d1_tz, feats.index)`, and the 1m-truth re-fill
(`tools_1m_truth_recert.walk_1m`, F1-fixed convention). This mirrors
`tools_phase3_config_sweep.a_streams_d1c()["exit3"]` exactly, extended to capture every
field the incident requires (both KEPT and DROPPED rows, `drift_sign`, `eval_ts`).

Data: real Databento NQ 1m, 2021-06-22 20:00 ET -> 2026-06-22 19:59 ET (260.7 weeks).

Outputs: `honest_d1c_stream.csv` (705 rows, one per detected `ny_am` exit3 signal — `ts,
direction, entry, stop, target, risk_usd, R, mae_r, kept, drift_sign, eval_ts`; `R`/`mae_r`
are populated only for `kept=True` rows, i.e. D1c-kept AND 1m-truth-filled) and
`honest_d1c_stream_summary.json` (all tables below, machine-readable).

## Totals

| Metric | Value |
|---|---|
| Total detected `ny_am` exit3 signals | 705 |
| Kept (D1c-agrees AND 1m-truth-filled) | 583 |
| Keep rate | 82.7% |
| WR (kept) | 44.9% |
| PF (kept) | **1.361** |
| expR (kept) | 0.153 |
| netR (kept) | **+89.2R** |
| Trades/week (kept) | 2.236 |
| Trades/week (unfiltered, all 705 fillable) | 2.704 |

**This matches the auditor's hand-verified reference exactly**: kept 583/705 (82.7%),
PF 1.361, WR 44.9%, netR +89.2R, at fill-bar-time evaluation. No delta to explain.

## Comparison rows

| Stream | n | keep-rate | PF | WR | netR | Status |
|---|---|---|---|---|---|---|
| Unfiltered A (no D1c) | 705 | 100% | **1.237** | 42.8% | +74.7R | reference (survives — `tools_1m_truth_recert.a_streams`, never called `attach_drift`) |
| Honest D1c (this report, FIXED attach_drift) | 583 | 82.7% | **1.361** | 44.9% | +89.2R | **NEW — this is the corrected number** |
| Defective D1c (pre-fix, lookahead) | ~413 (58.6% of 705) | 58.6% | **2.31** | ~58.6%* | n/a | **INVALIDATED-LOOKAHEAD** — see `04_invalidated_numbers.md` items 3-4; not recomputed here, cited as already established by the incident/vault record |

\* the pre-fix "58.6%" figure in the vault is documented as a WR benchmark at the
certified (contaminated) config, not the keep-rate; both the PF 2.31 and WR 58.6% numbers
for the defective stream are carried forward as-is from `04_invalidated_numbers.md` items
3-4, not re-derived by this task (recomputing the poisoned path was out of scope; the
canary report (`02_timestamp_canary.md`) proves the divergence mechanism directly instead).

**Sanity check**: honest D1c (PF 1.361) is modestly better than unfiltered A (PF 1.237) —
the drift gate cuts real edge, not artifact. Not >1.8 — no STOP triggered.

## Per-year (kept/honest)

| Year | n | PF | WR | totR |
|---|---|---|---|---|
| 2021 | 70 | 1.512 | 42.9% | +13.3R |
| 2022 | 113 | 1.072 | 40.7% | +3.8R |
| 2023 | 118 | 1.326 | 47.5% | +17.3R |
| 2024 | 110 | 1.087 | 38.2% | +4.5R |
| 2025 | 118 | 1.881 | 51.7% | +37.3R |
| 2026 (partial, thru 2026-06-22) | 54 | 1.605 | 50.0% | +13.0R |

All 6 years net-positive; no single year carries the whole edge (2022/2024 are the
softest at PF ~1.07-1.09, still >1).

## Long/short split (kept)

| Side | n | PF | WR | totR |
|---|---|---|---|---|
| Long | 269 | 1.264 | 43.5% | +32.5R |
| Short | 314 | 1.456 | 46.2% | +56.7R |

Short carries more of the total edge (as in prior Profile A research), but both sides
are net-positive.

## Stop-distance bucket (kept, `risk = |entry - stop|` in points)

| Bucket | n | PF | WR | totR |
|---|---|---|---|---|
| <10pt | 15 | 0.229 | 13.3% | -10.1R |
| 10-20pt | 59 | 1.361 | 40.7% | +9.0R |
| 20-30pt | 108 | 1.520 | 43.5% | +24.1R |
| 30-50pt | 174 | 1.072 | 37.9% | +6.0R |
| >=50pt | 227 | 1.761 | 54.2% | +60.2R |

The <10pt bucket (n=15, PF 0.23) is the one clear weak spot — small sample, consistent
with prior research flagging tight-stop OTE entries as noise-prone; not large enough to
move the aggregate (-10.1R of +89.2R total).

## Time-of-day split (kept, true NY hour of `eval_ts`)

| Hour (ET) | n | PF | WR | totR |
|---|---|---|---|---|
| 09:00 | 195 | 1.189 | 40.0% | +16.5R |
| 10:00 | 307 | 1.576 | 48.5% | +70.1R |
| 11:00 | 78 | 1.001 | 42.3% | +0.0R |
| 12:00 | 3 | 6.371 | 66.7% | +2.5R |

10:00 ET is the engine (307 trades, +70.1R of +89.2R total, PF 1.58); 11:00 ET is flat
(PF ~1.0, breakeven) on a real 78-trade sample — consistent with prior "10:00-10:30 ET
engine / 11:00-11:30 dead" research finding cited elsewhere in project memory, now
confirmed on the CORRECTED (non-lookahead) stream too.

## Reproduction

```python
d1_tz = RD.load_1m()                                     # real Databento 1m, tz-aware NY
df5   = DB.load_databento_5m()                            # validated 5m pipeline
mp    = M1Map(d1_tz.tz_localize(None), df5)
feats = ProfileAEngine(config.STRAT, buf=df5)._features()
tr    = M1.run(feats, "NQ", A_PARAMS["exit3"])
tr    = tr[tr.session == "ny_am"]
tr    = RD.attach_drift(tr, d1_tz, feats.index)           # FIXED (INC-20260706-1141)
# per trade: if valid_bar and d1c_keep -> walk_1m(...) -> R, mae_r; kept = filled and d1c_keep
```
