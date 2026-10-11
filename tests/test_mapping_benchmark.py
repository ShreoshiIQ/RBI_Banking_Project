import pytest

from regintel.mapping.mapping_benchmark import score_mapping


def cases():
    return [{"pair_id": str(index), "obligation_id": "o1", "policy_section_id": f"s{index}",
             "review_status": "approved", "split": "test", "expected_relevant": label}
            for index, label in enumerate((True, True, False, False))]


def test_hand_calculated_metrics_and_pair_errors():
    result = score_mapping(cases(), {"0": True, "1": False, "2": True, "3": False})
    assert result["precision"] == result["recall"] == result["f1"] == result["accuracy"] == 0.5
    assert [row["error_type"] for row in result["errors"]] == ["false_negatives", "false_positives"]


@pytest.mark.parametrize("field,value", [("review_status", "pending"), ("split", "train"), ("expected_relevant", 1), ("obligation_id", "")])
def test_invalid_reference_rejected(field, value):
    rows = cases()
    rows[0][field] = value
    with pytest.raises(ValueError):
        score_mapping(rows, {str(index): True for index in range(4)})


def test_duplicate_pairs_and_missing_predictions_rejected():
    rows = cases()
    rows[1]["policy_section_id"] = rows[0]["policy_section_id"]
    with pytest.raises(ValueError):
        score_mapping(rows, {str(index): True for index in range(4)})
    with pytest.raises(ValueError):
        score_mapping(cases(), {})


def test_string_predictions_rejected():
    with pytest.raises(ValueError):
        score_mapping(cases(), {str(index): "true" for index in range(4)})
