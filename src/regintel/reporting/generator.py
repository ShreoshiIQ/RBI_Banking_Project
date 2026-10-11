
import hashlib
import json
from typing import Any

from regintel.reporting.schemas import (
    EvidenceReference,
    GapFinding,
    GapStatus,
    GapSummary,
    RegulatoryGapReport,
)


ACTIONS = {
    GapStatus.SUPPORTED: (
        "Confirm that the cited policy commitment is applicable, "
        "current, and implemented in operational procedures."
    ),
    GapStatus.PARTIAL: (
        "Review the cited policy evidence, identify the uncovered "
        "elements, and determine whether policy clarification "
        "or additional controls are required."
    ),
    GapStatus.MISSING: (
        "Search additional approved policies and procedures. "
        "If the requirement remains unaddressed, propose "
        "an appropriate policy or control update."
    ),
    GapStatus.POTENTIAL_CONFLICT: (
        "Escalate the apparent inconsistency to the compliance "
        "team and confirm the correct regulatory interpretation "
        "before proposing remediation."
    ),
}


def generate_gap_report(
    source: dict[str, Any],
    *,
    regulatory_text: str | None = None,
) -> RegulatoryGapReport:
    workflow = source["workflow"]

    if source.get("mode") != "live":
        raise ValueError(
            "A live, validated assessment is required"
        )

    if workflow.get("errors"):
        raise ValueError(
            "Cannot generate a report from a failed verification"
        )

    if workflow.get("requires_human_review") is not True:
        raise ValueError(
            "Expected a human-reviewable assessment"
        )

    result = workflow.get("result")

    if not isinstance(result, dict):
        raise ValueError("No verification result found")

    if result.get("validation_errors"):
        raise ValueError(
            "Cannot report on unvalidated evidence"
        )

    if result.get("requires_human_review") is not True:
        raise ValueError(
            "Assessment is missing its human-review flag"
        )

    if not result.get("findings"):
        raise ValueError("Assessment contains no findings")

    if workflow.get("final_status") != result.get("status"):
        raise ValueError(
            "Workflow and assessment statuses disagree"
        )

    allowed_statuses = {
        "attributes_matched",
        "partial_evidence",
        "potential_conflict",
        "needs_review",
    }

    if result["status"] not in allowed_statuses:
        raise ValueError("Unsupported assessment status")

    sections = source.get("policy_sections", [])
    section_ids = {
        str(section["id"]) for section in sections
    }

    validated = {}

    for citation in result.get("citations", []):
        section_id = str(citation["section_id"])

        if section_id not in section_ids:
            raise ValueError(
                f"Unknown validated section: {section_id}"
            )

        key = (
            section_id,
            citation["quote"],
            citation["requirement"],
        )

        validated[key] = citation

    findings = []

    for raw in result["findings"]:
        status = GapStatus(raw["assessment"])
        evidence = []

        for citation in raw.get("citations", []):
            key = (
                str(citation["section_id"]),
                citation["exact_quote"],
                raw["requirement"],
            )

            matched = validated.get(key)

            if matched is None:
                raise ValueError(
                    "Finding references an unvalidated quotation"
                )

            evidence.append(
                EvidenceReference(
                    section_id=matched["section_id"],
                    section_number=matched["section_number"],
                    section_title=matched["section_title"],
                    quote=matched["quote"],
                    requirement=matched["requirement"],
                )
            )

        if status == GapStatus.SUPPORTED and not evidence:
            raise ValueError(
                "Supported finding has no validated evidence"
            )

        findings.append(
            GapFinding(
                requirement=raw["requirement"],
                status=status,
                explanation=raw["explanation"],
                evidence=evidence,
                suggested_action=ACTIONS[status],
            )
        )

    # Include reported missing requirements even if the
    # model did not create a corresponding finding.
    known_missing = {
        f.requirement.strip().casefold()
        for f in findings
        if f.status == GapStatus.MISSING
    }

    for requirement in result.get(
        "missing_requirements", []
    ):
        normalized = requirement.strip().casefold()

        if normalized and normalized not in known_missing:
            findings.append(
                GapFinding(
                    requirement=requirement,
                    status=GapStatus.MISSING,
                    explanation=(
                        "The verifier identified this as missing "
                        "evidence. Confirm against the complete "
                        "approved policy corpus."
                    ),
                    suggested_action=ACTIONS[GapStatus.MISSING],
                )
            )
            known_missing.add(normalized)

    # Preserve potential conflicts that were reported
    # outside the structured findings.
    known_conflicts = {
        f.requirement.strip().casefold()
        for f in findings
        if f.status == GapStatus.POTENTIAL_CONFLICT
    }

    for conflict in result.get("potential_conflicts", []):
        normalized = conflict.strip().casefold()

        if normalized and normalized not in known_conflicts:
            findings.append(
                GapFinding(
                    requirement=conflict,
                    status=GapStatus.POTENTIAL_CONFLICT,
                    explanation=(
                        "Potential inconsistency flagged by "
                        "the verifier; not a confirmed conflict."
                    ),
                    suggested_action=ACTIONS[
                        GapStatus.POTENTIAL_CONFLICT
                    ],
                )
            )
            known_conflicts.add(normalized)

    summary = GapSummary(
        total=len(findings),
        supported=sum(
            f.status == GapStatus.SUPPORTED for f in findings
        ),
        partial=sum(
            f.status == GapStatus.PARTIAL for f in findings
        ),
        missing=sum(
            f.status == GapStatus.MISSING for f in findings
        ),
        potential_conflicts=sum(
            f.status == GapStatus.POTENTIAL_CONFLICT
            for f in findings
        ),
    )

    reference = source.get("obligation", "unknown")

    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "reference": reference,
                "sections": sections,
                "result": result,
            },
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()[:16]

    return RegulatoryGapReport(
        report_id=f"gap-{fingerprint}",
        regulatory_reference=f"RBI KYC Section {reference}",
        regulatory_text=regulatory_text,
        assessment_status=result["status"],
        findings=findings,
        summary=summary,
        source_policy_sections=[
            str(s["number"]) for s in sections
        ],
        missing_requirements=result.get(
            "missing_requirements", []
        ),
        potential_conflicts=result.get(
            "potential_conflicts", []
        ),
        overall_explanation=result.get(
            "explanation", ""
        ),
        source_cache_status=workflow.get("cache_status"),
    )
