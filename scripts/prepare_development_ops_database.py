#!/usr/bin/env python3
"""Create the development_ops database and apply Alembic migrations."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "services" / "wasatch-api"

if str(REPO_ROOT / "libs" / "development_ops" / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "libs" / "development_ops" / "src"))

from development_ops.database import (  # noqa: E402
    development_ops_database_url,
    ensure_development_ops_database,
)


def main() -> int:
    database_url = ensure_development_ops_database()
    os.environ["WASATCH_DATABASE_URL"] = database_url
    sys.path.insert(0, str(API_ROOT / "src"))
    from wasatch_api.config import get_settings  # noqa: E402

    get_settings.cache_clear()
    alembic_cfg = Config(str(API_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    command.upgrade(alembic_cfg, "head")
    print(f"development_ops ready at {development_ops_database_url()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
