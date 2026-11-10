"""Persistence for the AI review verdict mirror.

The mirror is an audit/cache record only. It is never consulted to authorize a
merge: the gate and the coordinator both re-verify GitHub state directly. Its
uniqueness constraint ``(repository, pull_number, head_sha, review_id)`` makes
mirroring idempotent, so a duplicate tick cannot accumulate rows.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from development_ops.persistence.orm import ReviewVerdictORM


@dataclass(frozen=True, slots=True)
class ReviewVerdictRecord:
    id: uuid.UUID
    repository: str
    pull_number: int
    head_sha: str
    review_id: int
    reviewer_login: str
    reviewer_user_id: int
    verdict: str
    blocking_count: int
    policy_version: str
    reviewed_at: datetime
    recorded_at: datetime


def _to_record(row: ReviewVerdictORM) -> ReviewVerdictRecord:
    return ReviewVerdictRecord(
        id=row.id,
        repository=row.repository,
        pull_number=row.pull_number,
        head_sha=row.head_sha,
        review_id=row.review_id,
        reviewer_login=row.reviewer_login,
        reviewer_user_id=row.reviewer_user_id,
        verdict=row.verdict,
        blocking_count=row.blocking_count,
        policy_version=row.policy_version,
        reviewed_at=row.reviewed_at,
        recorded_at=row.recorded_at,
    )


class ReviewVerdictRepository:
    """PostgreSQL repository for development_ops.review_verdicts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self,
        *,
        repository: str,
        pull_number: int,
        head_sha: str,
        review_id: int,
    ) -> ReviewVerdictRecord | None:
        stmt = select(ReviewVerdictORM).where(
            ReviewVerdictORM.repository == repository,
            ReviewVerdictORM.pull_number == pull_number,
            ReviewVerdictORM.head_sha == head_sha,
            ReviewVerdictORM.review_id == review_id,
        )
        row = self._session.scalar(stmt)
        return _to_record(row) if row is not None else None

    def record(
        self,
        *,
        repository: str,
        pull_number: int,
        head_sha: str,
        review_id: int,
        reviewer_login: str,
        reviewer_user_id: int,
        verdict: str,
        blocking_count: int,
        policy_version: str,
        reviewed_at: datetime,
    ) -> tuple[ReviewVerdictRecord, bool]:
        """Mirror a verdict. Returns ``(record, created)``.

        ``created`` is false on idempotent replay. Concurrent inserts are handled
        by the unique constraint: a racing duplicate is caught and re-read.
        """
        existing = self.get(
            repository=repository,
            pull_number=pull_number,
            head_sha=head_sha,
            review_id=review_id,
        )
        if existing is not None:
            return existing, False

        row = ReviewVerdictORM(
            id=uuid.uuid4(),
            repository=repository,
            pull_number=pull_number,
            head_sha=head_sha,
            review_id=review_id,
            reviewer_login=reviewer_login,
            reviewer_user_id=reviewer_user_id,
            verdict=verdict,
            blocking_count=blocking_count,
            policy_version=policy_version,
            reviewed_at=reviewed_at,
        )
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            replay = self.get(
                repository=repository,
                pull_number=pull_number,
                head_sha=head_sha,
                review_id=review_id,
            )
            if replay is not None:
                return replay, False
            raise
        self._session.commit()
        self._session.refresh(row)
        return _to_record(row), True

    def list_for_pull(
        self, repository: str, pull_number: int
    ) -> list[ReviewVerdictRecord]:
        stmt = (
            select(ReviewVerdictORM)
            .where(
                ReviewVerdictORM.repository == repository,
                ReviewVerdictORM.pull_number == pull_number,
            )
            .order_by(ReviewVerdictORM.recorded_at)
        )
        return [_to_record(row) for row in self._session.scalars(stmt)]
