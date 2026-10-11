
from uuid import uuid4

import pytest
from pydantic import ValidationError

from regintel.schemas.obligation import (
    ObligationExtraction,
    ObligationType,
)


def test_valid_mandatory_obligation():
    obligation = ObligationExtraction(
        source_clause_id=uuid4(),
        clause_number="35",
        actor="Regulated Entity",
        action="Undertake ongoing due diligence",
        obligation_type=ObligationType.MANDATORY,
        evidence_quote=(
            "REs shall undertake on-going due diligence "
            "of customers"
        ),
        confidence=0.9,
    )

    assert obligation.obligation_type == "mandatory"


def test_confidence_must_be_valid():
    with pytest.raises(ValidationError):
        ObligationExtraction(
            source_clause_id=uuid4(),
            clause_number="35",
            actor="Regulated Entity",
            action="Undertake ongoing due diligence",
            obligation_type="mandatory",
            evidence_quote="REs shall undertake due diligence",
            confidence=1.5,
        )


def test_conditional_requires_condition():
    with pytest.raises(ValidationError):
        ObligationExtraction(
            source_clause_id=uuid4(),
            clause_number="35",
            actor="Regulated Entity",
            action="Perform additional verification",
            obligation_type="conditional",
            evidence_quote="If applicable, verification is required",
            confidence=0.8,
        )



def test_deleted_clause_not_extracted():
    from regintel.ingestion.obligation_extractor import (
        extract_obligations,
    )

    results = extract_obligations(
        source_clause_id=uuid4(),
        clause_number="71",
        clause_text="Banks shall verify customer identity.",
        status="deleted",
    )

    assert results == []


def test_mandatory_obligation_extracted():
    from regintel.ingestion.obligation_extractor import (
        extract_obligations,
    )

    results = extract_obligations(
        source_clause_id=uuid4(),
        clause_number="35",
        clause_text=(
            "Regulated entities shall verify "
            "customer information."
        ),
        status="active",
    )

    assert len(results) == 1
    assert results[0].obligation_type == ObligationType.MANDATORY
    assert results[0].evidence_quote == (
        "Regulated entities shall verify customer information."
    )


def test_prohibition_takes_priority():
    from regintel.ingestion.obligation_extractor import (
        extract_obligations,
    )

    results = extract_obligations(
        source_clause_id=uuid4(),
        clause_number="10",
        clause_text="Banks shall not disclose customer data.",
        status="active",
    )

    assert len(results) == 1
    assert results[0].obligation_type == ObligationType.PROHIBITION

