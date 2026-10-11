"""Evaluate relevance decisions for reviewed obligation-policy pairs."""


def score_mapping(cases: list[dict], predictions: dict) -> dict:
    if not cases:
        raise ValueError("A nonempty reviewed mapping test set is required")
    ids = [case["pair_id"] for case in cases]
    if any(not isinstance(item, str) or not item.strip() for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("Pair IDs must be nonempty and unique")
    if set(predictions) != set(ids):
        raise ValueError("Predictions must cover exactly the reviewed pairs")
    seen = set()
    counts = {"true_positives": 0, "false_positives": 0, "false_negatives": 0, "true_negatives": 0}
    errors = []
    for case in cases:
        if case.get("review_status") != "approved" or case.get("split") != "test":
            raise ValueError("Pairs must have approved test labels")
        pair = tuple(case.get(field) for field in ("obligation_id", "policy_section_id"))
        if any(not isinstance(item, str) or not item.strip() for item in pair) or pair in seen:
            raise ValueError("Obligation-policy pairs must be nonempty and unique")
        seen.add(pair)
        actual = case.get("expected_relevant")
        predicted = predictions[case["pair_id"]]
        if not isinstance(actual, bool) or not isinstance(predicted, bool):
            raise ValueError("Relevance labels and predictions must be booleans")
        key = ("true_positives" if predicted else "false_negatives") if actual else ("false_positives" if predicted else "true_negatives")
        counts[key] += 1
        if actual != predicted:
            errors.append({"pair_id": case["pair_id"], "obligation_id": pair[0], "policy_section_id": pair[1],
                           "expected_relevant": actual, "predicted_relevant": predicted, "error_type": key})
    tp, fp, fn = (counts[key] for key in ("true_positives", "false_positives", "false_negatives"))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"schema_version": 1, "pairs_scored": len(cases), **counts,
            "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "accuracy": (tp + counts["true_negatives"]) / len(cases),
            "positive_label": "relevant", "zero_division": 0, "errors": errors}
