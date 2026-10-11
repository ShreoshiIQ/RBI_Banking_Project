
from sqlalchemy import select
from sqlalchemy.orm import Session

from regintel.models.gap_report import RegulatoryGapReportRecord
from regintel.models.gap_report_review import GapReportReviewRecord


class ReviewError(ValueError):
    pass


ALLOWED_TRANSITIONS = {
    "pending_review": {"approved", "rejected"},
    "approved": set(),
    "rejected": set(),
}


def review_gap_report(
    session: Session,
    *,
    report_id: str,
    reviewer_id: str,
    decision: str,
    comment: str,
) -> GapReportReviewRecord:
    """
    Record a human review decision.

    The caller controls the database transaction.
    """

    if not reviewer_id or not reviewer_id.strip():
        raise ReviewError("Reviewer ID is required")

    if not comment or not comment.strip():
        raise ReviewError("Review comment is required")

    if decision not in {"approved", "rejected"}:
        raise ReviewError(
            "Decision must be approved or rejected"
        )

    report = session.execute(
        select(RegulatoryGapReportRecord)
        .where(RegulatoryGapReportRecord.report_id == report_id)
        .with_for_update()
    ).scalar_one_or_none()

    if report is None:
        raise ReviewError("Gap report not found")

    previous_status = report.review_status

    if decision not in ALLOWED_TRANSITIONS.get(
        previous_status, set()
    ):
        raise ReviewError(
            f"Invalid transition: {previous_status} -> {decision}"
        )

    review = GapReportReviewRecord(
        report_id=report_id,
        reviewer_id=reviewer_id.strip(),
        previous_status=previous_status,
        new_status=decision,
        comment=comment.strip(),
    )

    report.review_status = decision
    # Assign a new dictionary so SQLAlchemy tracks the JSON update atomically.
    report.report_json = {**report.report_json, "review_status": decision}
    session.add(review)
    session.flush()

    return review


def get_review_history(
    session: Session,
    report_id: str,
) -> list[GapReportReviewRecord]:
    return list(
        session.scalars(
            select(GapReportReviewRecord)
            .where(GapReportReviewRecord.report_id == report_id)
            .order_by(
                GapReportReviewRecord.reviewed_at,
                GapReportReviewRecord.id,
            )
        ).all()
    )
