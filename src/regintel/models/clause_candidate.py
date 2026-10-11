
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from regintel.db.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class RegulatoryClauseCandidate(Base):
    __tablename__ = "regulatory_clause_candidates"

    __table_args__ = (
        UniqueConstraint(
            "version_id",
            "clause_number",
            name="uq_clause_candidate_version_number",
        ),
        CheckConstraint(
            "start_page >= 1 AND end_page >= start_page",
            name="ck_clause_candidate_page_range",
        ),
        CheckConstraint(
            "status IN ('active', 'deleted')",
            name="ck_clause_candidate_status",
        ),
        CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected')",
            name="ck_clause_candidate_review_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "regulatory_document_versions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    clause_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    clause_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    start_page: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    end_page: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
    )

    extraction_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="regex_v4",
    )

    review_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
