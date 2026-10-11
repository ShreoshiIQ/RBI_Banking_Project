
"""
Unit tests for keyword-based policy retrieval.

Run:
    uv run pytest tests/test_keyword_matcher.py -v
"""

import pytest

from regintel.mapping.keyword_matcher import (
    cosine_similarity,
    rank_policy_sections,
    tokenize,
)

from collections import Counter


def sample_sections():
    return [
        {
            "id": "policy-section-1",
            "section_number": "1",
            "section_title": "Transaction Retention",
            "section_text": (
                "The bank shall maintain transaction records "
                "for at least five years."
            ),
        },
        {
            "id": "policy-section-2",
            "section_number": "2",
            "section_title": "Employee Leave",
            "section_text": (
                "Employees may request annual leave "
                "through the HR portal."
            ),
        },
        {
            "id": "policy-section-3",
            "section_number": "3",
            "section_title": "Customer Identification",
            "section_text": (
                "The bank shall preserve customer "
                "identification documents."
            ),
        },
    ]


def test_tokenize_lowercase():
    assert tokenize("BANK Customer Records") == [
        "bank",
        "customer",
        "records",
    ]


def test_tokenize_removes_stop_words():
    assert tokenize(
        "The bank shall maintain records"
    ) == [
        "bank",
        "maintain",
        "records",
    ]


def test_cosine_identical_vectors():
    vector = Counter(["bank", "records"])

    assert cosine_similarity(
        vector,
        vector,
    ) == pytest.approx(1.0)


def test_cosine_unrelated_vectors():
    assert cosine_similarity(
        Counter(["bank"]),
        Counter(["holiday"]),
    ) == 0.0


def test_relevant_policy_ranks_first():
    matches = rank_policy_sections(
        obligation_text=(
            "Banks shall maintain transaction records "
            "for at least five years."
        ),
        policy_sections=sample_sections(),
    )

    assert matches
    assert matches[0].policy_section_id == (
        "policy-section-1"
    )


def test_unrelated_policy_not_matched():
    matches = rank_policy_sections(
        obligation_text=(
            "Cryptographic quantum lattice"
        ),
        policy_sections=sample_sections(),
    )

    assert matches == []


def test_top_k_limits_results():
    matches = rank_policy_sections(
        obligation_text=(
            "The bank shall preserve customer records."
        ),
        policy_sections=sample_sections(),
        top_k=1,
    )

    assert len(matches) <= 1


def test_empty_obligation_returns_no_matches():
    matches = rank_policy_sections(
        obligation_text="",
        policy_sections=sample_sections(),
    )

    assert matches == []


def test_invalid_top_k_rejected():
    with pytest.raises(ValueError):
        rank_policy_sections(
            obligation_text="records",
            policy_sections=sample_sections(),
            top_k=0,
        )


def test_invalid_min_score_rejected():
    with pytest.raises(ValueError):
        rank_policy_sections(
            obligation_text="records",
            policy_sections=sample_sections(),
            min_score=1.5,
        )
