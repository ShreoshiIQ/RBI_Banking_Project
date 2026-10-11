
import json
import re
from pathlib import Path

from pydantic import BaseModel, Field


class ExtractedClause(BaseModel):
    clause_number: str
    clause_text: str
    start_page: int
    end_page: int
    status: str = "active"
    extraction_method: str = "regex_v5"
    confidence: float = Field(ge=0, le=1)


CLAUSE_PATTERN = re.compile(
    r"^\s*(\d{1,3}[A-Z]?)\.(?:\s*(\S.*))?$"
)

CHAPTER_PATTERN = re.compile(
    r"^CHAPTER\s*(?:[-–—]\s*)?[IVXLCDM]+(?:\s*[-–—]\s*[^.]+)?\s*$",
    re.IGNORECASE,
)

FOOTNOTE_SECTION_PATTERN = re.compile(
    r"^\s*(\d{1,3})(\d{1,3}[A-Z])\.\s*(\S.*)$"
)

DELETED_PATTERN = re.compile(
    r"^(?:\d+\s*)?Deleted\.?$",
    re.IGNORECASE,
)

ANNEXURE_PATTERN = re.compile(
    r"^\s*(?:ANNEX|ANNEXURE)\s*[-–:]?\s*(?:[IVXLCDM]+|\d+|[A-Z])?\s*$",
    re.IGNORECASE,
)


def split_section_number(number: str):
    match = re.fullmatch(r"(\d+)([A-Z]?)", number)

    if not match:
        return None

    return int(match.group(1)), match.group(2)


def is_next_clause(
    current_number: str | None,
    candidate_number: str,
) -> bool:
    candidate = split_section_number(candidate_number)

    if candidate is None:
        return False

    candidate_base, candidate_suffix = candidate

    if current_number is None:
        return candidate_base == 1 and candidate_suffix == ""

    current = split_section_number(current_number)

    if current is None:
        return False

    current_base, current_suffix = current

    if (
        candidate_base == current_base + 1
        and candidate_suffix == ""
    ):
        return True

    # Example: 5 -> 5A
    if (
    candidate_base == current_base
    and current_suffix == ""
    and candidate_suffix == "A"
    ):
        return True

# Example: 32 -> 33A
# Some amended regulations introduce 33A
# without retaining a standalone section 33.
    if (
        candidate_base == current_base + 1
        and candidate_suffix == "A"
        ):
        return True

    if (
        candidate_base == current_base
        and current_suffix
        and candidate_suffix
        and ord(candidate_suffix)
        == ord(current_suffix) + 1
    ):
        return True

    return False


def detect_clause_number(
    line: str,
    current_number: str | None,
) -> str | None:
    match = CLAUSE_PATTERN.match(line)

    if match:
        candidate_number = match.group(1)

        if is_next_clause(
            current_number,
            candidate_number,
        ):
            return candidate_number

    match = FOOTNOTE_SECTION_PATTERN.match(line)

    if match:
        candidate_number = match.group(2)

        if is_next_clause(
            current_number,
            candidate_number,
        ):
            return candidate_number

    return None


def detect_status(text: str) -> str:
    if not text.strip():
        return "active"

    first_line = text.splitlines()[0].strip()
    match = CLAUSE_PATTERN.match(first_line)

    if match:
        body = (match.group(2) or "").strip()

        if DELETED_PATTERN.fullmatch(body):
            return "deleted"

    return "active"



def extract_clauses(
    pages: list[dict],
) -> list[ExtractedClause]:
    clauses = []

    current_number = None
    current_lines = []
    start_page = None
    last_page = None

    inside_chapters = False
    inside_annexure = False

    def flush():
        if current_number is None:
            return

        text = "\n".join(current_lines).strip()

        if not text:
            return

        status = detect_status(text)

        if len(text) < 40 and status != "deleted":
            return

        clauses.append(
            ExtractedClause(
                clause_number=current_number,
                clause_text=text,
                start_page=start_page,
                end_page=last_page,
                status=status,
                extraction_method="regex_v5",
                confidence=0.60,
            )
        )

    for page in pages:
        page_number = int(page["page_number"])

        for line in page["text"].splitlines():
            cleaned = line.strip()

            if CHAPTER_PATTERN.match(cleaned):
                inside_chapters = True

            if not inside_chapters:
                continue

            if ANNEXURE_PATTERN.match(cleaned):
                flush()
                current_number = None
                current_lines = []
                inside_annexure = True
                continue

            if inside_annexure:
                continue

            candidate_number = detect_clause_number(
                cleaned,
                current_number,
            )

            if candidate_number is not None:
                flush()

                current_number = candidate_number
                current_lines = [cleaned]
                start_page = page_number
                last_page = page_number

            elif current_number is not None:
                current_lines.append(line)
                last_page = page_number

    flush()

    return clauses


def main():
    manifest_path = Path(
        "data/metadata/rbi_manifest.json"
    )

    records = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    output_dir = Path(
        "data/processed/clauses"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for record in records:
        pages = json.loads(
            Path(record["text_path"]).read_text(
                encoding="utf-8"
            )
        )

        clauses = extract_clauses(pages)

        output_path = (
            output_dir
            / f"{record['sha256'][:12]}_clauses.json"
        )

        output_path.write_text(
            json.dumps(
                [c.model_dump() for c in clauses],
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print(f"Document: {record['title']}")
        print(f"Total candidate clauses: {len(clauses)}")
        print(
            "Deleted clauses:",
            sum(
                c.status == "deleted"
                for c in clauses
            ),
        )
        print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
