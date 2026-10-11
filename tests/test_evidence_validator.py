
from regintel.verification.evidence_validator import (
    quote_exists,
    validate_verification,
)

from regintel.verification.llm_schemas import (
    AssessmentStatus,
    LLMVerification,
    RequirementComparison,
)


REGULATION = (
    "The bank shall retain transaction records "
    "for at least five years."
)

POLICY = (
    "The bank shall maintain transaction records "
    "for at least five years."
)


def make_proposal(
    regulatory_quote=REGULATION,
    policy_quote=POLICY,
):
    return LLMVerification(
        proposed_status=(
            AssessmentStatus.ATTRIBUTES_MATCHED
        ),
        regulatory_quote=regulatory_quote,
        policy_quote=policy_quote,
        comparisons=[
            RequirementComparison(
                attribute="duration",
                regulatory_requirement="five years",
                policy_commitment="five years",
                assessment="matched",
            )
        ],
        missing_requirements=[],
        potential_conflicts=[],
        explanation="Duration evidence is aligned.",
    )


def check(proposal):
    return validate_verification(
        obligation_id="ob-1",
        policy_section_id="section-2",
        regulatory_text=REGULATION,
        policy_text=POLICY,
        proposed=proposal,
        model_name="mock-model",
    )


def test_exact_quote_found():
    assert quote_exists(
        "retain transaction records",
        REGULATION,
    )


def test_whitespace_normalization():
    assert quote_exists(
        "retain   transaction\nrecords",
        REGULATION,
    )


def test_hallucinated_quote_rejected():
    assert not quote_exists(
        "The bank shall retain records for 20 years.",
        REGULATION,
    )


def test_valid_proposal_preserved():
    result = check(make_proposal())

    assert (
        result.status
        == AssessmentStatus.ATTRIBUTES_MATCHED
    )
    assert result.validation_errors == []
    assert result.requires_human_review is True


def test_invalid_policy_quote_downgrades():
    result = check(
        make_proposal(
            policy_quote="A policy statement that does not exist."
        )
    )

    assert (
        result.status
        == AssessmentStatus.NEEDS_REVIEW
    )
    assert result.validation_errors


def test_missing_policy_quote_downgrades():
    result = check(
        make_proposal(policy_quote=None)
    )

    assert (
        result.status
        == AssessmentStatus.NEEDS_REVIEW
    )
