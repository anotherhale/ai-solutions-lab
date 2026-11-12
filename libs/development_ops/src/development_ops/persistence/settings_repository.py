"""Durable orchestration settings (child-execution enablement).

The enable/disable decision lives in ``development_ops.orchestration_settings``,
not in an environment variable, so it survives coordinator restarts and cannot
be flipped by an exported variable or a service environment file. An absent row
is treated as disabled: child execution is off unless an operator has explicitly
enabled it.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from development_ops.persistence.orm import OrchestrationSettingORM

CHILD_EXECUTION_ENABLED = "child_execution_enabled"


@dataclass(frozen=True, slots=True)
class SettingRecord:
    key: str
    value: dict
    updated_at: str | None


class OrchestrationSettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: str) -> dict | None:
        row = self._session.get(OrchestrationSettingORM, key)
        return dict(row.value) if row is not None else None

    def set(self, key: str, value: dict) -> SettingRecord:
        row = self._session.get(OrchestrationSettingORM, key)
        if row is None:
            row = OrchestrationSettingORM(key=key, value=value)
            self._session.add(row)
        else:
            row.value = value
        self._session.commit()
        self._session.refresh(row)
        return SettingRecord(
            key=row.key,
            value=dict(row.value),
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
        )

    # -- child execution flag ---------------------------------------------

    def child_execution_enabled(self) -> bool:
        """The durable operator flag. Absent row means disabled."""
        value = self.get(CHILD_EXECUTION_ENABLED)
        if value is None:
            return False
        return bool(value.get("enabled", False))

    def set_child_execution_enabled(
        self,
        enabled: bool,
        *,
        by: str | None = None,
        reason: str | None = None,
    ) -> SettingRecord:
        payload: dict = {"enabled": enabled}
        if by:
            payload["by"] = by
        if reason:
            payload["reason"] = reason
        return self.set(CHILD_EXECUTION_ENABLED, payload)

    def list_settings(self) -> list[SettingRecord]:
        stmt = select(OrchestrationSettingORM).order_by(OrchestrationSettingORM.key)
        return [
            SettingRecord(
                key=row.key,
                value=dict(row.value),
                updated_at=row.updated_at.isoformat() if row.updated_at else None,
            )
            for row in self._session.scalars(stmt).all()
        ]
