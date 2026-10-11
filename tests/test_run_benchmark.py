import hashlib
import json

import pytest

from regintel.mapping.run_benchmark import run_benchmark


def test_relative_paths_hashes_and_partial_result(tmp_path):
    attempts = tmp_path / "attempts.json"
    attempts.write_text(json.dumps([{"attempt_id": "a", "scenario_id": "s", "method": "bm25",
                                     "duration_ms": 12, "outcome": "success"}]), encoding="utf-8")
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"runtime": {"attempts": "attempts.json"}}), encoding="utf-8")
    result = run_benchmark(config)
    assert result["inputs"]["runtime.attempts"]["sha256"] == hashlib.sha256(attempts.read_bytes()).hexdigest()
    assert result["config_sha256"] == hashlib.sha256(config.read_bytes()).hexdigest()
    assert set(result["components_not_supplied"]) == {"retrieval", "extraction", "gaps", "citations", "mapping"}
    assert result["results"]["runtime"]["methods"]["bm25"]["latency_ms"]["mean"] == 12


@pytest.mark.parametrize("configuration", [{}, {"unknown": {}}, {"runtime": {}}, {"runtime": {"attempts": "x", "k": 5}}])
def test_invalid_configuration_rejected(tmp_path, configuration):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError):
        run_benchmark(path)


def test_runner_preserves_review_validation(tmp_path):
    (tmp_path / "cases.json").write_text(json.dumps([{"scenario_id": "s", "review_status": "pending", "split": "test"}]), encoding="utf-8")
    (tmp_path / "predictions.json").write_text(json.dumps({"s": "missing"}), encoding="utf-8")
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"gaps": {"cases": "cases.json", "predictions": "predictions.json"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="approved"):
        run_benchmark(config)


def test_all_components_run_together_with_independent_inputs(tmp_path):
    # Toy fixtures verify integration, not project evaluation results.
    reviewed = {"review_status": "approved", "split": "test"}
    citation = {"source_sha256": "a" * 64, "page": 1, "clause_number": "2"}
    inputs = {
        "retrieval": ([{"scenario_id": "s", **reviewed, "relevant_section_ids": ["p"]}],
                      {method: {"s": ["p"]} for method in ("bm25", "vector", "hybrid")}),
        "extraction": ([{"case_id": "c", **reviewed, "annotation_complete": True,
                         "source_sha256": "a" * 64, "expected_obligation_ids": ["o"]}],
                       {"c": {"source_sha256": "a" * 64, "extracted_obligation_ids": ["o"]}}),
        "gaps": ([{"scenario_id": "s", **reviewed, "expected_gap_status": "missing"}], {"s": "missing"}),
        "citations": ([{"scenario_id": "s", **reviewed, "acceptable_citations": [citation]}], {"s": [citation]}),
        "mapping": ([{"pair_id": "pair", **reviewed, "obligation_id": "o", "policy_section_id": "p",
                      "expected_relevant": True}], {"pair": True}),
    }
    configuration = {}
    for component, (cases, predictions) in inputs.items():
        configuration[component] = {}
        for field, value in (("cases", cases), ("predictions", predictions)):
            filename = f"{component}_{field}.json"
            (tmp_path / filename).write_text(json.dumps(value), encoding="utf-8")
            configuration[component][field] = filename
    (tmp_path / "attempts.json").write_text(json.dumps([{"attempt_id": "a", "scenario_id": "s",
                                                        "method": "hybrid", "duration_ms": 10,
                                                        "outcome": "success", "input_tokens": 0, "output_tokens": 0}]), encoding="utf-8")
    configuration["runtime"] = {"attempts": "attempts.json"}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    result = run_benchmark(path)
    assert result["components_not_supplied"] == []
    assert len(result["inputs"]) == 11
    assert result["results"]["retrieval"]["methods"]["hybrid"]["recall_at_k"] == 1
    assert result["results"]["extraction"]["recall"] == 1
    assert result["results"]["gaps"]["accuracy"] == 1
    assert result["results"]["citations"]["case_coverage"] == 1
    assert result["results"]["mapping"]["f1"] == 1
    assert result["results"]["runtime"]["methods"]["hybrid"]["attempts"] == 1
