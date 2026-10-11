
"""
Internal bank policy models.

A policy document can have multiple versions.
Each version can contain multiple text sections.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from regintel.db.base import Base


class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )

    policy_code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    owner_department: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class PolicyDocumentVersion(Base):
    __tablename__ = "policy_document_versions"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "content_hash",
            name="uq_policy_document_content_hash",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policy_documents.id"),
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

    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class PolicySection(Base):
    __tablename__ = "policy_sections"

    __table_args__ = (
        UniqueConstraint(
            "version_id",
            "section_number",
            name="uq_policy_version_section_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policy_document_versions.id"),
        nullable=False,
    )

    section_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    section_title: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )

    section_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
