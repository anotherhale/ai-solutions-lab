from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
API_ROOT = REPO_ROOT / "services" / "wasatch-api"


def _load(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _load(
    "check_wasatch_api_pytest",
    REPO_ROOT / "scripts" / "check_wasatch_api_pytest.py",
)
CONFTEST = _load("wasatch_api_test_conftest", API_ROOT / "tests" / "conftest.py")


def _case(classname: str, name: str, outcome: str = "passed", message: str = "") -> str:
    body = ""
    if outcome == "skipped":
        body = f'<skipped type="pytest.skip" message="{message}"/>'
    elif outcome == "failed":
        body = '<failure message="assertion"/>'
    elif outcome == "error":
        body = '<error message="fixture setup"/>'
    return (
        f'<testcase classname="{classname}" name="{name}" '
        f'file="{classname.replace(".", "/")}.py">{body}</testcase>'
    )


def _report(cases: list[str]) -> str:
    body = "".join(cases)
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<testsuites><testsuite tests="{len(cases)}">{body}</testsuite></testsuites>'
    )


def test_gate_accepts_ran_database_suites(tmp_path: Path) -> None:
    report_path = tmp_path / "pytest.xml"
    report_path.write_text(
        _report(
            [
                _case("tests.unit.test_config", "test_defaults"),
                _case("tests.integration.test_seed_and_schema", "test_vector"),
                _case("tests.api.test_health_and_resources", "test_ready"),
            ]
        ),
        encoding="utf-8",
    )
    report = CHECKER.parse_junit(report_path)
    assert CHECKER.gate_errors(report) == []
    assert CHECKER.format_counts(report) == (
        "passed: 3\nfailed: 0\nskipped: 0\nerrors: 0\n"
    )
    assert CHECKER.main([str(report_path)]) == 0


def test_gate_rejects_skipped_required_suite(tmp_path: Path, capsys) -> None:
    report_path = tmp_path / "pytest.xml"
    report_path.write_text(
        _report(
            [
                _case("tests.unit.test_config", "test_defaults"),
                _case(
                    "tests.integration.test_seed_and_schema",
                    "test_vector",
                    "skipped",
                    "PostgreSQL is not available: database wasatch does not exist",
                ),
                _case(
                    "tests.api.test_health_and_resources",
                    "test_ready",
                    "skipped",
                    "PostgreSQL is not available: database wasatch does not exist",
                ),
            ]
        ),
        encoding="utf-8",
    )
    assert CHECKER.main([str(report_path)]) == 1
    captured = capsys.readouterr().out
    assert "skipped required test: tests.integration.test_seed_and_schema::" in captured
    assert "required integration tests were skipped" in captured
    assert "required api tests were skipped" in captured
    assert "passed: 1\nfailed: 0\nskipped: 2\nerrors: 0\n" in captured


def test_gate_rejects_a_partial_skip_and_a_missing_suite(tmp_path: Path) -> None:
    partial = tmp_path / "partial.xml"
    partial.write_text(
        _report(
            [
                _case("tests.integration.test_seed_and_schema", "test_vector"),
                _case(
                    "tests.integration.test_seed_and_schema",
                    "test_tables",
                    "skipped",
                    "skipped by environment",
                ),
                _case("tests.api.test_health_and_resources", "test_ready"),
            ]
        ),
        encoding="utf-8",
    )
    problems = CHECKER.gate_errors(CHECKER.parse_junit(partial))
    assert "required integration tests were skipped" in problems
    assert "required api tests did not run" not in problems

    missing = tmp_path / "missing.xml"
    missing.write_text(
        _report([_case("tests.unit.test_config", "test_defaults")]),
        encoding="utf-8",
    )
    problems = CHECKER.gate_errors(CHECKER.parse_junit(missing))
    assert "required integration tests did not run" in problems
    assert "required api tests did not run" in problems


def test_gate_rejects_failures_without_hiding_counts(tmp_path: Path, capsys) -> None:
    report_path = tmp_path / "pytest.xml"
    report_path.write_text(
        _report(
            [
                _case("tests.integration.test_seed_and_schema", "test_vector", "error"),
                _case("tests.api.test_health_and_resources", "test_ready", "failed"),
            ]
        ),
        encoding="utf-8",
    )
    assert CHECKER.main([str(report_path)]) == 1
    captured = capsys.readouterr().out
    assert "pytest reported failures" in captured
    assert "passed: 0\nfailed: 1\nskipped: 0\nerrors: 1\n" in captured


def test_missing_report_fails(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "absent.xml"
    assert CHECKER.main([str(missing)]) == 1
    captured = capsys.readouterr()
    assert "pytest report not found" in captured.err
    assert "passed: 0\nfailed: 0\nskipped: 0\nerrors: 0\n" in captured.out


def test_workflow_requires_postgres_and_the_skip_gate() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "validate.yml").read_text(
        encoding="utf-8"
    )
    assert "image: pgvector/pgvector:pg16" in workflow
    assert "POSTGRES_DB: wasatch\n" in workflow
    assert 'pg_isready -U wasatch -d wasatch"' in workflow
    assert 'WASATCH_REQUIRE_DATABASE: "1"' in workflow
    assert "check_wasatch_api_pytest.py" in workflow
    assert "--junitxml=" in workflow
    assert "pytest -ra" in workflow
    assert "continue-on-error" not in workflow
    assert "wasatch_test" in workflow


def test_missing_maintenance_database_is_not_a_down_server() -> None:
    class MissingDatabase(Exception):
        def __init__(self) -> None:
            super().__init__('database "wasatch" does not exist')
            self.sqlstate = "3D000"

    assert CONFTEST._missing_database(MissingDatabase()) is True
    wrapped = Exception("admin connection failed")
    wrapped.__cause__ = MissingDatabase()
    assert CONFTEST._missing_database(wrapped) is True
    assert CONFTEST._missing_database(ConnectionRefusedError("111")) is False


def test_local_skip_and_ci_failure_stay_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WASATCH_REQUIRE_DATABASE", raising=False)
    with pytest.raises(pytest.skip.Exception, match="PostgreSQL is not available"):
        CONFTEST._database_unavailable(ConnectionRefusedError("down"))

    monkeypatch.setenv("WASATCH_REQUIRE_DATABASE", "1")
    with pytest.raises(pytest.fail.Exception, match="PostgreSQL is not available"):
        CONFTEST._database_unavailable(ConnectionRefusedError("down"))
