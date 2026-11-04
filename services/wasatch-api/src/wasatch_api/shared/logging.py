"""Structured logs for laboratory access.

Records include actor, action, subject, and outcome. They do not include
message bodies, contact details, or secrets.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from wasatch_api.workforce.application.access import AccessDecision

_LOGGER = logging.getLogger("wasatch_api.access")


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "actor": getattr(record, "actor", None),
            "action": getattr(record, "action", None),
            "subject": getattr(record, "subject", None),
            "outcome": getattr(record, "outcome", None),
        }
        return json.dumps(payload, default=str)


def configure_logging(level_name: str) -> None:
    level = logging.getLevelNamesMapping().get(level_name.upper(), logging.INFO)
    logger = logging.getLogger("wasatch_api")
    # Alembic fileConfig disables loggers that already exist. Turn them back on.
    logger.disabled = False
    _LOGGER.disabled = False
    _LOGGER.setLevel(logging.NOTSET)
    logger.handlers.clear()
    logger.setLevel(level)
    logger.propagate = False
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    logger.addHandler(handler)


def log_access(decision: AccessDecision) -> None:
    actor = decision.actor.employee_id if decision.actor is not None else None
    _LOGGER.info(
        "laboratory access",
        extra={
            "actor": actor,
            "action": decision.action,
            "subject": decision.subject,
            "outcome": decision.outcome,
        },
    )
