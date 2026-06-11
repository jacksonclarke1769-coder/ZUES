"""W9 battery: evidence locker filing, chain integrity, tamper detection."""
import pytest
from locker import Locker


@pytest.fixture
def lk(tmp_path):
    return Locker(str(tmp_path / "evidence"))


def _mkfile(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content)
    return str(p)


def test_file_and_verify_clean(lk, tmp_path):
    a = _mkfile(tmp_path, "approval.pdf.txt", "MFFU says yes")
    b = _mkfile(tmp_path, "fill.json", '{"qty":4}')
    lk.file("approvals", a)
    lk.file("fills", b)
    ok, probs = lk.verify()
    assert ok and probs == []


def test_artifact_tamper_detected(lk, tmp_path):
    src = _mkfile(tmp_path, "x.txt", "original")
    dest = lk.file("incidents", src)
    with open(dest, "w") as f:
        f.write("DOCTORED")
    ok, probs = lk.verify()
    assert not ok and any("MODIFIED" in p for p in probs)


def test_manifest_tamper_detected(lk, tmp_path):
    lk.file("signals", _mkfile(tmp_path, "s1.txt", "sig1"))
    lk.file("signals", _mkfile(tmp_path, "s2.txt", "sig2"))
    lines = open(lk.manifest).read().splitlines()
    lines[0] = lines[0].replace("signals", "fills")        # edit history
    with open(lk.manifest, "w") as f:
        f.write("\n".join(lines) + "\n")
    ok, probs = lk.verify()
    assert not ok and any("chain broken" in p or "missing" in p for p in probs)


def test_missing_artifact_detected(lk, tmp_path):
    import os
    dest = lk.file("payouts", _mkfile(tmp_path, "p.txt", "payout"))
    os.remove(dest)
    ok, probs = lk.verify()
    assert not ok and any("missing" in p for p in probs)


def test_unknown_category_refused(lk, tmp_path):
    with pytest.raises(ValueError):
        lk.file("misc", _mkfile(tmp_path, "m.txt", "x"))


def test_journal_snapshot(lk, tmp_path):
    from journal import Journal
    j = Journal(str(tmp_path / "journal.db"))
    j.append("STATE_ASSERT", "A1", payload=dict(x=1))
    j.con.close()
    dest = lk.snapshot_journal(str(tmp_path / "journal.db"))
    ok, _ = lk.verify()
    assert ok and "journal-snapshots" in dest
