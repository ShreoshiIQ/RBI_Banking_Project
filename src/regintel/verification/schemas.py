
"""
Structured compliance verification results.

These are evidence assessments, not legal certifications.
"""

from enum import Enum

from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    SUPPORTED = "supported"
    CONFLICTING = "conflicting"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NEEDS_REVIEW = "needs_review"


class RetentionRequirement(BaseModel):
    years: int = Field(gt=0)
    minimum_required: bool = True
    evidence_quote: str


class VerificationResult(BaseModel):
    obligation_id: str
    policy_section_id: str

    status: VerificationStatus

    regulatory_requirement: (
        RetentionRequirement | None
    ) = None

    policy_requirement: (
        RetentionRequirement | None
    ) = None

    explanation: str

    regulatory_evidence: str
    policy_evidence: str

    verification_method: str = (
        "deterministic_retention_v1"
    )

    requires_human_review: bool = True
