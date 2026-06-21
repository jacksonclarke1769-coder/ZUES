"""EXITFORGE Phase 7 — exit-model parity check. Proves the live Exit #3 split payload
resolves to the integer two-leg P&L, NOT the single-target full-qty figure. Run:
    python3 tools/check_exit3_parity.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import trade_results as TR
import bridge_traderspost as BP

E, S, T, QTY = 30654.83, 30771.50, 30421.49, 3           # the reported $1,400 short

single_target = TR.pnl_from_r(2.0, E, S, QTY)            # full 3 @ +2R (legacy live)
exit3_integer = TR.pnl_exit3(E, S, QTY)                  # 1@1R + 2@2R (official)
exit3_fraction = TR.pnl_from_r(1.5, E, S, QTY)           # 1.5/1.5 (backtest fractional)

# what the LIVE split payload actually resolves to on a full win (sum of both legs)
legs, err = BP.build_entry_exit3(account="MFFU-50K-1", strategy="A", setup="sweep-OTE",
                                 signal_ts="t", side="short", qty=QTY, entry=E, stop=S, target=T)
assert err is None, err
live_payload_fullwin = sum(TR.pnl_from_r(L["r_target"], E, S, L["qty"]) for L in legs)

print("=== EXIT-MODEL PARITY (the $1,400 trade) ===")
print(f"  single-target full-qty @ 2R (LEGACY)      : ${single_target:+,.0f}")
print(f"  Exit #3 integer 1@1R+2@2R (OFFICIAL)       : ${exit3_integer:+,.0f}")
print(f"  Exit #3 fractional 1.5/1.5 (backtest)      : ${exit3_fraction:+,.0f}")
print(f"  LIVE split payload full-win (sum of legs)  : ${live_payload_fullwin:+,.0f}")
print()
ok_live = abs(live_payload_fullwin - exit3_integer) < 0.5
ok_split = abs(single_target - exit3_integer) > 0.5
print(f"  live payload == Exit #3 integer ? {'PASS' if ok_live else 'FAIL'}")
print(f"  live payload != single-target  ? {'PASS' if ok_split else 'FAIL'}")
print(f"\n  legs: " + ", ".join(f"{L['role']}={L['qty']}@{L['r_target']}R(${TR.pnl_from_r(L['r_target'],E,S,L['qty']):+,.0f})" for L in legs))
sys.exit(0 if (ok_live and ok_split) else 1)
