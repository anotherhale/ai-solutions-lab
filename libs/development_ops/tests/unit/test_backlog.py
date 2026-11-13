"""Backlog catalog parsing."""

from development_ops.backlog import BacklogTaskStatus, load_backlog


def test_load_backlog_accepts_pr_open_status(tmp_path) -> None:
    backlog = tmp_path / "backlog.yaml"
    backlog.write_text(
        """
repository: anotherhale/ai-solutions-lab
integration_branch: develop
tasks:
  - id: DOC-DBMAP-2
    title: Example
    status: pr_open
    depends_on: []
    branch: cursor/example
    pr_number: 88
""",
        encoding="utf-8",
    )
    document = load_backlog(backlog)
    assert document.tasks[0].status == BacklogTaskStatus.PR_OPEN
    assert document.tasks[0].pr_number == 88
