"""Append-only provenance for explicitly synthetic policy versions."""

import uuid

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from regintel.db.base import Base


class PolicyVersionProvenance(Base):
    __tablename__ = "policy_version_provenance"
    __table_args__ = (
        CheckConstraint(
            "review_status = 'pending'", name="ck_policy_provenance_pending"
        ),
        CheckConstraint("synthetic = true", name="ck_policy_provenance_synthetic"),
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policy_document_versions.id", ondelete="RESTRICT"), primary_key=True
    )
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    profile_id: Mapped[str] = mapped_column(String(100), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    variant: Mapped[str] = mapped_column(String(100), nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), nullable=False)
    source_anchor: Mapped[dict] = mapped_column(JSON, nullable=False)
