"""Flag explicit source withdrawal watermarks before obligation extraction."""

import re

WITHDRAWN_LINE = re.compile(r"^\s*withdrawn\s*$", re.IGNORECASE)


def inspect_source_status(pages: list[dict]) -> dict:
    marked = [
        page["page_number"] for page in pages
        if any(WITHDRAWN_LINE.fullmatch(line) for line in page["text"].splitlines())
    ]
    return {
        "status": "withdrawal_marker_detected" if marked else "requires_applicability_review",
        "withdrawal_marker_pages": marked,
        "current_obligation_extraction_allowed": False if marked else None,
        "notice": "No marker does not prove current applicability. Verify repeal and replacement instruments.",
    }
