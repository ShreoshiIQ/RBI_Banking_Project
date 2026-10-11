"""Hash-bound offline source/version/applicability registry."""

import hashlib
import json
from pathlib import Path

PROFILE_ID = "fictional-commercial-bank-demo"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def local_path(root, relative):
    path = (root / relative.replace("\\", "/")).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Dataset path escapes project root")
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_registry(root):
    records = load(root / "data/metadata/rbi_manifest.json")
    sources, seen = [], set()
    for record in records:
        sha = record["sha256"]
        if sha in seen:
            raise ValueError("Duplicate source hash in manifest")
        seen.add(sha)
        path = local_path(root, record["pdf_path"])
        if digest(path) != sha:
            raise ValueError("Source file hash mismatch")
        withdrawn = (
            record.get("source_status_check", {}).get(
                "current_obligation_extraction_allowed"
            )
            is False
        )
        sources.append(
            {
                "source_version_id": sha,
                "regulator": record["regulator"],
                "title": record["title"],
                "source_url": record["source_url"],
                "source_page_url": record.get("source_page_url"),
                "publication_date": record.get("publication_date"),
                "observed_updated_as_on": record.get("observed_updated_as_on"),
                "supersedes_source_versions": [],
                "supersession_review_status": "pending",
                "pdf_path": record["pdf_path"],
                "retrieved_at": record["retrieved_at"],
                "page_count": record["page_count"],
                "effective_date": record.get("effective_date"),
                "status": "historical_withdrawal_marker"
                if withdrawn
                else "status_verification_pending",
                "eligible_for_current_approved_catalog": False,
                "applicability": {
                    "profile_id": PROFILE_ID,
                    "decision": "pending",
                    "reviewer": None,
                },
                "status_evidence": record.get("source_status_check", {}),
            }
        )
    return {
        "schema_version": 1,
        "profile_id": PROFILE_ID,
        "profile_sha256": digest(root / "data/metadata/demo_institution_profile.json"),
        "profile": load(root / "data/metadata/demo_institution_profile.json"),
        "sources": sources,
        "notice": "Offline review registry, not runtime applicability enforcement or legal approval.",
    }
