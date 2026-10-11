
import re

from regintel.verification.llm_schemas import (
    AssessmentStatus,
    LLMVerification,
    ValidatedVerification,
)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def quote_exists(
    quote: str | None,
    source: str,
) -> bool:
    """
    Require a nonempty exact source substring,
    allowing whitespace normalization only.
    """

    if not quote or not quote.strip():
        return False

    return (
        normalize_whitespace(quote)
        in normalize_whitespace(source)
    )


def validate_verification(
    *,
    obligation_id: str,
    policy_section_id: str,
    regulatory_text: str,
    policy_text: str,
    proposed: LLMVerification,
    model_name: str,
) -> ValidatedVerification:

    errors = []

    if not quote_exists(
        proposed.regulatory_quote,
        regulatory_text,
    ):
        errors.append(
            "Regulatory quote not found in source."
        )

    if proposed.policy_quote is not None:
        if not quote_exists(
            proposed.policy_quote,
            policy_text,
        ):
            errors.append(
                "Policy quote not found in source."
            )

    if (
        proposed.proposed_status
        == AssessmentStatus.ATTRIBUTES_MATCHED
    ):
        if not proposed.policy_quote:
            errors.append(
                "Matched assessment lacks policy evidence."
            )

        if proposed.missing_requirements:
            errors.append(
                "Matched assessment has missing requirements."
            )

        if proposed.potential_conflicts:
            errors.append(
                "Matched assessment has potential conflicts."
            )

        if not proposed.comparisons:
            errors.append(
                "Matched assessment lacks comparisons."
            )

    status = proposed.proposed_status

    if errors:
        status = AssessmentStatus.NEEDS_REVIEW

    return ValidatedVerification(
        obligation_id=obligation_id,
        policy_section_id=policy_section_id,
        status=status,
        regulatory_quote=(
            proposed.regulatory_quote
            if quote_exists(
                proposed.regulatory_quote,
                regulatory_text,
            )
            else None
        ),
        policy_quote=(
            proposed.policy_quote
            if quote_exists(
                proposed.policy_quote,
                policy_text,
            )
            else None
        ),
        comparisons=proposed.comparisons,
        missing_requirements=(
            proposed.missing_requirements
        ),
        potential_conflicts=(
            proposed.potential_conflicts
        ),
        explanation=proposed.explanation,
        validation_errors=errors,
        model_name=model_name,
        requires_human_review=True,
    )
