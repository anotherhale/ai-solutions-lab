"""CLI for recording development activity events."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from development_ops.database import development_ops_database_url
from development_ops.errors import PersistenceError
from development_ops.models import ActivityEventCreate, GitHubReference
from development_ops.recorder import ActivityRecorder, RecordResult
from development_ops.taxonomy import EventSeverity, EventType

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
