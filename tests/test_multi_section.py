
from unittest.mock import Mock

from regintel.orchestration.multi_section import (
    PolicyEvidence,
    build_evidence_bundle,
    multi_section_cache_key,
    validate_section_citations,
)
from regintel.orchestration.multi_section_graph import (
    MultiSectionWorkflow,
)


SECTIONS = [
    PolicyEvidence(
        section_id="s4",
        section_number="4",
        section_title="Regulatory Requests",
        section_text=(
            "The bank shall make records available "
            "to competent authorities upon request."
        ),
    ),
    PolicyEvidence(
        section_id="s6",
        section_number="6",
        section_title="Record Retrieval",
        section_text=(
            "The bank shall maintain a system "
            "to retrieve account information efficiently."
        ),
    ),
]


def key(sections):
    return multi_section_cache_key(
        obligation_id="ob-f",
        obligation_text="Maintain retrievable account records.",
        sections=sections,
        model_name="gemini-test",
    )


def test_bundle_contains_both_sections():
    bundle = build_evidence_bundle(SECTIONS)

    assert "POLICY SECTION 4" in bundle
    assert "POLICY SECTION 6" in bundle
    assert "competent authorities" in bundle
    assert "retrieve account information" in bundle


def test_key_is_independent_of_section_order():
    assert key(SECTIONS) == key(list(reversed(SECTIONS)))


def test_key_changes_when_section_changes():
    changed = [
        SECTIONS[0],
        PolicyEvidence(
            section_id="s6",
            section_number="6",
            section_title="Record Retrieval",
            section_text="The bank retrieves information slowly.",
        ),
    ]

    assert key(SECTIONS) != key(changed)


def test_quote_resolves_to_correct_section():
    result = Mock()
    result.policy_quote = (
        "The bank shall maintain a system "
        "to retrieve account information efficiently."
    )

    citations, errors = validate_section_citations(
        result,
        SECTIONS,
    )

    assert not errors
    assert len(citations) == 1
    assert citations[0]["section_id"] == "s6"


def test_hallucinated_quote_is_rejected():
    result = Mock()
    result.policy_quote = (
        "The bank guarantees instant access worldwide."
    )

    citations, errors = validate_section_citations(
        result,
        SECTIONS,
    )

    assert not citations
    assert errors


def test_preview_skips_cache_and_gemini():
    verifier = Mock()
    verifier.model_name = "preview-only"

    cache = Mock()

    workflow = MultiSectionWorkflow(
        verifier=verifier,
        cache=cache,
        use_llm=False,
    )

    state = workflow.invoke(
        obligation_id="ob-f",
        obligation_text="Maintain retrievable account records.",
        sections=SECTIONS,
    )

    assert state["final_status"] == "needs_review"
    assert state["requires_human_review"] is True
    assert state["cache_status"] == "not_checked"

    verifier.verify.assert_not_called()
    cache.get.assert_not_called()
    cache.put.assert_not_called()


def test_cache_hit_skips_gemini():
    cached = {
        "proposed_status": "partial_evidence",
        "findings": [{
            "requirement": "Maintain retrievable account records.",
            "assessment": "partial",
            "explanation": "Retrieval is described, but completeness needs review.",
            "citations": [{
                "section_id": "s6",
                "exact_quote": SECTIONS[1].section_text,
                "supported_requirement": "Maintain retrievable account records.",
            }],
        }],
        "missing_requirements": [],
        "potential_conflicts": [],
        "explanation": "Partial evidence requires human review.",
    }

    verifier = Mock()
    verifier.model_name = "gemini-test"

    cache = Mock()
    cache.get.return_value = cached

    workflow = MultiSectionWorkflow(
        verifier=verifier,
        cache=cache,
    )

    state = workflow.invoke(
        obligation_id="ob-f",
        obligation_text="Maintain retrievable account records.",
        sections=SECTIONS,
    )

    assert state["cache_status"] == "hit"
    assert state["final_status"] == "partial_evidence"
    assert state["requires_human_review"] is True

    verifier.verify.assert_not_called()
    assert state["citations"][0]["section_id"] == "s6"
    cache.put.assert_not_called()


def test_invalid_model_quote_is_not_cached():
    result = {
        "status": "needs_review",
        "citations": [],
        "validation_errors": ["Quotation not found in policy section"],
    }

    verifier = Mock()
    verifier.model_name = "gemini-test"
    verifier.verify.return_value = result

    cache = Mock()
    cache.get.return_value = None
    cache.stats.api_calls = 0

    workflow = MultiSectionWorkflow(
        verifier=verifier,
        cache=cache,
    )

    state = workflow.invoke(
        obligation_id="ob-f",
        obligation_text="Maintain retrievable account records.",
        sections=SECTIONS,
    )

    assert state["final_status"] == "needs_review"
    assert state["errors"]
    assert state["requires_human_review"] is True
    cache.put.assert_not_called()
    assert "evidence_rejected" in state["trace"]
    assert "gemini_failed" not in state["trace"]
