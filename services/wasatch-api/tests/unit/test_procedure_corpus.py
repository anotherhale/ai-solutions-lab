from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from wasatch_api.customer_service.infrastructure.procedure_corpus import (
    CORPUS_NAME,
    SYNTHETIC_LABEL,
    ProcedureCorpus,
    ProcedureCorpusError,
    content_terms,
)

PACKAGE = (
    Path(__file__).resolve().parents[2] / "src" / "wasatch_api" / "customer_service"
)
RETRIEVAL_FILES = (
    PACKAGE / "application" / "ports.py",
    PACKAGE / "application" / "retrieval.py",
    PACKAGE / "domain" / "retrieval.py",
    PACKAGE / "infrastructure" / "procedure_corpus.py",
    PACKAGE / "infrastructure" / "relational_retrieval.py",
)
BANNED_IMPORTS = {"openai", "httpx", "urllib", "requests", "anthropic", "socket"}
ROOFTOP_INQUIRY = (
    "Service request related to wo_0015\n"
    "Please send a technician. Rooftop unit is down."
)


def test_shipped_corpus_matches_rooftop_inquiry_only() -> None:
    corpus = ProcedureCorpus.load_default()
    pages = corpus.matching_pages(ROOFTOP_INQUIRY)
    assert [page.id for page in pages] == ["proc_0001"]
    page = pages[0]
    assert page.synthetic is True
    assert page.path == "rooftop-unit-down.txt"
    assert page.text.startswith(SYNTHETIC_LABEL)
    assert "rooftop" in page.text.lower()
    assert content_terms(ROOFTOP_INQUIRY) == {"rooftop"}


def test_other_procedure_pages_match_their_own_words() -> None:
    corpus = ProcedureCorpus.load_default()
    boiler = corpus.matching_pages("The boiler is in lockout.")
    filters = corpus.matching_pages("Schedule a filter replacement.")
    assert [page.id for page in boiler] == ["proc_0002"]
    assert [page.id for page in filters] == ["proc_0003"]


def test_generic_inquiry_words_do_not_match_every_page() -> None:
    corpus = ProcedureCorpus.load_default()
    assert corpus.matching_pages("Service request related to wo_0001") == ()


def test_catalog_must_be_labeled_synthetic(tmp_path: Path) -> None:
    _write_page(tmp_path, "rooftop-unit-down.txt")
    catalog = {
        "synthetic": False,
        "corpus": CORPUS_NAME,
        "pages": [
            {
                "id": "proc_0001",
                "title": "Rooftop unit is down",
                "path": "rooftop-unit-down.txt",
            }
        ],
    }
    (tmp_path / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(ProcedureCorpusError, match="synthetic"):
        ProcedureCorpus.load(tmp_path)


def test_page_file_must_carry_the_synthetic_label(tmp_path: Path) -> None:
    (tmp_path / "rooftop-unit-down.txt").write_text(
        "Rooftop unit is down.\n", encoding="utf-8"
    )
    _write_catalog(tmp_path)
    with pytest.raises(ProcedureCorpusError, match="labeled synthetic"):
        ProcedureCorpus.load(tmp_path)


def test_page_path_cannot_escape_the_corpus(tmp_path: Path) -> None:
    _write_catalog(tmp_path, path="../secret.txt")
    with pytest.raises(ProcedureCorpusError, match="file name"):
        ProcedureCorpus.load(tmp_path)


def test_retrieval_modules_do_not_import_a_network_client() -> None:
    for path in RETRIEVAL_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        assert imported.isdisjoint(BANNED_IMPORTS)


def _write_page(directory: Path, name: str) -> None:
    (directory / name).write_text(
        f"{SYNTHETIC_LABEL}\nRooftop unit is down.\n", encoding="utf-8"
    )


def _write_catalog(directory: Path, *, path: str = "rooftop-unit-down.txt") -> None:
    catalog = {
        "synthetic": True,
        "corpus": CORPUS_NAME,
        "pages": [{"id": "proc_0001", "title": "Rooftop unit is down", "path": path}],
    }
    (directory / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
