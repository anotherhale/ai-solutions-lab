"""Liveness and readiness."""

from __future__ import annotations

from fastapi import APIRouter, Response
from sqlalchemy import text

from wasatch_api.shared.database.session import get_engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "wasatch-api"}


@router.get("/health/ready")
def ready(response: Response) -> dict[str, str]:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        response.status_code = 503
        return {"status": "unavailable", "database": "down"}
    return {"status": "ready", "database": "up"}
