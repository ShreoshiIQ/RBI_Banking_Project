
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from regintel.db.base import Base


class GapReportReviewRecord(Base):
    __tablename__ = "gap_report_reviews"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    report_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("regulatory_gap_reports.report_id"),
        nullable=False,
        index=True,
    )

    reviewer_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    previous_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    new_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    comment: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
