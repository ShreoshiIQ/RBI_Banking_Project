
"""
Unit tests for Gemini-based LLM compliance verification.

All Gemini API calls are mocked.
No real API requests are made.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from regintel.verification.llm_verifier import (
    LLMComplianceVerifier,
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


def make_proposal():
    """
    Create a valid mock Gemini verification result.
    """

    return LLMVerification(
        proposed_status=AssessmentStatus.ATTRIBUTES_MATCHED,
        regulatory_quote=REGULATION,
        policy_quote=POLICY,
        comparisons=[
            RequirementComparison(
                attribute="retention duration",
                regulatory_requirement="five years",
                policy_commitment="five years",
                assessment="matched",
            )
        ],
        missing_requirements=[],
        potential_conflicts=[],
        explanation="The stated duration matches.",
    )


def make_client(parsed):
    """
    Simulate the response returned by Gemini.
    """

    client = MagicMock()

    client.models.generate_content.return_value = (
        SimpleNamespace(
            parsed=parsed,
            text=None,
        )
    )

    return client


def test_llm_verification_with_mock():

    client = make_client(make_proposal())

    verifier = LLMComplianceVerifier(
        client=client,
        model_name="mock-gemini",
    )

    result = verifier.verify(
        obligation_id="ob-1",
        obligation_text=REGULATION,
        policy_section_id="section-2",
        policy_text=POLICY,
    )

    assert (
        result.status
        == AssessmentStatus.ATTRIBUTES_MATCHED
    )

    assert result.model_name == "mock-gemini"

    assert result.validation_errors == []

    client.models.generate_content.assert_called_once()


def test_empty_regulation_rejected():

    verifier = LLMComplianceVerifier(
        client=MagicMock(),
        model_name="mock-gemini",
    )

    with pytest.raises(ValueError):
        verifier.verify(
            obligation_id="ob-1",
            obligation_text="",
            policy_section_id="section-2",
            policy_text=POLICY,
        )


def test_missing_gemini_response_rejected():

    client = make_client(parsed=None)

    verifier = LLMComplianceVerifier(
        client=client,
        model_name="mock-gemini",
    )

    with pytest.raises(RuntimeError):
        verifier.verify(
            obligation_id="ob-1",
            obligation_text=REGULATION,
            policy_section_id="section-2",
            policy_text=POLICY,
        )


def test_hallucinated_evidence_downgraded():

    proposal = make_proposal()

    proposal.policy_quote = (
        "The bank retains all records for 20 years."
    )

    client = make_client(proposal)

    verifier = LLMComplianceVerifier(
        client=client,
        model_name="mock-gemini",
    )

    result = verifier.verify(
        obligation_id="ob-1",
        obligation_text=REGULATION,
        policy_section_id="section-2",
        policy_text=POLICY,
    )

    assert (
        result.status
        == AssessmentStatus.NEEDS_REVIEW
    )

    assert len(result.validation_errors) > 0
