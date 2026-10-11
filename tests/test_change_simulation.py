from copy import deepcopy

import pytest

from regintel.changes.simulate import simulate


def test_hypothetical_change_preserves_baseline_and_drops_false_citations():
    base = {"document_id": "test", "content_hash": "hash", "clauses": [{"clause_number": "1", "clause_text": "Keep records for five years", "start_page": 4}]}
    original = deepcopy(base)
    proposal = {"base_content_hash": "hash", "edits": [{"clause_number": "1", "operation": "modify", "clause_text": "Keep records for ten years"}]}
    result = simulate(base, proposal, [])
    assert base == original
    assert result["simulation"] is True
    assert result["comparison"]["summary"] == {"modified": 1}
    assert result["hypothetical_version"]["content_hash"].startswith("simulation:")
    assert "start_page" not in result["hypothetical_version"]["clauses"][0]
    assert result["baseline"]["clauses"][0]["start_page"] == 4


@pytest.mark.parametrize("edit", [
    {"clause_number": "1", "operation": "remove"},
    {"clause_number": "1", "operation": "unknown"},
    {"clause_number": "1", "operation": "add", "clause_text": ""},
])
def test_invalid_edits_rejected(edit):
    with pytest.raises(ValueError):
        simulate({"document_id": "test", "content_hash": "hash", "clauses": []}, {"base_content_hash": "hash", "edits": [edit]}, [])
