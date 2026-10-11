
"""
Store semantic embeddings for internal policy sections.
"""

import uuid

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from regintel.db.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class PolicySectionEmbedding(Base):
    __tablename__ = "policy_section_embeddings"

    __table_args__ = (
        UniqueConstraint(
            "policy_section_id",
            "embedding_model",
            name="uq_policy_section_embedding_model",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    policy_section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policy_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    embedding_model: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    embedding: Mapped[list[float]] = mapped_column(
        Vector(384),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
