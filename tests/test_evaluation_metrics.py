
import pytest

from regintel.mapping.evaluation_metrics import (
    recall_at_k,
    reciprocal_rank,
    mean_reciprocal_rank,
)


def test_recall_at_one():
    assert recall_at_k(
        ["a", "b", "c"],
        {"b"},
        1,
    ) == 0.0


def test_recall_at_three():
    assert recall_at_k(
        ["a", "b", "c"],
        {"b"},
        3,
    ) == 1.0


def test_recall_multiple_relevant():
    assert recall_at_k(
        ["a", "b", "c"],
        {"b", "d"},
        3,
    ) == 0.5


def test_reciprocal_rank():
    assert reciprocal_rank(
        ["a", "b", "c"],
        {"b"},
    ) == 0.5


def test_reciprocal_rank_missing():
    assert reciprocal_rank(
        ["a", "b"],
        {"c"},
    ) == 0.0


def test_mrr():
    result = mean_reciprocal_rank(
        [["a", "b"], ["c", "d"]],
        [{"b"}, {"c"}],
    )

    assert result == pytest.approx(0.75)


def test_empty_relevance_rejected():
    with pytest.raises(ValueError):
        recall_at_k(["a"], set(), 1)


def test_invalid_k_rejected():
    with pytest.raises(ValueError):
        recall_at_k(["a"], {"a"}, 0)


def test_mismatched_mrr_inputs():
    with pytest.raises(ValueError):
        mean_reciprocal_rank(
            [["a"]],
            [{"a"}, {"b"}],
        )
