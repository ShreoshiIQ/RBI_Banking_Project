import pytest

from regintel.mapping.gap_benchmark import score_gaps


def cases():
    return [{"scenario_id": str(index), "review_status": "approved", "split": "test", "expected_gap_status": label}
            for index, label in enumerate(("supported", "missing", "missing", "partial"))]


def test_hand_calculated_confusion_and_errors():
    result = score_gaps(cases(), {"0": "supported", "1": "missing", "2": "partial", "3": "missing"})
    assert result["accuracy"] == 0.5
    missing = result["per_class"]["missing"]
    assert missing["precision"] == missing["recall"] == missing["f1"] == 0.5
    assert missing["false_positive_scenario_ids"] == ["3"]
    assert missing["false_negative_scenario_ids"] == ["2"]
    assert result["macro"]["f1"] == 0.375
    assert result["per_class"]["potential_conflict"]["support"] == 0


@pytest.mark.parametrize("field,value", [("review_status", "pending"), ("split", "train"), ("expected_gap_status", None), ("expected_gap_status", "compliant")])
def test_reject_unreviewed_or_unknown_reference(field, value):
    rows = cases()
    rows[0][field] = value
    with pytest.raises(ValueError):
        score_gaps(rows, {str(index): "missing" for index in range(4)})


def test_reject_missing_predictions_and_unknown_predictions():
    with pytest.raises(ValueError):
        score_gaps(cases(), {})
    with pytest.raises(ValueError):
        score_gaps(cases(), {str(index): "unknown" for index in range(4)})


def test_reject_duplicate_cases_and_empty_set():
    with pytest.raises(ValueError):
        score_gaps([cases()[0], cases()[0]], {"0": "supported"})
    with pytest.raises(ValueError):
        score_gaps([], {})
