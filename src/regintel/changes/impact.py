"""Rank policy passages for review of textual regulatory changes."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from regintel.mapping.bm25_retriever import BM25PolicyRetriever


def shortlist_impacts(comparison: dict, sections: list[dict], top_k: int = 3) -> dict:
    if top_k < 1:
        raise ValueError("top_k must be positive")
    ids = [str(section["id"]) for section in sections]
    if len(ids) != len(set(ids)):
        raise ValueError("Policy section IDs must be unique")
    lookup = {str(section["id"]): section for section in sections}
    retriever = BM25PolicyRetriever(sections)
    results = []
    for change in comparison["changes"]:
        kind = change["change_type"]
        if kind == "unchanged":
            continue
        if kind not in ("added", "removed", "modified"):
            raise ValueError("Unknown clause change type")
        # Search each side independently so removed requirements remain visible.
        candidates = {}
        for side in ("before", "after"):
            clause = change.get(side)
            if clause is None:
                continue
            for match in retriever.search(clause["clause_text"], top_k=top_k):
                entry = candidates.setdefault(match.policy_section_id, {
                    "policy_section": lookup[match.policy_section_id],
                    "matches": [], "review_status": "pending",
                })
                entry["matches"].append({"source_side": side, **asdict(match)})
        results.append({
            "clause_number": change["clause_number"], "change_type": kind,
            "before": change.get("before"), "after": change.get("after"),
            "candidate_policy_sections": list(candidates.values()),
            "match_status": "candidates_found" if candidates else "no_lexical_match",
        })
    return {
        "schema_version": 1, "document_id": comparison["document_id"],
        "before_hash": comparison["before_hash"], "after_hash": comparison["after_hash"],
        "method": "BM25_before_and_after", "impacts": results,
        "notice": "Lexical review shortlist, not confirmed affected controls or compliance decisions. No match does not prove no impact.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comparison", type=Path)
    parser.add_argument("policy_sections", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    result = shortlist_impacts(
        json.loads(args.comparison.read_text(encoding="utf-8")),
        json.loads(args.policy_sections.read_text(encoding="utf-8")), args.top_k,
    )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
