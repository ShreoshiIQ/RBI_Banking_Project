
import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from regintel.models.gap_report import (
    RegulatoryGapReportRecord,
)
from regintel.reporting.schemas import (
    RegulatoryGapReport,
)


class ReportConflictError(ValueError):
    pass


def _assessment_payload(report: RegulatoryGapReport) -> dict:
    """
    Immutable assessment content.

    Review status and generation timestamp are excluded
    because they are not part of the assessment identity.
    """
    payload = report.model_dump(mode="json")
    payload.pop("generated_at", None)
    payload.pop("review_status", None)
    payload.pop("source_cache_status", None)
    return payload


def save_gap_report(
    session: Session,
    report: RegulatoryGapReport,
) -> tuple[RegulatoryGapReportRecord, bool]:
    """
    Returns (record, created).

    created=True: newly inserted
    created=False: already exists with identical assessment
    """

    if report.review_status != "pending_review":
        raise ValueError(
            "New reports must start as pending_review"
        )

    if report.requires_human_review is not True:
        raise ValueError(
            "Human review must be required"
        )

    existing = session.get(
        RegulatoryGapReportRecord,
        report.report_id,
    )

    if existing is not None:
        stored = RegulatoryGapReport.model_validate(
            existing.report_json
        )

        if (
            _assessment_payload(stored)
            != _assessment_payload(report)
        ):
            raise ReportConflictError(
                "Report ID already exists with "
                "different assessment content"
            )

        return existing, False

    record = RegulatoryGapReportRecord(
        report_id=report.report_id,
        regulatory_reference=report.regulatory_reference,
        assessment_status=report.assessment_status,
        review_status="pending_review",
        report_json=report.model_dump(mode="json"),
    )

    try:
        # Nested transaction protects a caller's outer
        # transaction if another process inserts first.
        with session.begin_nested():
            session.add(record)
            session.flush()

    except IntegrityError:
        existing = session.get(
            RegulatoryGapReportRecord,
            report.report_id,
        )

        if existing is None:
            raise

        stored = RegulatoryGapReport.model_validate(
            existing.report_json
        )

        if (
            _assessment_payload(stored)
            != _assessment_payload(report)
        ):
            raise ReportConflictError(
                "Concurrent report ID conflict"
            )

        return existing, False

    return record, True


def get_gap_report(
    session: Session,
    report_id: str,
) -> RegulatoryGapReportRecord | None:
    return session.get(
        RegulatoryGapReportRecord,
        report_id,
    )
