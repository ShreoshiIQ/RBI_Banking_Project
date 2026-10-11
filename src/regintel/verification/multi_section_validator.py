
from typing import Any

from regintel.orchestration.multi_section import (
    PolicyEvidence,
)
from regintel.verification.evidence_validator import (
    quote_exists,
)
from regintel.verification.multi_section_schemas import (
    MultiSectionAssessment,
)


def validate_multi_section_assessment(
    *,
    assessment: MultiSectionAssessment,
    sections: list[PolicyEvidence],
) -> dict[str, Any]:

    section_map = {
        section.section_id: section
        for section in sections
    }

    errors = []
    validated_citations = []
    seen = set()

    for index, finding in enumerate(assessment.findings):

        if finding.assessment == "supported" and not finding.citations:
            errors.append(
                f"Finding {index}: supported claim lacks a citation"
            )

        for citation in finding.citations:

            section = section_map.get(citation.section_id)

            if section is None:
                errors.append(
                    f"Finding {index}: unknown section "
                    f"{citation.section_id}"
                )
                continue

            if not citation.exact_quote.strip():
                errors.append(
                    f"Finding {index}: empty quotation"
                )
                continue

            if not quote_exists(
                citation.exact_quote,
                section.section_text,
            ):
                errors.append(
                    f"Finding {index}: quotation not found "
                    f"in section {section.section_number}"
                )
                continue

            citation_key = (
                citation.section_id,
                citation.exact_quote,
                finding.requirement,
            )

            if citation_key not in seen:
                seen.add(citation_key)

                validated_citations.append({
                    "section_id": section.section_id,
                    "section_number": section.section_number,
                    "section_title": section.section_title,
                    "quote": citation.exact_quote,
                    "requirement": finding.requirement,
                })

    if (
        assessment.proposed_status == "attributes_matched"
        and (
            assessment.missing_requirements
            or assessment.potential_conflicts
            or any(
                finding.assessment != "supported"
                for finding in assessment.findings
            )
        )
    ):
        errors.append(
            "Full-match status contradicts the findings"
        )

    if (
        assessment.proposed_status == "attributes_matched"
        and not validated_citations
    ):
        errors.append(
            "Full-match status has no validated citations"
        )

    # Fail closed when citations are invalid.
    if errors:
        status = "needs_review"
    else:
        status = assessment.proposed_status

    return {
        "status": status,
        "proposed_status": assessment.proposed_status,
        "findings": [
            finding.model_dump(mode="json")
            for finding in assessment.findings
        ],
        "citations": validated_citations,
        "missing_requirements": (
            assessment.missing_requirements
        ),
        "potential_conflicts": (
            assessment.potential_conflicts
        ),
        "explanation": assessment.explanation,
        "validation_errors": errors,
        "requires_human_review": True,
    }
