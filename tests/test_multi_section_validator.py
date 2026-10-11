
from regintel.orchestration.multi_section import PolicyEvidence
from regintel.verification.multi_section_schemas import (
    MultiSectionAssessment,
)
from regintel.verification.multi_section_validator import (
    validate_multi_section_assessment,
)


SECTIONS = [
    PolicyEvidence(
        section_id="s4",
        section_number="4",
        section_title="Regulatory Requests",
        section_text=(
            "The bank shall make records available "
            "to competent authorities upon request."
        ),
    ),
    PolicyEvidence(
        section_id="s6",
        section_number="6",
        section_title="Record Retrieval",
        section_text=(
            "The bank shall maintain a system that "
            "permits authorized personnel to retrieve "
            "required account information efficiently."
        ),
    ),
]


def assessment(quote, section_id="s6"):
    return MultiSectionAssessment(
        proposed_status="partial_evidence",
        findings=[
            {
                "requirement": "Efficient retrieval",
                "assessment": "partial",
                "explanation": "Retrieval is addressed.",
                "citations": [
                    {
                        "section_id": section_id,
                        "exact_quote": quote,
                        "supported_requirement": (
                            "Efficient retrieval"
                        ),
                    }
                ],
            },
            {
                "requirement": "Record preservation",
                "assessment": "missing",
                "explanation": "Not explicitly established.",
                "citations": [],
            },
        ],
        missing_requirements=["Record preservation"],
        potential_conflicts=[],
        explanation="The policy provides partial evidence.",
    )


def test_valid_section_quote():
    result = validate_multi_section_assessment(
        assessment=assessment(
            "The bank shall maintain a system that "
            "permits authorized personnel to retrieve "
            "required account information efficiently."
        ),
        sections=SECTIONS,
    )

    assert result["status"] == "partial_evidence"
    assert not result["validation_errors"]
    assert result["citations"][0]["section_id"] == "s6"


def test_wrong_section_is_rejected():
    result = validate_multi_section_assessment(
        assessment=assessment(
            "The bank shall maintain a system that "
            "permits authorized personnel to retrieve "
            "required account information efficiently.",
            section_id="s4",
        ),
        sections=SECTIONS,
    )

    assert result["status"] == "needs_review"
    assert result["validation_errors"]


def test_invented_quote_is_rejected():
    result = validate_multi_section_assessment(
        assessment=assessment(
            "The bank guarantees immediate access."
        ),
        sections=SECTIONS,
    )

    assert result["validation_errors"]


def test_missing_requirement_needs_no_quote():
    result = validate_multi_section_assessment(
        assessment=MultiSectionAssessment(
            proposed_status="needs_review",
            findings=[
                {
                    "requirement": "Preservation",
                    "assessment": "missing",
                    "explanation": "No evidence found.",
                    "citations": [],
                }
            ],
            missing_requirements=["Preservation"],
            potential_conflicts=[],
            explanation="Insufficient evidence.",
        ),
        sections=SECTIONS,
    )

    assert result["status"] == "needs_review"
    assert not result["validation_errors"]
