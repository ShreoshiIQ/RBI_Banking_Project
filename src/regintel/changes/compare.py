"""Compare extracted clauses from two preserved versions of one instrument."""

import argparse
import difflib
import json
from collections import Counter
from pathlib import Path


def normalized(text: str) -> str:
    # Preserve case, punctuation, quantities, and negation.
    return " ".join(text.split())


def index_clauses(version: dict) -> dict:
    clauses = {}
    for clause in version["clauses"]:
        number = str(clause["clause_number"])
        if number in clauses:
            raise ValueError(f"Duplicate clause number: {number}")
        if not clause["clause_text"].strip():
            raise ValueError(f"Empty source clause: {number}")
        clauses[number] = clause
    return clauses


def compare_versions(before: dict, after: dict) -> dict:
    if not before.get("document_id") or before["document_id"] != after.get("document_id"):
        raise ValueError("Revision comparison requires the same instrument identity; replacements need separate mapping")
    if not before.get("content_hash") or not after.get("content_hash"):
        raise ValueError("Both source versions require content hashes")
    old, new = index_clauses(before), index_clauses(after)
    if before["content_hash"] == after["content_hash"] and old != new:
        raise ValueError("Same source hash has different extracted clauses; compare extraction revisions separately")
    changes = []
    for number in sorted(old.keys() | new.keys()):
        a, b = old.get(number), new.get(number)
        if a is None:
            kind = "added"
        elif b is None:
            kind = "removed"
        elif normalized(a["clause_text"]) == normalized(b["clause_text"]) and a.get("status", "active") == b.get("status", "active"):
            kind = "unchanged"
        else:
            kind = "modified"
        delta = ""
        if kind == "modified":
            delta = "\n".join(difflib.unified_diff(
                normalized(a["clause_text"]).split(), normalized(b["clause_text"]).split(),
                fromfile="before", tofile="after", lineterm="",
            ))
        changes.append({"clause_number": number, "change_type": kind, "before": a, "after": b, "word_diff": delta})
    # Exact matching across numbers is a review hint, never automatic legal mapping.
    hints = []
    for removed in (row for row in changes if row["change_type"] == "removed"):
        for added in (row for row in changes if row["change_type"] == "added"):
            if normalized(removed["before"]["clause_text"]) == normalized(added["after"]["clause_text"]):
                hints.append({"from_clause": removed["clause_number"], "to_clause": added["clause_number"], "review_status": "pending"})
    return {
        "schema_version": 1, "document_id": before["document_id"],
        "before_hash": before["content_hash"], "after_hash": after["content_hash"],
        "summary": dict(Counter(row["change_type"] for row in changes)),
        "changes": changes, "possible_renumberings": hints,
        "notice": "Textual differences, not legally verified amendments or compliance impact. Source hashes must be independently verified.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare_versions(*[json.loads(path.read_text(encoding="utf-8")) for path in (args.before, args.after)])
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
