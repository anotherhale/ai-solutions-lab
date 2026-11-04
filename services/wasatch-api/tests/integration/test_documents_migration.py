"""Upgrade and downgrade revision 0005 on the synthetic database."""

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


def _vector_columns(engine: Engine) -> list[tuple]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name IN (
                        'documents',
                        'document_versions',
                        'document_extractions'
                  )
                  AND udt_name = 'vector'
                """
            )
        ).all()
    return list(rows)


def test_documents_revision_upgrades_and_downgrades(seeded_engine: Engine) -> None:
    config = _alembic_config(seeded_engine)
    seeded_engine.dispose()
    command.downgrade(config, "0004")
    try:
        assert _version(seeded_engine) == "0004"
        inspector = inspect(seeded_engine)
        names = set(inspector.get_table_names())
        assert "documents" not in names
        assert "document_versions" not in names
        assert "document_extractions" not in names
        assert "customers" in names
        assert "support_tickets" in names

        command.upgrade(config, "0005")
        assert _version(seeded_engine) == "0005"
        upgraded = inspect(seeded_engine)
        upgraded_names = set(upgraded.get_table_names())
        assert {
            "documents",
            "document_versions",
            "document_extractions",
        } <= upgraded_names
        for table in ("documents", "document_versions", "document_extractions"):
            assert upgraded.get_pk_constraint(table)["constrained_columns"] == ["id"]
            assert _is_uuid(_column(upgraded, table, "id"))
            assert _has_unique_business_id(upgraded, table)
        assert _is_string(_column(upgraded, "documents", "invoice_id"))
        invoice_keys = [
            fk
            for fk in upgraded.get_foreign_keys("documents")
            if "invoice_id" in fk.get("constrained_columns", [])
        ]
        assert invoice_keys == []
        assert (
            "JSONB"
            in str(
                _column(upgraded, "document_extractions", "extracted_fields")["type"]
            ).upper()
        )
        version_uniques = upgraded.get_unique_constraints("document_versions")
        assert any(
            constraint.get("column_names") == ["document_id", "version_number"]
            for constraint in version_uniques
        )
        current_keys = [
            fk
            for fk in upgraded.get_foreign_keys("documents")
            if fk.get("name") == "fk_documents_current_version"
        ]
        assert len(current_keys) == 1
        assert current_keys[0]["referred_table"] == "document_versions"
        assert _vector_columns(seeded_engine) == []
        with seeded_engine.connect() as connection:
            empty = connection.execute(text("SELECT count(*) FROM documents")).scalar()
        assert empty == 0
    finally:
        command.upgrade(config, "head")
        _reseed(seeded_engine)

    with seeded_engine.connect() as connection:
        documents = connection.execute(text("SELECT count(*) FROM documents")).scalar()
        versions = connection.execute(
            text("SELECT count(*) FROM document_versions")
        ).scalar()
        extractions = connection.execute(
            text("SELECT count(*) FROM document_extractions")
        ).scalar()
        current = connection.execute(
            text(
                """
                SELECT versions.business_id
                FROM documents
                JOIN document_versions AS versions
                  ON versions.id = documents.current_version_id
                WHERE documents.business_id = 'doc_0004'
                """
            )
        ).scalar()
    assert documents == 30
    assert versions == 31
    assert extractions == 18
    assert current == "dv_0031"
    assert _version(seeded_engine) == "0007"
    assert "follow_up_visits" in set(inspect(seeded_engine).get_table_names())
    assert _vector_columns(seeded_engine) == []
