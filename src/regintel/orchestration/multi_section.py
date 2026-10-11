
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from regintel.verification.evidence_validator import (
    quote_exists,
)


MULTI_SECTION_VERSION = "multi_section_v1"
PROMPT_VERSION = "gemini_verifier_v1"
VALIDATOR_VERSION = "multi_section_validator_v1"


@dataclass(frozen=True)
class PolicyEvidence:
    section_id: str
    section_number: str
    section_title: str
    section_text: str


def build_evidence_bundle(
    sections: list[PolicyEvidence],
) -> str:
    if not sections:
        raise ValueError("At least one policy section is required")

    if len({s.section_id for s in sections}) != len(sections):
        raise ValueError("Duplicate policy section IDs")

    blocks = []

    for section in sections:
        if not section.section_text.strip():
            raise ValueError(
                f"Empty policy section: {section.section_id}"
            )

        blocks.append(
            f"POLICY SECTION {section.section_number}\n"
            f"TITLE: {section.section_title}\n"
            f"SECTION ID: {section.section_id}\n"
            "BEGIN POLICY TEXT\n"
            f"{section.section_text}\n"
            "END POLICY TEXT"
        )

    return "\n\n".join(blocks)


def multi_section_cache_key(
    *,
    obligation_id: str,
    obligation_text: str,
    sections: list[PolicyEvidence],
    model_name: str,
) -> str:
    if not sections:
        raise ValueError("Cannot cache an empty evidence bundle")

    ordered = sorted(
        sections,
        key=lambda section: section.section_id,
    )

    payload = {
        "kind": MULTI_SECTION_VERSION,
        "prompt_version": PROMPT_VERSION,
        "validator_version": VALIDATOR_VERSION,
        "obligation_id": obligation_id,
        "obligation_text": obligation_text,
        "model_name": model_name,
        "sections": [
            {
                "id": s.section_id,
                "number": s.section_number,
                "title": s.section_title,
                "text": s.section_text,
            }
            for s in ordered
        ],
    }

    raw = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_section_citations(
    result: Any,
    sections: list[PolicyEvidence],
) -> tuple[list[dict], list[str]]:
    """
    Resolve the model's exact policy quote to its source
    section. Fail closed when the quote cannot be located
    within one individual policy section.
    """
    citations = []
    errors = []

    quote = result.policy_quote

    if not quote or not quote.strip():
        errors.append(
            "No section-specific policy quotation provided"
        )
        return citations, errors

    matches = [
        section
        for section in sections
        if quote_exists(quote, section.section_text)
    ]

    if not matches:
        errors.append(
            "Policy quotation was not found within "
            "an individual source section"
        )
        return citations, errors

    for section in matches:
        citations.append({
            "section_id": section.section_id,
            "section_number": section.section_number,
            "section_title": section.section_title,
            "quote": quote,
        })

    return citations, errors
