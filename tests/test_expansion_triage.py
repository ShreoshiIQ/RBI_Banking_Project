import pytest

from regintel.ingestion.triage_expansion import classify_section


@pytest.mark.parametrize("text,category", [
    ("These Directions shall be called test directions.", "title_or_commencement"),
    ("These Directions shall come into force with immediate effect.", "title_or_commencement"),
    ("In these Directions, unless the context otherwise requires, terms mean:", "definitions"),
    ("Existing directions stand repealed.", "repeal_or_saving"),
    ("Notwithstanding such repeal, actions remain governed by prior rules.", "repeal_or_saving"),
    ("These Directions shall be applicable to commercial banks.", "applicability_or_scope"),
    ("Banks shall apply access controls as applicable to their systems.", "potential_operational_control"),
])
def test_section_routing(text, category):
    assert classify_section(text) == category
