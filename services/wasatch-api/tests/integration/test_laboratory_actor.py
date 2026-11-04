"""Role authority comes from the persisted role, not from team membership."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from wasatch_api.shared.database.models import EmployeeORM
from wasatch_api.shared.errors import AuthorizationDenied
from wasatch_api.workforce.domain.authorization import authorize_approval_decision
from wasatch_api.workforce.infrastructure.repository import EmployeeDirectory


def test_non_approver_role_cannot_decide_an_approval(db_session: Session) -> None:
    directory = EmployeeDirectory(db_session)
    dispatcher = directory.find_actor("emp_0004")
    assert dispatcher is not None
    assert dispatcher.role_id == "role_0004"
    assert dispatcher.is_approver is False
    with pytest.raises(AuthorizationDenied, match="role role_0004"):
        authorize_approval_decision(dispatcher)

    manager = directory.find_actor("emp_0001")
    assert manager is not None
    assert manager.role_id == "role_0001"
    assert manager.is_approver is True
    authorize_approval_decision(manager)
    manager_team = db_session.execute(
        text("SELECT team_id FROM employees WHERE business_id = 'emp_0001'")
    ).scalar()
    assert manager_team is None


def test_terminated_employee_is_not_a_laboratory_actor(db_session: Session) -> None:
    employee = db_session.scalar(
        select(EmployeeORM).where(EmployeeORM.business_id == "emp_0004")
    )
    assert employee is not None
    employee.status = "terminated"
    db_session.flush()
    try:
        assert EmployeeDirectory(db_session).find_actor("emp_0004") is None
    finally:
        db_session.rollback()
