"""The single sanctioned writer for ``data/coordinator/backlog.yaml`` status.

The catalog is a *tracked* file, so every autonomous agent that edited it to
record its own task produced a merge conflict on the next agent's pull request.
Once the catalog carried unresolved conflicts, GitHub refused the merge and the
coordinator could not auto-merge — the pull request stalled until a human
intervened.

This module makes the coordinator (and only the coordinator) the writer of
catalog status, through an idempotent, atomic, advisory-locked update that
touches a single task block and preserves the rest of the file byte-for-byte.

Design notes:

* **Line-preserving.** The file is edited as text, not re-serialized, so
  comments, ordering, and formatting survive. Re-dumping the YAML would churn
  the whole file and conflict with every other branch.
* **Atomic.** The new content is written to a sibling temp file and renamed over
  the original, so a crash never leaves a truncated catalog.
* **Advisory-locked.** An exclusive ``flock`` serializes two coordinator
  processes on the same workstation (matching the single-workstation model of
  ADR 0013).
* **Idempotent.** Re-marking an already-merged task is a no-op that reports
  ``changed=False``.
"""

from __future__ import annotations

import fcntl
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from development_ops.backlog import BacklogTaskStatus

_TASK_HEADER = re.compile(r"^(\s*-\s*id:\s*)(?P<id>\S+)\s*$")
_TOP_LEVEL = re.compile(r"^\S")
_FIELD = re.compile(r"^(?P<indent>\s*)(?P<key>[a-z_]+):(?P<rest>.*)$")


class CatalogWriteError(RuntimeError):
    """The catalog could not be updated safely."""


@dataclass(frozen=True, slots=True)
class CatalogUpdate:
    task_id: str
    changed: bool
    status: BacklogTaskStatus
    path: Path


class BacklogCatalogWriter(Protocol):
    def mark_merged(self, task_id: str, *, merge_commit: str | None = None) -> bool:
        """Set ``task_id`` to merged. Returns True when the file changed."""

    def mark_status(self, task_id: str, status: BacklogTaskStatus) -> bool:
        """Set ``task_id`` to ``status``. Returns True when the file changed."""


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    lock_path = path.with_suffix(path.suffix + ".lock")
    handle = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        os.close(handle)


class YamlBacklogCatalogWriter:
    """Line-preserving, atomic, locked writer for the YAML backlog catalog."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def mark_merged(self, task_id: str, *, merge_commit: str | None = None) -> bool:
        return self._update(
            task_id,
            status=BacklogTaskStatus.MERGED,
            merge_commit=merge_commit,
        )

    def mark_status(self, task_id: str, status: BacklogTaskStatus) -> bool:
        return self._update(task_id, status=status, merge_commit=None)

    # -- internals ---------------------------------------------------------

    def _update(
        self,
        task_id: str,
        *,
        status: BacklogTaskStatus,
        merge_commit: str | None,
    ) -> bool:
        if not self._path.is_file():
            raise CatalogWriteError(f"backlog catalog not found: {self._path}")
        with _exclusive_lock(self._path):
            original = self._path.read_text(encoding="utf-8")
            updated, changed = self._render(
                original,
                task_id=task_id,
                status=status,
                merge_commit=merge_commit,
            )
            if not changed:
                return False
            self._atomic_write(updated)
            return True

    def _render(
        self,
        text: str,
        *,
        task_id: str,
        status: BacklogTaskStatus,
        merge_commit: str | None,
    ) -> tuple[str, bool]:
        lines = text.splitlines(keepends=True)
        start, end = self._locate_task(lines, task_id)
        block = lines[start:end]
        changed = False

        status_index = self._field_index(block, "status")
        if status_index is None:
            msg = f"task {task_id} has no 'status' field"
            raise CatalogWriteError(msg)
        new_status_line = self._set_value(block[status_index], status.value)
        if new_status_line != block[status_index]:
            block[status_index] = new_status_line
            changed = True

        if merge_commit is not None:
            commit_index = self._field_index(block, "merge_commit")
            if commit_index is None:
                insert_at = status_index + 1
                indent = self._indent_of(block[status_index])
                block.insert(insert_at, f"{indent}merge_commit: {merge_commit}\n")
                changed = True
            else:
                new_commit_line = self._set_value(block[commit_index], merge_commit)
                if new_commit_line != block[commit_index]:
                    block[commit_index] = new_commit_line
                    changed = True

        if not changed:
            return text, False
        return "".join(lines[:start] + block + lines[end:]), True

    @staticmethod
    def _locate_task(lines: list[str], task_id: str) -> tuple[int, int]:
        start: int | None = None
        for index, line in enumerate(lines):
            match = _TASK_HEADER.match(line.rstrip("\n"))
            if match:
                if start is not None:
                    return start, index
                if match.group("id") == task_id:
                    start = index
                continue
            if start is not None and _TOP_LEVEL.match(line):
                return start, index
        if start is not None:
            return start, len(lines)
        raise CatalogWriteError(f"task {task_id} not found in catalog")

    @staticmethod
    def _field_index(block: list[str], key: str) -> int | None:
        for index, line in enumerate(block):
            match = _FIELD.match(line.rstrip("\n"))
            if match and match.group("key") == key:
                return index
        return None

    @staticmethod
    def _indent_of(line: str) -> str:
        match = _FIELD.match(line.rstrip("\n"))
        return match.group("indent") if match else "    "

    @staticmethod
    def _set_value(line: str, value: str) -> str:
        newline = "\n" if line.endswith("\n") else ""
        match = _FIELD.match(line.rstrip("\n"))
        if match is None:
            return line
        return f"{match.group('indent')}{match.group('key')}: {value}{newline}"

    def _atomic_write(self, content: str) -> None:
        directory = self._path.parent
        handle, temp_name = tempfile.mkstemp(
            dir=directory, prefix=self._path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, self._path)
        except BaseException:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
            raise
