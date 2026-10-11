
"""
Unit tests for regulatory obligation quality validation.

Run:
    uv run pytest tests/test_obligation_quality.py -v

These tests verify:
1. Valid-looking obligation candidates
2. Historical or deleted regulatory text
3. Amendment metadata
4. Incomplete obligations
5. Multiple modal keywords
6. Very short evidence
7. Permissions
8. Prohibitions
9. Multiple quality warnings
10. Empty evidence

Note:
Passing the quality gate does not mean an obligation
is legally verified or approved.
"""

from regintel.ingestion.obligation_quality import (
    evaluate_obligation,
)


def test_normal_candidate():
    """A simple obligation should have no quality warnings."""

    result = evaluate_obligation(
        "Banks shall maintain customer records for five years."
    )

    assert result.status == "candidate"
    assert result.reasons == []


def test_historical_deleted_text():
    """Deleted historical provisions must be flagged."""

    result = evaluate_obligation(
        "Deleted portion read as: "
        "Banks shall collect customer documents."
    )

    assert result.status == "needs_review"

    assert (
        "historical_or_deleted_text"
        in result.reasons
    )


def test_prior_amendment_text():
    """Earlier versions of provisions must be flagged."""

    result = evaluate_obligation(
        "Prior to amendment, banks shall "
        "verify customer identity manually."
    )

    assert result.status == "needs_review"

    assert (
        "historical_or_deleted_text"
        in result.reasons
    )


def test_amendment_metadata():
    """Amendment footnotes must trigger review."""

    result = evaluate_obligation(
        "Regulated entities shall maintain records. "
        "Amended vide circular dated April 28, 2023."
    )

    assert result.status == "needs_review"

    assert (
        "contains_amendment_metadata"
        in result.reasons
    )


def test_incomplete_obligation():
    """A sentence ending with 'shall' is incomplete."""

    result = evaluate_obligation(
        "Regulated entities shall"
    )

    assert result.status == "needs_review"

    assert (
        "incomplete_obligation"
        in result.reasons
    )


def test_multiple_modal_keywords():
    """A compound requirement should be reviewed."""

    result = evaluate_obligation(
        "Banks may open accounts and "
        "shall maintain customer records."
    )

    assert result.status == "needs_review"

    assert (
        "multiple_modal_keywords"
        in result.reasons
    )


def test_very_short_evidence():
    """Very short evidence should trigger review."""

    result = evaluate_obligation(
        "Banks shall act."
    )

    assert result.status == "needs_review"

    assert (
        "very_short_evidence"
        in result.reasons
    )


def test_permission_candidate():
    """A simple permission can pass the heuristic gate."""

    result = evaluate_obligation(
        "Banks may open accounts subject to applicable conditions."
    )

    assert result.status == "candidate"
    assert result.reasons == []


def test_prohibition_candidate():
    """A simple prohibition can pass the heuristic gate."""

    result = evaluate_obligation(
        "Banks shall not disclose confidential customer information."
    )

    assert result.status == "candidate"
    assert result.reasons == []


def test_multiple_quality_warnings():
    """One candidate may contain several quality issues."""

    result = evaluate_obligation(
        "Deleted portion read as: Banks shall "
        "maintain records and may disclose information. "
        "Amended vide circular dated April 28, 2023."
    )

    assert result.status == "needs_review"

    assert (
        "historical_or_deleted_text"
        in result.reasons
    )

    assert (
        "contains_amendment_metadata"
        in result.reasons
    )

    assert (
        "multiple_modal_keywords"
        in result.reasons
    )


def test_empty_evidence():
    """Empty evidence must be flagged for review."""

    result = evaluate_obligation("")

    assert result.status == "needs_review"

    assert (
        "very_short_evidence"
        in result.reasons
    )
