
"""
PostgreSQL integration tests for regulatory obligations.

These tests use the real PostgreSQL database but roll back
test changes. Existing obligation records are not modified.

Run:
    uv run pytest tests/test_obligation_db_integration.py -v
"""

from uuid import uuid4

import pytest

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from regintel.db.session import SessionLocal
from regintel.models.obligation import RegulatoryObligation
from regintel.models.clause_candidate import RegulatoryClauseCandidate


@pytest.fixture
def db_session():
    """
    Open a database session inside an outer transaction.

    Roll back the outer transaction after each test.
    """

    session = SessionLocal()

    connection = session.connection()
    transaction = connection.get_transaction()

    try:
        yield session
    finally:
        session.close()

        if transaction is not None and transaction.is_active:
            transaction.rollback()


def get_existing_clause(session):
    """Find an active regulatory clause."""

    clause = session.scalar(
        select(RegulatoryClauseCandidate)
        .where(RegulatoryClauseCandidate.status == "active")
        .limit(1)
    )

    if clause is None:
        pytest.skip("No active regulatory clauses available")

    return clause


def make_obligation(clause, fingerprint=None):
    """Build an obligation associated with an existing clause."""

    return RegulatoryObligation(
        source_clause_id=clause.id,
        document_version_id=clause.version_id,
        obligation_fingerprint=fingerprint or uuid4().hex,
        clause_number=clause.clause_number,
        obligation_type="mandatory",
        actor="Test Regulated Entity",
        action="Test entity shall maintain records.",
        evidence_quote="Test entity shall maintain records.",
        condition=None,
        confidence=0.5,
        extraction_method="integration_test",
        quality_status="candidate",
        quality_reasons=[],
        review_status="pending",
        start_page=clause.start_page,
        end_page=clause.end_page,
        source_url="https://example.org/test.pdf",
    )


# =========================================================
# TEST 1: FOREIGN KEY ENFORCEMENT
# =========================================================

def test_foreign_key_rejects_missing_clause(db_session):

    clause = get_existing_clause(db_session)

    obligation = make_obligation(clause)

    obligation.source_clause_id = uuid4()

    db_session.add(obligation)

    with pytest.raises(IntegrityError):
        db_session.flush()


# =========================================================
# TEST 2: DUPLICATE FINGERPRINT
# =========================================================

def test_duplicate_fingerprint_is_rejected(db_session):

    clause = get_existing_clause(db_session)

    fingerprint = uuid4().hex

    first = make_obligation(
        clause,
        fingerprint=fingerprint,
    )

    second = make_obligation(
        clause,
        fingerprint=fingerprint,
    )

    db_session.add(first)
    db_session.flush()

    db_session.add(second)

    with pytest.raises(IntegrityError):
        db_session.flush()


# =========================================================
# TEST 3: TRANSACTION ROLLBACK
# =========================================================

def test_transaction_rollback(db_session):

    clause = get_existing_clause(db_session)

    before_count = db_session.scalar(
        select(func.count())
        .select_from(RegulatoryObligation)
    )

    obligation = make_obligation(clause)

    db_session.add(obligation)
    db_session.flush()

    after_insert = db_session.scalar(
        select(func.count())
        .select_from(RegulatoryObligation)
    )

    assert after_insert == before_count + 1

    db_session.rollback()

    after_rollback = db_session.scalar(
        select(func.count())
        .select_from(RegulatoryObligation)
    )

    assert after_rollback == before_count
