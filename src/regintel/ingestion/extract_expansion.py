"""Extract file-only previews with local IDs; never write database records."""

import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from regintel.ingestion.clause_extractor import extract_clauses
from regintel.ingestion.obligation_extractor import extract_with_tracking
from regintel.ingestion.obligation_quality import evaluate_obligation
from regintel.ingestion.source_status import inspect_source_status
from regintel.ingestion.validate_dataset import validate_catalog


def extract_preview(record: dict, pages: list[dict]) -> dict:
    if inspect_source_status(pages)["current_obligation_extraction_allowed"] is False:
        raise ValueError("Withdrawn sources cannot produce current-obligation previews")
    clauses = [clause.model_dump() for clause in extract_clauses(pages)]
    if not clauses:
        raise ValueError("No supported clause sequence found")
    version_id = uuid5(NAMESPACE_URL, "local-preview:" + record["sha256"])
    obligations, deferred = [], []
    for clause in clauses:
        clause_id = uuid5(version_id, clause["clause_number"])
        provenance = {
            "source_clause_id": str(clause_id), "document_version_id": str(version_id),
            "clause_number": clause["clause_number"],
            "source_url": record["source_url"], "content_hash": record["sha256"],
            "start_page": clause["start_page"], "end_page": clause["end_page"],
            "review_status": "pending", "id_scope": "local_preview_not_database",
        }
        if clause["clause_number"] in ("1", "2", "3"):
            deferred.append({**provenance, "text": clause["clause_text"], "reason": "preliminary_or_applicability_section"})
            continue
        extracted = extract_with_tracking(
            clause_id, clause["clause_number"], clause["clause_text"], clause["status"],
        )
        for item in extracted.obligations:
            data = item.model_dump(mode="json")
            quality = evaluate_obligation(data["evidence_quote"])
            obligations.append({**data, **provenance, "quality_status": quality.status, "quality_reasons": quality.reasons})
        for item in extracted.deferred:
            deferred.append({**vars(item), **provenance})
    catalog = {
        "source_url": record["source_url"], "content_hash": record["sha256"],
        "extraction_method": "rule_based_v4_1_local_preview",
        "id_scope": "local_preview_not_database", "obligations": obligations,
        "deferred_passages": deferred,
    }
    return {
        "notice": "Unreviewed preview. Local IDs must not be treated as database identities or validated obligations.",
        "clauses": clauses, "catalog": catalog,
        "validation": validate_catalog(catalog, clauses, record),
    }


def main():
    records = json.loads(Path("data/metadata/rbi_manifest.json").read_text(encoding="utf-8"))
    output = Path("data/processed/expansion_previews")
    output.mkdir(parents=True, exist_ok=True)
    for record in records:
        if not record.get("discovery_id", "").startswith("replacement-"):
            continue
        if hashlib.sha256(Path(record["pdf_path"]).read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("PDF hash mismatch")
        pages = json.loads(Path(record["text_path"]).read_text(encoding="utf-8"))
        preview = extract_preview(record, pages)
        path = output / f"{record['sha256'][:12]}_preview.json"
        if path.exists():
            print("Preserved existing preview:", path)
            continue
        with path.open("x", encoding="utf-8") as stream:
            json.dump(preview, stream, indent=2, ensure_ascii=False)
        print(record["discovery_id"], len(preview["clauses"]), "clauses", len(preview["catalog"]["obligations"]), "obligation candidates")


if __name__ == "__main__":
    main()
