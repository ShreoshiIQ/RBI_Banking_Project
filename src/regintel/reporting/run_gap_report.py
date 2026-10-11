
import json
from pathlib import Path

from regintel.reporting.generator import generate_gap_report


SOURCE = Path(
    "data/processed/verification/multi_section_results.json"
)

OUTPUT_DIR = Path("data/processed/reports")


def markdown_report(report) -> str:
    lines = [
        "# Regulatory Gap Assessment",
        "",
        f"**Report ID:** {report.report_id}",
        f"**Regulation:** {report.regulatory_reference}",
        f"**Assessment:** {report.assessment_status}",
        f"**Review status:** {report.review_status.value}",
        "",
        "> Preliminary AI-assisted evidence assessment. "
        "Not a legal compliance determination.",
        "",
        "## Summary",
        "",
        f"- Total findings: {report.summary.total}",
        f"- Supported: {report.summary.supported}",
        f"- Partial: {report.summary.partial}",
        f"- Missing: {report.summary.missing}",
        (
            "- Potential conflicts: "
            f"{report.summary.potential_conflicts}"
        ),
        "",
        "## Findings",
        "",
    ]

    for index, finding in enumerate(
        report.findings, start=1
    ):
        lines.extend([
            f"### {index}. {finding.requirement}",
            "",
            f"**Status:** {finding.status.value}",
            "",
            finding.explanation,
            "",
        ])

        if finding.evidence:
            lines.append("**Supporting policy evidence:**")
            lines.append("")

            for evidence in finding.evidence:
                lines.extend([
                    (
                        f"- Policy Section "
                        f"{evidence.section_number} "
                        f"({evidence.section_title})"
                    ),
                    "",
                    f"  > {evidence.quote}",
                    "",
                ])

        else:
            lines.extend([
                "**Validated supporting quotations:** None",
                "",
            ])

        lines.extend([
            f"**Suggested action:** {finding.suggested_action}",
            "",
        ])

    lines.extend([
        "## Overall assessment",
        "",
        report.overall_explanation,
        "",
        "## Human review",
        "",
        "- Confirm the regulatory source and effective version.",
        "- Confirm that all applicable policies were searched.",
        "- Validate the meaning and scope of cited evidence.",
        "- Review proposed remediation before approval.",
        "",
    ])

    return "\n".join(lines)


def main():
    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Verification input not found: {SOURCE}"
        )

    source = json.loads(
        SOURCE.read_text(encoding="utf-8")
    )

    report = generate_gap_report(source)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path = OUTPUT_DIR / "rbi_46f_gap_report.json"
    md_path = OUTPUT_DIR / "rbi_46f_gap_report.md"

    json_path.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )

    md_path.write_text(
        markdown_report(report),
        encoding="utf-8",
    )

    print("\nREGULATORY GAP REPORT")
    print("-" * 50)
    print("Report ID:", report.report_id)
    print("Regulation:", report.regulatory_reference)
    print("Assessment:", report.assessment_status)
    print("Review:", report.review_status.value)

    print("\nFINDING SUMMARY")
    print("Supported:", report.summary.supported)
    print("Partial:", report.summary.partial)
    print("Missing:", report.summary.missing)
    print(
        "Potential conflicts:",
        report.summary.potential_conflicts,
    )

    print("\nSaved JSON:", json_path)
    print("Saved Markdown:", md_path)
    print("\nGemini API calls: 0")


if __name__ == "__main__":
    main()
