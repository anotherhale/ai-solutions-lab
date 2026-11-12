"""Durable runner state: pause flag and last-run bookkeeping.

Pause must survive a process restart, so it lives in a small JSON file in the
runner state directory rather than in memory. Only the pause flag is
authoritative for scheduling; the remaining fields are diagnostics for the
status command.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


@dataclass(slots=True)
class RunnerState:
    """Mutable, persisted runner state."""

    paused: bool = False
    paused_at: str | None = None
    paused_by: str | None = None
    pause_reason: str | None = None
    last_tick_started_at: str | None = None
    last_tick_completed_at: str | None = None
    last_tick_error: str | None = None
    last_tick_run_id: str | None = None
    last_recovery_at: str | None = None
    recovery_events: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunnerState:
        known = {
            "paused",
            "paused_at",
            "paused_by",
            "pause_reason",
            "last_tick_started_at",
            "last_tick_completed_at",
            "last_tick_error",
            "last_tick_run_id",
            "last_recovery_at",
            "recovery_events",
        }
        # ``extra`` must be excluded from the unknown-key sweep: otherwise the
        # persisted ``extra`` key is captured as an unknown key and re-wrapped one
        # level deeper on every save, growing the state file without bound.
        extra = {
            key: value
            for key, value in data.items()
            if key not in known and key != "extra"
        }
        persisted_extra = data.get("extra")
        # Heal files written by earlier builds that nested ``extra`` per save.
        while isinstance(persisted_extra, dict) and isinstance(
            persisted_extra.get("extra"), dict
        ):
            persisted_extra = persisted_extra["extra"]
        if isinstance(persisted_extra, dict):
            extra = {**persisted_extra, **extra}
        return cls(
            paused=bool(data.get("paused", False)),
            paused_at=data.get("paused_at"),
            paused_by=data.get("paused_by"),
            pause_reason=data.get("pause_reason"),
            last_tick_started_at=data.get("last_tick_started_at"),
            last_tick_completed_at=data.get("last_tick_completed_at"),
            last_tick_error=data.get("last_tick_error"),
            last_tick_run_id=data.get("last_tick_run_id"),
            last_recovery_at=data.get("last_recovery_at"),
            recovery_events=int(data.get("recovery_events", 0)),
            extra=extra,
        )


class RunnerStateStore:
    """Read/write :class:`RunnerState` with atomic replacement."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path).expanduser()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> RunnerState:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return RunnerState()
        except OSError:
            return RunnerState()
        if not raw.strip():
            return RunnerState()
        try:
            data = json.loads(raw)
        except ValueError:
            return RunnerState()
        if not isinstance(data, dict):
            return RunnerState()
        return RunnerState.from_dict(data)

    def save(self, state: RunnerState) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state.to_dict(), indent=2, sort_keys=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self._path.parent), prefix=".runner-state-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self._path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def pause(self, *, by: str | None = None, reason: str | None = None) -> RunnerState:
        state = self.load()
        state.paused = True
        state.paused_at = _utc_now_iso()
        state.paused_by = by
        state.pause_reason = reason
        self.save(state)
        return state

    def resume(self) -> RunnerState:
        state = self.load()
        state.paused = False
        state.paused_at = None
        state.paused_by = None
        state.pause_reason = None
        self.save(state)
        return state

    def record_tick_started(self, *, run_id: str) -> None:
        state = self.load()
        state.last_tick_started_at = _utc_now_iso()
        state.last_tick_run_id = run_id
        self.save(state)

    def record_tick_completed(self, *, run_id: str) -> None:
        state = self.load()
        state.last_tick_completed_at = _utc_now_iso()
        state.last_tick_error = None
        state.last_tick_run_id = run_id
        self.save(state)

    def record_tick_error(self, *, run_id: str, error: str) -> None:
        state = self.load()
        state.last_tick_completed_at = _utc_now_iso()
        state.last_tick_error = error
        state.last_tick_run_id = run_id
        self.save(state)

    def record_recovery(self, *, count: int) -> None:
        state = self.load()
        state.last_recovery_at = _utc_now_iso()
        state.recovery_events += count
        self.save(state)
