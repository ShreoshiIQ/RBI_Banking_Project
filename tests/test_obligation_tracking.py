
from uuid import uuid4

from regintel.ingestion.obligation_extractor import (
    extract_with_tracking,
)


def test_long_passage_deferred():
    result = extract_with_tracking(
        source_clause_id=uuid4(),
        clause_number="46",
        clause_text=(
            "Banks shall " + "maintain records " * 50
        ),
        status="active",
    )

    assert len(result.obligations) == 0
    assert any(
        item.reason == "long_passage"
        for item in result.deferred
    )


def test_definitions_deferred():
    result = extract_with_tracking(
        source_clause_id=uuid4(),
        clause_number="3",
        clause_text=(
            "A customer shall mean a person."
        ),
        status="active",
    )

    assert len(result.obligations) == 0
    assert result.deferred[0].reason == (
        "definitions_section"
    )


def test_exception_deferred():
    result = extract_with_tracking(
        source_clause_id=uuid4(),
        clause_number="23",
        clause_text=(
            "This requirement shall not apply "
            "to small accounts."
        ),
        status="active",
    )

    assert len(result.obligations) == 0
    assert result.deferred[0].reason == (
        "exception_or_applicability"
    )


def test_deleted_clause_excluded():
    result = extract_with_tracking(
        source_clause_id=uuid4(),
        clause_number="71",
        clause_text=(
            "Banks shall maintain records."
        ),
        status="deleted",
    )

    assert result.obligations == []
    assert result.deferred == []


def test_normal_obligation_extracted():
    result = extract_with_tracking(
        source_clause_id=uuid4(),
        clause_number="46",
        clause_text=(
            "Banks shall maintain customer records "
            "for five years."
        ),
        status="active",
    )

    assert len(result.obligations) == 1
    assert result.deferred == []
