"""Export and validate offline human dataset review decisions."""

import argparse
import hashlib
import json
from pathlib import Path


def identity(row: dict) -> str:
    # Bind decisions to the complete original candidate, not just its quote.
    payload = json.dumps(row["source"], sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def review_template(report: dict) -> dict:
    return {
        "schema_version": 1,
        "source_hash": report["source_metadata"]["sha256"],
        "decisions": [{
            "candidate_index": row["candidate_index"],
            "candidate_hash": identity(row),
            "status": "pending", "reviewer": "", "rationale": "",
            "actor": "", "applicability": "", "source_citation": "",
        } for row in report["candidates"]],
    }


def reviewed_catalog(report: dict, decisions: dict) -> dict:
    if decisions.get("schema_version") != 1:
        raise ValueError("Unsupported review schema")
    if decisions.get("source_hash") != report["source_metadata"]["sha256"]:
        raise ValueError("Review source hash does not match the report")
    rows = {row["candidate_index"]: row for row in report["candidates"]}
    seen = set()
    approved = []
    counts = {"pending": 0, "approved": 0, "rejected": 0}
    for decision in decisions["decisions"]:
        index = decision["candidate_index"]
        if type(index) is not int or index not in rows or index in seen:
            raise ValueError("Unknown or duplicate candidate index")
        seen.add(index)
        row = rows[index]
        if decision.get("candidate_hash") != identity(row):
            raise ValueError(f"Stale candidate decision: {index}")
        status = decision.get("status")
        if status not in counts:
            raise ValueError(f"Invalid review status: {index}")
        if status != "pending":
            for field in ("reviewer", "rationale", "source_citation"):
                if not isinstance(decision.get(field), str) or not decision[field].strip():
                    raise ValueError(f"Reviewed candidate {index} requires {field}")
        if status == "approved":
            if report["source_metadata"].get("source_status_check", {}).get("current_obligation_extraction_allowed") is False:
                raise ValueError("Withdrawn source cannot enter the current reviewed catalog")
            for field in ("actor", "applicability"):
                if not isinstance(decision.get(field), str) or not decision[field].strip():
                    raise ValueError(f"Approved candidate {index} requires {field}")
            if decision["actor"].strip().casefold() == "unresolved":
                raise ValueError(f"Approved candidate {index} has unresolved actor")
            if row["evidence_match"] == "unmatched":
                raise ValueError(f"Approved candidate {index} has unmatched evidence")
            approved.append({"original_candidate": row["source"], "human_review": decision})
        counts[status] += 1
    counts["pending"] += len(rows) - len(seen)
    return {
        "schema_version": 1, "source_metadata": report["source_metadata"],
        "notice": "Recorded offline human decisions; not regulatory certification or authenticated API review.",
        "summary": counts, "approved_candidates": approved,
        "decisions": decisions["decisions"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    result = (
        reviewed_catalog(report, json.loads(args.decisions.read_text(encoding="utf-8")))
        if args.decisions else review_template(report)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite a source artifact or a completed review file.
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
    print(f"Created {args.output}")


if __name__ == "__main__":
    main()
