import pytest

from regintel.mapping.runtime_benchmark import summarize_runtime


def attempt(identifier="1", **changes):
    return {"attempt_id": identifier, "scenario_id": "s1", "method": "hybrid",
            "duration_ms": 10, "outcome": "success", "input_tokens": 20, "output_tokens": 5, **changes}


def test_failures_count_and_missing_usage_is_not_zero():
    result = summarize_runtime([attempt(), attempt("2", duration_ms=30, outcome="failure", input_tokens=None)])
    row = result["methods"]["hybrid"]
    assert row["failures"] == 1
    assert row["unique_scenarios"] == 1
    assert row["latency_ms"] == {"mean": 20, "p50": 10, "p95": 30, "maximum": 30}
    assert row["usage"]["input_tokens"]["known_total"] == 20
    assert row["usage"]["input_tokens"]["complete_total"] is None
    assert row["usage"]["output_tokens"]["complete_total"] == 10


@pytest.mark.parametrize("changes", [{"duration_ms": float("nan")}, {"duration_ms": float("inf")}, {"duration_ms": -1},
                                     {"duration_ms": True}, {"input_tokens": -1}, {"output_tokens": 1.5}, {"outcome": "pending"}])
def test_invalid_measurements_rejected(changes):
    with pytest.raises(ValueError):
        summarize_runtime([attempt(**changes)])


def test_empty_and_duplicate_attempts_rejected():
    with pytest.raises(ValueError):
        summarize_runtime([])
    with pytest.raises(ValueError):
        summarize_runtime([attempt(), attempt()])


def test_methods_are_separate_and_unreported_tokens_stay_unknown():
    row = attempt(method="bm25")
    del row["input_tokens"]
    result = summarize_runtime([row, attempt("2")])
    assert set(result["methods"]) == {"bm25", "hybrid"}
    assert result["methods"]["bm25"]["usage"]["input_tokens"]["missing_attempts"] == 1
