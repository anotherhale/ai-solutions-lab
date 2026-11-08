"""CLI for recording development activity events."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from development_ops.backlog import default_backlog_path
from development_ops.child_agents import (
    DEFAULT_AGENT_SERVER_URL,
    ChildAgentLauncher,
    ChildAgentLaunchError,
    HttpChildAgentLauncher,
)
from development_ops.coordinator_engine import CoordinatorEngine
from development_ops.database import (
    development_ops_database_url,
    ensure_development_ops_database,
)
from development_ops.errors import PersistenceError
from development_ops.github_client import github_client_from_env
from development_ops.models import ActivityEventCreate, GitHubReference
from development_ops.recorder import ActivityRecorder, RecordResult
from development_ops.runner_config import RunnerConfig
from development_ops.runner_status import collect_status
from development_ops.task_worktrees import (
    TaskWorktreeOrchestrator,
    worktree_manager_from_env,
)
from development_ops.taxonomy import EventSeverity, EventType
from development_ops.worktrees import WorktreeError

EXIT_OK = 0
EXIT_PERSISTENCE_FAILED = 1
EXIT_SLACK_FAILED = 2
EXIT_USAGE = 64


@dataclass(frozen=True, slots=True)
class CliRecordOutcome:
    persisted: bool
    event_id: str | None
    created: bool
    run_id: str
    slack_attempted: bool
    slack_delivered: bool
    slack_error: str | None
    error: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def _database_url() -> str:
    return development_ops_database_url()


def _run_id(value: str | None) -> uuid.UUID:
    raw = value or os.environ.get("DEVELOPMENT_OPS_RUN_ID", "").strip()
    if not raw:
        msg = "run id is required (--run-id or DEVELOPMENT_OPS_RUN_ID)"
        raise argparse.ArgumentTypeError(msg)
    return uuid.UUID(raw)


def _parse_metadata(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        msg = "metadata must be a JSON object"
        raise ValueError(msg)
    return parsed


def _github_from_args(args: argparse.Namespace) -> GitHubReference | None:
    if not any(
        (
            args.github_repository,
            args.github_pull_number,
            args.github_commit_sha,
            args.github_actions_run_url,
        )
    ):
        default_repo = os.environ.get("DEVELOPMENT_OPS_GITHUB_REPOSITORY", "").strip()
        if default_repo:
            return GitHubReference(repository=default_repo)
        return None
    return GitHubReference(
        repository=args.github_repository
        or os.environ.get("DEVELOPMENT_OPS_GITHUB_REPOSITORY"),
        pull_number=args.github_pull_number,
        commit_sha=args.github_commit_sha,
        actions_run_url=args.github_actions_run_url,
    )


def _build_payload(args: argparse.Namespace) -> ActivityEventCreate:
    return ActivityEventCreate(
        run_id=_run_id(args.run_id),
        task_id=args.task_id or os.environ.get("DEVELOPMENT_OPS_TASK_ID"),
        agent_name=args.agent_name or os.environ.get("DEVELOPMENT_OPS_AGENT_NAME"),
        event_type=EventType(args.event_type),
        severity=EventSeverity(args.severity),
        title=args.title,
        summary=args.summary,
        metadata=_parse_metadata(args.metadata),
        idempotency_key=args.idempotency_key,
        occurred_at=datetime.fromisoformat(args.occurred_at)
        if args.occurred_at
        else None,
        github=_github_from_args(args),
    )


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine(_database_url(), pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False)


def record_command(args: argparse.Namespace) -> int:
    payload = _build_payload(args)
    notify_slack = args.notify_slack and not args.no_slack
    factory = _session_factory()
    session = factory()
    try:
        recorder = ActivityRecorder(session, notify_slack=notify_slack)
        result = recorder.record(payload, attempt_slack=notify_slack)
    except SQLAlchemyError as exc:
        session.rollback()
        outcome = CliRecordOutcome(
            persisted=False,
            event_id=None,
            created=False,
            run_id=str(payload.run_id),
            slack_attempted=False,
            slack_delivered=False,
            slack_error=None,
            error=f"persistence failed: {exc}",
        )
        print(outcome.to_json(), file=sys.stderr)
        raise PersistenceError(str(exc)) from exc
    finally:
        session.close()

    outcome = _outcome_from_result(result, run_id=str(payload.run_id))
    print(outcome.to_json())
    if not outcome.persisted:
        return EXIT_PERSISTENCE_FAILED
    if notify_slack and outcome.slack_attempted and not outcome.slack_delivered:
        return EXIT_SLACK_FAILED
    return EXIT_OK


def _outcome_from_result(result: RecordResult, *, run_id: str) -> CliRecordOutcome:
    return CliRecordOutcome(
        persisted=True,
        event_id=str(result.event.id),
        created=result.created,
        run_id=run_id,
        slack_attempted=result.slack_attempted,
        slack_delivered=result.slack_delivered,
        slack_error=result.slack_error,
    )


def coordinator_tick_command(args: argparse.Namespace) -> int:
    ensure_development_ops_database()
    run_id = _run_id(args.run_id)
    repository = (
        args.github_repository
        or os.environ.get("DEVELOPMENT_OPS_GITHUB_REPOSITORY", "").strip()
        or "anotherhale/ai-solutions-lab"
    )
    factory = _session_factory()
    session = factory()
    try:
        recorder = ActivityRecorder(session, notify_slack=args.notify_slack)
        worktrees = None
        if getattr(args, "worktrees", False):
            worktrees = TaskWorktreeOrchestrator(
                session,
                worktree_manager_from_env(),
                repository=repository,
                launcher=None,
                github=github_client_from_env(),
                run_id=run_id,
            )
        engine = CoordinatorEngine(
            session,
            github=github_client_from_env(),
            recorder=recorder,
            run_id=run_id,
            repository=repository,
            backlog_path=Path(args.backlog) if args.backlog else None,
            worktrees=worktrees,
        )
        result = engine.tick()
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return EXIT_OK
    except SQLAlchemyError as exc:
        session.rollback()
        print(json.dumps({"error": f"persistence failed: {exc}"}), file=sys.stderr)
        return EXIT_PERSISTENCE_FAILED
    finally:
        session.close()


def confirm_slack_command(args: argparse.Namespace) -> int:
    event_id = uuid.UUID(args.event_id)
    factory = _session_factory()
    session = factory()
    try:
        recorder = ActivityRecorder(session, notify_slack=False)
        updated = recorder.confirm_slack_delivery(
            event_id,
            channel_id=args.channel_id,
            message_ts=args.message_ts,
            duplicate=args.duplicate,
        )
        if updated is None:
            outcome = {
                "persisted": False,
                "error": f"event {event_id} not found",
            }
            print(json.dumps(outcome, indent=2), file=sys.stderr)
            return EXIT_PERSISTENCE_FAILED
        print(
            json.dumps(
                {
                    "persisted": True,
                    "event_id": str(updated.id),
                    "slack_delivered": updated.slack.delivery_status.value
                    in {"delivered", "duplicate"},
                    "slack_message_ts": updated.slack.message_ts,
                    "slack_channel_id": updated.slack.channel_id,
                },
                indent=2,
            )
        )
        return EXIT_OK
    except SQLAlchemyError as exc:
        print(json.dumps({"persisted": False, "error": str(exc)}), file=sys.stderr)
        return EXIT_PERSISTENCE_FAILED
    finally:
        session.close()


def _worktree_orchestrator(
    session: Session,
    args: argparse.Namespace,
    *,
    launcher: ChildAgentLauncher | None = None,
) -> TaskWorktreeOrchestrator:
    repository = (
        getattr(args, "github_repository", None)
        or os.environ.get("DEVELOPMENT_OPS_GITHUB_REPOSITORY", "").strip()
        or "anotherhale/ai-solutions-lab"
    )
    manager = worktree_manager_from_env()
    return TaskWorktreeOrchestrator(
        session,
        manager,
        repository=repository,
        launcher=launcher,
        github=github_client_from_env(),
    )


def _child_agent_launcher_from_env(
    args: argparse.Namespace,
) -> HttpChildAgentLauncher:
    base_url = (
        getattr(args, "agent_server_url", None)
        or os.environ.get("DEVELOPMENT_OPS_AGENT_SERVER_URL")
        or DEFAULT_AGENT_SERVER_URL
    )
    return HttpChildAgentLauncher(
        base_url=base_url,
        api_key=os.environ.get("OPENHANDS_SESSION_API_KEY"),
    )


def _worktree_record_dict(record: Any) -> dict[str, Any]:
    return {
        "task_id": record.task_id,
        "state": record.state.value,
        "branch_name": record.branch_name,
        "worktree_path": record.worktree_path,
        "base_ref": record.base_ref,
        "base_sha": record.base_sha,
        "conversation_id": record.conversation_id,
        "pr_number": record.pr_number,
        "notes": record.notes,
    }


def worktree_list_command(args: argparse.Namespace) -> int:
    factory = _session_factory()
    session = factory()
    try:
        orchestrator = _worktree_orchestrator(session, args)
        records = orchestrator.registry.list_all()
        print(
            json.dumps(
                {"worktrees": [_worktree_record_dict(r) for r in records]},
                indent=2,
                sort_keys=True,
            )
        )
        return EXIT_OK
    finally:
        session.close()


def worktree_status_command(args: argparse.Namespace) -> int:
    factory = _session_factory()
    session = factory()
    try:
        orchestrator = _worktree_orchestrator(session, args)
        record = orchestrator.registry.get(args.task_id)
        if record is None:
            print(
                json.dumps({"error": f"no worktree registered for {args.task_id}"}),
                file=sys.stderr,
            )
            return EXIT_USAGE
        payload = _worktree_record_dict(record)
        status = orchestrator.manager.status(args.task_id)
        payload["filesystem"] = {
            "exists": status.exists,
            "dirty": status.dirty,
            "head_sha": status.head_sha,
            "merged_into_base": status.merged_into_base,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return EXIT_OK
    finally:
        session.close()


def worktree_prepare_command(args: argparse.Namespace) -> int:
    factory = _session_factory()
    session = factory()
    try:
        orchestrator = _worktree_orchestrator(session, args)
        record = orchestrator.prepare(args.task_id, title=args.title or "")
        print(json.dumps(_worktree_record_dict(record), indent=2, sort_keys=True))
        return EXIT_OK
    except WorktreeError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return EXIT_PERSISTENCE_FAILED
    finally:
        session.close()


def worktree_launch_command(args: argparse.Namespace) -> int:
    """Launch a child conversation inside a task's worktree.

    This starts a real agent conversation and therefore must be invoked
    explicitly with ``--agent-settings``; it is never triggered by a bare tick.
    """
    settings_path = Path(args.agent_settings)
    if not settings_path.exists():
        print(
            json.dumps({"error": f"agent settings not found: {settings_path}"}),
            file=sys.stderr,
        )
        return EXIT_USAGE
    try:
        agent_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": f"invalid agent settings: {exc}"}), file=sys.stderr)
        return EXIT_USAGE

    factory = _session_factory()
    session = factory()
    try:
        orchestrator = _worktree_orchestrator(
            session, args, launcher=_child_agent_launcher_from_env(args)
        )
        result = orchestrator.launch(
            args.task_id,
            title=args.title or args.task_id,
            agent_settings=agent_settings,
            extra_instructions=args.instructions,
        )
        print(
            json.dumps(
                {
                    "task_id": result.task_id,
                    "conversation_id": result.conversation_id,
                    "worktree_path": str(result.worktree_path),
                    "branch_name": result.branch_name,
                    "launched": result.launched,
                    "notes": list(result.notes),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return EXIT_OK
    except (WorktreeError, ChildAgentLaunchError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return EXIT_PERSISTENCE_FAILED
    finally:
        session.close()


def worktree_cleanup_command(args: argparse.Namespace) -> int:
    factory = _session_factory()
    session = factory()
    try:
        orchestrator = _worktree_orchestrator(session, args)
        outcome = orchestrator.cleanup_after_merge(args.task_id)
        print(
            json.dumps(
                {
                    "task_id": outcome.task_id,
                    "cleaned": outcome.cleaned,
                    "verified_merge": outcome.verified_merge,
                    "reason": outcome.reason,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return EXIT_OK if outcome.cleaned else EXIT_PERSISTENCE_FAILED
    except WorktreeError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return EXIT_PERSISTENCE_FAILED
    finally:
        session.close()


def _runner_config(args: argparse.Namespace) -> RunnerConfig:
    from development_ops.runner_config import RunnerConfig, RunnerConfigError

    try:
        return RunnerConfig.from_env(
            repository=getattr(args, "github_repository", None)
        )
    except RunnerConfigError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def runner_run_command(args: argparse.Namespace) -> int:
    """Run the persistent coordinator loop until SIGTERM/SIGINT."""
    from development_ops.instance_lock import InstanceLockedError
    from development_ops.runner_logging import configure_logging
    from development_ops.runner_service import build_runner_from_env, ensure_database

    config = _runner_config(args)
    logger = configure_logging(level=config.log_level, fmt=config.log_format)
    ensure_database()
    runner, _factory = build_runner_from_env(config)
    runner.install_signal_handlers()
    max_ticks = getattr(args, "max_ticks", None)
    try:
        ticks = runner.run(max_ticks=max_ticks)
    except InstanceLockedError as exc:
        logger.error(
            "another coordinator runner is already active",
            extra={"event": "runner.lock_held", "error": str(exc)},
        )
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return EXIT_USAGE
    print(json.dumps({"ticks": ticks, "run_id": str(runner.run_id)}))
    return EXIT_OK


def runner_once_command(args: argparse.Namespace) -> int:
    """Run exactly one coordinator tick through the runner's recovery path."""
    return runner_run_command(_with_max_ticks(args, 1))


