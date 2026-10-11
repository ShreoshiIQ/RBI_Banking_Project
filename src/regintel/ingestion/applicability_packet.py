"""Export exact source passages for institution applicability review."""

import hashlib
import json
import re
from pathlib import Path

from regintel.ingestion.triage_expansion import classify_section


def build_packet(previews: list[dict], profile: dict) -> dict:
    sources = []
    for preview in previews:
        metadata = preview["validation"]["source_metadata"]
        passages = []
        for clause in preview["clauses"]:
            category = classify_section(clause["clause_text"])
            is_scope_exception = re.search(
                r"\b(?:shall not (?:be applicable|apply)|foreign banks?|foreign bank|exclusions?)\b",
                clause["clause_text"], re.IGNORECASE,
            )
            if category in ("title_or_commencement", "applicability_or_scope", "repeal_or_saving") or is_scope_exception:
                passages.append({
                    "category": category if not is_scope_exception else "scope_or_exception",
                    "clause_number": clause["clause_number"],
                    "start_page": clause["start_page"], "end_page": clause["end_page"],
                    "quote": clause["clause_text"],
                    "quote_sha256": hashlib.sha256(clause["clause_text"].encode()).hexdigest(),
                })
        sources.append({
            "title": metadata["title"], "source_url": metadata["source_url"],
            "source_page_url": metadata.get("source_page_url"),
            "content_hash": metadata["sha256"], "pdf_path": metadata["pdf_path"],
            "review_status": "pending", "applicability_decision": None,
            "passages": passages,
        })
    return {
        "schema_version": 1, "demo_profile": profile,
        "notice": "Exact extracted source passages for review; no legal applicability decisions are inferred.",
        "sources": sources,
        "review_checklist": [
            "Confirm the institution matches the source definition and exclusions.",
            "Verify commencement, amendment dates, transitional periods, and saving clauses.",
            "Check feature and activity scope separately for each candidate obligation.",
            "Verify quoted text against the preserved PDF; extraction boundaries may contain annexes.",
        ],
    }


def main():
    profile = json.loads(Path("data/metadata/demo_institution_profile.json").read_text(encoding="utf-8"))
    previews = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(Path("data/processed/expansion_previews").glob("*_preview.json"))]
    packet = build_packet(previews, profile)
    output = Path("data/processed/expansion_reviews/applicability_packet.json")
    output.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Prepared {len(packet['sources'])} sources and {sum(len(s['passages']) for s in packet['sources'])} source passages")


if __name__ == "__main__":
    main()
