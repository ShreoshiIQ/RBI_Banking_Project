
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import pymupdf
from bs4 import BeautifulSoup

BASE_DIR = Path("data/raw/rbi")
MANIFEST_PATH = Path("data/metadata/rbi_manifest.json")

INDEX_URL = (
    "https://www.rbi.org.in/Scripts/"
    "BS_ViewMasterDirections.aspx?did=338"
)

SEED_DOCUMENTS = [
    {
        "title": "Master Direction - KYC 2016",
        "url": (
            "https://www.rbi.org.in/commonman/Upload/"
            "English/Notification/PDFs/"
            "MD18KYCF6E92C82E1E1419D87323E3869BC9F13.pdf"
        ),
    }
]

ALLOWED_HOSTS = {
    "rbidocs.rbi.org.in",
    "rbi.org.in",
    "www.rbi.org.in",
    "old.rbi.org.in",
    "m.rbi.org.in",
}

MAX_DISCOVERED = 30
MAX_FILE_BYTES = 30 * 1024 * 1024
DELAY_SECONDS = 2

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_HOSTS
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_filename(title: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_-]+", "_", title)
    return name.strip("_")[:100] or "document"


def load_manifest() -> list[dict]:
    if MANIFEST_PATH.exists():
        return json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8")
        )
    return []


def save_manifest(records: list[dict]) -> None:
    MANIFEST_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    MANIFEST_PATH.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def discover_pdf_links(
    client: httpx.Client,
) -> list[dict]:
    logger.info("Discovering RBI documents...")

    response = client.get(INDEX_URL)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    discovered = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        url = urljoin(
            str(response.url),
            anchor["href"],
        )

        if not allowed_url(url):
            continue

        if not urlparse(url).path.lower().endswith(".pdf"):
            continue

        if url in seen:
            continue

        seen.add(url)

        title = anchor.get_text(" ", strip=True)
        if not title:
            title = Path(urlparse(url).path).stem

        discovered.append({
            "title": title,
            "url": url,
        })

        if len(discovered) >= MAX_DISCOVERED:
            break

    logger.info(
        "Found %s direct PDF links",
        len(discovered),
    )
    return discovered


def download_document(
    client: httpx.Client,
    document: dict,
    records: list[dict],
) -> None:
    url = document["url"]

    if not allowed_url(url):
        logger.warning("Skipping unapproved URL: %s", url)
        return

    response = client.get(url)
    response.raise_for_status()

    if not allowed_url(str(response.url)):
        raise ValueError("Unexpected redirect destination")

    data = response.content

    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Document exceeds size limit")

    if not data.startswith(b"%PDF-"):
        raise ValueError("Response is not a PDF")

    content_hash = sha256_bytes(data)

    if any(
        record["sha256"] == content_hash
        for record in records
    ):
        logger.info("Duplicate PDF skipped: %s", url)
        return

    with pymupdf.open(
        stream=data,
        filetype="pdf",
    ) as pdf:
        pages = [
            {
                "page_number": number,
                "text": page.get_text("text"),
            }
            for number, page in enumerate(pdf, start=1)
        ]

    file_stem = (
        f"{safe_filename(document['title'])}_"
        f"{content_hash[:12]}"
    )

    pdf_path = BASE_DIR / f"{file_stem}.pdf"
    text_path = BASE_DIR / f"{file_stem}.json"

    BASE_DIR.mkdir(parents=True, exist_ok=True)

    pdf_path.write_bytes(data)

    text_path.write_text(
        json.dumps(
            pages,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    records.append({
        "regulator": "RBI",
        "title": document["title"],
        "source_url": url,
        "resolved_url": str(response.url),
        "sha256": content_hash,
        "retrieved_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "pdf_path": str(pdf_path),
        "text_path": str(text_path),
        "page_count": len(pages),
        "text_characters": sum(
            len(page["text"]) for page in pages
        ),
    })

    save_manifest(records)

    logger.info(
        "Saved %s (%s pages)",
        pdf_path.name,
        len(pages),
    )


def main() -> None:
    records = load_manifest()

    with httpx.Client(
        timeout=45,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "RegulatoryComplianceResearch/0.1 "
                "(educational document ingestion)"
            )
        },
    ) as client:

        documents = list(SEED_DOCUMENTS)

        try:
            documents.extend(
                discover_pdf_links(client)
            )
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "Index discovery unavailable: %s",
                exc,
            )

        seen_urls = set()

        for document in documents:
            url = document["url"]

            if url in seen_urls:
                continue

            seen_urls.add(url)

            try:
                download_document(
                    client,
                    document,
                    records,
                )
            except (
                httpx.HTTPError,
                ValueError,
                pymupdf.FileDataError,
            ) as exc:
                logger.error(
                    "Download failed for %s: %s",
                    url,
                    exc,
                )

            time.sleep(DELAY_SECONDS)

    logger.info(
        "Completed. %s unique PDFs in manifest.",
        len(records),
    )


if __name__ == "__main__":
    main()
