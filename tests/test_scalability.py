"""Benchmark safety, measured failures, recall gates, and synthetic evidence."""

from pathlib import Path

import pytest

from regintel.evidence.evaluation import evaluate
from regintel.mapping.scalability import (
    QUERIES,
    measure,
    run,
    score_labels,
    stress_snapshot,
    unique_rows,
    validate_url,
)


def test_benchmark_requires_separate_database_name():
    for name in ("regintel", "regintel_test", "regintel_benchmark_existing"):
        with pytest.raises(ValueError, match="benchmark database"):
            validate_url("postgresql+psycopg://localhost/" + name)
    validate_url("postgresql+psycopg://localhost/regintel_benchmark_" + "a" * 32)


def test_duplicate_source_quotes_not_inflated():
    rows = [
        {"id": "a", "content_hash": "one", "text": "must  review"},
        {"id": "b", "content_hash": "one", "text": "must review"},
        {"id": "c", "content_hash": "two", "text": "must review"},
    ]
    assert [r["id"] for r in unique_rows(rows)] == ["a", "c"]


def test_measured_attempts_count_failure_without_fabricated_recall():
    def search(query):
        if query == "fail":
            raise RuntimeError("fixture failure")
        return ["test-fixture-id"]

    result = measure(search, ["pass", "fail"], 2)
    assert result["error_rate"] == 0.5
    assert result["p50_ms"] >= 0
    assert result["requests_per_second"] > 0
    assert result["recall_at_5"] is None and result["recall_at_10"] is None
    assert result["attempts"][1]["error"] == "RuntimeError"


def test_no_synthetic_substitution_or_duplicate_genuine_rows():
    url = "postgresql+psycopg://localhost/regintel_benchmark_" + "a" * 32
    with pytest.raises(ValueError, match="Synthetic"):
        run({"workload": "unlabeled_synthetic"}, url)
    row = {"id": "a", "content_hash": "hash", "text": "quote"}
    with pytest.raises(ValueError, match="Duplicate"):
        run(
            {"workload": "genuine_source_pending_candidates", "records": [row, row]},
            url,
        )


def test_actual_multimodal_fixture_and_gap_evaluation():
    result = evaluate(Path(__file__).resolve().parents[1])
    assert len(result["extraction"]) == 7
    assert all(r["passed"] for r in result["extraction"])
    assert all(r["passed"] for r in result["gap_classification"])
    assert result["citation_checks"] == [True, True, True, True]
    assert result["pdf_citation_checks"] == [True, True, True]
    assert result["operating_failed_ids"] == ["SYN-002"]
    assert result["independent_ocr_accuracy"] is None


def test_synthetic_stress_stays_out_of_regulatory_coverage():
    result = stress_snapshot(10000)
    assert result["regulatory_coverage_rows"] == 0
    assert result["synthetic"] is True
    assert len(unique_rows(result["records"])) == 10000
    assert all("SYNTHETIC" in r["text"] for r in result["records"])
    with pytest.raises(ValueError):
        stress_snapshot(10001)


def test_recall_requires_reviewed_exact_subset_labels():
    # Artificial rankings/reference IDs verify scorer plumbing only, never benchmark scores.
    cases = [
        {
            "scenario_id": f"probe-{i}",
            "query": query,
            "review_status": "pending",
            "split": "test",
            "relevant_section_ids": ["fixture"],
        }
        for i, query in enumerate(QUERIES)
    ]
    attempts = [{"ids": ["fixture"]} for _ in QUERIES]
    methods = {
        name: [{"attempts": attempts}] for name in ("bm25", "exact_vector", "hybrid")
    }
    with pytest.raises(ValueError, match="approved"):
        score_labels(cases, methods, [{"id": "fixture"}])
    for case in cases:
        case["review_status"] = "approved"  # synthetic unit-test reference only
    result = score_labels(cases, methods, [{"id": "fixture"}])
    assert set(result) == {"5", "10"}
    with pytest.raises(ValueError, match="subset"):
        score_labels(cases, methods, [{"id": "another-fixture"}])
