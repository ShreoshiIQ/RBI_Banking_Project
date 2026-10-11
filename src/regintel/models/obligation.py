
"""
Database model for extracted regulatory obligations.

Stores:
- Source clause and document version
- Obligation type and extracted content
- Original evidence
- Quality assessment
- Human review status
- Extraction provenance
"""

import uuid

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Float,
    JSON,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from sqlalchemy.dialects.postgresql import UUID

from regintel.db.base import Base


class RegulatoryObligation(Base):

    __tablename__ = "regulatory_obligations"

    __table_args__ = (
        UniqueConstraint(
            "source_clause_id",
            "obligation_fingerprint",
            name="uq_obligation_clause_fingerprint",
        ),
        CheckConstraint(
            "review_status IN "
            "('pending', 'approved', 'rejected')",
            name="ck_obligation_review_status",
        ),
        CheckConstraint(
            "quality_status IN "
            "('candidate', 'needs_review')",
            name="ck_obligation_quality_status",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_obligation_confidence",
        ),
        Index(
            "ix_obligation_version_review",
            "document_version_id",
            "review_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    source_clause_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "regulatory_clause_candidates.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "regulatory_document_versions.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    obligation_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    clause_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    obligation_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    actor: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    evidence_quote: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    condition: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    extraction_method: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    quality_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="candidate",
    )

    quality_reasons: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    review_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )

    start_page: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    end_page: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    source_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
