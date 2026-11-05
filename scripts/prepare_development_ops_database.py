#!/usr/bin/env python3
"""Ensure the development_ops PostgreSQL database exists and is migrated."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "libs" / "development_ops" / "src"))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from development_ops.database import (  # noqa: E402
    development_ops_database_url,
    ensure_development_ops_database,
)


def main() -> int:
    url = ensure_development_ops_database()
    os.environ["WASATCH_DATABASE_URL"] = url
    api_root = REPO_ROOT / "services" / "wasatch-api"
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    print(f"development_ops database ready at {development_ops_database_url()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
