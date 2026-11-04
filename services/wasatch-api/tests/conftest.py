from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import NoReturn

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
from wasatch_api.workforce.infrastructure.local_authenticator import (
    LABORATORY_ACTOR_HEADER,
)

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


def _database_required() -> bool:
    return os.environ.get("WASATCH_REQUIRE_DATABASE") == "1"


def _sqlstate(exc: BaseException) -> str | None:
    sqlstate = getattr(exc, "sqlstate", None)
    if sqlstate:
        return str(sqlstate)
    origin = getattr(exc, "orig", None)
    if origin is not None and origin is not exc:
        nested = getattr(origin, "sqlstate", None)
        if nested:
            return str(nested)
    return None


def _missing_database(exc: Exception) -> bool:
    """True when the server is up but the named database is absent."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if _sqlstate(current) == "3D000":
            return True
        current = current.__cause__ or current.__context__
    message = str(exc).lower()
    return "database" in message and "does not exist" in message


def _database_unavailable(exc: Exception) -> NoReturn:
    # Local runs skip when PostgreSQL is down. CI must fail instead.
    message = f"PostgreSQL is not available: {exc}"
    if _database_required():
        pytest.fail(message, pytrace=False)
    pytest.skip(message)


def _ensure_database(database_url: str) -> None:
    parsed = make_url(database_url)
    target = parsed.database
    if not target or target in {"wasatch", "postgres"}:
        return
    # Compose keeps maintenance data in "wasatch". The stock image also
    # has "postgres". A missing maintenance database is not a down server.
    for admin_name in ("wasatch", "postgres"):
        if admin_name == target:
            continue
        admin_engine = create_engine(
            parsed.set(database=admin_name),
            isolation_level="AUTOCOMMIT",
            pool_pre_ping=True,
        )
        try:
            with admin_engine.connect() as connection:
                exists = connection.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :name"),
                    {"name": target},
                ).scalar()
                if not exists:
                    connection.execute(text(f'CREATE DATABASE "{target}"'))
            return
        except Exception as exc:
            if _missing_database(exc):
                continue
            return
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
    except Exception as exc:  # local skip when PostgreSQL is down; CI fails
        _database_unavailable(exc)
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


def _bind_app_database(seeded_engine: Engine) -> None:
    # str(URL) hides the password, so the app would authenticate as "***".
    os.environ["WASATCH_DATABASE_URL"] = seeded_engine.url.render_as_string(
        hide_password=False
    )
    get_settings.cache_clear()
    reset_engine()


@pytest.fixture
def client(seeded_engine: Engine) -> Iterator[TestClient]:
    _bind_app_database(seeded_engine)
    with TestClient(create_app()) as test_client:
        test_client.headers.update({LABORATORY_ACTOR_HEADER: "emp_0001"})
        yield test_client
    reset_engine()
    get_settings.cache_clear()


@pytest.fixture
def anonymous_client(seeded_engine: Engine) -> Iterator[TestClient]:
    _bind_app_database(seeded_engine)
    with TestClient(create_app()) as test_client:
        yield test_client
    reset_engine()
    get_settings.cache_clear()
