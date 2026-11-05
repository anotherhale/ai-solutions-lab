"""Validate repository conventions for AI Solutions Lab."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = (
    "AGENTS.md",
    "README.md",
    "PROJECT_STATUS.md",
    "ENGINEERING_BACKLOG.md",
    "LICENSE",
    ".gitignore",
    ".editorconfig",
    ".env.example",
    "pyproject.toml",
    "docs/PROJECT_CHARTER.md",
    "docs/ARCHITECTURE.md",
    "docs/DEVELOPMENT_WORKFLOW.md",
    "docs/SECURITY.md",
    "docs/ROADMAP.md",
    "docs/adr/README.md",
    "docs/business/WASATCH_BUSINESS_PROFILE.md",
    "docs/business/WASATCH_DOMAIN_MODEL.md",
    "docs/business/WASATCH_WORKFLOWS.md",
    "docs/architecture/DATA_CONTRACTS.md",
    "docs/architecture/DATABASE_MAPPING.md",
    "docs/architecture/API_CONVENTIONS.md",
    "docs/architecture/IMPLEMENTATION_PLAN.md",
    "docs/architecture/AGENT_OPERATING_MODEL.md",
    "compose.yaml",
    "services/wasatch-api/pyproject.toml",
    ".github/workflows/validate.yml",
)

REQUIRED_DIRECTORIES = (
    "apps",
    "services",
    "libs",
    "docs/adr",
    "docs/architecture",
    "docs/business",
    "docs/case-studies",
    "infrastructure/docker",
    "infrastructure/terraform",
    "data/seed",
    "data/fixtures",
    "data/fixtures/valid",
    "data/fixtures/quality-issues",
    "data/documents",
    "data/schemas",
    "data/schemas/v1",
    "scripts",
    "tests/integration",
    "tests/e2e",
)

REQUIRED_ADRS = (
    "0001-modular-monolith-architecture.md",
    "0002-python-fastapi-backend.md",
    "0003-postgresql-pgvector.md",
    "0004-openai-provider-abstraction.md",
    "0005-docker-compose-local-development.md",
    "0006-laboratory-actor-development-only.md",
    "0008-development-activity-log-schema.md",
    "0009-coordinator-continuity-scheduling.md",
)

ADR_NAME = re.compile(r"^\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
SECRET_ASSIGNMENT = re.compile(
    r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{8,}['\"]"
)
PLACEHOLDER_VALUES = ("replace-me", "changeme", "example", "placeholder", "todo")


def error(errors: list[str], message: str) -> None:
    errors.append(message)


def check_required_paths(errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            error(errors, f"Missing required file: {relative}")
    for relative in REQUIRED_DIRECTORIES:
        if not (ROOT / relative).is_dir():
            error(errors, f"Missing required directory: {relative}")


def check_gitignore(errors: list[str]) -> None:
    gitignore = ROOT / ".gitignore"
    if not gitignore.is_file():
        return
    text = gitignore.read_text(encoding="utf-8")
    if ".env" not in text:
        error(errors, ".gitignore must ignore .env files")


def check_env_example(errors: list[str]) -> None:
    env_example = ROOT / ".env.example"
    if not env_example.is_file():
        return
    for line_number, raw_line in enumerate(
        env_example.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("'\"")
        if not value:
            continue
        lowered = value.lower()
        if any(marker in lowered for marker in PLACEHOLDER_VALUES):
            continue
        if key.endswith(("PASSWORD", "API_KEY", "SECRET", "TOKEN")):
            error(
                errors,
                (
                    f".env.example:{line_number} has a non-placeholder "
                    f"secret-like value for {key}"
                ),
            )


def check_adrs(errors: list[str]) -> None:
    adr_dir = ROOT / "docs" / "adr"
    if not adr_dir.is_dir():
        return
    adr_files = sorted(
        path.name for path in adr_dir.glob("*.md") if path.name != "README.md"
    )
    for name in REQUIRED_ADRS:
        if name not in adr_files:
            error(errors, f"Missing required ADR: {name}")
    for name in adr_files:
        if not ADR_NAME.match(name):
            error(errors, f"ADR filename does not match NNNN-title.md: {name}")


def check_tracked_secret_patterns(errors: list[str]) -> None:
    skip_parts = {".git", ".ruff_cache", ".venv", "node_modules"}
    text_suffixes = {".md", ".py", ".toml", ".yml", ".yaml", ".txt", ".env.example"}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_parts for part in path.parts):
            continue
        if path.suffix not in text_suffixes and path.name not in {".env.example"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            if SECRET_ASSIGNMENT.search(line) and "replace-me" not in line.lower():
                relative = path.relative_to(ROOT)
                error(
                    errors,
                    (
                        f"{relative}:{line_number} looks like a "
                        "committed secret assignment"
                    ),
                )


def main() -> int:
    errors: list[str] = []
    check_required_paths(errors)
    check_gitignore(errors)
    check_env_example(errors)
    check_adrs(errors)
    check_tracked_secret_patterns(errors)

    if errors:
        print("Repository convention checks failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Repository conventions validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
