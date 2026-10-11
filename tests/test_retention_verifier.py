
import pytest

from regintel.verification.retention_verifier import (
    extract_retention_requirement,
    verify_retention,
)

from regintel.verification.schemas import (
    VerificationStatus,
)


REGULATION = (
    "The bank shall maintain transaction records "
    "for at least five years."
)


def verify(policy_text):
    return verify_retention(
        obligation_id="obligation-1",
        obligation_text=REGULATION,
        policy_section_id="policy-section-1",
        policy_text=policy_text,
    )


def test_extract_five_year_minimum():
    result = extract_retention_requirement(
        REGULATION
    )

    assert result is not None
    assert result.years == 5


def test_supported_equal_duration():
    result = verify(
        "The bank shall maintain transaction records "
        "for at least five years."
    )

    assert result.status == VerificationStatus.SUPPORTED


def test_supported_longer_duration():
    result = verify(
        "The bank shall retain transaction records "
        "for a minimum of seven years."
    )

    assert result.status == VerificationStatus.SUPPORTED


def test_shorter_minimum_flagged():
    result = verify(
        "The bank shall retain transaction records "
        "for at least three years."
    )

    assert result.status == VerificationStatus.CONFLICTING
    assert result.requires_human_review is True


def test_missing_duration():
    result = verify(
        "The bank shall maintain transaction records "
        "according to internal procedures."
    )

    assert (
        result.status
        == VerificationStatus.INSUFFICIENT_EVIDENCE
    )


def test_unrelated_policy():
    result = verify(
        "Employees must complete annual "
        "cybersecurity training."
    )

    assert (
        result.status
        == VerificationStatus.INSUFFICIENT_EVIDENCE
    )


def test_ambiguous_multiple_durations():
    result = verify(
        "The bank shall retain transaction records "
        "for at least three years and preserve "
        "archived copies for at least seven years."
    )

    assert (
        result.status
        == VerificationStatus.INSUFFICIENT_EVIDENCE
    )


def test_bare_duration_requires_review():
    result = verify(
        "The bank shall retain records for five years."
    )

    assert (
        result.status
        == VerificationStatus.INSUFFICIENT_EVIDENCE
    )


def test_unparseable_regulation():
    result = verify_retention(
        obligation_id="obligation-1",
        obligation_text=(
            "The bank shall retain records "
            "for the prescribed period."
        ),
        policy_section_id="policy-section-1",
        policy_text=(
            "The bank shall retain records "
            "for at least five years."
        ),
    )

    assert result.status == VerificationStatus.NEEDS_REVIEW
