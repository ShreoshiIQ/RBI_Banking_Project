"""Evaluate exact citation locations against reviewed acceptable references."""

import argparse
import json
from pathlib import Path


def citation_key(citation: dict) -> tuple:
    if not isinstance(citation, dict) or set(citation) != {"source_sha256", "page", "clause_number"}:
        raise ValueError("Citations require exactly source_sha256, page, and clause_number")
    digest, page, clause = (citation[key] for key in ("source_sha256", "page", "clause_number"))
    if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("Citation source must be a lowercase SHA-256 digest")
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ValueError("Citation page must be a positive one-based PDF page index")
    if not isinstance(clause, str) or not clause.strip():
        raise ValueError("Citation clause number is required")
    return digest, page, clause


def citation_keys(citations):
    if not isinstance(citations, list):
        raise ValueError("Citations must be an array")
    keys = [citation_key(citation) for citation in citations]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate citation locations are not allowed")
    return keys


def score_citations(cases: list[dict], predictions: dict) -> dict:
    if not cases:
        raise ValueError("A nonempty reviewed test set is required")
    ids = [case["scenario_id"] for case in cases]
    if any(not isinstance(item, str) or not item.strip() for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("Scenario IDs must be nonempty and unique")
    if set(predictions) != set(ids):
        raise ValueError("Predictions must cover exactly the reviewed cases")
    correct = submitted = covered = 0
    details = []
    for case in cases:
        if case.get("review_status") != "approved" or case.get("split") != "test":
            raise ValueError("Cases must contain approved test references")
        acceptable = set(citation_keys(case.get("acceptable_citations")))
        if not acceptable:
            raise ValueError("Each case requires at least one acceptable citation")
        citations = predictions[case["scenario_id"]]
        keys = citation_keys(citations)
        matched = sum(key in acceptable for key in keys)
        submitted += len(keys)
        correct += matched
        covered += int(matched > 0)
        details.append({"scenario_id": case["scenario_id"], "submitted": len(keys), "correct": matched,
                        "has_correct_citation": matched > 0,
                        "incorrect_citations": [citation for citation, key in zip(citations, keys) if key not in acceptable]})
    return {"schema_version": 1, "cases_scored": len(cases), "citations_submitted": submitted,
            "correct_citations": correct, "citation_location_precision": correct / submitted if submitted else 0.0,
            "case_coverage": covered / len(cases), "zero_division": 0,
            "matching": "exact_source_sha256_pdf_page_clause", "per_case": details}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = score_citations(json.loads(args.cases.read_text(encoding="utf-8")), json.loads(args.predictions.read_text(encoding="utf-8")))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)


if __name__ == "__main__":
    main()
