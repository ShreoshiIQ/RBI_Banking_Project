
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from regintel.db.base import Base
from regintel.models.gap_report import RegulatoryGapReportRecord
from regintel.models.gap_report_review import GapReportReviewRecord
from regintel.reporting.review_service import (
    ReviewError,
    get_review_history,
    review_gap_report,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    Base.metadata.create_all(
        engine,
        tables=[
            RegulatoryGapReportRecord.__table__,
            GapReportReviewRecord.__table__,
        ],
    )

    with Session(engine) as db:
        db.add(
            RegulatoryGapReportRecord(
                report_id="gap-test-001",
                regulatory_reference="RBI KYC 46(f)",
                assessment_status="partial_evidence",
                review_status="pending_review",
                report_json={"report_id": "gap-test-001"},
            )
        )
        db.commit()
        yield db

    engine.dispose()


def test_approve_report(session):
    review = review_gap_report(
        session,
        report_id="gap-test-001",
        reviewer_id="compliance-officer-01",
        decision="approved",
        comment="Reviewed the evidence.",
    )
    session.commit()

    assert review.previous_status == "pending_review"
    assert review.new_status == "approved"
    assert session.get(
        RegulatoryGapReportRecord,
        "gap-test-001",
    ).review_status == "approved"


def test_reject_report(session):
    review = review_gap_report(
        session,
        report_id="gap-test-001",
        reviewer_id="compliance-officer-01",
        decision="rejected",
        comment="Insufficient supporting evidence.",
    )

    assert review.new_status == "rejected"


def test_prevent_second_decision(session):
    review_gap_report(
        session,
        report_id="gap-test-001",
        reviewer_id="officer-01",
        decision="approved",
        comment="Reviewed.",
    )
    session.commit()

    with pytest.raises(ReviewError):
        review_gap_report(
            session,
            report_id="gap-test-001",
            reviewer_id="officer-02",
            decision="rejected",
            comment="Attempted second decision.",
        )


def test_reviewer_is_required(session):
    with pytest.raises(ReviewError):
        review_gap_report(
            session,
            report_id="gap-test-001",
            reviewer_id="",
            decision="approved",
            comment="Reviewed.",
        )


def test_comment_is_required(session):
    with pytest.raises(ReviewError):
        review_gap_report(
            session,
            report_id="gap-test-001",
            reviewer_id="officer-01",
            decision="approved",
            comment=" ",
        )


def test_review_history(session):
    review_gap_report(
        session,
        report_id="gap-test-001",
        reviewer_id="officer-01",
        decision="approved",
        comment="Evidence checked.",
    )
    session.commit()

    history = get_review_history(
        session,
        "gap-test-001",
    )

    assert len(history) == 1
    assert history[0].reviewer_id == "officer-01"
    assert history[0].new_status == "approved"


def test_missing_report(session):
    with pytest.raises(ReviewError):
        review_gap_report(
            session,
            report_id="nonexistent",
            reviewer_id="officer-01",
            decision="approved",
            comment="Reviewed.",
        )
