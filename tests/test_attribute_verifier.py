
from regintel.verification.attribute_verifier import (
    verify_attributes,
)


RBI_A = """
REs shall,
(a) maintain all necessary records of transactions
between the RE and the customer, both domestic and
international, for at least five years from the
date of transaction;
"""

RBI_B = """
REs shall,
(b) preserve the records pertaining to the
identification of the customers and their
addresses for at least five years after
the business relationship is ended;
"""

POLICY_2 = """
The bank shall maintain records of domestic
and international customer transactions for
at least five years from the transaction date.
"""

POLICY_3 = """
The bank shall preserve customer identification
and address records for at least five years
after the customer relationship ends.
"""


def check(regulation, policy):
    return verify_attributes(
        obligation_text=regulation,
        policy_text=policy,
        policy_section_id="test-section",
    )


def test_transaction_policy_matches():
    result = check(RBI_A, POLICY_2)

    assert result.status == "attributes_matched"
    assert not result.missing_attributes


def test_identification_policy_matches():
    result = check(RBI_B, POLICY_3)

    assert result.status == "attributes_matched"
    assert not result.missing_attributes


def test_transaction_obligation_wrong_policy():
    result = check(RBI_A, POLICY_3)

    assert result.status != "attributes_matched"


def test_identification_obligation_wrong_policy():
    result = check(RBI_B, POLICY_2)

    assert result.status != "attributes_matched"


def test_wrong_retention_trigger():
    policy = """
    The bank shall maintain domestic and
    international customer transactions
    for at least five years after the
    customer relationship ends.
    """

    result = check(RBI_A, policy)

    assert result.status == "partial_evidence"
    assert (
        "transaction_date_trigger"
        in result.missing_attributes
    )


def test_shorter_retention_duration():
    policy = """
    The bank shall maintain domestic and
    international customer transactions
    for at least three years from
    the transaction date.
    """

    result = check(RBI_A, policy)

    assert result.status == "partial_evidence"
    assert (
        "minimum_retention_duration"
        in result.missing_attributes
    )


def test_unrelated_policy():
    result = check(
        RBI_A,
        "The bank shall train employees annually.",
    )

    assert result.status == "scope_mismatch"
