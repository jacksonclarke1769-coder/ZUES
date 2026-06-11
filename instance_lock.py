"""W2 — Single-instance lock. Two trading processes must never coexist.

Mechanism: fcntl.flock(LOCK_EX | LOCK_NB) on a lockfile. The OS releases the lock
when the holding process dies (any death: clean exit, crash, kill -9) — so crash
recovery is automatic and there is no stale-lock problem. The pid + timestamp inside
the file are diagnostic only, never used for liveness decisions.

Fail-closed: a second instance gets LockHeld and must exit without trading.
"""
import fcntl
import os
import time


class LockHeld(RuntimeError):
    pass


class InstanceLock:
    def __init__(self, path="data/bot.lock"):
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        self.path = path
        self.fd = None

    def acquire(self):
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            try:
                holder = os.read(fd, 256).decode(errors="replace").strip()
            finally:
                os.close(fd)
            raise LockHeld(f"another instance holds {self.path} ({holder or 'unknown'})")
        os.ftruncate(fd, 0)
        os.write(fd, f"pid={os.getpid()} ts={time.time():.0f}\n".encode())
        os.fsync(fd)
        self.fd = fd
        return self

    def release(self):
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *a):
        self.release()
