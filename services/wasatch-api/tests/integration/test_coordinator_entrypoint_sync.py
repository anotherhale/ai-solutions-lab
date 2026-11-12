"""Regression tests for coordinator_automation_entrypoint develop sync."""

from __future__ import annotations

import subprocess

from wasatch_api.config import REPO_ROOT

ENTRYPOINT = REPO_ROOT / "scripts" / "coordinator_automation_entrypoint.sh"
BACKLOG = REPO_ROOT / "data" / "coordinator" / "backlog.yaml"


def test_entrypoint_syncs_catalog_from_develop_when_not_on_develop() -> None:
    assert ENTRYPOINT.is_file()
    script = ENTRYPOINT.read_text(encoding="utf-8")
    assert "sync_coordinator_sources_from_develop" in script
    assert "origin/develop -- data/coordinator/backlog.yaml" in script
    assert "libs/development_ops" in script

    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    if branch == "develop":
        return

    origin_develop = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/develop"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if origin_develop.returncode != 0:
        return

    develop_backlog = subprocess.check_output(
        ["git", "show", "origin/develop:data/coordinator/backlog.yaml"],
        cwd=REPO_ROOT,
        text=True,
    )
    assert "STATUS-2" in develop_backlog
    assert "COORD-CATALOG-2" in develop_backlog

    sync_only = subprocess.check_output(
        [
            "sed",
            "-n",
            "/^sync_coordinator_sources_from_develop/,/^}/p",
            str(ENTRYPOINT),
        ],
        text=True,
    )
    backup = BACKLOG.read_bytes()
    minimal = (
        "repository: example/stale\n"
        "integration_branch: develop\n"
        "tasks:\n"
        "  - id: STALE-ONLY\n"
        "    title: Stale catalog row\n"
        "    status: in_progress\n"
        "    depends_on: []\n"
    )
    bash_body = (
        f'ROOT="{REPO_ROOT}"\n'
        'VENV_BIN="${ROOT}/services/wasatch-api/.venv/bin"\n'
        f"{sync_only}\n"
        "sync_coordinator_sources_from_develop\n"
    )
    try:
        BACKLOG.write_text(minimal, encoding="utf-8")
        subprocess.run(
            ["bash", "-c", bash_body],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        restored = BACKLOG.read_text(encoding="utf-8")
        assert "STALE-ONLY" not in restored
        assert "STATUS-2" in restored
        assert "COORD-CATALOG-2" in restored
    finally:
        BACKLOG.write_bytes(backup)
