"""Upgrade and downgrade revision 0008 on the synthetic database."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from wasatch_api.config import REPO_ROOT, get_settings
from wasatch_api.shared.database.models import WorkOrderORM
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


def _reseed(engine: Engine) -> None:
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        seed_valid_fixtures(session, REPO_ROOT / "data" / "fixtures" / "valid")
    finally:
        session.close()


def test_invoice_revision_upgrades_and_downgrades(seeded_engine: Engine) -> None:
    config = _alembic_config(seeded_engine)
    seeded_engine.dispose()
    with seeded_engine.connect() as connection:
        count = connection.execute(text("SELECT count(*) FROM invoices")).scalar()
    assert count == 30
    inspector = inspect(seeded_engine)
    foreign_keys = inspector.get_foreign_keys("work_orders")
    assert any(
        fk.get("name") == "fk_work_orders_invoice"
        and fk.get("referred_table") == "invoices"
        for fk in foreign_keys
    )

    command.downgrade(config, "0007")
    try:
        assert _version(seeded_engine) == "0007"
        names = set(inspect(seeded_engine).get_table_names())
        assert "invoices" not in names
        command.upgrade(config, "0008")
        assert _version(seeded_engine) == "0008"
        assert "invoices" in set(inspect(seeded_engine).get_table_names())
    finally:
        command.upgrade(config, "head")
        _reseed(seeded_engine)


def test_work_order_invoice_foreign_key_is_enforced(db_session) -> None:
    work_order_id = db_session.execute(
        text("SELECT id FROM work_orders WHERE business_id = 'wo_0001'")
    ).scalar_one()
    template = db_session.get(WorkOrderORM, work_order_id)
    assert template is not None
    now = datetime.now(tz=UTC)
    bad = WorkOrderORM(
        id=uuid.uuid4(),
        business_id="wo_9998",
        customer_id=template.customer_id,
        service_location_id=template.service_location_id,
        status="created",
        priority="normal",
        work_type="service",
        summary="invalid invoice link",
        opened_at=now,
        created_at=now,
        updated_at=now,
        invoice_id="inv_9999",
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
