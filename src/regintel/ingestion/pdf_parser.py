
from pathlib import Path
import hashlib

import pymupdf


def calculate_sha256(file_path: str) -> str:
    """Calculate a unique content fingerprint for a file."""
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def extract_pdf_text(file_path: str) -> list[dict]:
    """Extract text from each page of a PDF."""
    pages = []

    with pymupdf.open(file_path) as document:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text")

            pages.append({
                "page_number": page_number,
                "text": text,
            })

    return pages


if __name__ == "__main__":
    pdf_path = Path("data/raw/sample.pdf")

    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
    else:
        print("SHA-256:", calculate_sha256(str(pdf_path)))

        pages = extract_pdf_text(str(pdf_path))

        print("Total pages:", len(pages))

        if pages:
            print("First page preview:")
            print(pages[0]["text"][:1000])
