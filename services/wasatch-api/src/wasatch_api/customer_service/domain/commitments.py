"""Rules for an outbound reply before it can leave the building.

Model output is untrusted. A reply that would commit Wasatch needs a human
approval. Citing a retrieved source is required either way. Neither rule
marks the message sent.
"""

from __future__ import annotations

import re

from wasatch_api.customer_service.domain.retrieval import RetrievalResult

_SOURCE_ID = re.compile(r"\b(?:msg|tkt|ixn|wo|proc)_\d+\b")
_COMMITMENT = re.compile(
    r"("
    r"\bwe will\b|"
    r"\bwe'll\b|"
    r"\bwe can be\b|"
    r"\bon site\b|"
    r"\bguarantee(?:d|s)?\b|"
    r"\bwarrant(?:y|ies)\b|"
    r"\bovertime\b|"
    r"\bdiscount\b|"
    r"\b(?:waive|waived|waiver)\b|"
    r"\brefund\b|"
    r"\$\s*\d|"
    r"\b\d{1,2}:\d{2}\b"
    r")",
    re.IGNORECASE,
)


def outbound_text_commits_company(body: str) -> bool:
    """True when the reply promises time, money, or a company obligation."""

    return _COMMITMENT.search(body) is not None


def reply_cites_retrieval(body: str, result: RetrievalResult) -> bool:
    """True when the reply names at least one source from this retrieval."""

    available = {passage.source_id for passage in result.history}
    available.update(page.id for page in result.procedures)
    cited = set(_SOURCE_ID.findall(body))
    return bool(cited & available)
