
"""
Regulatory Obligation Extraction Pipeline - Version 3

Reads regulatory clause candidates from PostgreSQL,
extracts potential obligations, evaluates their quality,
and tracks deferred passages for further review.

Run:
    uv run python -m regintel.ingestion.run_obligation_extraction

Output:
    data/processed/obligations/<hash>_obligations.json

Important:
    Extracted obligations are candidates only.
    They are not automatically verified or approved.
"""

import json
import logging

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from regintel.db.session import SessionLocal
from regintel.ingestion.source_status import inspect_source_status

from regintel.models.regulation import (
    RegulatoryDocument,
    RegulatoryDocumentVersion,
)

from regintel.models.clause_candidate import (
    RegulatoryClauseCandidate,
)

from regintel.ingestion.obligation_extractor import (
    extract_with_tracking,
)

from regintel.ingestion.obligation_quality import (
    evaluate_obligation,
)


# =========================================================
# 1. CONFIGURATION
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

logger = logging.getLogger(__name__)

MANIFEST_PATH = Path(
    "data/metadata/rbi_manifest.json"
)

OUTPUT_DIR = Path(
    "data/processed/obligations"
)

EXTRACTION_METHOD = "rule_based_v4_1"


# =========================================================
# 2. MAIN EXTRACTION FUNCTION
# =========================================================

