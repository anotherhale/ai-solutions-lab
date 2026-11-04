"""Synthetic procedure pages stored as files, not fixture rows."""

from __future__ import annotations

import json
import re
from pathlib import Path

from wasatch_api.config import REPO_ROOT
from wasatch_api.customer_service.domain.retrieval import ProcedurePage

SYNTHETIC_LABEL = "Synthetic laboratory procedure for Wasatch Business Systems."
CORPUS_NAME = "wasatch-procedures"
_PAGE_ID = re.compile(r"^proc_[0-9]{4}$")
_TERM = re.compile(r"[a-z]{5,}")
# Generic words on every inbound ticket. They must not select a procedure page.
_STOPWORDS = frozenset({"please", "technician", "service", "request", "related"})


class ProcedureCorpusError(ValueError):
    """The procedure catalog cannot be searched."""


def default_procedure_corpus_dir() -> Path:
    return REPO_ROOT / "data" / "documents" / "procedures"


def content_terms(text: str) -> set[str]:
    return set(_TERM.findall(text.lower())) - _STOPWORDS


class ProcedureCorpus:
    def __init__(self, pages: tuple[ProcedurePage, ...]) -> None:
        self.pages = pages

    @classmethod
    def load(cls, directory: Path) -> ProcedureCorpus:
        root = directory.resolve()
        catalog_path = root / "catalog.json"
        if not catalog_path.is_file():
            raise ProcedureCorpusError(f"missing procedure catalog at {catalog_path}")
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        if payload.get("synthetic") is not True:
            raise ProcedureCorpusError("procedure catalog must set synthetic to true")
        if payload.get("corpus") != CORPUS_NAME:
            raise ProcedureCorpusError(
                f"procedure catalog corpus must be {CORPUS_NAME}"
            )
        records = payload.get("pages")
        if not isinstance(records, list) or not records:
            raise ProcedureCorpusError(
                "procedure catalog pages must be a non-empty array"
            )
        pages: list[ProcedurePage] = []
        seen: set[str] = set()
        for record in records:
            page = _load_page(root, record, seen)
            seen.add(page.id)
            pages.append(page)
        pages.sort(key=lambda page: page.id)
        return cls(tuple(pages))

    @classmethod
    def load_default(cls) -> ProcedureCorpus:
        return cls.load(default_procedure_corpus_dir())

    def matching_pages(self, query_text: str) -> tuple[ProcedurePage, ...]:
        """Return pages that share a content word with the inquiry text."""

        needed = content_terms(query_text)
        if not needed:
            return ()
        matched = [
            page
            for page in self.pages
            if needed & content_terms(f"{page.title}\n{page.text}")
        ]
        return tuple(matched)


def _load_page(root: Path, record: object, seen: set[str]) -> ProcedurePage:
    if not isinstance(record, dict):
        raise ProcedureCorpusError("procedure page must be an object")
    page_id = record.get("id")
    title = record.get("title")
    relative = record.get("path")
    if not isinstance(page_id, str) or _PAGE_ID.fullmatch(page_id) is None:
        raise ProcedureCorpusError(f"procedure page id is invalid: {page_id!r}")
    if page_id in seen:
        raise ProcedureCorpusError(f"duplicate procedure page id {page_id}")
    if not isinstance(title, str) or not title.strip():
        raise ProcedureCorpusError(f"procedure page {page_id} needs a title")
    if not isinstance(relative, str) or Path(relative).name != relative:
        raise ProcedureCorpusError(f"procedure page {page_id} path must be a file name")
    file_path = (root / relative).resolve()
    try:
        file_path.relative_to(root)
    except ValueError as exc:
        raise ProcedureCorpusError(
            f"procedure page {page_id} path escapes the corpus"
        ) from exc
    if not file_path.is_file():
        raise ProcedureCorpusError(f"missing procedure page file {relative}")
    text = file_path.read_text(encoding="utf-8")
    if not _is_labeled_synthetic(text):
        raise ProcedureCorpusError(f"{relative} must be labeled synthetic")
    return ProcedurePage(
        id=page_id,
        title=title.strip(),
        path=relative,
        text=text,
        synthetic=True,
    )


def _is_labeled_synthetic(text: str) -> bool:
    lines = text.lstrip("\ufeff").splitlines()
    return bool(lines) and lines[0].strip() == SYNTHETIC_LABEL
