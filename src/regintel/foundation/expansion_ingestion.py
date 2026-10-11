"""Append bank candidates only; SEBI remains a separate offline review corpus."""

import re
from uuid import NAMESPACE_URL, uuid5

import pymupdf
from sqlalchemy import select

from regintel.foundation.expansion import BANK, BROKER, verify_corpus
from regintel.foundation.registry import load, local_path
from regintel.ingestion.extract_expansion import extract_preview
from regintel.ingestion.persist_obligations import persist_records
from regintel.ingestion.source_status import inspect_source_status
from regintel.models.clause_candidate import RegulatoryClauseCandidate
from regintel.models.regulation import RegulatoryDocument, RegulatoryDocumentVersion


def prepare_bank(root, corpus):
    prepared = []
    for source in verify_corpus(root, corpus, BANK):
        pages = load(local_path(root, source["text_path"]))
        if (
            inspect_source_status(pages)["current_obligation_extraction_allowed"]
            is False
        ):
            raise ValueError(
                "Historical withdrawn source cannot enter expansion candidates"
            )
        record = {
            "sha256": source["content_hash"],
            "source_url": source["source_url"],
            "title": source["title"],
            "pdf_path": source["pdf_path"],
            "page_count": source["page_count"],
        }
        prepared.append({"source": source, "preview": extract_preview(record, pages)})
    return prepared


def append_bank(session, root, corpus):
    """Caller owns transaction and serialization; no existing row is updated."""
    prepared = prepare_bank(root, corpus)  # validate everything before touching DB
    result = {
        "documents_inserted": 0,
        "versions_inserted": 0,
        "clauses_inserted": 0,
        "obligations_inserted": 0,
        "obligations_skipped": 0,
        "source_versions": [],
    }
    for item in prepared:
        source, preview = item["source"], item["preview"]
        document = session.scalar(
            select(RegulatoryDocument).where(
                RegulatoryDocument.source_url == source["source_page_url"],
                RegulatoryDocument.regulator == "RBI",
            )
        )
        if document is None:
            document = RegulatoryDocument(
                regulator="RBI",
                title=source["title"],
                jurisdiction="India",
                source_url=source["source_page_url"],
            )
            session.add(document)
            session.flush()
            result["documents_inserted"] += 1
        version = session.scalar(
            select(RegulatoryDocumentVersion).where(
                RegulatoryDocumentVersion.document_id == document.id,
                RegulatoryDocumentVersion.content_hash == source["content_hash"],
            )
        )
        if version is None:
            version = RegulatoryDocumentVersion(
                document_id=document.id,
                content_hash=source["content_hash"],
                storage_uri=source["pdf_path"],
            )
            session.add(version)
            session.flush()
            result["versions_inserted"] += 1
        identities = {}
        for clause in preview["clauses"]:
            existing = session.scalar(
                select(RegulatoryClauseCandidate).where(
                    RegulatoryClauseCandidate.version_id == version.id,
                    RegulatoryClauseCandidate.clause_number == clause["clause_number"],
                )
            )
            if existing is None:
                existing = RegulatoryClauseCandidate(
                    version_id=version.id,
                    clause_number=clause["clause_number"],
                    clause_text=clause["clause_text"],
                    start_page=clause["start_page"],
                    end_page=clause["end_page"],
                    status=clause["status"],
                    review_status="pending",
                    extraction_method="regex_v4_phase3",
                )
                session.add(existing)
                session.flush()
                result["clauses_inserted"] += 1
            elif (
                existing.clause_text,
                existing.start_page,
                existing.end_page,
                existing.status,
            ) != (
                clause["clause_text"],
                clause["start_page"],
                clause["end_page"],
                clause["status"],
            ):
                raise ValueError("Existing clause differs; preserve and investigate")
            identities[clause["clause_number"]] = existing.id
        rows = [
            {
                **row,
                "source_clause_id": str(identities[row["clause_number"]]),
                "document_version_id": str(version.id),
            }
            for row in preview["catalog"]["obligations"]
        ]
        counts = persist_records(session, rows)
        result["obligations_inserted"] += counts["inserted"]
        result["obligations_skipped"] += counts["skipped_existing"]
        result["source_versions"].append(
            {
                "content_hash": source["content_hash"],
                "database_version_id": str(version.id),
                "profile_id": BANK,
                "applicability_decision": "pending",
                "legal_current_status": "pending",
            }
        )
    return result


def sebi_review_packet(root, corpus):
    """Exact PDF blocks, including context; not segmented/validated obligations."""
    sources = verify_corpus(root, corpus, BROKER)
    records, seen, repeated = [], set(), 0
    for source in sources:
        pages = load(local_path(root, source["text_path"]))
        if (
            inspect_source_status(pages)["current_obligation_extraction_allowed"]
            is False
        ):
            raise ValueError("Withdrawn source is historical only")
        with pymupdf.open(local_path(root, source["pdf_path"])) as pdf:
            for page_index, page in enumerate(pdf):
                for block in page.get_text("blocks"):
                    quote = block[4].strip()
                    if not re.search(
                        r"\b(?:shall|must|should|required|stock\s*brokers?|applicab|categor)\b",
                        quote,
                        re.IGNORECASE,
                    ):
                        continue
                    key = (source["content_hash"], quote)
                    if key in seen:
                        repeated += 1
                        continue
                    seen.add(key)
                    records.append(
                        {
                            "candidate_id": str(
                                uuid5(NAMESPACE_URL, source["content_hash"] + quote)
                            ),
                            "profile_id": BROKER,
                            "source_url": source["source_url"],
                            "content_hash": source["content_hash"],
                            "evidence_quote": quote,
                            "location": {
                                "page": page_index + 1,
                                "bbox": list(block[:4]),
                                "units": "pdf_points",
                            },
                            "record_type": "source_block_for_review",
                            "review_status": "pending",
                            "applicability_decision": "pending",
                            "current_catalog_eligible": False,
                        }
                    )
    return {
        "schema_version": 1,
        "profile_id": BROKER,
        "synthetic_entity": True,
        "regulatory_sources_synthetic": False,
        "runtime_access": "offline_only",
        "source_blocks": records,
        "repeated_exact_blocks_skipped": repeated,
        "notice": "Review blocks are not distinct obligations or measured regulatory coverage. No bank policy matching or tenant access.",
    }
