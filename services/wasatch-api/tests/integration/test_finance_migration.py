"""Upgrade and downgrade revision 0008 on the synthetic database."""

from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from wasatch_api.config import REPO_ROOT, get_settings
from wasatch_api.shared.seed import seed_valid_fixtures

API_ROOT = REPO_ROOT / "services" / "wasatch-api"


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


def _invoice_business_id(engine: Engine, work_order_id: str) -> str | None:
    with engine.connect() as connection:
        return connection.execute(
            text(
                """
                SELECT inv.business_id
                FROM work_orders AS wo
                LEFT JOIN invoices AS inv ON inv.id = wo.invoice_id
                WHERE wo.business_id = :work_order_id
                """
            ),
            {"work_order_id": work_order_id},
        ).scalar()


def _string_invoice_id(engine: Engine, work_order_id: str) -> str | None:
    with engine.connect() as connection:
        return connection.execute(
            text(
                """
                SELECT invoice_id
                FROM work_orders
                WHERE business_id = :work_order_id
                """
            ),
            {"work_order_id": work_order_id},
        ).scalar()


def _reseed(engine: Engine) -> None:
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        seed_valid_fixtures(session, REPO_ROOT / "data" / "fixtures" / "valid")
        session.commit()
    finally:
        session.close()


def test_finance_revision_upgrades_and_downgrades(seeded_engine: Engine) -> None:
    config = _alembic_config(seeded_engine)
    assert _version(seeded_engine) == "0008"
    assert _invoice_business_id(seeded_engine, "wo_0028") == "inv_0005"
    seeded_engine.dispose()
    command.downgrade(config, "0007")
    try:
        assert _version(seeded_engine) == "0007"
        names = set(inspect(seeded_engine).get_table_names())
        assert "invoices" not in names
        assert "invoice_lines" not in names
        assert "payments" not in names
        column = _column(inspect(seeded_engine), "work_orders", "invoice_id")
        assert _is_string(column)
        assert _string_invoice_id(seeded_engine, "wo_0028") == "inv_0005"
        document_invoice = _column(inspect(seeded_engine), "documents", "invoice_id")
        assert _is_string(document_invoice)

        command.upgrade(config, "0008")
        assert _version(seeded_engine) == "0008"
        upgraded = inspect(seeded_engine)
        assert {"invoices", "invoice_lines", "payments"} <= set(
            upgraded.get_table_names()
        )
        invoice_column = _column(upgraded, "work_orders", "invoice_id")
        assert _is_uuid(invoice_column)
        foreign_keys = [
            fk
            for fk in upgraded.get_foreign_keys("work_orders")
            if fk.get("name") == "fk_work_orders_invoice"
        ]
        assert len(foreign_keys) == 1
        assert foreign_keys[0]["referred_table"] == "invoices"
        assert foreign_keys[0]["constrained_columns"] == ["invoice_id"]
        document_keys = [
            fk
            for fk in upgraded.get_foreign_keys("documents")
            if "invoice_id" in fk.get("constrained_columns", [])
        ]
        assert document_keys == []
        assert _is_string(_column(upgraded, "documents", "invoice_id"))
        with seeded_engine.connect() as connection:
            empty = connection.execute(text("SELECT count(*) FROM invoices")).scalar()
        assert empty == 0
        assert _invoice_business_id(seeded_engine, "wo_0028") is None
    finally:
        command.upgrade(config, "head")
        _reseed(seeded_engine)

    assert _version(seeded_engine) == "0008"
    assert _invoice_business_id(seeded_engine, "wo_0028") == "inv_0005"
    with seeded_engine.connect() as connection:
        invoices = connection.execute(text("SELECT count(*) FROM invoices")).scalar()
        lines = connection.execute(text("SELECT count(*) FROM invoice_lines")).scalar()
        payments = connection.execute(text("SELECT count(*) FROM payments")).scalar()
    assert invoices == 30
    assert lines == 40
    assert payments == 20
