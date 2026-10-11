
"""
Tests for hierarchical regulatory obligation extraction.

Version: 4.1

Covers:
- Parent modal inheritance
- Multiple lettered obligations
- Nested Roman numeral details
- Hierarchy boundaries
- Original evidence preservation
- Deleted clause exclusion
- Explicit obligations
- Long inherited passage deferral

Run:
    uv run pytest tests/test_hierarchical_obligations.py -v
"""

from uuid import uuid4

from regintel.ingestion.obligation_extractor import (
    extract_with_tracking,
)


def extract(text: str):
    """Extract active Section 46 obligation candidates."""
    return extract_with_tracking(
        source_clause_id=uuid4(),
        clause_number="46",
        clause_text=text,
        status="active",
    )


def inherited_obligations(result):
    """Return only inherited obligation candidates."""
    return [
        item
        for item in result.obligations
        if item.extraction_method
        == "rule_based_v4_1_inherited"
    ]


# =========================================================
# TEST 1: SIX INHERITED OBLIGATIONS
# =========================================================

def test_six_inherited_obligations():
    text = """
REs shall,

(a) maintain transaction records;
(b) preserve customer identification records;
(c) make records available upon request;
(d) introduce a record maintenance system;
(e) maintain information for reconstructing transactions;
(f) evolve a system for preserving account information.
"""

    result = extract(text)
    inherited = inherited_obligations(result)

    assert len(inherited) == 6

    assert all(
        item.obligation_type.value == "mandatory"
        for item in inherited
    )

    assert all(
        "REs shall" in item.evidence_quote
        for item in inherited
    )


# =========================================================
# TEST 2: ROMAN NUMERAL DETAILS
# =========================================================

def test_roman_details_attached_to_parent():
    text = """
REs shall,

(e) maintain information for reconstructing transactions,
including the following:

(i) the nature of transactions;
(ii) the transaction amount and currency;
(iii) the transaction date; and
(iv) the parties to the transaction.

(f) evolve a system for preserving account information.
"""

    result = extract(text)

    inherited = inherited_obligations(result)

    assert len(inherited) == 2

    parent = inherited[0]

    assert "(e)" in parent.evidence_quote
    assert "(i)" in parent.evidence_quote
    assert "(ii)" in parent.evidence_quote
    assert "(iii)" in parent.evidence_quote
    assert "(iv)" in parent.evidence_quote

    assert "(f)" not in parent.evidence_quote


# =========================================================
# TEST 3: HIERARCHY BOUNDARY
# =========================================================

def test_hierarchy_stops_at_unrelated_paragraph():
    text = """
REs shall,

(a) maintain customer records.

This section explains the general framework.

(b) unrelated historical information.
"""

    result = extract(text)

    inherited = inherited_obligations(result)

    assert len(inherited) == 1

    assert any(
        item.reason == "no_explicit_modal"
        and "(b)" in item.text
        for item in result.deferred
    )


# =========================================================
# TEST 4: EVIDENCE PRESERVATION
# =========================================================

def test_evidence_preserves_original_wording():
    text = """
REs shall,

(a) maintain all necessary records of transactions
for at least five years.
"""

    result = extract(text)

    assert len(result.obligations) == 1

    evidence = result.obligations[0].evidence_quote

    assert "REs shall," in evidence
    assert "(a) maintain all necessary records" in evidence
    assert "for at least five years" in evidence


# =========================================================
# TEST 5: DELETED CLAUSE
# =========================================================

def test_deleted_clause_produces_no_obligations():
    result = extract_with_tracking(
        source_clause_id=uuid4(),
        clause_number="46",
        clause_text="REs shall maintain records.",
        status="deleted",
    )

    assert result.obligations == []
    assert result.deferred == []


# =========================================================
# TEST 6: EXPLICIT OBLIGATION
# =========================================================

def test_explicit_obligation_still_works():
    result = extract(
        "Banks shall maintain customer records "
        "for at least five years."
    )

    assert len(result.obligations) == 1

    obligation = result.obligations[0]

    assert obligation.obligation_type.value == "mandatory"

    assert obligation.extraction_method == (
        "rule_based_v4_1_explicit"
    )


# =========================================================
# TEST 7: LONG INHERITED PASSAGE
# =========================================================

def test_long_inherited_passage_is_deferred():
    text = (
        "REs shall,\n\n"
        "(a) " + "maintain customer records " * 35
    )

    result = extract(text)

    assert len(inherited_obligations(result)) == 0

    assert any(
        item.reason == "long_inherited_passage"
        for item in result.deferred
    )


# =========================================================
# TEST 8: ROMAN DETAILS ARE NOT INDEPENDENT
# =========================================================

def test_roman_details_not_independent_obligations():
    text = """
REs shall,

(e) maintain transaction information, including:

(i) the transaction amount;
(ii) the currency;
(iii) the transaction date;
(iv) the parties to the transaction.

(f) preserve records for five years.
"""

    result = extract(text)

    assert len(result.obligations) == 2

    assert all(
        not item.evidence_quote.startswith(
            ("(i)", "(ii)", "(iii)", "(iv)")
        )
        for item in result.obligations
    )


# =========================================================
# TEST 9: PARENT MODAL WITHOUT CHILDREN
# =========================================================

def test_parent_modal_without_children():
    text = """
REs shall,

This is explanatory text without any listed requirement.
"""

    result = extract(text)

    assert len(inherited_obligations(result)) == 0


# =========================================================
# TEST 10: NO INHERITANCE WITHOUT PARENT
# =========================================================

def test_no_inheritance_without_parent():
    text = """
(a) maintain customer records;
(b) preserve identification documents.
"""

    result = extract(text)

    assert len(inherited_obligations(result)) == 0
