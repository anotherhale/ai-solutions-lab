"""Single-instance protection for the persistent coordinator runner.

A PID file alone cannot prove ownership: the recorded process may have exited,
the PID may have been recycled, or the file may be stale after a crash. This
uses an ``flock`` on a dedicated lock file as the authority, and records the
owning PID/host only as diagnostic metadata. The lock is released by the
kernel when the process exits, so a crash never leaves a permanent lock.

The model is deliberately single-workstation: ``flock`` is local to a host and
gives no protection across machines. See ADR 0013.
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
import socket
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import IO


class InstanceLockError(RuntimeError):
    """Raised when the instance lock cannot be acquired."""


class InstanceLockedError(InstanceLockError):
    """Raised when another live process already owns the lock."""


@dataclass(frozen=True, slots=True)
class LockOwner:
    pid: int
    hostname: str
    acquired_at: float
    run_id: str | None = None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Exists but owned by another user: treat as alive.
        return True
    except OSError:
        return False
    return True


class CoordinatorInstanceLock:
    """Exclusive, crash-safe ownership of the local coordinator environment."""

    def __init__(self, path: Path | str, *, run_id: str | None = None) -> None:
        self._path = Path(path).expanduser()
        self._run_id = run_id
        self._handle: IO[str] | None = None
        self._owner: LockOwner | None = None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def owner(self) -> LockOwner | None:
        return self._owner

    @property
    def held(self) -> bool:
        return self._handle is not None

    def read_owner(self) -> LockOwner | None:
        """Read recorded owner metadata, if present and parseable."""
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError:
            return None
        if not raw.strip():
            return None
        try:
            data = json.loads(raw)
        except ValueError:
            return None
        try:
            return LockOwner(
                pid=int(data["pid"]),
                hostname=str(data.get("hostname", "")),
                acquired_at=float(data.get("acquired_at", 0.0)),
                run_id=data.get("run_id"),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def acquire(self, *, wait_seconds: float = 0.0) -> LockOwner:
        """Take the lock or fail.

        The lock file is never deleted while held, because deleting it would let
        a second process create a fresh inode and both would "own" the lock.
        Stale metadata from a dead PID is overwritten only after the flock is
        held, which is the real guard.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = os.open(str(self._path), os.O_CREAT | os.O_RDWR, 0o644)
        deadline = time.monotonic() + max(wait_seconds, 0.0)
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EAGAIN, errno.EACCES):
                    os.close(handle)
                    raise InstanceLockError(f"flock failed: {exc}") from exc
                if time.monotonic() >= deadline:
                    owner = self._read_owner_from_fd(handle)
                    os.close(handle)
                    detail = f" (pid {owner.pid} on {owner.hostname})" if owner else ""
                    raise InstanceLockedError(
                        f"another coordinator runner holds {self._path}{detail}"
                    ) from exc
                time.sleep(0.05)
        owner = LockOwner(
            pid=os.getpid(),
            hostname=socket.gethostname(),
            acquired_at=time.time(),
            run_id=self._run_id,
        )
        try:
            os.ftruncate(handle, 0)
            os.lseek(handle, 0, os.SEEK_SET)
            os.write(handle, (json.dumps(asdict(owner)) + "\n").encode("utf-8"))
            os.fsync(handle)
        except OSError:
            # Metadata is diagnostic only; the flock is the authority.
            pass
        self._handle = os.fdopen(handle, "r+")
        self._owner = owner
        return owner

    def release(self) -> None:
        """Release ownership. Safe to call when not held."""
        if self._handle is None:
            return
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            try:
                self._handle.close()
            finally:
                self._handle = None
                self._owner = None

    def is_stale(self) -> bool:
        """True when a recorded owner PID is no longer alive.

        Informational: the flock is authoritative, so a stale record does not by
        itself grant the lock. Used by the status command.
        """
        owner = self.read_owner()
        if owner is None:
            return False
        if owner.hostname and owner.hostname != socket.gethostname():
            return False
        return not _pid_alive(owner.pid)

    def _read_owner_from_fd(self, handle: int) -> LockOwner | None:
        try:
            os.lseek(handle, 0, os.SEEK_SET)
            raw = os.read(handle, 4096).decode("utf-8")
        except OSError:
            return None
        if not raw.strip():
            return None
        try:
            data = json.loads(raw)
        except ValueError:
            return None
        try:
            return LockOwner(
                pid=int(data["pid"]),
                hostname=str(data.get("hostname", "")),
                acquired_at=float(data.get("acquired_at", 0.0)),
                run_id=data.get("run_id"),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def __enter__(self) -> CoordinatorInstanceLock:
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()
