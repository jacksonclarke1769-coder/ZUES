"""W9 — Evidence Locker. Tamper-evident filing for payout reviews and disputes.

Structure (evidence/):
    mffu/ topstep/ payouts/ approvals/ signals/ fills/ reconciliations/ incidents/
    journal-snapshots/   (dated journal.db copies)
    MANIFEST.txt         (hash chain: each line commits to the previous line)

Tamper evidence: every filed artifact appends a manifest line
    seq | utc | category/name | sha256(file) | sha256(prev_line)
Any later modification of a filed artifact or of the manifest itself breaks the chain
and is detected by verify(). The manifest is append-only by convention AND should be
synced off-box hourly (HEIMDALL ops procedure).
"""
import hashlib
import os
import shutil
from datetime import datetime, timezone

CATEGORIES = ("mffu", "topstep", "payouts", "approvals", "signals", "fills",
              "reconciliations", "incidents", "journal-snapshots")


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class Locker:
    def __init__(self, root="evidence"):
        self.root = root
        for c in CATEGORIES:
            os.makedirs(os.path.join(root, c), exist_ok=True)
        self.manifest = os.path.join(root, "MANIFEST.txt")

    # ---------------- filing ----------------

    def file(self, category, src_path, name=None):
        """Copy an artifact into the locker and chain it into the manifest."""
        if category not in CATEGORIES:
            raise ValueError(f"unknown category {category}")
        name = name or os.path.basename(src_path)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = os.path.join(self.root, category, f"{ts}-{name}")
        shutil.copy2(src_path, dest)
        self._append(f"{category}/{os.path.basename(dest)}", _sha(dest))
        return dest

    def snapshot_journal(self, journal_db="data/journal.db"):
        return self.file("journal-snapshots", journal_db, "journal.db")

    def _append(self, relname, digest):
        prev = self._last_line_hash()
        with open(self.manifest, "a") as f:
            n = self._count() + 1
            ts = datetime.now(timezone.utc).isoformat()
            f.write(f"{n}|{ts}|{relname}|{digest}|{prev}\n")

    def _count(self):
        if not os.path.exists(self.manifest):
            return 0
        with open(self.manifest) as f:
            return sum(1 for _ in f)

    def _last_line_hash(self):
        if not os.path.exists(self.manifest):
            return "GENESIS"
        last = None
        with open(self.manifest) as f:
            for line in f:
                if line.strip():
                    last = line.strip()
        return hashlib.sha256(last.encode()).hexdigest() if last else "GENESIS"

    # ---------------- verification ----------------

    def verify(self):
        """Returns (ok, problems). Checks the hash chain AND every artifact digest."""
        problems = []
        if not os.path.exists(self.manifest):
            return True, []
        prev = "GENESIS"
        prev_line = None
        with open(self.manifest) as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) != 5:
                    problems.append(f"line {i}: malformed")
                    continue
                n, ts, rel, digest, chain = parts
                if chain != prev:
                    problems.append(f"line {i}: chain broken (manifest edited?)")
                path = os.path.join(self.root, rel)
                if not os.path.exists(path):
                    problems.append(f"line {i}: missing artifact {rel}")
                elif _sha(path) != digest:
                    problems.append(f"line {i}: artifact MODIFIED {rel}")
                prev = hashlib.sha256(line.encode()).hexdigest()
                prev_line = line
        return (not problems), problems


if __name__ == "__main__":
    import sys
    lk = Locker()
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        ok, probs = lk.verify()
        print("LOCKER OK" if ok else "TAMPER DETECTED:\n" + "\n".join(probs))
        sys.exit(0 if ok else 1)
    if len(sys.argv) > 1 and sys.argv[1] == "snapshot":
        print("filed:", lk.snapshot_journal())
