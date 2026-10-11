import pytest
from regintel.ingestion.applicability_review import template, validate


def fixture():
    packet = {"demo_profile": {"type": "commercial"}, "sources": [{"content_hash": "source", "passages": [{"clause_number": "3", "quote": "Scope"}]}]}
    return packet, template(packet)


def test_pending_template():
    packet, reviews = fixture()
    assert validate(packet, reviews)["summary"]["pending"] == 1


@pytest.mark.parametrize("change", ["profile", "passage", "duplicate", "incomplete", "citation"])
def test_invalid_review_rejected(change):
    packet, reviews = fixture()
    if change == "profile": packet["demo_profile"]["type"] = "NBFC"
    elif change == "passage": packet["sources"][0]["passages"][0]["quote"] = "Changed"
    elif change == "duplicate": reviews["decisions"] *= 2
    elif change == "incomplete": reviews["decisions"][0]["decision"] = "applicable"
    else: reviews["decisions"][0].update(decision="applicable", reviewer="Reviewer", rationale="Checked", cited_clause_numbers=["999"])
    with pytest.raises(ValueError): validate(packet, reviews)
