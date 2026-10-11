
"""
Persist extracted regulatory obligations into PostgreSQL.

Run:
    uv run python -m regintel.ingestion.persist_obligations

Features:
- Deterministic SHA-256 fingerprints
- Source clause and document version validation
- Idempotent inserts
- Human review preservation
- Transactional writes
"""

import hashlib
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from regintel.db.session import SessionLocal
from regintel.models.clause_candidate import RegulatoryClauseCandidate
from regintel.models.obligation import RegulatoryObligation
from regintel.models.regulation import RegulatoryDocumentVersion


OUTPUT_DIR = Path("data/processed/obligations")


def calculate_fingerprint(record: dict) -> str:
    """
    Fingerprint the obligation's source identity and evidence.

    The fingerprint deliberately excludes extraction timestamps,
    confidence, and review status.
    """

    payload = {
        "source_clause_id": str(record["source_clause_id"]),
        "evidence_quote": record["evidence_quote"],
        "obligation_type": record["obligation_type"],
    }

    normalized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


def persist_records(
    session,
    records: list[dict],
) -> dict:
    """
    Persist obligation records using an existing SQLAlchemy session.

    The caller controls the transaction.

    Existing records are not overwritten, protecting human
    review decisions and previously stored evidence.
    """

    inserted = 0
    skipped = 0

    for record in records:

        source_clause_id = UUID(
            str(record["source_clause_id"])
        )

        document_version_id = UUID(
            str(record["document_version_id"])
        )

        clause = session.get(
            RegulatoryClauseCandidate,
            source_clause_id,
        )

        if clause is None:
            raise ValueError(
                "Source clause does not exist: "
                f"{source_clause_id}"
            )

        if clause.version_id != document_version_id:
            raise ValueError(
                "Document version mismatch for clause: "
                f"{source_clause_id}"
            )

        if clause.status != "active":
            raise ValueError(
                "Cannot persist obligation for deleted clause: "
                f"{source_clause_id}"
            )

        version = session.get(
            RegulatoryDocumentVersion,
            document_version_id,
        )

        if version is None:
            raise ValueError(
                "Document version does not exist: "
                f"{document_version_id}"
            )

        fingerprint = calculate_fingerprint(record)

        existing = session.scalar(
            select(RegulatoryObligation).where(
                RegulatoryObligation.source_clause_id
                == source_clause_id,
                RegulatoryObligation.obligation_fingerprint
                == fingerprint,
            )
        )

        if existing is not None:
            skipped += 1
            continue

        obligation = RegulatoryObligation(
            source_clause_id=source_clause_id,
            document_version_id=document_version_id,
            obligation_fingerprint=fingerprint,
            clause_number=record["clause_number"],
            obligation_type=record["obligation_type"],
            actor=record["actor"],
            action=record["action"],
            evidence_quote=record["evidence_quote"],
            condition=record.get("condition"),
            confidence=record["confidence"],
            extraction_method=record["extraction_method"],
            quality_status=record["quality_status"],
            quality_reasons=record.get(
                "quality_reasons", []
            ),
            review_status="pending",
            start_page=record.get("start_page"),
            end_page=record.get("end_page"),
            source_url=record["source_url"],
        )

        session.add(obligation)

        # Flush to detect database constraint failures
        # before committing the transaction.
        session.flush()

        inserted += 1

    return {
        "inserted": inserted,
        "skipped_existing": skipped,
        "processed": len(records),
    }


def main():

    files = sorted(
        OUTPUT_DIR.glob("*_obligations.json")
    )

    if not files:
        raise FileNotFoundError(
            f"No obligation JSON files found in {OUTPUT_DIR}"
        )

    totals = {
        "inserted": 0,
        "skipped_existing": 0,
        "processed": 0,
    }

    with SessionLocal.begin() as session:

        for path in files:

            print(f"Processing: {path}")

            data = json.loads(
                path.read_text(encoding="utf-8")
            )

            records = data.get("obligations", [])

            result = persist_records(
                session,
                records,
            )

            for key in totals:
                totals[key] += result[key]

    print("\nPersistence completed")
    print("Processed:", totals["processed"])
    print("Inserted:", totals["inserted"])
    print(
        "Skipped existing:",
        totals["skipped_existing"],
    )


if __name__ == "__main__":
    main()
