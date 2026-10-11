
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from regintel.db.base import Base


class RegulatoryGapReportRecord(Base):
    __tablename__ = "regulatory_gap_reports"

    report_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    regulatory_reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    assessment_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    review_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending_review",
    )

    report_json: Mapped[dict] = mapped_column(
        JSON,
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

    __table_args__ = (
        Index(
            "ix_gap_reports_review_status",
            "review_status",
        ),
    )
