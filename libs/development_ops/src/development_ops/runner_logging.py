"""Structured logging for the persistent coordinator runner.

JSON is the default so launchd ``StandardOutPath``/``StandardErrorPath`` capture
machine-readable records. A ``text`` format is available for interactive use.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_EXTRA_FIELDS = (
    "event",
    "lock_path",
    "pid",
    "hostname",
    "signal",
    "error",
    "ticks",
    "tick",
)


class JsonFormatter(logging.Formatter):
    """Render each record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for name in _EXTRA_FIELDS:
            value = getattr(record, name, None)
            if value is not None:
                payload[name] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(
    *, level: str = "INFO", fmt: str = "json", stream: Any = None
) -> logging.Logger:
    """Configure the runner logger and return it.

    The handler is written to ``stderr`` by default so launchd's error path
    captures lifecycle records alongside any traceback.
    """
    logger = logging.getLogger("development_ops.coordinator.runner")
    logger.setLevel(level.upper())
    for existing in list(logger.handlers):
        logger.removeHandler(existing)
    handler = logging.StreamHandler(stream or sys.stderr)
    if fmt.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
    logger.addHandler(handler)
    logger.propagate = False
    return logger
