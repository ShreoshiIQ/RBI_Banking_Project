
import json
import logging
from pathlib import Path

from sqlalchemy import select

from regintel.db.session import SessionLocal
from regintel.models.regulation import (
    RegulatoryDocument,
    RegulatoryDocumentVersion,
)
from regintel.models.clause_candidate import (
    RegulatoryClauseCandidate,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

logger = logging.getLogger(__name__)


def persist_candidates():
    manifest_path = Path(
        "data/metadata/rbi_manifest.json"
    )

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    total_inserted = 0
    total_updated = 0
    total_skipped = 0

    for record in manifest:
        content_hash = record["sha256"]
        source_url = record["source_url"]

        clauses_path = (
            Path("data/processed/clauses")
            / f"{content_hash[:12]}_clauses.json"
        )

        if not clauses_path.exists():
            raise FileNotFoundError(
                f"Extracted clauses not found: {clauses_path}"
            )

        clauses = json.loads(
            clauses_path.read_text(encoding="utf-8")
        )

        # Reject duplicate numbers before changing the DB.
        numbers = [c["clause_number"] for c in clauses]

        if len(numbers) != len(set(numbers)):
            raise ValueError(
                "Duplicate clause numbers in extraction JSON"
            )

        # Validate expected main-document boundary.
        if (
            not clauses
            or clauses[-1]["clause_number"] != "74"
            or clauses[-1]["end_page"] > 71
            or "Annex I" in clauses[-1]["clause_text"]
        ):
            raise ValueError(
                "RBI KYC clause boundary validation failed"
            )

        with SessionLocal.begin() as session:
            document = session.scalar(
                select(RegulatoryDocument).where(
                    RegulatoryDocument.source_url == source_url
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
                    f"Document version not found: {content_hash}"
                )

            existing = {
                c.clause_number: c
                for c in session.scalars(
                    select(RegulatoryClauseCandidate).where(
                        RegulatoryClauseCandidate.version_id
                        == version.id
                    )
                ).all()
            }

            for clause in clauses:
                number = clause["clause_number"]
                candidate = existing.get(number)

                if candidate is None:
                    session.add(
                        RegulatoryClauseCandidate(
                            version_id=version.id,
                            clause_number=number,
                            clause_text=clause["clause_text"],
                            start_page=clause["start_page"],
                            end_page=clause["end_page"],
                            status=clause["status"],
                            extraction_method=clause.get(
                                "extraction_method",
                                "regex_v5",
                            ),
                            review_status="pending",
                        )
                    )
                    total_inserted += 1
                    continue

                # Never overwrite reviewed candidates.
                if candidate.review_status != "pending":
                    logger.warning(
                        "Preserving reviewed candidate: %s",
                        number,
                    )
                    total_skipped += 1
                    continue

                fields = {
                    "clause_text": clause["clause_text"],
                    "start_page": clause["start_page"],
                    "end_page": clause["end_page"],
                    "status": clause["status"],
                    "extraction_method": clause.get(
                        "extraction_method",
                        "regex_v5",
                    ),
                }

                changed = False

                for field, value in fields.items():
                    if getattr(candidate, field) != value:
                        setattr(candidate, field, value)
                        changed = True

                if changed:
                    total_updated += 1
                else:
                    total_skipped += 1

    logger.info("Inserted: %s", total_inserted)
    logger.info("Updated: %s", total_updated)
    logger.info("Unchanged or preserved: %s", total_skipped)


if __name__ == "__main__":
    persist_candidates()
