import pytest

from regintel.mapping.extraction_benchmark import score_extraction


def data():
    cases = [{"case_id": "clause1", "review_status": "approved", "split": "test", "annotation_complete": True,
              "source_sha256": "a" * 64, "expected_obligation_ids": ["o1", "o2"]}]
    predictions = {"clause1": {"source_sha256": "a" * 64, "extracted_obligation_ids": ["o2", "extra"]}}
    return cases, predictions


def test_known_precision_recall_and_error_ids():
    result = score_extraction(*data())
    assert result["precision"] == result["recall"] == result["f1"] == 0.5
    assert result["per_case"][0]["missed_obligation_ids"] == ["o1"]
    assert result["per_case"][0]["unexpected_obligation_ids"] == ["extra"]


@pytest.mark.parametrize("field,value", [("review_status", "pending"), ("split", "train"), ("annotation_complete", False), ("source_sha256", "bad"), ("expected_obligation_ids", ["o1", "o1"])])
def test_reject_invalid_reference(field, value):
    cases, predictions = data()
    cases[0][field] = value
    with pytest.raises(ValueError):
        score_extraction(cases, predictions)


def test_reject_mismatched_source_or_missing_case():
    cases, predictions = data()
    predictions["clause1"]["source_sha256"] = "b" * 64
    with pytest.raises(ValueError):
        score_extraction(cases, predictions)
    with pytest.raises(ValueError):
        score_extraction(cases, {})


def test_empty_annotated_unit_is_valid_and_ratios_are_zero():
    cases, predictions = data()
    cases[0]["expected_obligation_ids"] = []
    predictions["clause1"]["extracted_obligation_ids"] = []
    result = score_extraction(cases, predictions)
    assert result["precision"] == result["recall"] == 0
