"""Build source-backed, unapproved review queues from expansion previews."""

import json
import re
from collections import Counter
from pathlib import Path

from regintel.ingestion.catalog_review import review_template


def classify_section(text: str) -> str:
    normalized = " ".join(text.split())
    if re.search(r"\bstand repealed\b|\bnotwithstanding such repeal\b|\brepeal.*saving\b", normalized, re.I):
        return "repeal_or_saving"
    if re.search(r"\bunless the context (?:otherwise requires|states otherwise)\b", normalized, re.I):
        return "definitions"
    if re.search(r"\bThese Directions shall (?:be called|come into force|come into effect)\b", normalized, re.I):
        return "title_or_commencement"
    if re.search(r"\bThese Directions shall be applicable\b|\bThe scope of provisions\b", normalized, re.I):
        return "applicability_or_scope"
    return "potential_operational_control"


def triage_preview(preview: dict) -> dict:
    clauses = {item["clause_number"]: item for item in preview["clauses"]}
    rows = []
    for row in preview["validation"]["candidates"]:
        clause = clauses[row["source"]["clause_number"]]
        category = classify_section(clause["clause_text"])
        priority = "high" if category != "potential_operational_control" or row["issues"] else "normal"
        rows.append({
            **row, "section_category": category, "review_priority": priority,
            "section_evidence": clause,
            "review_instruction": (
                "Review as context; do not assume this is an operational control."
                if category != "potential_operational_control" else
                "Confirm actor, applicability, evidence, and atomic requirement against the PDF."
            ),
        })
    return {
        **preview["validation"], "candidates": rows,
        "triage_summary": dict(Counter(row["section_category"] for row in rows)),
        "notice": "Heuristic review routing only. No candidate is approved or rejected.",
    }


def main():
    output = Path("data/processed/expansion_reviews")
    output.mkdir(parents=True, exist_ok=True)
    for path in sorted(Path("data/processed/expansion_previews").glob("*_preview.json")):
        preview = json.loads(path.read_text(encoding="utf-8"))
        report = triage_preview(preview)
        prefix = path.name.split("_")[0]
        for name, data in (
            (f"{prefix}_triage.json", report),
            (f"{prefix}_decisions.json", review_template(report)),
        ):
            target = output / name
            if not target.exists():
                with target.open("x", encoding="utf-8") as stream:
                    json.dump(data, stream, indent=2, ensure_ascii=False)
        print(prefix, json.dumps(report["triage_summary"]))


if __name__ == "__main__":
    main()
