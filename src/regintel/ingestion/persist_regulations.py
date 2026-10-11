
import hashlib
import json
import logging
import uuid
from pathlib import Path

from sqlalchemy import select, func

from regintel.db.session import SessionLocal
from regintel.models.regulation import (
    RegulatoryDocument,
    RegulatoryDocumentVersion,
    RegulatoryClause,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

logger = logging.getLogger(__name__)

MANIFEST_PATH = Path(
    "data/metadata/rbi_manifest.json"
)


def verify_file_hash(
    pdf_path: Path,
    expected_hash: str,
) -> None:
    actual_hash = hashlib.sha256(
        pdf_path.read_bytes()
    ).hexdigest()

    if actual_hash != expected_hash:
        raise ValueError(
            f"SHA-256 mismatch for {pdf_path}"
        )


def load_pages(text_path: Path) -> list[dict]:
    pages = json.loads(
        text_path.read_text(encoding="utf-8")
    )

    if not isinstance(pages, list):
        raise ValueError("Expected a list of PDF pages")

    return pages


def import_document(record: dict) -> None:
    source_url = record["source_url"]
    content_hash = record["sha256"]

    pdf_path = Path(record["pdf_path"])
    text_path = Path(record["text_path"])

    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)

    if not text_path.is_file():
        raise FileNotFoundError(text_path)

    verify_file_hash(pdf_path, content_hash)
    pages = load_pages(text_path)

    with SessionLocal.begin() as session:
        document = session.scalar(
            select(RegulatoryDocument).where(
                RegulatoryDocument.source_url
                == source_url
            )
        )

        if document is None:
            document = RegulatoryDocument(
                id=uuid.uuid4(),
                regulator=record["regulator"],
                title=record["title"],
                jurisdiction="India",
                source_url=source_url,
            )

            session.add(document)
            session.flush()

            logger.info(
                "Created document: %s",
                document.title,
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
            version = RegulatoryDocumentVersion(
                id=uuid.uuid4(),
                document_id=document.id,
                content_hash=content_hash,
                storage_uri=str(pdf_path),
                effective_date=None,
            )

            session.add(version)
            session.flush()

            logger.info(
                "Created version: %s",
                content_hash[:12],
            )
        else:
            logger.info(
                "Existing version found: %s",
                content_hash[:12],
            )

        inserted = 0

        for page in pages:
            page_number = int(
                page["page_number"]
            )

            page_text = page["text"].strip()

            if not page_text:
                continue

            passage_id = (
                f"PAGE-{page_number:04d}"
            )

            existing = session.scalar(
                select(RegulatoryClause.id).where(
                    RegulatoryClause.version_id
                    == version.id,
                    RegulatoryClause.clause_number
                    == passage_id,
                )
            )

            if existing is not None:
                continue

            clause = RegulatoryClause(
                id=uuid.uuid4(),
                version_id=version.id,
                clause_number=passage_id,
                section_title=(
                    "Unclassified source passage"
                ),
                clause_text=page_text,
                page_number=page_number,
            )

            session.add(clause)
            inserted += 1

        logger.info(
            "Inserted %s new page passages",
            inserted,
        )


def show_summary() -> None:
    with SessionLocal() as session:
        documents = session.scalar(
            select(func.count())
            .select_from(RegulatoryDocument)
        )

        versions = session.scalar(
            select(func.count())
            .select_from(
                RegulatoryDocumentVersion
            )
        )

        passages = session.scalar(
            select(func.count())
            .select_from(RegulatoryClause)
        )

    logger.info("Database summary:")
    logger.info("Documents: %s", documents)
    logger.info("Versions: %s", versions)
    logger.info("Passages: %s", passages)


def main() -> None:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(
            f"Manifest not found: {MANIFEST_PATH}"
        )

    records = json.loads(
        MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    logger.info(
        "Found %s documents in manifest",
        len(records),
    )

    for record in records:
        try:
            import_document(record)
        except Exception:
            logger.exception(
                "Failed to import %s",
                record.get("title", "Unknown"),
            )

    show_summary()


if __name__ == "__main__":
    main()
