
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from regintel.db.base import Base
from regintel.models.gap_report import (
    RegulatoryGapReportRecord,
)
from regintel.reporting.persistence import (
    ReportConflictError,
    get_gap_report,
    save_gap_report,
)
from regintel.reporting.schemas import (
    GapFinding,
    GapStatus,
    GapSummary,
    RegulatoryGapReport,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    Base.metadata.create_all(
        engine,
        tables=[RegulatoryGapReportRecord.__table__],
    )

    with Session(engine) as db:
        yield db

    engine.dispose()


def sample_report():
    return RegulatoryGapReport(
        report_id="gap-test-001",
        regulatory_reference="RBI KYC Section 46(f)",
        assessment_status="partial_evidence",
        findings=[
            GapFinding(
                requirement="Preservation of account records",
                status=GapStatus.MISSING,
                explanation="Evidence not established.",
                evidence=[],
                suggested_action="Review approved policies.",
            )
        ],
        summary=GapSummary(
            total=1,
            supported=0,
            partial=0,
            missing=1,
            potential_conflicts=0,
        ),
        source_policy_sections=["4", "6"],
        missing_requirements=[
            "Preservation of account records"
        ],
        potential_conflicts=[],
        overall_explanation="Partial evidence.",
    )


def test_insert_new_report(session):
    report = sample_report()

    record, created = save_gap_report(
        session,
        report,
    )
    session.commit()

    assert created is True
    assert record.report_id == "gap-test-001"
    assert record.review_status == "pending_review"


def test_duplicate_report_is_not_inserted(session):
    report = sample_report()

    save_gap_report(session, report)
    session.commit()

    record, created = save_gap_report(
        session,
        report,
    )

    assert created is False
    assert record.report_id == report.report_id


def test_conflicting_report_is_rejected(session):
    original = sample_report()

    save_gap_report(session, original)
    session.commit()

    changed = original.model_copy(deep=True)
    changed.overall_explanation = (
        "A different assessment."
    )

    with pytest.raises(ReportConflictError):
        save_gap_report(session, changed)


def test_report_can_be_retrieved(session):
    report = sample_report()

    save_gap_report(session, report)
    session.commit()

    stored = get_gap_report(
        session,
        "gap-test-001",
    )

    assert stored is not None
    assert stored.assessment_status == "partial_evidence"


def test_unknown_report_returns_none(session):
    assert get_gap_report(
        session,
        "does-not-exist",
    ) is None


def test_report_cannot_start_approved(session):
    report = sample_report()
    report.review_status = "approved"

    with pytest.raises(ValueError):
        save_gap_report(session, report)
