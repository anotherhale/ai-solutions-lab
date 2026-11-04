from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from wasatch_api.config import get_settings
from wasatch_api.main import create_app
from wasatch_api.shared.database.session import reset_engine
from wasatch_api.shared.seed import seed_valid_fixtures

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]


def _database_url() -> str:
    return os.environ.get(
        "WASATCH_TEST_DATABASE_URL",
        os.environ.get(
            "WASATCH_DATABASE_URL",
            "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch_test",
        ),
    )


@pytest.fixture(scope="session")
def database_url() -> str:
    return _database_url()


def _ensure_database(database_url: str) -> None:
    parsed = make_url(database_url)
    target = parsed.database
    if not target or target in {"wasatch", "postgres"}:
        return
    admin_url = parsed.set(database="wasatch")
    admin_engine = create_engine(
        admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True
    )
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target},
            ).scalar()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{target}"'))
    except Exception as exc:
        pytest.skip(f"PostgreSQL is not available: {exc}")
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    os.environ["WASATCH_DATABASE_URL"] = database_url
    get_settings.cache_clear()
    reset_engine()
    _ensure_database(database_url)
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - skip when DB is down
        pytest.skip(f"PostgreSQL is not available: {exc}")
    alembic_cfg = Config(str(API_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    command.upgrade(alembic_cfg, "head")
    yield engine
    engine.dispose()
    reset_engine()
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def seeded_engine(engine: Engine) -> Engine:
    factory = sessionmaker(bind=engine, autoflush=False)
    session = factory()
    try:
        seed_valid_fixtures(session, REPO_ROOT / "data" / "fixtures" / "valid")
    finally:
        session.close()
    return engine


@pytest.fixture
def db_session(seeded_engine: Engine) -> Iterator[Session]:
    session = sessionmaker(bind=seeded_engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(seeded_engine: Engine) -> Iterator[TestClient]:
    # str(URL) hides the password, so the app would authenticate as "***".
    os.environ["WASATCH_DATABASE_URL"] = seeded_engine.url.render_as_string(
        hide_password=False
    )
    get_settings.cache_clear()
    reset_engine()
    with TestClient(create_app()) as test_client:
        yield test_client
    reset_engine()
    get_settings.cache_clear()
