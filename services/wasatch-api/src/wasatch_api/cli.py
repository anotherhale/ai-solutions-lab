"""Command-line entry points for seed and local operations."""

from __future__ import annotations

import argparse
import json
import sys

from wasatch_api.config import get_settings
from wasatch_api.shared.database.session import get_session_factory
from wasatch_api.shared.seed import SeedError, seed_valid_fixtures


def seed() -> int:
    settings = get_settings()
    session = get_session_factory(settings)()
    try:
        counts = seed_valid_fixtures(session, settings.resolved_fixtures_dir())
    except SeedError as exc:
        session.rollback()
        print(f"seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()
    print(json.dumps({"synthetic": True, "counts": counts}, indent=2))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Wasatch laboratory API commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("seed", help="Load valid synthetic fixtures")
    args = parser.parse_args()
    if args.command == "seed":
        raise SystemExit(seed())
    parser.error(f"unknown command {args.command}")


if __name__ == "__main__":
    main()
