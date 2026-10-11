"""Hypothetical clause edits with explicit simulation provenance."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from regintel.changes.compare import compare_versions, index_clauses
from regintel.changes.impact import shortlist_impacts


def simulate(base: dict, proposal: dict, sections: list[dict]) -> dict:
    if proposal.get("base_content_hash") != base.get("content_hash"):
        raise ValueError("Proposal targets a different baseline")
    clauses = deepcopy(index_clauses(base))
    seen = set()
    for edit in proposal["edits"]:
        number = str(edit["clause_number"])
        if number in seen:
            raise ValueError("Repeated edits to the same clause")
        seen.add(number)
        operation = edit["operation"]
        if operation not in ("add", "modify", "remove"):
            raise ValueError("Unsupported simulation operation")
        if operation == "add" and number in clauses:
            raise ValueError("Cannot add an existing clause")
        if operation != "add" and number not in clauses:
            raise ValueError("Cannot modify or remove a missing clause")
        if operation == "remove":
            del clauses[number]
        else:
            text = edit.get("clause_text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Hypothetical text is required")
            # Do not attach real PDF page citations to hypothetical wording.
            clauses[number] = {"clause_number": number, "clause_text": text, "status": "active", "synthetic": True}
    hypothetical = {"document_id": base["document_id"], "clauses": list(clauses.values()), "synthetic": True}
    hypothetical["content_hash"] = "simulation:" + hashlib.sha256(
        json.dumps(hypothetical, sort_keys=True).encode()
    ).hexdigest()
    comparison = compare_versions(base, hypothetical)
    comparison.update(simulation=True, notice="Hypothetical textual changes; not an actual regulatory amendment.")
    impacts = shortlist_impacts(comparison, sections)
    impacts.update(simulation=True, notice="Hypothetical lexical policy shortlist; not an actual compliance impact.")
    return {
        "schema_version": 1, "simulation": True, "baseline": base,
        "proposal": proposal, "hypothetical_version": hypothetical,
        "comparison": comparison, "policy_shortlist": impacts,
        "notice": "WHAT-IF SIMULATION ONLY. No source files, regulatory records, or review statuses were changed.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("proposal", type=Path)
    parser.add_argument("policy_sections", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = simulate(*[json.loads(path.read_text(encoding="utf-8")) for path in (args.baseline, args.proposal, args.policy_sections)])
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
