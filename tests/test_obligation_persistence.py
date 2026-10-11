
"""
Tests for regulatory obligation persistence.

Version: 1.1

Covers:
1. Deterministic SHA-256 fingerprints
2. Fingerprints independent of confidence
3. Fingerprint changes when evidence changes
4. New obligation insertion
5. Duplicate obligation prevention
6. Missing source clause rejection
7. Document version mismatch rejection
8. Deleted clause rejection
9. Missing document version rejection
10. Database failure propagation
11. Empty batch handling

These are unit tests using mocked SQLAlchemy sessions.

Run:
    uv run pytest tests/test_obligation_persistence.py -v
"""

from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from regintel.ingestion.persist_obligations import (
    calculate_fingerprint,
    persist_records,
)

from regintel.models.clause_candidate import (
    RegulatoryClauseCandidate,
)

from regintel.models.regulation import (
    RegulatoryDocumentVersion,
)


# =========================================================
# 1. TEST DATA HELPER
# =========================================================

def make_record(
    source_clause_id=None,
    document_version_id=None,
):
    """
    Create a representative regulatory obligation record.
    """

    return {
        "source_clause_id": str(
            source_clause_id or uuid4()
        ),
        "document_version_id": str(
            document_version_id or uuid4()
        ),
        "clause_number": "46",
        "obligation_type": "mandatory",
        "actor": "Unresolved",
        "action": (
            "REs shall maintain transaction records."
        ),
        "evidence_quote": (
            "REs shall maintain transaction records."
        ),
        "condition": None,
        "confidence": 0.5,
        "extraction_method": (
            "rule_based_v4_1_explicit"
        ),
        "quality_status": "candidate",
        "quality_reasons": [],
        "review_status": "pending",
        "start_page": 49,
        "end_page": 50,
        "source_url": (
            "https://example.org/regulation.pdf"
        ),
    }


# =========================================================
# 2. MOCK DATABASE SESSION HELPER
# =========================================================

def make_session(record):
    """
    Create a mocked SQLAlchemy session.

    The session returns the correct mock object based
    on the SQLAlchemy model requested.

    This avoids depending on the order of session.get()
    calls and fixes the list_iterator TypeError.
    """

    session = MagicMock()

    # -----------------------------------------------------
    # Mock regulatory clause
    # -----------------------------------------------------

    clause = MagicMock()

    clause.id = UUID(
        record["source_clause_id"]
    )

    clause.version_id = UUID(
        record["document_version_id"]
    )

    clause.status = "active"

    # -----------------------------------------------------
    # Mock document version
    # -----------------------------------------------------

    version = MagicMock()

    version.id = UUID(
        record["document_version_id"]
    )

    # -----------------------------------------------------
    # Store references for individual tests
    # -----------------------------------------------------

    session.test_clause = clause
    session.test_version = version

    # -----------------------------------------------------
    # Model-aware session.get()
    # -----------------------------------------------------

    def mock_get(model, object_id):

        if model is RegulatoryClauseCandidate:
            return session.test_clause

        if model is RegulatoryDocumentVersion:
            return session.test_version

        return None

    session.get.side_effect = mock_get

    # By default, no existing obligation is found.
    session.scalar.return_value = None

    return session


# =========================================================
# TEST 1: FINGERPRINT DETERMINISM
# =========================================================

def test_fingerprint_is_deterministic():

    record = make_record()

    first = calculate_fingerprint(record)
    second = calculate_fingerprint(record)

    assert first == second
    assert len(first) == 64


# =========================================================
# TEST 2: FINGERPRINT IGNORES CONFIDENCE
# =========================================================

def test_fingerprint_ignores_confidence():

    record = make_record()

    first = calculate_fingerprint(record)

    record["confidence"] = 0.99

    second = calculate_fingerprint(record)

    assert first == second


# =========================================================
# TEST 3: DIFFERENT EVIDENCE CHANGES FINGERPRINT
# =========================================================

def test_different_evidence_changes_fingerprint():

    record = make_record()

    first = calculate_fingerprint(record)

    record["evidence_quote"] = (
        "REs shall preserve identification records."
    )

    second = calculate_fingerprint(record)

    assert first != second


# =========================================================
# TEST 4: NEW OBLIGATION INSERTION
# =========================================================

def test_new_record_is_inserted():

    record = make_record()

    session = make_session(record)

    result = persist_records(
        session,
        [record],
    )

    assert result["inserted"] == 1

    assert result["skipped_existing"] == 0

    assert result["processed"] == 1

    session.add.assert_called_once()

    session.flush.assert_called_once()


# =========================================================
# TEST 5: DUPLICATE OBLIGATION PREVENTION
# =========================================================

def test_existing_record_is_skipped():

    record = make_record()

    session = make_session(record)

    existing = MagicMock()

    existing.review_status = "approved"

    session.scalar.return_value = existing

    result = persist_records(
        session,
        [record],
    )

    assert result["inserted"] == 0

    assert result["skipped_existing"] == 1

    assert result["processed"] == 1

    # Existing human review must remain unchanged.
    assert existing.review_status == "approved"

    session.add.assert_not_called()

    session.flush.assert_not_called()


# =========================================================
# TEST 6: MISSING SOURCE CLAUSE
# =========================================================

def test_missing_source_clause_is_rejected():

    record = make_record()

    session = make_session(record)

    session.test_clause = None

    with pytest.raises(
        ValueError,
        match="Source clause does not exist",
    ):

        persist_records(
            session,
            [record],
        )

    session.add.assert_not_called()


# =========================================================
# TEST 7: DOCUMENT VERSION MISMATCH
# =========================================================

def test_document_version_mismatch_is_rejected():

    record = make_record()

    session = make_session(record)

    # Deliberately assign the wrong version.
    session.test_clause.version_id = uuid4()

    with pytest.raises(
        ValueError,
        match="Document version mismatch",
    ):

        persist_records(
            session,
            [record],
        )

    session.add.assert_not_called()


# =========================================================
# TEST 8: DELETED CLAUSE REJECTION
# =========================================================

def test_deleted_clause_is_rejected():

    record = make_record()

    session = make_session(record)

    session.test_clause.status = "deleted"

    with pytest.raises(
        ValueError,
        match="deleted clause",
    ):

        persist_records(
            session,
            [record],
        )

    session.add.assert_not_called()


# =========================================================
# TEST 9: MISSING DOCUMENT VERSION
# =========================================================

def test_missing_document_version_is_rejected():

    record = make_record()

    session = make_session(record)

    session.test_version = None

    with pytest.raises(
        ValueError,
        match="Document version does not exist",
    ):

        persist_records(
            session,
            [record],
        )

    session.add.assert_not_called()


# =========================================================
# TEST 10: DATABASE FAILURE PROPAGATION
# =========================================================

def test_database_failure_propagates():

    record = make_record()

    session = make_session(record)

    session.flush.side_effect = RuntimeError(
        "Simulated database failure"
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated database failure",
    ):

        persist_records(
            session,
            [record],
        )

    session.add.assert_called_once()

    session.flush.assert_called_once()


# =========================================================
# TEST 11: EMPTY BATCH
# =========================================================

def test_empty_batch():

    session = MagicMock()

    result = persist_records(
        session,
        [],
    )

    assert result == {
        "inserted": 0,
        "skipped_existing": 0,
        "processed": 0,
    }

    session.add.assert_not_called()

    session.flush.assert_not_called()
