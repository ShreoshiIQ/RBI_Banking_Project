
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from regintel.db.base import Base


class RegulatoryDocument(Base):
    __tablename__ = "regulatory_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    regulator: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    jurisdiction: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    source_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class RegulatoryDocumentVersion(Base):
    __tablename__ = "regulatory_document_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_documents.id"),
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    storage_uri: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    effective_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "content_hash",
            name="uq_document_content_hash",
        ),
    )


class RegulatoryClause(Base):
    __tablename__ = "regulatory_clauses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_document_versions.id"),
        nullable=False,
    )

    clause_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    section_title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    clause_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "version_id",
            "clause_number",
            name="uq_version_clause",
        ),
    )
