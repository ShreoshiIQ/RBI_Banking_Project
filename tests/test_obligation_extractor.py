
from uuid import uuid4

from regintel.ingestion.obligation_extractor import (
    classify_obligation,
    extract_obligations,
    segment_regulatory_text,
)
from regintel.schemas.obligation import ObligationType


def test_subclause_segmentation():
    text = (
        "Banks shall comply with the following:\n"
        "(a) Banks shall verify identity.\n"
        "(b) Banks shall maintain records."
    )

    segments = segment_regulatory_text(text)

    assert len(segments) == 3
    assert "(a) Banks shall verify identity." in segments
    assert "(b) Banks shall maintain records." in segments


def test_exception_not_prohibition():
    assert classify_obligation(
        "This requirement shall not apply to small accounts."
    ) is None


def test_explicit_prohibition():
    assert classify_obligation(
        "Banks shall not disclose customer information."
    ) == ObligationType.PROHIBITION


def test_permission():
    assert classify_obligation(
        "Banks may open accounts subject to conditions."
    ) == ObligationType.PERMISSION


def test_definitions_excluded():
    results = extract_obligations(
        source_clause_id=uuid4(),
        clause_number="3",
        clause_text=(
            "Definitions: A customer shall mean any person."
        ),
        status="active",
    )

    assert results == []


def test_long_passage_not_promoted():
    results = extract_obligations(
        source_clause_id=uuid4(),
        clause_number="46",
        clause_text="Banks shall " + "maintain records " * 50,
        status="active",
    )

    assert results == []


def test_deleted_clause_excluded():
    results = extract_obligations(
        source_clause_id=uuid4(),
        clause_number="71",
        clause_text="Banks shall maintain records.",
        status="deleted",
    )

    assert results == []
