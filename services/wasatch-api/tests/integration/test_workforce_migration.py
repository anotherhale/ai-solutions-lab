"""Upgrade and downgrade revision 0004 on the synthetic database."""

from __future__ import annotations

import importlib.util
import os
import uuid

from alembic import command
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from wasatch_api.config import REPO_ROOT, get_settings
from wasatch_api.shared.seed import seed_valid_fixtures

API_ROOT = REPO_ROOT / "services" / "wasatch-api"
REVISION_PATH = API_ROOT / "alembic" / "versions" / "0004_workforce_slice.py"


def _revision():
    spec = importlib.util.spec_from_file_location("revision_0004", REVISION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _alembic_config(engine: Engine) -> Config:
    os.environ["WASATCH_DATABASE_URL"] = engine.url.render_as_string(
        hide_password=False
    )
    get_settings.cache_clear()
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.set_main_option(
        "sqlalchemy.url", engine.url.render_as_string(hide_password=False)
    )
    return config


def _version(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()


def _column(inspector, table: str, name: str) -> dict:
    for column in inspector.get_columns(table):
        if column["name"] == name:
            return column
    raise AssertionError(f"{table}.{name} is missing")


def _is_uuid(column: dict) -> bool:
    return "UUID" in str(column["type"]).upper()


def _is_string(column: dict) -> bool:
    label = str(column["type"]).upper()
    return "CHAR" in label or "STRING" in label or "VARCHAR" in label


def _employee_role(engine: Engine, business_id: str):
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT role_id FROM employees WHERE business_id = :id"),
            {"id": business_id},
        ).scalar()


def _employee_team(engine: Engine, business_id: str):
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT team_id FROM employees WHERE business_id = :id"),
            {"id": business_id},
        ).scalar()


def _has_unique_business_id(inspector, table: str) -> bool:
    for constraint in inspector.get_unique_constraints(table):
        if constraint.get("column_names") == ["business_id"]:
            return True
    for index in inspector.get_indexes(table):
        if index.get("unique") and index.get("column_names") == ["business_id"]:
            return True
    return False


def _reseed(engine: Engine) -> None:
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        seed_valid_fixtures(session, REPO_ROOT / "data" / "fixtures" / "valid")
    finally:
        session.close()


def test_workforce_revision_upgrades_and_downgrades(seeded_engine: Engine) -> None:
    config = _alembic_config(seeded_engine)
    revision = _revision()
    seeded_engine.dispose()
    command.downgrade(config, "0003")
    try:
        assert _version(seeded_engine) == "0003"
        inspector = inspect(seeded_engine)
        names = set(inspector.get_table_names())
        assert "roles" not in names
        assert "teams" not in names
        assert _is_string(_column(inspector, "employees", "role_id"))
        assert _is_string(_column(inspector, "employees", "team_id"))
        assert _employee_role(seeded_engine, "emp_0001") == "role_0001"
        assert _employee_team(seeded_engine, "emp_0001") is None
        assert _employee_role(seeded_engine, "emp_0004") == "role_0004"
        assert _employee_team(seeded_engine, "emp_0004") == "team_0003"

        _assert_upgrade_backfill_rolls_back(seeded_engine, revision)
        assert "roles" not in set(inspect(seeded_engine).get_table_names())

        command.upgrade(config, "0004")
        assert _version(seeded_engine) == "0004"
        upgraded = inspect(seeded_engine)
        for table in ("roles", "teams"):
            assert upgraded.get_pk_constraint(table)["constrained_columns"] == ["id"]
            assert _is_uuid(_column(upgraded, table, "id"))
            assert _has_unique_business_id(upgraded, table)
        assert _is_uuid(_column(upgraded, "employees", "role_id"))
        assert _is_uuid(_column(upgraded, "employees", "team_id"))
        employee_columns = {item["name"] for item in upgraded.get_columns("employees")}
        assert "is_approver" not in employee_columns
        role_keys = [
            fk
            for fk in upgraded.get_foreign_keys("employees")
            if fk.get("referred_table") == "roles"
        ]
        team_keys = [
            fk
            for fk in upgraded.get_foreign_keys("employees")
            if fk.get("referred_table") == "teams"
        ]
        lead_keys = [
            fk
            for fk in upgraded.get_foreign_keys("teams")
            if fk.get("referred_table") == "employees"
        ]
        assert len(role_keys) == 1
        assert role_keys[0]["name"] == "fk_employees_role"
        assert role_keys[0]["constrained_columns"] == ["role_id"]
        assert len(team_keys) == 1
        assert team_keys[0]["name"] == "fk_employees_team"
        assert team_keys[0]["constrained_columns"] == ["team_id"]
        assert len(lead_keys) == 1
        assert lead_keys[0]["name"] == "fk_teams_lead_employee"
        assert _employee_role(seeded_engine, "emp_0001") is None
        assert _employee_team(seeded_engine, "emp_0004") is None
    finally:
        command.upgrade(config, "head")
        _reseed(seeded_engine)

    with seeded_engine.connect() as connection:
        approver = connection.execute(
            text(
                """
                SELECT roles.business_id, roles.is_approver
                FROM employees
                JOIN roles ON roles.id = employees.role_id
                WHERE employees.business_id = 'emp_0001'
                """
            )
        ).one()
        dispatcher_team = connection.execute(
            text(
                """
                SELECT teams.business_id
                FROM employees
                JOIN teams ON teams.id = employees.team_id
                WHERE employees.business_id = 'emp_0004'
                """
            )
        ).scalar()
        roles = connection.execute(text("SELECT count(*) FROM roles")).scalar()
        teams = connection.execute(text("SELECT count(*) FROM teams")).scalar()
    assert tuple(approver) == ("role_0001", True)
    assert dispatcher_team == "team_0003"
    assert roles == 12
    assert teams == 5


def _assert_upgrade_backfill_rolls_back(engine: Engine, revision) -> None:
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                revision.create_role_and_team_tables()
                role_id = uuid.uuid4()
                team_id = uuid.uuid4()
                connection.execute(
                    text(
                        """
                        INSERT INTO roles (
                            id, business_id, name, department, is_approver,
                            created_at, updated_at
                        )
                        VALUES (
                            :id, 'role_0001', 'General Manager', 'management',
                            true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """
                    ),
                    {"id": role_id},
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO teams (
                            id, business_id, name, department, created_at, updated_at
                        )
                        VALUES (
                            :id, 'team_0003', 'Dispatch Desk', 'dispatch',
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """
                    ),
                    {"id": team_id},
                )
                revision.replace_employee_role_column()
                revision.replace_employee_team_column()
                manager_role = connection.execute(
                    text(
                        """
                        SELECT role_id FROM employees WHERE business_id = 'emp_0001'
                        """
                    )
                ).scalar()
                dispatcher_role = connection.execute(
                    text(
                        """
                        SELECT role_id FROM employees WHERE business_id = 'emp_0004'
                        """
                    )
                ).scalar()
                dispatcher_team = connection.execute(
                    text(
                        """
                        SELECT team_id FROM employees WHERE business_id = 'emp_0004'
                        """
                    )
                ).scalar()
                manager_team = connection.execute(
                    text(
                        """
                        SELECT team_id FROM employees WHERE business_id = 'emp_0001'
                        """
                    )
                ).scalar()
                assert manager_role == role_id
                assert dispatcher_role is None
                assert dispatcher_team == team_id
                assert manager_team is None
        finally:
            transaction.rollback()