def run_extraction():

    # -----------------------------------------------------
    # Validate manifest
    # -----------------------------------------------------

    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Manifest file not found: {MANIFEST_PATH}"
        )

    manifest = json.loads(
        MANIFEST_PATH.read_text(encoding="utf-8")
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -----------------------------------------------------
    # Process each regulatory document
    # -----------------------------------------------------

    for record in manifest:

        pages = json.loads(Path(record["text_path"]).read_text(encoding="utf-8"))
        if inspect_source_status(pages)["current_obligation_extraction_allowed"] is False:
            logger.warning("Skipping withdrawn source: %s", record["title"])
            continue

        content_hash = record["sha256"]
        source_url = record["source_url"]

        logger.info(
            "Processing document: %s",
            record.get("title", source_url),
        )

        # -------------------------------------------------
        # 3. FETCH DOCUMENT AND VERSION
        # -------------------------------------------------

        with SessionLocal() as session:

            document = session.scalar(
                select(RegulatoryDocument).where(
                    RegulatoryDocument.source_url
                    == source_url
                )
            )

            if document is None:
                raise RuntimeError(
                    f"Document not found: {source_url}"
                )

            version = session.scalar(
                select(RegulatoryDocumentVersion).where(
                    RegulatoryDocumentVersion.document_id
                    == document.id,
                    RegulatoryDocumentVersion.content_hash
                    == content_hash,
                )
            )

            if version is None:
                raise RuntimeError(
                    "Document version not found for hash: "
                    f"{content_hash}"
                )

            # ---------------------------------------------
            # 4. FETCH REGULATORY CLAUSE CANDIDATES
            # ---------------------------------------------

            candidates = session.scalars(
                select(RegulatoryClauseCandidate)
                .where(
                    RegulatoryClauseCandidate.version_id
                    == version.id
                )
                .order_by(
                    RegulatoryClauseCandidate.start_page,
                    RegulatoryClauseCandidate.clause_number,
                )
            ).all()

            if not candidates:
                raise RuntimeError(
                    "No regulatory clause candidates found."
                )

            # ---------------------------------------------
            # 5. INITIALIZE EXTRACTION COLLECTIONS
            # ---------------------------------------------

            obligations = []
            deferred_passages = []

            skipped_deleted = 0
            processed_active = 0

            # ---------------------------------------------
            # 6. PROCESS EACH CLAUSE
            # ---------------------------------------------

            for candidate in candidates:

                # Deleted clauses must not produce
                # current regulatory obligations.
                if candidate.status == "deleted":
                    skipped_deleted += 1
                    continue

                processed_active += 1

                # -----------------------------------------
                # 7. EXTRACT WITH DEFERRED TRACKING
                # -----------------------------------------

                extraction_result = extract_with_tracking(
                    source_clause_id=candidate.id,
                    clause_number=candidate.clause_number,
                    clause_text=candidate.clause_text,
                    status=candidate.status,
                )

                # -----------------------------------------
                # 8. RECORD DEFERRED PASSAGES
                # -----------------------------------------

                for deferred in extraction_result.deferred:

                    deferred_item = {
                        "source_clause_id": (
                            deferred.source_clause_id
                        ),
                        "clause_number": (
                            deferred.clause_number
                        ),
                        "text": deferred.text,
                        "reason": deferred.reason,
                        "review_status": (
                            deferred.review_status
                        ),
                        "start_page": (
                            candidate.start_page
                        ),
                        "end_page": (
                            candidate.end_page
                        ),
                        "source_url": source_url,
                        "document_version_id": str(
                            version.id
                        ),
                        "content_hash": content_hash,
                    }

                    deferred_passages.append(
                        deferred_item
                    )

                # -----------------------------------------
                # 9. QUALITY CHECK EXTRACTED OBLIGATIONS
                # -----------------------------------------

                for obligation in extraction_result.obligations:

                    item = obligation.model_dump(
                        mode="json"
                    )

                    quality = evaluate_obligation(
                        item["evidence_quote"]
                    )

                    item["quality_status"] = (
                        quality.status
                    )

                    item["quality_reasons"] = (
                        quality.reasons
                    )

                    # -------------------------------------
                    # 10. ATTACH SOURCE TRACEABILITY
                    # -------------------------------------

                    item["start_page"] = (
                        candidate.start_page
                    )

                    item["end_page"] = (
                        candidate.end_page
                    )

                    item["source_url"] = source_url

                    item["document_version_id"] = str(
                        version.id
                    )

                    item["content_hash"] = content_hash

                    # No automatic approval.
                    item["review_status"] = "pending"

                    obligations.append(item)

        # -------------------------------------------------
        # 11. CALCULATE STATISTICS
        # -------------------------------------------------

        type_counts = Counter(
            item["obligation_type"]
            for item in obligations
        )

        quality_counts = Counter(
            item["quality_status"]
            for item in obligations
        )

        review_reasons = Counter(
            reason
            for item in obligations
            for reason in item["quality_reasons"]
        )

        deferred_reasons = Counter(
            item["reason"]
            for item in deferred_passages
        )

        # -------------------------------------------------
        # 12. BUILD OUTPUT DOCUMENT
        # -------------------------------------------------

        result = {
            "source_url": source_url,
            "content_hash": content_hash,
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "extraction_method": EXTRACTION_METHOD,

            # Clause statistics
            "total_clause_candidates": len(candidates),
            "active_clauses_processed": processed_active,
            "deleted_clauses_skipped": skipped_deleted,

            # Obligation statistics
            "total_obligation_candidates": len(obligations),
            "obligation_type_counts": dict(type_counts),

            # Quality statistics
            "quality_status_counts": dict(quality_counts),
            "quality_review_reasons": dict(review_reasons),

            # Deferred passage statistics
            "total_deferred_passages": len(
                deferred_passages
            ),
            "deferred_reason_counts": dict(
                deferred_reasons
            ),

            # Detailed results
            "obligations": obligations,
            "deferred_passages": deferred_passages,
        }

        # -------------------------------------------------
        # 13. SAVE OUTPUT JSON
        # -------------------------------------------------

        output_path = (
            OUTPUT_DIR
            / f"{content_hash[:12]}_obligations.json"
        )

        output_path.write_text(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        # -------------------------------------------------
        # 14. LOG RESULTS
        # -------------------------------------------------

        logger.info(
            "Total clause candidates: %s",
            len(candidates),
        )

        logger.info(
            "Active clauses processed: %s",
            processed_active,
        )

        logger.info(
            "Deleted clauses skipped: %s",
            skipped_deleted,
        )

        logger.info(
            "Obligation candidates: %s",
            len(obligations),
        )

        logger.info(
            "Obligation types: %s",
            dict(type_counts),
        )

        logger.info(
            "Quality distribution: %s",
            dict(quality_counts),
        )

        logger.info(
            "Quality review reasons: %s",
            dict(review_reasons),
        )

        logger.info(
            "Deferred passages: %s",
            len(deferred_passages),
        )

        logger.info(
            "Deferred reasons: %s",
            dict(deferred_reasons),
        )

        logger.info(
            "Saved: %s",
            output_path,
        )


# =========================================================
# 15. ENTRY POINT
# =========================================================

if __name__ == "__main__":
    run_extraction()
