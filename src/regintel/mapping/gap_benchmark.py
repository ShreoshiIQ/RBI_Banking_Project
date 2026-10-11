"""Offline multiclass evaluation of exported gap predictions."""

import argparse
import json
from pathlib import Path

from regintel.reporting.schemas import GapStatus

LABELS = tuple(status.value for status in GapStatus)


def score_gaps(cases: list[dict], predictions: dict[str, str]) -> dict:
    if not cases:
        raise ValueError("A nonempty reviewed test set is required")
    ids = [case["scenario_id"] for case in cases]
    if any(not isinstance(item, str) or not item.strip() for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("Scenario IDs must be nonempty and unique")
    if set(predictions) != set(ids):
        raise ValueError("Predictions must cover exactly the evaluation cases")
    confusion = {actual: {predicted: 0 for predicted in LABELS} for actual in LABELS}
    errors = []
    for case in cases:
        if case.get("review_status") != "approved" or case.get("split") != "test":
            raise ValueError("Cases must have approved labels and belong to the test split")
        actual = case.get("expected_gap_status")
        predicted = predictions[case["scenario_id"]]
        if actual not in LABELS or predicted not in LABELS:
            raise ValueError("Labels must use the reporting GapStatus values")
        confusion[actual][predicted] += 1
        if actual != predicted:
            errors.append({"scenario_id": case["scenario_id"], "expected": actual, "predicted": predicted})
    metrics = {}
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in LABELS if other != label)
        fn = sum(confusion[label][other] for other in LABELS if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        metrics[label] = {
            "support": sum(confusion[label].values()), "true_positives": tp,
            "false_positives": fp, "false_negatives": fn,
            "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "false_positive_scenario_ids": [row["scenario_id"] for row in errors if row["predicted"] == label],
            "false_negative_scenario_ids": [row["scenario_id"] for row in errors if row["expected"] == label],
        }
    return {
        "schema_version": 1, "cases_scored": len(cases),
        "accuracy": sum(confusion[label][label] for label in LABELS) / len(cases),
        "macro": {name: sum(row[name] for row in metrics.values()) / len(LABELS) for name in ("precision", "recall", "f1")},
        "per_class": metrics, "confusion_matrix": confusion, "errors": errors,
        "zero_division": 0, "macro_label_scope": list(LABELS),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = score_gaps(json.loads(args.cases.read_text(encoding="utf-8")), json.loads(args.predictions.read_text(encoding="utf-8")))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)


if __name__ == "__main__":
    main()
