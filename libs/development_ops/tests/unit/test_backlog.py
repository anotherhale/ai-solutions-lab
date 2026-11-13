"""Backlog catalog parsing accepts the full task lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest
from development_ops.backlog import BacklogTaskStatus, load_backlog

CATALOG = """
repository: anotherhale/ai-solutions-lab
integration_branch: develop
tasks:
  - id: TASK-PENDING
    title: Waiting
    status: pending
    depends_on: []

  - id: TASK-ASSIGNED
    title: Assigned
    status: assigned
    depends_on: []

  - id: TASK-IN-PROGRESS
    title: In progress
    status: in_progress
    depends_on: []
    branch: cursor/example
    pr_number: 88

  - id: TASK-PR-OPEN
    title: Pull request open
    status: pr_open
    depends_on: []
    branch: cursor/example
    pr_number: 88

  - id: TASK-MERGE-READY
    title: Ready to merge
    status: merge_ready
    depends_on: []
    branch: cursor/example
    pr_number: 88

  - id: TASK-MERGED
    title: Merged
    status: merged
    merge_commit: e8c2a22
    depends_on: []

  - id: TASK-BLOCKED
    title: Blocked
    status: blocked
    depends_on: []
"""


@pytest.fixture()
def catalog(tmp_path: Path) -> Path:
    path = tmp_path / "backlog.yaml"
    path.write_text(CATALOG, encoding="utf-8")
    return path


def test_load_backlog_accepts_every_lifecycle_status(catalog: Path) -> None:
    document = load_backlog(catalog)
    statuses = {task.id: task.status for task in document.tasks}
    assert statuses == {
        "TASK-PENDING": BacklogTaskStatus.PENDING,
        "TASK-ASSIGNED": BacklogTaskStatus.ASSIGNED,
        "TASK-IN-PROGRESS": BacklogTaskStatus.IN_PROGRESS,
        "TASK-PR-OPEN": BacklogTaskStatus.PR_OPEN,
        "TASK-MERGE-READY": BacklogTaskStatus.MERGE_READY,
        "TASK-MERGED": BacklogTaskStatus.MERGED,
        "TASK-BLOCKED": BacklogTaskStatus.BLOCKED,
    }


def test_pr_open_status_preserves_pr_number(catalog: Path) -> None:
    document = load_backlog(catalog)
    by_id = {task.id: task for task in document.tasks}
    assert by_id["TASK-PR-OPEN"].pr_number == 88
    assert by_id["TASK-MERGE-READY"].pr_number == 88


def test_unknown_status_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "backlog.yaml"
    path.write_text(
        "repository: r\nintegration_branch: develop\ntasks:\n"
        "  - id: X\n    title: t\n    status: not_a_status\n    depends_on: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_backlog(path)
