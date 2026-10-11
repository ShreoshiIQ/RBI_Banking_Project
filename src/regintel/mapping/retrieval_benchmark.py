"""Score exported retrieval rankings against reviewed held-out references."""

import argparse
import json
from pathlib import Path

from regintel.mapping.evaluation_metrics import recall_at_k, reciprocal_rank

METHODS = ("bm25", "vector", "hybrid")


def score_retrieval(cases: list[dict], rankings: dict, k: int = 5) -> dict:
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer")
    if not cases:
        raise ValueError("A nonempty reviewed evaluation set is required")
    ids = [case["scenario_id"] for case in cases]
    if any(not isinstance(item, str) or not item.strip() for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("Scenario IDs must be nonempty and unique")
    references = {}
    for case in cases:
        if case.get("review_status") != "approved" or case.get("split") != "test":
            raise ValueError("Every case must be approved and assigned to the test split")
        relevant = case.get("relevant_section_ids")
        if not isinstance(relevant, list) or not relevant or any(not isinstance(item, str) or not item.strip() for item in relevant):
            raise ValueError("Each case requires nonempty reference section IDs")
        if len(set(relevant)) != len(relevant):
            raise ValueError("Duplicate reference section IDs")
        references[case["scenario_id"]] = set(relevant)
    if set(rankings) != set(METHODS):
        raise ValueError("Provide exactly bm25, vector, and hybrid rankings")
    results = {}
    for method in METHODS:
        entries = rankings[method]
        if not isinstance(entries, dict) or set(entries) != set(ids):
            raise ValueError("Every method must rank exactly the same evaluation cases")
        per_case = []
        for scenario_id in ids:
            ranked = entries[scenario_id]
            if not isinstance(ranked, list) or any(not isinstance(item, str) or not item.strip() for item in ranked):
                raise ValueError("Rankings must contain section ID strings")
            if len(set(ranked)) != len(ranked):
                raise ValueError("Rankings must not contain duplicate section IDs")
            relevant = references[scenario_id]
            top = ranked[:k]
            recall = recall_at_k(ranked, relevant, k)
            rr = reciprocal_rank(top, relevant)
            per_case.append({"scenario_id": scenario_id, "recall_at_k": recall, "reciprocal_rank_at_k": rr})
        results[method] = {
            "recall_at_k": sum(row["recall_at_k"] for row in per_case) / len(cases),
            "mrr_at_k": sum(row["reciprocal_rank_at_k"] for row in per_case) / len(cases),
            "per_case": per_case,
        }
    return {"schema_version": 1, "k": k, "cases_scored": len(cases), "methods": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("rankings", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    result = score_retrieval(json.loads(args.cases.read_text(encoding="utf-8")), json.loads(args.rankings.read_text(encoding="utf-8")), args.k)
    # Exclusive creation preserves existing benchmark artifacts.
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)


if __name__ == "__main__":
    main()
