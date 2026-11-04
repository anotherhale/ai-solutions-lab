#!/usr/bin/env python3
"""Fail CI when Wasatch API database tests did not actually run.

GitHub Actions used to report a green Wasatch API job while pytest skipped
the integration and API suites. This gate reads a JUnit report and rejects
that outcome. Local pytest does not invoke this script, so a workstation
without PostgreSQL can still skip those tests.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

REQUIRED_SUITES = ("integration", "api")


@dataclass
class SuiteCounts:
    ran: int = 0
    skipped: int = 0


@dataclass
class PytestReport:
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    suites: dict[str, SuiteCounts] = field(default_factory=dict)
    skipped_required: list[tuple[str, str]] = field(default_factory=list)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _suite_name(classname: str, filename: str) -> str | None:
    normalized = f"{classname} {filename}".replace(".", "/").replace("\\", "/")
    padded = f"{normalized}/"
    for suite in REQUIRED_SUITES:
        if f"tests/{suite}/" in padded:
            return suite
    return None


def parse_junit(path: Path) -> PytestReport:
    root = ET.parse(path).getroot()
    report = PytestReport()
    for element in root.iter():
        if _local_name(element.tag) != "testcase":
            continue
        classname = element.attrib.get("classname", "")
        filename = element.attrib.get("file", "")
        name = element.attrib.get("name", "")
        node = f"{classname}::{name}" if classname else name
        outcome = "passed"
        skip_message = ""
        for child in list(element):
            kind = _local_name(child.tag)
            if kind == "error":
                outcome = "error"
            elif kind == "failure" and outcome != "error":
                outcome = "failed"
            elif kind == "skipped" and outcome == "passed":
                outcome = "skipped"
                skip_message = child.attrib.get("message", "").strip()
        if outcome == "passed":
            report.passed += 1
        elif outcome == "failed":
            report.failed += 1
        elif outcome == "error":
            report.errors += 1
        else:
            report.skipped += 1
        suite = _suite_name(classname, filename)
        if suite is None:
            continue
        counts = report.suites.setdefault(suite, SuiteCounts())
        if outcome == "skipped":
            counts.skipped += 1
            report.skipped_required.append((node, skip_message))
        else:
            counts.ran += 1
    return report


def gate_errors(report: PytestReport) -> list[str]:
    problems: list[str] = []
    for node, message in report.skipped_required:
        detail = f": {message}" if message else ""
        problems.append(f"skipped required test: {node}{detail}")
    for suite in REQUIRED_SUITES:
        counts = report.suites.get(suite, SuiteCounts())
        if counts.skipped:
            problems.append(f"required {suite} tests were skipped")
        if counts.ran == 0:
            problems.append(f"required {suite} tests did not run")
    if report.failed or report.errors:
        problems.append("pytest reported failures")
    if report.passed + report.failed + report.errors + report.skipped == 0:
        problems.append("pytest report contained no tests")
    return problems


def format_counts(report: PytestReport) -> str:
    return (
        f"passed: {report.passed}\n"
        f"failed: {report.failed}\n"
        f"skipped: {report.skipped}\n"
        f"errors: {report.errors}\n"
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(
            "usage: check_wasatch_api_pytest.py pytest-report.xml",
            file=sys.stderr,
        )
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"pytest report not found: {path}", file=sys.stderr)
        print("passed: 0")
        print("failed: 0")
        print("skipped: 0")
        print("errors: 0")
        return 1
    try:
        report = parse_junit(path)
    except ET.ParseError as exc:
        print(f"pytest report is not valid XML: {exc}", file=sys.stderr)
        return 1
    problems = gate_errors(report)
    for problem in problems:
        print(problem)
    sys.stdout.write(format_counts(report))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
