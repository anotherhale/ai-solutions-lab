"""Roll back writes made through the API during one test.

Audit events are insert-only, so a committed decision cannot be removed
without fighting the database trigger. The outer transaction keeps the seeded
counts stable for the rest of the suite.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def decision_transaction(
    seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    connection = seeded_engine.connect()
    transaction = connection.begin()
    factory = sessionmaker(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    def _factory(settings: object = None) -> sessionmaker:
        return factory

    monkeypatch.setattr("wasatch_api.api.middleware.get_session_factory", _factory)
    monkeypatch.setattr("wasatch_api.api.dependencies.get_session_factory", _factory)
    try:
        yield
    finally:
        transaction.rollback()
        connection.close()
