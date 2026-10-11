import pytest

from regintel.ingestion.actor_review import suggest_actor


def test_explicit_actor_has_exact_source_support():
    evidence = "REs shall maintain transaction records."
    result = suggest_actor({"evidence_quote": evidence, "clause_number": "46"}, "contiguous")
    assert result["suggested_actor"] == "REs"
    support = result["support"]
    assert evidence[support["start"]:support["end"]] == support["quote"]
    assert result["review_status"] == "pending"
    assert result["applicability_status"] == "requires_human_review"


@pytest.mark.parametrize("text,clause,match", [
    ("REs shall maintain records.", "46", "unmatched"),
    ("REs shall be notified.", "46", "contiguous"),
    ("Records shall be kept by REs.", "46", "contiguous"),
    ("Banks shall maintain records; customers must submit documents.", "46", "contiguous"),
    ("REs shall follow these directions.", "2", "contiguous"),
    ("Transactions shall be monitored.", "36", "contiguous"),
])
def test_ambiguous_or_unsupported_actors_remain_unresolved(text, clause, match):
    result = suggest_actor({"evidence_quote": text, "clause_number": clause}, match)
    assert result["suggested_actor"] is None
    assert result["support"] is None


def test_inherited_actor_and_conditional_scope():
    result = suggest_actor({
        "evidence_quote": "REs shall,\n(b) retain records unless an exception applies;",
        "clause_number": "46",
    }, "inherited_reconstruction")
    assert result["suggested_actor"] == "REs"
    assert "conditional_scope_requires_review" in result["applicability_flags"]
