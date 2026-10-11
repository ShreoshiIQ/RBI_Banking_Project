"""Prevalidate all synthetic drafts, then append them in one transaction."""

from sqlalchemy import select

from regintel.foundation.registry import (
    PROFILE_ID,
    build_registry,
    digest,
    load,
    local_path,
)
from regintel.ingestion.policy_ingestor import extract_metadata, extract_sections
from regintel.models.policy import PolicyDocument, PolicyDocumentVersion, PolicySection
from regintel.models.policy_provenance import PolicyVersionProvenance


def prepare_policies(root):
    manifest = load(root / "data/metadata/synthetic_policy_drafts.json")
    if manifest.get("synthetic") is not True:
        raise ValueError("Synthetic manifest label required")
    sources = {s["source_version_id"]: s for s in build_registry(root)["sources"]}
    prepared, seen = [], set()
    for item in manifest["policies"]:
        path = local_path(root, item["path"])
        if digest(path) != item["sha256"]:
            raise ValueError("Synthetic policy hash mismatch")
        text = path.read_text(encoding="utf-8-sig")
        meta, sections = extract_metadata(text), extract_sections(text)
        code = item["policy_code"]
        if code in seen or meta["policy_code"] != code or not code.startswith("SYN-"):
            raise ValueError("Duplicate or mismatched synthetic policy code")
        seen.add(code)
        if (
            not meta["title"]
            or "SYNTHETIC" not in (meta["status"] or "")
            or item.get("review_status") != "pending"
        ):
            raise ValueError("Synthetic pending-review labels required")
        if (
            not sections
            or len({s.section_number for s in sections}) != len(sections)
            or any(not s.section_text for s in sections)
        ):
            raise ValueError("Invalid policy sections")
        anchor = item["source_anchor"]
        source = sources.get(anchor["content_hash"])
        if (
            not source
            or source["source_url"] != anchor["source_url"]
            or source["status"] == "historical_withdrawal_marker"
        ):
            raise ValueError("Invalid or historical synthetic source anchor")
        if (
            not anchor.get("clause_number")
            or anchor.get("relationship")
            != "topic_anchor_only_not_verified_control_mapping"
        ):
            raise ValueError("Source anchor must remain an unverified topic link")
        start, end = anchor.get("start_page"), anchor.get("end_page")
        if (
            type(start) is not int
            or type(end) is not int
            or not 1 <= start <= end <= source["page_count"]
        ):
            raise ValueError("Invalid source anchor page range")
        preview = load(
            root
            / f"data/processed/expansion_previews/{anchor['content_hash'][:12]}_preview.json"
        )
        candidate = preview["catalog"]["obligations"][anchor["candidate_index"]]
        if any(
            candidate.get(k) != anchor.get(k)
            for k in (
                "clause_number",
                "start_page",
                "end_page",
                "source_url",
                "content_hash",
            )
        ):
            raise ValueError("Source anchor does not match extracted candidate")
        prepared.append(
            {"item": item, "metadata": meta, "sections": sections, "path": path}
        )
    return prepared


def ingest_prepared(session, prepared):
    result = {
        "inserted_documents": 0,
        "inserted_versions": 0,
        "inserted_sections": 0,
        "skipped_versions": 0,
    }
    for draft in prepared:
        item, meta = draft["item"], draft["metadata"]
        document = session.scalar(
            select(PolicyDocument).where(
                PolicyDocument.policy_code == item["policy_code"]
            )
        )
        if document is None:
            document = PolicyDocument(
                policy_code=item["policy_code"],
                title="[SYNTHETIC DRAFT] " + meta["title"],
                owner_department=meta["owner"],
            )
            session.add(document)
            session.flush()
            result["inserted_documents"] += 1
        elif document.title != "[SYNTHETIC DRAFT] " + meta["title"]:
            raise ValueError("Existing policy identity conflict; nothing overwritten")
        version = session.scalar(
            select(PolicyDocumentVersion).where(
                PolicyDocumentVersion.document_id == document.id,
                PolicyDocumentVersion.content_hash == item["sha256"],
            )
        )
        expected = {
            "synthetic": True,
            "profile_id": PROFILE_ID,
            "file_sha256": item["sha256"],
            "topic": item["topic"],
            "variant": item["variant"],
            "review_status": "pending",
            "source_anchor": item["source_anchor"],
        }
        if version is not None:
            provenance = session.get(PolicyVersionProvenance, version.id)
            if provenance is None or any(
                getattr(provenance, k) != v for k, v in expected.items()
            ):
                raise ValueError("Existing provenance conflict; nothing overwritten")
            stored = session.scalars(
                select(PolicySection).where(PolicySection.version_id == version.id)
            ).all()
            actual = {
                (s.section_number, s.section_title, s.section_text) for s in stored
            }
            wanted = {
                (s.section_number, s.section_title, s.section_text)
                for s in draft["sections"]
            }
            if actual != wanted:
                raise ValueError("Existing section content conflict")
            result["skipped_versions"] += 1
            continue
        version = PolicyDocumentVersion(
            document_id=document.id,
            content_hash=item["sha256"],
            storage_uri=str(draft["path"]),
        )
        session.add(version)
        session.flush()
        session.add(PolicyVersionProvenance(version_id=version.id, **expected))
        for section in draft["sections"]:
            session.add(
                PolicySection(
                    version_id=version.id,
                    section_number=section.section_number,
                    section_title=section.section_title,
                    section_text=section.section_text,
                )
            )
        result["inserted_versions"] += 1
        result["inserted_sections"] += len(draft["sections"])
    session.flush()
    return result
