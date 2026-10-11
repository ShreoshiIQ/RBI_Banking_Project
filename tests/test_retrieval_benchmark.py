import copy

import pytest

from regintel.mapping.retrieval_benchmark import METHODS, score_retrieval


def fixture_data():
    cases = [{"scenario_id": "a", "review_status": "approved", "split": "test", "relevant_section_ids": ["s1", "s2"]},
             {"scenario_id": "b", "review_status": "approved", "split": "test", "relevant_section_ids": ["s3"]}]
    rankings = {method: {"a": ["wrong", "s1", "s2"], "b": []} for method in METHODS}
    return cases, rankings


def test_macro_metrics_cutoff_and_empty_results():
    cases, rankings = fixture_data()
    original = copy.deepcopy(rankings)
    result = score_retrieval(cases, rankings, 2)
    for method in METHODS:
        assert result["methods"][method]["recall_at_k"] == 0.25
        assert result["methods"][method]["mrr_at_k"] == 0.25
    assert rankings == original


@pytest.mark.parametrize("field,value", [("review_status", "pending"), ("split", "train"), ("relevant_section_ids", []), ("relevant_section_ids", ["s1", "s1"])])
def test_reject_unreviewed_or_invalid_references(field, value):
    cases, rankings = fixture_data()
    cases[0][field] = value
    with pytest.raises(ValueError):
        score_retrieval(cases, rankings)


def test_reject_missing_case_and_duplicate_rankings():
    cases, rankings = fixture_data()
    del rankings["vector"]["b"]
    with pytest.raises(ValueError):
        score_retrieval(cases, rankings)
    cases, rankings = fixture_data()
    rankings["hybrid"]["a"] = ["s1", "s1"]
    with pytest.raises(ValueError):
        score_retrieval(cases, rankings)


@pytest.mark.parametrize("k", [0, -1, True, 1.5])
def test_reject_invalid_cutoff(k):
    with pytest.raises(ValueError):
        score_retrieval(*fixture_data(), k)
