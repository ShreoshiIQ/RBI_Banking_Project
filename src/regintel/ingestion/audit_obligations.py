
import json
import re
from collections import Counter
from pathlib import Path


INPUT_PATH = Path(
    "data/processed/obligations/"
    "e525b18753fd_obligations.json"
)

FOOTNOTE_PATTERN = re.compile(
    r"\b(?:Amended|Inserted|Substituted|Deleted)\s+vide\b",
    re.IGNORECASE,
)

MODAL_PATTERN = re.compile(
    r"\b(?:shall|must|may|required to|permitted to)\b",
    re.IGNORECASE,
)


def main():
    data = json.loads(
        INPUT_PATH.read_text(encoding="utf-8")
    )

    obligations = data["obligations"]

    long_candidates = []
    footnote_candidates = []
    multiple_modal_candidates = []

    for item in obligations:
        evidence = item["evidence_quote"]

        if len(evidence) > 600:
            long_candidates.append(item)

        if FOOTNOTE_PATTERN.search(evidence):
            footnote_candidates.append(item)

        if len(MODAL_PATTERN.findall(evidence)) > 1:
            multiple_modal_candidates.append(item)

    print("OBLIGATION EXTRACTION QUALITY AUDIT")
    print("=" * 60)

    print("Total candidates:", len(obligations))
    print("Long evidence (>600 chars):", len(long_candidates))
    print("Contains amendment notes:", len(footnote_candidates))
    print("Multiple modal keywords:", len(multiple_modal_candidates))

    print("\nCANDIDATES BY CLAUSE")
    counts = Counter(
        item["clause_number"]
        for item in obligations
    )

    for clause, count in counts.most_common(10):
        print(f"Section {clause}: {count}")

    print("\nLONGEST 5 CANDIDATES")
    print("-" * 60)

    longest = sorted(
        obligations,
        key=lambda item: len(item["evidence_quote"]),
        reverse=True,
    )

    for item in longest[:5]:
        print(
            f"Section {item['clause_number']} | "
            f"Type: {item['obligation_type']} | "
            f"Characters: {len(item['evidence_quote'])}"
        )
        print(
            item["evidence_quote"][:300]
            .replace("\n", " ")
        )
        print("-" * 60)


if __name__ == "__main__":
    main()
