
"""
Run retention verification on retrieved policy sections.

Output:
data/processed/verification/retention_results.json

This is an exploratory evidence-assessment report.
"""

import json

from pathlib import Path

from sqlalchemy import select

from regintel.db.session import SessionLocal
from regintel.models.obligation import RegulatoryObligation

from regintel.mapping.run_policy_mapping import (
    load_policy_sections,
)
from regintel.mapping.hybrid_retriever import (
    HybridPolicyRetriever,
)
from regintel.verification.retention_verifier import (
    verify_retention,
)


OUTPUT_PATH = Path(
    "data/processed/verification/retention_results.json"
)


def main():
    with SessionLocal() as session:
        sections = load_policy_sections(session)

        obligations = session.scalars(
            select(RegulatoryObligation)
            .where(
                RegulatoryObligation.clause_number == "46",
                RegulatoryObligation.extraction_method
                == "rule_based_v4_1_inherited",
            )
        ).all()

    if not sections:
        raise ValueError("No policy sections found.")

    retriever = HybridPolicyRetriever(sections)

    results = []

    for obligation in obligations:
        matches = retriever.search(
            obligation_text=obligation.evidence_quote,
            top_k=3,
        )

        for match in matches:
            result = verify_retention(
                obligation_id=str(obligation.id),
                obligation_text=obligation.evidence_quote,
                policy_section_id=match.policy_section_id,
                policy_text=match.policy_text,
            )

            results.append(
                {
                    "clause_number": obligation.clause_number,
                    "policy_section_number": match.section_number,
                    "retrieval_score": match.rrf_score,
                    "verification": result.model_dump(
                        mode="json"
                    ),
                }
            )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "verification_method": (
                    "deterministic_retention_v1"
                ),
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nRETENTION VERIFICATION COMPLETED")
    print("Assessments:", len(results))
    print("Output:", OUTPUT_PATH)

    for item in results:
        verification = item["verification"]

        print(
            f"RBI {item['clause_number']} "
            f"-> Policy Section "
            f"{item['policy_section_number']} "
            f"=> {verification['status']}"
        )


if __name__ == "__main__":
    main()
