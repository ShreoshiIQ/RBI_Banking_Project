
"""
Attribute-based verification for RBI Section 46(a)-(f).

Version: 1.0
Scope: synthetic KYC policy demonstration.

Results are evidence assessments, not legal
compliance certifications.
"""

import re
from dataclasses import dataclass, asdict

from regintel.verification.retention_verifier import (
    extract_retention_requirement,
)


@dataclass
class AttributeResult:
    obligation: str
    policy_section_id: str
    status: str
    matched_attributes: list[str]
    missing_attributes: list[str]
    explanation: str
    regulatory_evidence: str
    policy_evidence: str
    requires_human_review: bool = True

    def to_dict(self):
        return asdict(self)


REQUIREMENTS = {
    "a": {
        "scope": r"\btransactions?\b",
        "attributes": {
            "domestic_transactions": r"\bdomestic\b",
            "international_transactions": r"\binternational\b",
            "transaction_date_trigger": (
                r"(?:from\s+(?:the\s+)?"
                r"(?:transaction\s+date|date\s+of\s+transaction))"
            ),
        },
        "retention_years": 5,
    },
    "b": {
        "scope": r"\bidentification\b",
        "attributes": {
            "customer_identification": r"\bidentification\b",
            "address_records": r"\baddresses?\b",
            "relationship_end_trigger": (
                r"(?:after\s+(?:the\s+)?"
                r"(?:customer|business)\s+relationship\s+ends?"
                r"|after\s+(?:the\s+)?"
                r"(?:customer|business)\s+relationship\s+"
                r"is\s+ended)"
            ),
        },
        "retention_years": 5,
    },
    "c": {
        "scope": r"\b(?:authorit(?:y|ies)|regulator)\b",
        "attributes": {
            "identification_records": r"\bidentification\b",
            "transaction_data": (
                r"\btransaction\s+(?:data|records?)\b"
            ),
            "competent_authorities": (
                r"\bcompetent\s+authorit(?:y|ies)\b"
            ),
            "prompt_access": (
                r"\b(?:promptly|swiftly|quickly|immediately)\b"
            ),
            "upon_request": r"\bupon\s+request\b",
        },
    },
    "d": {
        "scope": r"\b(?:transaction|record)\b",
        "attributes": {
            "record_keeping_system": (
                r"\bsystem\b"
            ),
            "transaction_records": (
                r"\btransactions?\b"
            ),
            "pml_rule_3": (
                r"\b(?:pml\s+rule\s*3|"
                r"rule\s*3\s+of\s+(?:the\s+)?"
                r"prevention\s+of\s+money\s+laundering)\b"
            ),
        },
    },
    "e": {
        "scope": r"\btransaction\b",
        "attributes": {
            "transaction_nature": (
                r"\b(?:type|nature)\b"
            ),
            "amount": r"\bamount\b",
            "currency": r"\bcurrency\b",
            "transaction_date": r"\bdate\b",
            "parties": r"\bparties\b",
            "pml_rule_3": (
                r"\b(?:pml\s+rule\s*3|"
                r"rule\s*3\s+of\s+(?:the\s+)?"
                r"prevention\s+of\s+money\s+laundering)\b"
            ),
        },
    },
    "f": {
        "scope": r"\b(?:account|retriev)\w*\b",
        "attributes": {
            "account_information": (
                r"\baccount\s+information\b"
            ),
            "retrieval_system": (
                r"\bsystem\b"
            ),
            "retrieval_capability": (
                r"\bretriev\w*\b"
            ),
            "efficient_retrieval": (
                r"\b(?:quickly|easily|efficiently|promptly)\b"
            ),
            "authority_request_access": (
                r"\b(?:competent\s+authorit(?:y|ies)|"
                r"upon\s+request)\b"
            ),
        },
    },
}


def get_obligation_suffix(text: str) -> str | None:
    match = re.search(
        r"\(([a-f])\)",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).lower() if match else None


def matches(pattern: str, text: str) -> bool:
    return bool(re.search(pattern, text, re.IGNORECASE))


def verify_attributes(
    obligation_text: str,
    policy_text: str,
    policy_section_id: str,
) -> AttributeResult:

    suffix = get_obligation_suffix(obligation_text)

    if suffix not in REQUIREMENTS:
        return AttributeResult(
            obligation="unknown",
            policy_section_id=policy_section_id,
            status="needs_review",
            matched_attributes=[],
            missing_attributes=[],
            explanation="Unsupported obligation identifier.",
            regulatory_evidence=obligation_text,
            policy_evidence=policy_text,
        )

    requirement = REQUIREMENTS[suffix]

    # Require a clear, operative policy statement.
    if not matches(
        r"\b(?:shall|must|will|required\s+to)\b",
        policy_text,
    ):
        return AttributeResult(
            obligation=f"46({suffix})",
            policy_section_id=policy_section_id,
            status="insufficient_evidence",
            matched_attributes=[],
            missing_attributes=list(
                requirement["attributes"].keys()
            ),
            explanation=(
                "No explicit operative policy commitment "
                "was identified."
            ),
            regulatory_evidence=obligation_text,
            policy_evidence=policy_text,
        )

    if not matches(requirement["scope"], policy_text):
        return AttributeResult(
            obligation=f"46({suffix})",
            policy_section_id=policy_section_id,
            status="scope_mismatch",
            matched_attributes=[],
            missing_attributes=list(
                requirement["attributes"].keys()
            ),
            explanation=(
                "The policy does not establish the "
                "required record or activity scope."
            ),
            regulatory_evidence=obligation_text,
            policy_evidence=policy_text,
        )

    matched = []
    missing = []

    for name, pattern in requirement["attributes"].items():
        if matches(pattern, policy_text):
            matched.append(name)
        else:
            missing.append(name)

    if "retention_years" in requirement:
        regulatory_duration = extract_retention_requirement(
            obligation_text
        )
        policy_duration = extract_retention_requirement(
            policy_text
        )

        if (
            regulatory_duration is None
            or policy_duration is None
        ):
            missing.append("minimum_retention_duration")
        elif (
            policy_duration.years
            >= regulatory_duration.years
        ):
            matched.append("minimum_retention_duration")
        else:
            missing.append("minimum_retention_duration")

    if not missing:
        status = "attributes_matched"
        explanation = (
            "All attributes checked by this limited "
            "rule set were found in the policy. "
            "This is not a final compliance determination."
        )
    else:
        status = "partial_evidence"
        explanation = (
            "Some required attributes were not "
            "established by this policy section."
        )

    return AttributeResult(
        obligation=f"46({suffix})",
        policy_section_id=policy_section_id,
        status=status,
        matched_attributes=matched,
        missing_attributes=missing,
        explanation=explanation,
        regulatory_evidence=obligation_text,
        policy_evidence=policy_text,
    )
