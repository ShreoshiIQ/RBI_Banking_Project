
"""
Evaluate RBI Section 46(a)-(f) against all
current synthetic policy sections.

Run:
uv run python -m regintel.verification.run_attribute_verification
"""

import json
from pathlib import Path

from sqlalchemy import select

from regintel.db.session import SessionLocal
from regintel.models.obligation import RegulatoryObligation
from regintel.mapping.run_policy_mapping import (
    load_policy_sections,
)
from regintel.verification.attribute_verifier import (
    verify_attributes,
    get_obligation_suffix,
)


OUTPUT_PATH = Path(
    "data/processed/verification/"
    "attribute_verification_results.json"
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

    if not sections or not obligations:
        raise ValueError(
            "Missing policy sections or RBI obligations."
        )

    results = []

    for obligation in obligations:
        suffix = get_obligation_suffix(
            obligation.evidence_quote
        )

        if suffix is None:
            raise ValueError(
                f"Cannot identify obligation {obligation.id}"
            )

        for section in sections:
            result = verify_attributes(
                obligation_text=obligation.evidence_quote,
                policy_text=section["section_text"],
                policy_section_id=str(section["id"]),
            )

            results.append({
                "obligation_id": str(obligation.id),
                "obligation": result.obligation,
                "policy_section_number": section[
                    "section_number"
                ],
                "policy_section_id": str(section["id"]),
                "verification": result.to_dict(),
            })

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "verification_method": (
                    "deterministic_attributes_v1"
                ),
                "dataset_type": "synthetic_demonstration",
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nATTRIBUTE VERIFICATION RESULTS")
    print("=" * 65)

    for item in results:
        verification = item["verification"]

        if verification["status"] in (
            "attributes_matched",
            "partial_evidence",
        ):
            print(
                f"{item['obligation']} -> "
                f"Policy Section "
                f"{item['policy_section_number']} "
                f"=> {verification['status']}"
            )

            if verification["missing_attributes"]:
                print(
                    "  Missing:",
                    ", ".join(
                        verification["missing_attributes"]
                    ),
                )

    print("\nTotal assessments:", len(results))
    print("Saved:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
