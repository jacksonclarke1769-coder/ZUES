# Re-Lock DEC + Funded Re-Run — Preflight (2026-07-06)

- Repo HEAD: caf7b443f237d552f83a4fc2c419ef4f80cc62cb (optimisation caf7b44, VPC audit e6766a8, discovery db33d4b, salvage 4bf64eb, D1c re-cert 818cda8)
- Vault: 8853c57 lineage · LIVE HOLD ACTIVE · go-live-recert.sh untouched (e739a3423f67…)
- Funded hash: 95276d506ec33330… · Eval lock: 3ca389fc5a8a9fe4…
- Tracked modifications: 0 (expect 0)
- latest_signal() defect: TICKETED, NOT FIXED (operator-gated; mandatory pre-arm)
- VPC exec-lane blockers: trail management (no order-modify path) / A-vs-VPC arbitration / trail-aware kill switch — NOT STARTED (07_vpc_execution_lane_requirements.md)
- Recommended eval row: A900/6+VPC600/3 = 37.4/18.0/44.6, flip 0.068R, f/slot 5.89
- Watch row: A900/6+VPC700/3 = 39.3/19.6/41.1, flip 0.076R, f/slot 6.37 (2025 share 47%)
- Env: pandas pinned <3 (INC-20260706-1627), canary in gate

## Gate
auto_safety.py: OK
== gate.sh: ALL CHECKS GREEN ==
