"""Deterministic dataset checks; no database writes or legal approval."""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from uuid import UUID

from regintel.ingestion.obligation_quality import evaluate_obligation
from regintel.ingestion.obligation_extractor import extract_with_tracking
from regintel.ingestion.actor_review import suggest_actor
from regintel.ingestion.source_status import inspect_source_status


def normalize(text: str) -> str:
    return " ".join(text.split()).casefold()


def evidence_match(item: dict, clause: dict | None) -> str:
    """Check direct quotes or source-reconstructable inherited evidence."""
    if clause is None or not item.get("evidence_quote", "").strip():
        return "unmatched"
    quote = normalize(item["evidence_quote"])
    if quote in normalize(clause["clause_text"]):
        return "contiguous"
    if item.get("extraction_method") != "rule_based_v4_1_inherited":
        return "unmatched"
    reconstructed = extract_with_tracking(
        source_clause_id=UUID(int=0),
        clause_number=str(clause["clause_number"]),
        clause_text=clause["clause_text"],
        status=clause.get("status", "active"),
    )
    for candidate in reconstructed.obligations:
        if candidate.extraction_method == "rule_based_v4_1_inherited" and normalize(candidate.evidence_quote) == quote:
            return "inherited_reconstruction"
    return "unmatched"


def validate_catalog(catalog: dict, clauses: list[dict], manifest: dict) -> dict:
    clause_index = {str(item["clause_number"]): item for item in clauses}
    seen = {}
    rows = []
    counts = Counter()
    for index, item in enumerate(catalog["obligations"]):
        evidence = item.get("evidence_quote", "")
        reasons = list(evaluate_obligation(evidence).reasons)
        clause = clause_index.get(str(item.get("clause_number")))
        match = evidence_match(item, clause)
        if clause is None:
            reasons.append("missing_source_clause")
        else:
            if clause.get("status") != "active":
                reasons.append("inactive_source_clause")
            if match == "unmatched":
                reasons.append("evidence_not_in_source_clause")
        for field in ("source_clause_id", "document_version_id", "source_url", "content_hash"):
            if not item.get(field):
                reasons.append("missing_" + field)
        if item.get("content_hash") != manifest.get("sha256"):
            reasons.append("source_hash_mismatch")
        if item.get("source_url") != manifest.get("source_url"):
            reasons.append("source_url_mismatch")
        start, end = item.get("start_page"), item.get("end_page")
        if not (type(start) is int and type(end) is int and 1 <= start <= end <= manifest["page_count"]):
            reasons.append("invalid_page_range")
        elif clause and not (clause["start_page"] <= start <= end <= clause["end_page"]):
            reasons.append("pages_outside_source_clause")
        if normalize(item.get("actor", "")) in ("", "unresolved"):
            reasons.append("unresolved_actor")
        if str(item.get("clause_number")) in ("1", "2", "3"):
            reasons.append("preliminary_or_applicability_clause")
        if len(evidence) > 600:
            reasons.append("long_evidence")
        fingerprint = hashlib.sha256(normalize(evidence).encode()).hexdigest()
        key = (item.get("document_version_id"), fingerprint)
        duplicate_of = seen.get(key)
        if duplicate_of is not None:
            reasons.append("duplicate_evidence")
        else:
            seen[key] = index
        reasons = sorted(set(reasons))
        counts.update(reasons)
        rows.append({
            "candidate_index": index, "fingerprint": fingerprint,
            "evidence_match": match,
            "actor_review": suggest_actor(item, match),
            "duplicate_of": duplicate_of, "issues": reasons,
            "validation_status": "needs_review" if reasons else "candidate",
            "human_review_status": item.get("review_status", "pending"),
            "source": item,
        })
    return {
        "schema_version": 1,
        "notice": "Heuristic validation only; candidates are not legally validated obligations.",
        "source_metadata": manifest,
        "extraction_metadata": {k: v for k, v in catalog.items() if k not in ("obligations", "deferred_passages")},
        "summary": {
            "total_candidates": len(rows),
            "needs_review": sum(bool(row["issues"]) for row in rows),
            "actor_suggestions": sum(row["actor_review"]["suggested_actor"] is not None for row in rows),
            "issue_counts": dict(sorted(counts.items())),
            "deferred_passages": len(catalog.get("deferred_passages", [])),
        },
        "candidates": rows,
        "deferred_passages": catalog.get("deferred_passages", []),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("data/processed/validation"))
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    # Output is separate from all source artifacts.
    if output == root or output in (root / "data/raw", root / "data/metadata", root / "data/processed/obligations", root / "data/processed/clauses"):
        parser.error("Choose a separate validation output directory")
    manifests = json.loads((root / "data/metadata/rbi_manifest.json").read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    inventory = {"sources": [], "policies": [], "evaluation_sets": []}
    for metadata in manifests:
        prefix = metadata["sha256"][:12]
        catalog_path = root / f"data/processed/obligations/{prefix}_obligations.json"
        clause_path = root / f"data/processed/clauses/{prefix}_clauses.json"
        metadata = dict(metadata)
        pdf = root / Path(metadata["pdf_path"].replace("\\", "/"))
        metadata["pdf_hash_verified"] = pdf.exists() and hashlib.sha256(pdf.read_bytes()).hexdigest() == metadata["sha256"]
        pages_path = root / Path(metadata["text_path"].replace("\\", "/"))
        if pages_path.exists():
            pages = json.loads(pages_path.read_text(encoding="utf-8"))
            metadata["source_status_check"] = inspect_source_status(pages)
            first_page = pages[0]["text"] if pages else ""
            metadata["version_date_mentions"] = re.findall(r"Updated as on ([^)]+)", first_page)
            metadata["publication_date_status"] = "requires_manual_confirmation"
        source = {"metadata": metadata, "catalog_available": catalog_path.exists() and clause_path.exists()}
        if source["catalog_available"]:
            report = validate_catalog(
                json.loads(catalog_path.read_text(encoding="utf-8")),
                json.loads(clause_path.read_text(encoding="utf-8")), metadata,
            )
            (output / f"{prefix}_validation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            source["summary"] = report["summary"]
        inventory["sources"].append(source)
    for path in sorted((root / "data/raw/policies").rglob("*.txt")):
        text = path.read_text(encoding="utf-8")
        inventory["policies"].append({"path": str(path.relative_to(root)), "synthetic_label_present": "SYNTHETIC" in text.upper()})
    for path in sorted((root / "data/evaluation").glob("*labels.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        inventory["evaluation_sets"].append({"path": str(path.relative_to(root)), "label_type": data.get("label_type"), "count": len(data.get("labels", []))})
    (output / "inventory.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"sources": len(inventory["sources"]), "policies": len(inventory["policies"]), "output": str(output)}))


if __name__ == "__main__":
    main()
