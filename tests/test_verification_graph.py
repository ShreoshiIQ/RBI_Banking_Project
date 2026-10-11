
from unittest.mock import Mock

from regintel.orchestration.verification_graph import (
    VerificationWorkflow,
)


OBLIGATION = (
    "REs shall,\n"
    "(a) maintain all necessary records of transactions "
    "between the RE and the customer, both domestic and "
    "international, for at least five years from the "
    "date of transaction;"
)

POLICY = (
    "The bank shall maintain records of domestic and "
    "international customer transactions for at least "
    "five years from the transaction date."
)


def inputs():
    return {
        "obligation_id": "ob-1",
        "obligation_text": OBLIGATION,
        "policy_section_id": "section-2",
        "policy_text": POLICY,
    }


def make_workflow(
    cached_result=None,
    use_llm=True,
    llm_result=None,
):
    verifier = Mock()
    verifier.model_name = "gemini-test"

    if llm_result is not None:
        verifier.verify.return_value = llm_result

    cache = Mock()
    cache.get.return_value = cached_result
    cache.put.return_value = True
    cache.stats.api_calls = 0

    workflow = VerificationWorkflow(
        verifier=verifier,
        cache=cache,
        use_llm=use_llm,
    )

    return workflow, verifier, cache


def test_cache_hit_skips_gemini():
    cached = Mock()
    cached.model_dump.return_value = {
        "status": "attributes_matched",
        "validation_errors": [],
        "requires_human_review": True,
    }

    workflow, verifier, cache = make_workflow(
        cached_result=cached
    )

    state = workflow.invoke(**inputs())

    assert state["cache_status"] == "hit"
    assert state["final_status"] == "attributes_matched"
    assert state["requires_human_review"] is True
    assert "cache_hit" in state["trace"]

    verifier.verify.assert_not_called()
    cache.put.assert_not_called()


def test_cache_miss_calls_gemini():
    llm_result = Mock()
    llm_result.model_dump.return_value = {
        "status": "partial_evidence",
        "validation_errors": [],
        "requires_human_review": True,
    }

    workflow, verifier, cache = make_workflow(
        llm_result=llm_result
    )

    state = workflow.invoke(**inputs())

    assert state["cache_status"] == "miss"
    assert state["final_status"] == "partial_evidence"
    assert state["requires_human_review"] is True
    assert "gemini_verification" in state["trace"]

    verifier.verify.assert_called_once()
    cache.put.assert_called_once()
    assert cache.stats.api_calls == 1


def test_preview_mode_never_calls_gemini():
    workflow, verifier, cache = make_workflow(
        use_llm=False
    )

    state = workflow.invoke(**inputs())

    assert state["cache_status"] == "miss"
    assert state["final_status"] == "needs_review"
    assert state["requires_human_review"] is True

    verifier.verify.assert_not_called()
    cache.put.assert_not_called()


def test_gemini_failure_requires_review():
    workflow, verifier, cache = make_workflow()

    verifier.verify.side_effect = RuntimeError(
        "API quota exceeded"
    )

    state = workflow.invoke(**inputs())

    assert state["final_status"] == "verification_failed"
    assert state["requires_human_review"] is True
    assert "gemini_verification_failed" in state["trace"]
    assert state["errors"]

    cache.put.assert_not_called()


def test_empty_obligation_is_rejected():
    workflow, _, _ = make_workflow()

    data = inputs()
    data["obligation_text"] = ""

    try:
        workflow.invoke(**data)
        assert False, "Expected ValueError"
    except ValueError:
        pass
