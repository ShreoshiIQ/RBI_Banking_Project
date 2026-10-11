
"""
Deterministic keyword-based policy retrieval.

Version: 1.0

This module ranks policy sections by lexical similarity
to regulatory obligation text.

IMPORTANT:
A high score indicates textual relevance, not compliance.
"""

import math
import re

from collections import Counter
from dataclasses import dataclass


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been",
    "by", "can", "for", "from", "has", "have", "in",
    "into", "is", "it", "its", "of", "on", "or", "shall",
    "should", "such", "that", "the", "their", "these",
    "this", "those", "to", "under", "was", "were",
    "which", "while", "with", "within", "may", "must",
    "all", "any", "each", "other", "including",
    "following", "thereof", "therein", "thereby",
}

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass
class PolicyMatch:
    policy_section_id: str
    section_number: str
    section_title: str
    score: float
    matched_terms: list[str]
    policy_text: str


def tokenize(text: str) -> list[str]:
    """Normalize text into meaningful lowercase tokens."""

    tokens = TOKEN_PATTERN.findall(text.lower())

    return [
        token
        for token in tokens
        if token not in STOP_WORDS and len(token) > 1
    ]


def cosine_similarity(
    left: Counter,
    right: Counter,
) -> float:
    """Calculate cosine similarity between token frequencies."""

    if not left or not right:
        return 0.0

    shared = set(left) & set(right)

    dot_product = sum(
        left[token] * right[token]
        for token in shared
    )

    left_norm = math.sqrt(
        sum(value ** 2 for value in left.values())
    )

    right_norm = math.sqrt(
        sum(value ** 2 for value in right.values())
    )

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return dot_product / (left_norm * right_norm)


def rank_policy_sections(
    obligation_text: str,
    policy_sections: list[dict],
    top_k: int = 3,
    min_score: float = 0.05,
) -> list[PolicyMatch]:
    """
    Rank policy sections for a regulatory obligation.

    Parameters:
        obligation_text: Source regulatory obligation.
        policy_sections: Policy sections with IDs and text.
        top_k: Maximum number of returned candidates.
        min_score: Minimum lexical similarity.

    Returns:
        Ranked candidate matches.
    """

    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    if not 0 <= min_score <= 1:
        raise ValueError("min_score must be between 0 and 1")

    obligation_tokens = Counter(
        tokenize(obligation_text)
    )

    results = []

    for section in policy_sections:

        searchable_text = (
            section["section_title"]
            + "\n"
            + section["section_text"]
        )

        policy_tokens = Counter(
            tokenize(searchable_text)
        )

        score = cosine_similarity(
            obligation_tokens,
            policy_tokens,
        )

        if score < min_score or score == 0:
            continue

        matched_terms = sorted(
            set(obligation_tokens) & set(policy_tokens)
        )

        results.append(
            PolicyMatch(
                policy_section_id=str(section["id"]),
                section_number=section["section_number"],
                section_title=section["section_title"],
                score=round(score, 4),
                matched_terms=matched_terms,
                policy_text=section["section_text"],
            )
        )

    results.sort(
        key=lambda item: (
            -item.score,
            item.section_number,
            item.policy_section_id,
        )
    )

    return results[:top_k]
