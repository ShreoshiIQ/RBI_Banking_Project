"""Score exact-ID extraction matches on completely annotated source units."""

import argparse
import json
from pathlib import Path


def _ids(value):
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError("Obligation IDs must be an array of nonempty strings")
    if len(set(value)) != len(value):
        raise ValueError("Duplicate obligation IDs are not allowed")
    return set(value)


def score_extraction(cases: list[dict], predictions: dict) -> dict:
    if not cases:
        raise ValueError("A nonempty reviewed test set is required")
    ids = [case["case_id"] for case in cases]
    if any(not isinstance(item, str) or not item.strip() for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("Case IDs must be nonempty and unique")
    if set(predictions) != set(ids):
        raise ValueError("Predictions must cover exactly the reference cases")
    totals = {"true_positives": 0, "false_positives": 0, "false_negatives": 0}
    details = []
    for case in cases:
        if case.get("review_status") != "approved" or case.get("split") != "test" or case.get("annotation_complete") is not True:
            raise ValueError("Each case needs approved, complete test annotations")
        source_hash = case.get("source_sha256")
        if not isinstance(source_hash, str) or len(source_hash) != 64 or any(char not in "0123456789abcdef" for char in source_hash):
            raise ValueError("Each case requires a lowercase SHA-256 source digest")
        prediction = predictions[case["case_id"]]
        if not isinstance(prediction, dict) or prediction.get("source_sha256") != source_hash:
            raise ValueError("Prediction source digest must match the reviewed source")
        reference = _ids(case.get("expected_obligation_ids"))
        extracted = _ids(prediction.get("extracted_obligation_ids"))
        tp, fp, fn = len(reference & extracted), len(extracted - reference), len(reference - extracted)
        for key, value in zip(totals, (tp, fp, fn)):
            totals[key] += value
        details.append({"case_id": case["case_id"], "source_sha256": source_hash,
                        "true_positives": tp, "false_positives": fp, "false_negatives": fn,
                        "unexpected_obligation_ids": sorted(extracted - reference),
                        "missed_obligation_ids": sorted(reference - extracted)})
    tp, fp, fn = (totals[key] for key in totals)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"schema_version": 1, "cases_scored": len(cases), "matching": "exact_reviewed_obligation_id",
            "aggregation": "micro", "zero_division": 0, **totals,
            "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "per_case": details}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = score_extraction(json.loads(args.cases.read_text(encoding="utf-8")), json.loads(args.predictions.read_text(encoding="utf-8")))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)


if __name__ == "__main__":
    main()
