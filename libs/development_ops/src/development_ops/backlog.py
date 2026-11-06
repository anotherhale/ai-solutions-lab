"""Load structured coordinator backlog from data/coordinator/backlog.yaml."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class BacklogTaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    MERGED = "merged"
    BLOCKED = "blocked"


class BacklogTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=512)
    status: BacklogTaskStatus = BacklogTaskStatus.PENDING
    depends_on: list[str] = Field(default_factory=list)
    pr_number: int | None = Field(default=None, ge=1)
    branch: str | None = None
    merge_commit: str | None = None


class BacklogDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str
    integration_branch: str = "ai-dev"
    tasks: list[BacklogTask]


def default_backlog_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[4]
    return root / "data" / "coordinator" / "backlog.yaml"


def load_backlog(path: Path | None = None) -> BacklogDocument:
    backlog_path = path or default_backlog_path()
    raw: Any = yaml.safe_load(backlog_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"backlog root must be a mapping: {backlog_path}"
        raise ValueError(msg)
    return BacklogDocument.model_validate(raw)
