"""Upgrade and downgrade revision 0006 on the synthetic database."""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from wasatch_api.ai.infrastructure.fake import FakeModelPort
from wasatch_api.config import REPO_ROOT, get_settings
from wasatch_api.shared.database.vector import PROCEDURE_EMBEDDING_WIDTH

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


def test_procedure_embedding_revision_upgrades_and_downgrades(engine: Engine) -> None:
    config = _alembic_config(engine)
    engine.dispose()
    try:
        command.downgrade(config, "0005")
        assert _version(engine) == "0005"
        assert "procedure_page_embeddings" not in set(inspect(engine).get_table_names())
        assert "documents" in set(inspect(engine).get_table_names())

        command.upgrade(config, "0006")
        assert _version(engine) == "0006"
        upgraded = inspect(engine)
        assert "procedure_page_embeddings" in set(upgraded.get_table_names())
        assert upgraded.get_pk_constraint("procedure_page_embeddings")[
            "constrained_columns"
        ] == ["id"]
        column_type = _embedding_type(engine)
        port_width = len(FakeModelPort().embed(("synthetic procedure page",))[0].vector)
        assert column_type == f"vector({port_width})"
        assert port_width == PROCEDURE_EMBEDDING_WIDTH == 8
        _assert_extraction_id_is_rejected(engine)
        _assert_document_tables_have_no_vector(engine)
    finally:
        command.upgrade(config, "head")
        get_settings.cache_clear()


def _embedding_type(engine: Engine) -> str:
    with engine.connect() as connection:
        label = connection.execute(
            text(
                """
                SELECT format_type(atttypid, atttypmod)
                FROM pg_attribute
                WHERE attrelid = 'procedure_page_embeddings'::regclass
                  AND attname = 'embedding'
                  AND NOT attisdropped
                """
            )
        ).scalar()
    assert isinstance(label, str)
    return label


def _assert_extraction_id_is_rejected(engine: Engine) -> None:
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        """
                        INSERT INTO procedure_page_embeddings (
                            id,
                            procedure_id,
                            embedding_model,
                            embedding,
                            token_count,
                            embedded_at
                        )
                        VALUES (
                            CAST('00000000-0000-0000-0000-000000000001' AS uuid),
                            'dx_0001',
                            'fake-embedding',
                            CAST('[0,0,0,0,0,0,0,0]' AS vector),
                            1,
                            CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
        finally:
            transaction.rollback()


def _assert_document_tables_have_no_vector(engine: Engine) -> None:
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
    assert rows == []
