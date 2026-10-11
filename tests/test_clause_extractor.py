
from regintel.ingestion.clause_extractor import (
    extract_clauses,
    is_next_clause,
)


def test_normal_sequence():
    assert is_next_clause("4", "5")
    assert is_next_clause("5B", "6")


def test_amendment_sequence():
    assert is_next_clause("5", "5A")
    assert is_next_clause("5A", "5B")


def test_invalid_sequence():
    assert not is_next_clause("5", "7")
    assert not is_next_clause("5A", "5A")

def test_section_without_base_number():
    assert is_next_clause("32", "33A")
    assert is_next_clause("33A", "33B")
    assert is_next_clause("33B", "34")

def test_deleted_section():
    pages = [
        {
            "page_number": 1,
            "text": (
                "CHAPTER I\n"
                "1. Short Title and Commencement.\n"
                "These Directions shall apply as specified.\n"
                "2. 54Deleted\n"
                "3. Applicability\n"
                "These Directions apply to regulated entities."
            ),
        }
    ]

    clauses = extract_clauses(pages)

    assert [c.clause_number for c in clauses] == [
        "1", "2", "3"
    ]
    assert clauses[1].status == "deleted"

def test_heading_without_same_line_text():
    pages = [
        {
            "page_number": 1,
            "text": (
                "CHAPTER I\n"
                "1. Collection of Account Payee Cheques\n"
                "Account payee cheques shall be handled "
                "according to applicable requirements.\n"
                "2.\n"
                "(a) A Unique Customer Identification "
                "Code shall be allotted to customers."
            ),
        }
    ]

    clauses = extract_clauses(pages)

    assert len(clauses) == 2
    assert clauses[0].clause_number == "1"
    assert clauses[1].clause_number == "2"
    assert "(a) A Unique Customer" in clauses[1].clause_text

def test_annexure_not_included_in_main_clause():
    pages = [
        {
            "page_number": 1,
            "text": (
                "CHAPTER I\n"
                "1. Regulatory requirement\n"
                "Banks shall comply with the requirements "
                "specified in this direction."
            ),
        },
        {
            "page_number": 2,
            "text": (
                "Annex I\n"
                "Digital KYC Process\n"
                "A. The regulated entity shall develop "
                "an application for digital KYC."
            ),
        },
    ]

    clauses = extract_clauses(pages)

    assert len(clauses) == 1
    assert clauses[0].clause_number == "1"
    assert clauses[0].end_page == 1
    assert "Digital KYC" not in clauses[0].clause_text