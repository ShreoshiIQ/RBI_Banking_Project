
"""
Conservative deterministic retention-period verifier.

Version: 1.1

Supports:
- Numeric durations: 5 years, 7 years
- Written durations: five years, seven years
- Explicit minimum retention requirements
- Single unambiguous retention periods

This is a narrow evidence-assessment baseline,
not a complete regulatory compliance verifier.
"""

import re

from regintel.verification.schemas import (
    RetentionRequirement,
    VerificationResult,
    VerificationStatus,
)


NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
}

NUMBER_ALTERNATIVES = "|".join(
    sorted(NUMBER_WORDS, key=len, reverse=True)
)

YEAR_PATTERN = re.compile(
    rf"\b(\d{{1,3}}|{NUMBER_ALTERNATIVES})\s+years?\b",
    re.IGNORECASE,
)

MINIMUM_PATTERN = re.compile(
    r"\b(?:at\s+least|minimum(?:\s+of)?|"
    r"not\s+less\s+than)\b",
    re.IGNORECASE,
)

RETENTION_PATTERN = re.compile(
    r"\b(?:retain|retained|retention|"
    r"maintain|maintained|preserve|preserved|"
    r"keep|kept|archive|archived)\b",
    re.IGNORECASE,
)


def parse_years(value: str) -> int | None:
    """
    Convert a numeric or written year value to int.

    Examples:
        "5" -> 5
        "five" -> 5
        "seven" -> 7
    """

    normalized = value.lower().strip()

    if normalized.isdigit():
        return int(normalized)

    return NUMBER_WORDS.get(normalized)


def extract_retention_requirement(
    text: str,
) -> RetentionRequirement | None:
    """
    Extract one explicit minimum retention period.

    Returns None if the statement:
    - Does not mention retention
    - Has no supported year duration
    - Contains multiple year durations
    - Does not explicitly specify a minimum
    """

    if not text or not text.strip():
        return None

    if not RETENTION_PATTERN.search(text):
        return None

    matches = list(YEAR_PATTERN.finditer(text))

    if len(matches) != 1:
        return None

    match = matches[0]

    years = parse_years(match.group(1))

    if years is None or years <= 0:
        return None

    # Require the minimum expression to be
    # directly associated with the year duration.
    prefix = text[:match.start()]

    minimum = re.search(
        r"(?:at\s+least|minimum(?:\s+of)?|"
        r"not\s+less\s+than)\s*$",
        prefix,
        re.IGNORECASE,
    )

    if minimum is None:
        return None

    return RetentionRequirement(
        years=years,
        minimum_required=True,
        evidence_quote=text.strip(),
    )


def verify_retention(
    obligation_id: str,
    obligation_text: str,
    policy_section_id: str,
    policy_text: str,
) -> VerificationResult:
    """
    Compare explicitly stated minimum retention periods.

    Does not verify:
    - Retention start events
    - Scope of records
    - Exceptions
    - Actor equivalence
    - Complete regulatory compliance
    """

    regulatory = extract_retention_requirement(
        obligation_text
    )

    policy = extract_retention_requirement(
        policy_text
    )

    if regulatory is None:
        return VerificationResult(
            obligation_id=obligation_id,
            policy_section_id=policy_section_id,
            status=VerificationStatus.NEEDS_REVIEW,
            explanation=(
                "The regulatory retention requirement "
                "could not be extracted unambiguously."
            ),
            regulatory_evidence=obligation_text,
            policy_evidence=policy_text,
        )

    if policy is None:
        return VerificationResult(
            obligation_id=obligation_id,
            policy_section_id=policy_section_id,
            status=VerificationStatus.INSUFFICIENT_EVIDENCE,
            regulatory_requirement=regulatory,
            explanation=(
                "The policy does not contain a supported "
                "explicit minimum retention period."
            ),
            regulatory_evidence=obligation_text,
            policy_evidence=policy_text,
        )

    if policy.years >= regulatory.years:
        return VerificationResult(
            obligation_id=obligation_id,
            policy_section_id=policy_section_id,
            status=VerificationStatus.SUPPORTED,
            regulatory_requirement=regulatory,
            policy_requirement=policy,
            explanation=(
                f"The policy specifies a minimum of "
                f"{policy.years} years, meeting the "
                f"extracted regulatory minimum of "
                f"{regulatory.years} years. "
                f"Only the duration was compared; "
                f"scope, start event, and exceptions "
                f"remain unverified."
            ),
            regulatory_evidence=obligation_text,
            policy_evidence=policy_text,
        )

    return VerificationResult(
        obligation_id=obligation_id,
        policy_section_id=policy_section_id,
        status=VerificationStatus.CONFLICTING,
        regulatory_requirement=regulatory,
        policy_requirement=policy,
        explanation=(
            f"The policy states a minimum of "
            f"{policy.years} years, below the "
            f"regulatory minimum of "
            f"{regulatory.years} years. "
            f"This is a potential requirement "
            f"mismatch requiring human review, "
            f"not a definitive legal contradiction."
        ),
        regulatory_evidence=obligation_text,
        policy_evidence=policy_text,
    )
