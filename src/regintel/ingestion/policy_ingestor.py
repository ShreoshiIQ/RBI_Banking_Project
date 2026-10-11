
"""
Internal Bank Policy Ingestion Pipeline - Version 1

Features:
- Reads TXT policy documents
- Extracts policy metadata
- Extracts numbered sections
- Calculates SHA-256 content hashes
- Stores documents, versions and sections in PostgreSQL
- Prevents duplicate document versions
- Uses a database transaction for atomic persistence

Run:
    uv run python -m regintel.ingestion.policy_ingestor
"""

import hashlib
import re

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from regintel.db.session import SessionLocal
from regintel.models.policy import (
    PolicyDocument,
    PolicyDocumentVersion,
    PolicySection,
)


POLICY_DIRECTORY = Path("data/raw/policies")

SECTION_PATTERN = re.compile(
    r"^SECTION\s+(\d+(?:\.\d+)*)\s*:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)

METADATA_PATTERN = re.compile(
    r"^(POLICY CODE|TITLE|OWNER|STATUS):\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class ParsedSection:
    section_number: str
    section_title: str
    section_text: str


def calculate_content_hash(content: bytes) -> str:
    """Calculate SHA-256 over the original file bytes."""
    return hashlib.sha256(content).hexdigest()


def extract_metadata(text: str) -> dict:
    """Extract policy metadata from document headers."""

    metadata = {}

    for match in METADATA_PATTERN.finditer(text):
        metadata[match.group(1).upper()] = (
            match.group(2).strip()
        )

    return {
        "policy_code": metadata.get("POLICY CODE"),
        "title": metadata.get("TITLE"),
        "owner": metadata.get("OWNER"),
        "status": metadata.get("STATUS"),
    }


def extract_sections(text: str) -> list[ParsedSection]:
    """Extract numbered policy sections."""

    matches = list(SECTION_PATTERN.finditer(text))
    sections = []

    for index, match in enumerate(matches):
        start = match.end()

        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(text)
        )

        section_number = match.group(1)
        section_title = match.group(2).strip()
        section_text = text[start:end].strip()

        sections.append(
            ParsedSection(
                section_number=section_number,
                section_title=section_title,
                section_text=section_text,
            )
        )

    return sections


def ingest_policy(path: Path) -> dict:
    """Ingest one policy file transactionally."""

    raw_bytes = path.read_bytes()

    content_hash = calculate_content_hash(
        raw_bytes
    )

    text = raw_bytes.decode("utf-8-sig")

    metadata = extract_metadata(text)
    sections = extract_sections(text)

    if not metadata["policy_code"]:
        raise ValueError(
            f"Missing POLICY CODE in {path}"
        )

    if not metadata["title"]:
        raise ValueError(
            f"Missing TITLE in {path}"
        )

    if not sections:
        raise ValueError(
            f"No numbered sections found in {path}"
        )

    numbers = [
        section.section_number
        for section in sections
    ]

    if len(numbers) != len(set(numbers)):
        raise ValueError(
            f"Duplicate section numbers in {path}"
        )

    with SessionLocal.begin() as session:

        document = session.scalar(
            select(PolicyDocument).where(
                PolicyDocument.policy_code
                == metadata["policy_code"]
            )
        )

        if document is None:
            document = PolicyDocument(
                policy_code=metadata["policy_code"],
                title=metadata["title"],
                owner_department=metadata["owner"],
            )

            session.add(document)
            session.flush()

        existing_version = session.scalar(
            select(PolicyDocumentVersion).where(
                PolicyDocumentVersion.document_id
                == document.id,
                PolicyDocumentVersion.content_hash
                == content_hash,
            )
        )

        if existing_version is not None:
            return {
                "file": str(path),
                "status": "skipped_existing",
                "sections": 0,
                "content_hash": content_hash,
            }

        version = PolicyDocumentVersion(
            document_id=document.id,
            content_hash=content_hash,
            storage_uri=str(path.resolve()),
        )

        session.add(version)
        session.flush()

        for section in sections:
            session.add(
                PolicySection(
                    version_id=version.id,
                    section_number=section.section_number,
                    section_title=section.section_title,
                    section_text=section.section_text,
                    page_number=None,
                )
            )

        session.flush()

    return {
        "file": str(path),
        "status": "inserted",
        "sections": len(sections),
        "content_hash": content_hash,
    }


def main():

    if not POLICY_DIRECTORY.exists():
        raise FileNotFoundError(
            f"Policy directory missing: {POLICY_DIRECTORY}"
        )

    files = sorted(
        POLICY_DIRECTORY.glob("*.txt")
    )

    if not files:
        raise FileNotFoundError(
            "No TXT policy files found."
        )

    print("\nStarting policy ingestion...\n")

    for path in files:

        result = ingest_policy(path)

        print("File:", result["file"])
        print("Status:", result["status"])
        print("Sections:", result["sections"])
        print("SHA-256:", result["content_hash"])
        print("-" * 60)

    print("\nPolicy ingestion completed.")


if __name__ == "__main__":
    main()
