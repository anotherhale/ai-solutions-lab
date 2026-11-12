"""Catalog writer: line-preserving, idempotent, concurrency-safe."""

from __future__ import annotations

import multiprocessing
import textwrap
from pathlib import Path

import pytest
from development_ops.backlog import BacklogTaskStatus, load_backlog
from development_ops.catalog import CatalogWriteError, YamlBacklogCatalogWriter

CATALOG = textwrap.dedent(
    """
    # Machine-readable backlog for the development coordinator.
    repository: anotherhale/ai-solutions-lab
    integration_branch: ai-dev

    tasks:
      - id: TASK-A
        title: First task
        status: in_progress
        pr_number: 10
        depends_on: []

      - id: TASK-B
        title: Second task
        status: pending
        depends_on: [TASK-A]
    """
).lstrip()


def _write(tmp_path: Path) -> Path:
    path = tmp_path / "backlog.yaml"
    path.write_text(CATALOG, encoding="utf-8")
    return path


def test_mark_merged_sets_status_and_commit(tmp_path: Path) -> None:
    path = _write(tmp_path)
    writer = YamlBacklogCatalogWriter(path)
    assert writer.mark_merged("TASK-A", merge_commit="abc1234") is True
    document = load_backlog(path)
    task = next(item for item in document.tasks if item.id == "TASK-A")
    assert task.status == BacklogTaskStatus.MERGED
    assert task.merge_commit == "abc1234"


def test_mark_merged_preserves_comments_and_other_tasks(tmp_path: Path) -> None:
    path = _write(tmp_path)
    YamlBacklogCatalogWriter(path).mark_merged("TASK-A", merge_commit="abc1234")
    text = path.read_text(encoding="utf-8")
    assert "# Machine-readable backlog" in text
    assert "Second task" in text
    assert "depends_on: [TASK-A]" in text


def test_mark_merged_is_idempotent(tmp_path: Path) -> None:
    path = _write(tmp_path)
    writer = YamlBacklogCatalogWriter(path)
    assert writer.mark_merged("TASK-A", merge_commit="abc1234") is True
    first = path.read_text(encoding="utf-8")
    assert writer.mark_merged("TASK-A", merge_commit="abc1234") is False
    assert path.read_text(encoding="utf-8") == first


def test_mark_merged_updates_existing_commit(tmp_path: Path) -> None:
    path = _write(tmp_path)
    writer = YamlBacklogCatalogWriter(path)
    writer.mark_merged("TASK-A", merge_commit="aaaaaaa")
    assert writer.mark_merged("TASK-A", merge_commit="bbbbbbb") is True
    document = load_backlog(path)
    task = next(item for item in document.tasks if item.id == "TASK-A")
    assert task.merge_commit == "bbbbbbb"


def test_mark_status_without_commit(tmp_path: Path) -> None:
    path = _write(tmp_path)
    YamlBacklogCatalogWriter(path).mark_status("TASK-B", BacklogTaskStatus.BLOCKED)
    document = load_backlog(path)
    task = next(item for item in document.tasks if item.id == "TASK-B")
    assert task.status == BacklogTaskStatus.BLOCKED


def test_unknown_task_raises(tmp_path: Path) -> None:
    path = _write(tmp_path)
    with pytest.raises(CatalogWriteError):
        YamlBacklogCatalogWriter(path).mark_merged("NOPE")


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(CatalogWriteError):
        YamlBacklogCatalogWriter(tmp_path / "absent.yaml").mark_merged("TASK-A")


def test_no_temp_files_left_behind(tmp_path: Path) -> None:
    path = _write(tmp_path)
    YamlBacklogCatalogWriter(path).mark_merged("TASK-A", merge_commit="abc1234")
    leftovers = [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []


def _merge_worker(path: str) -> None:
    YamlBacklogCatalogWriter(Path(path)).mark_merged("TASK-A", merge_commit="abc1234")


def test_concurrent_writers_do_not_corrupt(tmp_path: Path) -> None:
    """Two processes marking the same task must not truncate or interleave."""
    path = _write(tmp_path)
    processes = [
        multiprocessing.Process(target=_merge_worker, args=(str(path),))
        for _ in range(4)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join()
    assert all(process.exitcode == 0 for process in processes)
    document = load_backlog(path)
    task = next(item for item in document.tasks if item.id == "TASK-A")
    assert task.status == BacklogTaskStatus.MERGED
    assert task.merge_commit == "abc1234"