def _with_max_ticks(args: argparse.Namespace, ticks: int) -> argparse.Namespace:
    args.max_ticks = ticks
    return args


def runner_status_command(args: argparse.Namespace) -> int:
    """Print a read-only runner/coordinator status snapshot."""
    from development_ops.runner_service import _session_factory, ensure_database

    config = _runner_config(args)
    try:
        ensure_database()
    except Exception as exc:  # noqa: BLE001 - status must still render
        print(
            json.dumps({"error": f"database unavailable: {exc}"}),
            file=sys.stderr,
        )
    status = collect_status(config, session_factory=_session_factory())
    print(json.dumps(status.to_dict(), indent=2, sort_keys=True, default=str))
    return EXIT_OK


def runner_pause_command(args: argparse.Namespace) -> int:
    """Durably pause new task claims. Running work is preserved."""
    from development_ops.runner_service import ensure_database
    from development_ops.runner_state import RunnerStateStore

    config = _runner_config(args)
    ensure_database()
    store = RunnerStateStore(config.state_dir / "runner-state.json")
    state = store.pause(by=args.by, reason=args.reason)
    print(json.dumps(state.to_dict(), indent=2, sort_keys=True))
    return EXIT_OK


def runner_resume_command(args: argparse.Namespace) -> int:
    """Clear a durable pause and re-enable normal scheduling."""
    from development_ops.runner_service import ensure_database
    from development_ops.runner_state import RunnerStateStore

    config = _runner_config(args)
    ensure_database()
    store = RunnerStateStore(config.state_dir / "runner-state.json")
    state = store.resume()
    print(json.dumps(state.to_dict(), indent=2, sort_keys=True))
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record development activity in development_ops.activity_events."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="Append an activity event")
    record.add_argument("--run-id", help="Agent run UUID (or DEVELOPMENT_OPS_RUN_ID)")
    record.add_argument("--task-id", help="Task identifier")
    record.add_argument("--agent-name", help="Agent or worker name")
    record.add_argument(
        "--event-type",
        required=True,
        choices=[item.value for item in EventType],
    )
    record.add_argument(
        "--severity",
        default=EventSeverity.INFO.value,
        choices=[item.value for item in EventSeverity],
    )
    record.add_argument("--title", required=True)
    record.add_argument("--summary")
    record.add_argument(
        "--metadata",
        help='JSON object, e.g. \'{"pytest":"passed"}\'',
    )
    record.add_argument("--idempotency-key")
    record.add_argument(
        "--occurred-at",
        help="ISO-8601 timestamp (default: now UTC)",
    )
    record.add_argument("--github-repository")
    record.add_argument("--github-pull-number", type=int)
    record.add_argument("--github-commit-sha")
    record.add_argument("--github-actions-run-url")
    record.add_argument(
        "--notify-slack",
        action="store_true",
        help="Attempt Slack after persist (requires bot token env)",
    )
    record.add_argument(
        "--no-slack",
        action="store_true",
        help="Do not attempt Slack (default for coordinator flows)",
    )
    record.set_defaults(func=record_command)

    confirm = sub.add_parser(
        "confirm-slack",
        help="Record Slack delivery after MCP post",
    )
    confirm.add_argument("--event-id", required=True)
    confirm.add_argument("--channel-id", required=True)
    confirm.add_argument("--message-ts", required=True)
    confirm.add_argument(
        "--duplicate",
        action="store_true",
        help="Mark delivery as duplicate replay",
    )
    confirm.set_defaults(func=confirm_slack_command)

    coordinator = sub.add_parser(
        "coordinator",
        help="Coordinator reconciliation and scheduling",
    )
    coordinator_sub = coordinator.add_subparsers(
        dest="coordinator_command",
        required=True,
    )
    tick = coordinator_sub.add_parser(
        "tick",
        help="Reconcile PRs, attempt auto-merge, select next eligible task",
    )
    tick.add_argument("--run-id", help="Coordinator run UUID")
    tick.add_argument("--github-repository")
    tick.add_argument(
        "--backlog",
        help=f"Backlog YAML (default: {default_backlog_path()})",
    )
    tick.add_argument(
        "--notify-slack",
        action="store_true",
        help="Attempt Slack notifications for recorded events",
    )
    tick.add_argument(
        "--worktrees",
        action="store_true",
        help="Prepare isolated worktrees for claimed tasks and clean up merged ones",
    )
    tick.set_defaults(func=coordinator_tick_command)

    worktree = sub.add_parser(
        "worktree",
        help="Inspect and operate isolated agent worktrees",
    )
    worktree_sub = worktree.add_subparsers(
        dest="worktree_command",
        required=True,
    )
    wt_list = worktree_sub.add_parser("list", help="List registered worktrees")
    wt_list.add_argument("--github-repository")
    wt_list.set_defaults(func=worktree_list_command)

    wt_status = worktree_sub.add_parser(
        "status", help="Show a task's registry row and filesystem state"
    )
    wt_status.add_argument("task_id")
    wt_status.add_argument("--github-repository")
    wt_status.set_defaults(func=worktree_status_command)

    wt_prepare = worktree_sub.add_parser(
        "prepare", help="Create the task's branch and worktree from origin/ai-dev"
    )
    wt_prepare.add_argument("task_id")
    wt_prepare.add_argument("--title", help="Human-readable task title")
    wt_prepare.add_argument("--github-repository")
    wt_prepare.set_defaults(func=worktree_prepare_command)

    wt_launch = worktree_sub.add_parser(
        "launch",
        help="Launch a child agent conversation inside the task's worktree",
    )
    wt_launch.add_argument("task_id")
    wt_launch.add_argument("--title", help="Human-readable task title")
    wt_launch.add_argument(
        "--agent-settings",
        required=True,
        help="Path to a JSON file with the child agent_settings payload",
    )
    wt_launch.add_argument(
        "--instructions", help="Extra instructions appended to the child prompt"
    )
    wt_launch.add_argument("--agent-server-url")
    wt_launch.add_argument("--github-repository")
    wt_launch.set_defaults(func=worktree_launch_command)

    wt_cleanup = worktree_sub.add_parser(
        "cleanup",
        help="Remove a worktree after GitHub confirms its pull request merged",
    )
    wt_cleanup.add_argument("task_id")
    wt_cleanup.add_argument("--github-repository")
    wt_cleanup.set_defaults(func=worktree_cleanup_command)

    runner = sub.add_parser(
        "runner",
        help="Persistent, restart-safe coordinator runner",
    )
    runner_sub = runner.add_subparsers(
        dest="runner_command",
        required=True,
    )
    r_run = runner_sub.add_parser(
        "run", help="Run the coordinator loop until SIGTERM/SIGINT"
    )
    r_run.add_argument("--github-repository")
    r_run.add_argument(
        "--max-ticks",
        type=int,
        default=None,
        help="Stop after N ticks (default: run until signalled)",
    )
    r_run.set_defaults(func=runner_run_command)

    r_once = runner_sub.add_parser(
        "once", help="Run one recovery + tick cycle and exit"
    )
    r_once.add_argument("--github-repository")
    r_once.set_defaults(func=runner_once_command)

    r_status = runner_sub.add_parser(
        "status", help="Read-only runner and coordinator health snapshot"
    )
    r_status.add_argument("--github-repository")
    r_status.set_defaults(func=runner_status_command)

    r_pause = runner_sub.add_parser(
        "pause", help="Durably stop new task claims (running work is preserved)"
    )
    r_pause.add_argument("--by", help="Operator identity for the audit record")
    r_pause.add_argument("--reason", help="Why the runner was paused")
    r_pause.add_argument("--github-repository")
    r_pause.set_defaults(func=runner_pause_command)

    r_resume = runner_sub.add_parser(
        "resume", help="Clear a durable pause and re-enable scheduling"
    )
    r_resume.add_argument("--github-repository")
    r_resume.set_defaults(func=runner_resume_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except PersistenceError:
        return EXIT_PERSISTENCE_FAILED
    except (argparse.ArgumentTypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
