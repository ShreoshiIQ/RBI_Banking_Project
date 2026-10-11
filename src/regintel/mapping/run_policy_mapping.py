
"""
Batch regulatory obligation-to-policy retrieval.

Version: 1.0

Reads:
- regulatory_obligations
- policy_documents
- policy_document_versions
- policy_sections

Writes:
- data/processed/mappings/keyword_policy_matches.json

This first version does not write mappings to PostgreSQL.

Run:
    uv run python -m regintel.mapping.run_policy_mapping
"""

import json

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from regintel.db.session import SessionLocal

from regintel.models.obligation import RegulatoryObligation
from regintel.models.policy import (
    PolicyDocument,
    PolicyDocumentVersion,
    PolicySection,
)

from regintel.mapping.keyword_matcher import (
    rank_policy_sections,
)


OUTPUT_PATH = Path(
    "data/processed/mappings/keyword_policy_matches.json"
)

TOP_K = 3
MIN_SCORE = 0.05


def load_policy_sections(session) -> list[dict]:
    """Load policy sections with their document metadata."""

    rows = session.execute(
        select(
            PolicySection,
            PolicyDocumentVersion,
            PolicyDocument,
        )
        .join(
            PolicyDocumentVersion,
            PolicySection.version_id
            == PolicyDocumentVersion.id,
        )
        .join(
            PolicyDocument,
            PolicyDocumentVersion.document_id
            == PolicyDocument.id,
        )
        .order_by(
            PolicyDocument.policy_code,
            PolicyDocumentVersion.retrieved_at.desc(),
            PolicySection.section_number,
        )
    ).all()

    # Use only the latest ingested version of each policy.
    latest_version_by_document = {}

    for section, version, document in rows:
        latest_version_by_document.setdefault(
            str(document.id),
            str(version.id),
        )

    sections = []

    for section, version, document in rows:
        if (
            str(version.id)
            != latest_version_by_document[str(document.id)]
        ):
            continue

        sections.append(
            {
                "id": str(section.id),
                "policy_document_id": str(document.id),
                "policy_version_id": str(version.id),
                "policy_code": document.policy_code,
                "section_number": section.section_number,
                "section_title": section.section_title or "",
                "section_text": section.section_text,
            }
        )

    return sections


def run_mapping() -> dict:
    """Run candidate retrieval for all stored obligations."""

    with SessionLocal() as session:
        obligations = session.scalars(
            select(RegulatoryObligation)
            .order_by(
                RegulatoryObligation.clause_number,
                RegulatoryObligation.id,
            )
        ).all()

        sections = load_policy_sections(session)

        if not sections:
            raise ValueError(
                "No policy sections found in PostgreSQL."
            )

        results = []
        matched_count = 0

        for obligation in obligations:
            matches = rank_policy_sections(
                obligation_text=obligation.evidence_quote,
                policy_sections=sections,
                top_k=TOP_K,
                min_score=MIN_SCORE,
            )

            if matches:
                matched_count += 1

            results.append(
                {
                    "obligation_id": str(obligation.id),
                    "source_clause_id": str(
                        obligation.source_clause_id
                    ),
                    "document_version_id": str(
                        obligation.document_version_id
                    ),
                    "clause_number": obligation.clause_number,
                    "obligation_type": obligation.obligation_type,
                    "obligation_text": obligation.evidence_quote,
                    "review_status": obligation.review_status,
                    "retrieval_status": (
                        "candidate_matches_found"
                        if matches
                        else "no_lexical_match_found"
                    ),
                    "matches": [
                        {
                            "policy_section_id": match.policy_section_id,
                            "section_number": match.section_number,
                            "section_title": match.section_title,
                            "score": match.score,
                            "matched_terms": match.matched_terms,
                            "policy_text": match.policy_text,
                        }
                        for match in matches
                    ],
                }
            )

    report = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "retrieval_method": "keyword_cosine_v1",
        "top_k": TOP_K,
        "min_score": MIN_SCORE,
        "total_obligations": len(results),
        "total_policy_sections": len(sections),
        "obligations_with_candidate_matches": matched_count,
        "obligations_without_lexical_matches": (
            len(results) - matched_count
        ),
        "results": results,
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return report


def main():
    report = run_mapping()

    print("\nPOLICY MAPPING RETRIEVAL RESULTS")
    print("-" * 50)
    print("Method:", report["retrieval_method"])
    print("Obligations:", report["total_obligations"])
    print("Policy sections:", report["total_policy_sections"])
    print(
        "With candidate matches:",
        report["obligations_with_candidate_matches"],
    )
    print(
        "Without lexical matches:",
        report["obligations_without_lexical_matches"],
    )
    print("Output:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
