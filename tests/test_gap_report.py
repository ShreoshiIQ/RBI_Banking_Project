
import copy

import pytest

from regintel.reporting.generator import generate_gap_report


def sample_source():
    quote = (
        "The bank shall maintain a system that "
        "permits authorized personnel to retrieve "
        "required account information efficiently."
    )

    return {
        "obligation": "46(f)",
        "mode": "live",
        "policy_sections": [
            {
                "id": "s6",
                "number": "6",
                "title": "Record Retrieval",
            }
        ],
        "workflow": {
            "cache_status": "hit",
            "final_status": "partial_evidence",
            "requires_human_review": True,
            "errors": [],
            "result": {
                "status": "partial_evidence",
                "proposed_status": "partial_evidence",
                "requires_human_review": True,
                "validation_errors": [],
                "explanation": (
                    "Retrieval is addressed but preservation "
                    "is not established."
                ),
                "findings": [
                    {
                        "requirement": "Efficient retrieval",
                        "assessment": "partial",
                        "explanation": (
                            "The policy supports retrieval."
                        ),
                        "citations": [
                            {
                                "section_id": "s6",
                                "exact_quote": quote,
                                "supported_requirement": (
                                    "Efficient retrieval"
                                ),
                            }
                        ],
                    },
                    {
                        "requirement": "Record preservation",
                        "assessment": "missing",
                        "explanation": (
                            "No explicit evidence supplied."
                        ),
                        "citations": [],
                    },
                ],
                "citations": [
                    {
                        "section_id": "s6",
                        "section_number": "6",
                        "section_title": "Record Retrieval",
                        "quote": quote,
                        "requirement": "Efficient retrieval",
                    }
                ],
                "missing_requirements": [
                    "Record preservation"
                ],
                "potential_conflicts": [],
            },
        },
    }


def test_generates_gap_report():
    report = generate_gap_report(sample_source())

    assert report.regulatory_reference == (
        "RBI KYC Section 46(f)"
    )
    assert report.assessment_status == "partial_evidence"
    assert report.requires_human_review is True


def test_summary_counts():
    report = generate_gap_report(sample_source())

    assert report.summary.total == 2
    assert report.summary.partial == 1
    assert report.summary.missing == 1
    assert report.summary.supported == 0


def test_validated_citation_preserved():
    report = generate_gap_report(sample_source())

    finding = report.findings[0]

    assert len(finding.evidence) == 1
    assert finding.evidence[0].section_number == "6"
    assert "retrieve" in finding.evidence[0].quote


def test_report_id_is_deterministic():
    source = sample_source()

    first = generate_gap_report(source)
    second = generate_gap_report(source)

    assert first.report_id == second.report_id


def test_preview_is_rejected():
    source = sample_source()
    source["mode"] = "preview"

    with pytest.raises(ValueError):
        generate_gap_report(source)


def test_invalid_evidence_is_rejected():
    source = sample_source()

    source["workflow"]["result"][
        "validation_errors"
    ] = ["Quote not found"]

    with pytest.raises(ValueError):
        generate_gap_report(source)


def test_unvalidated_finding_quote_is_rejected():
    source = sample_source()

    source["workflow"]["result"]["findings"][0][
        "citations"
    ][0]["exact_quote"] = "Fabricated quotation"

    with pytest.raises(ValueError):
        generate_gap_report(source)


def test_missing_requirement_is_added():
    source = copy.deepcopy(sample_source())

    source["workflow"]["result"][
        "missing_requirements"
    ].append("Broader account information coverage")

    report = generate_gap_report(source)

    assert report.summary.missing == 2
    assert report.summary.total == 3
