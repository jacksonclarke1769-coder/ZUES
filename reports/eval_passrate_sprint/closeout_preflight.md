# Sprint Closeout — Preflight Integrity Check (2026-07-05)

Command run: `bash gate.sh` (full 843-test suite + funded firewall named tests + eval firewall +
`shasum -c` on config_eval_locked.py / config_defaults.py / auto_safety.py), plus
`shasum -a 256 config_funded_locked.py` diffed against the pre-sprint recording, plus
`git status --short` tracked-modification scan.

| Check | Result |
|---|---|
| Full suite + gate | **GREEN** (== gate.sh: ALL CHECKS GREEN ==) |
| Funded firewall | GREEN (named tests pass) |
| Funded hash pre vs post sprint | **byte-identical** (`95276d50…3acbe4`) |
| Live machine files modified | **NONE** (zero tracked files modified; working tree = new research/report files only) |
| Expected artifacts present | 20 report files in reports/eval_passrate_sprint/ + 12 in reports/asia_london_extra_lane/ + 4 vault drafts |

Unexpected modified files: none. Auditor escalation: none required. **PREFLIGHT: PASS.**
