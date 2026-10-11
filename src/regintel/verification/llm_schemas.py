
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AssessmentStatus(str, Enum):
    ATTRIBUTES_MATCHED = "attributes_matched"
    PARTIAL_EVIDENCE = "partial_evidence"
    POTENTIAL_CONFLICT = "potential_conflict"
    NEEDS_REVIEW = "needs_review"


class RequirementComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attribute: str
    regulatory_requirement: str
    policy_commitment: str | None
    assessment: str


class LLMVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposed_status: AssessmentStatus
    regulatory_quote: str
    policy_quote: str | None

    comparisons: list[RequirementComparison]

    missing_requirements: list[str]
    potential_conflicts: list[str]

    explanation: str


class ValidatedVerification(BaseModel):
    obligation_id: str
    policy_section_id: str

    status: AssessmentStatus

    regulatory_quote: str | None = None
    policy_quote: str | None = None

    comparisons: list[RequirementComparison] = Field(
        default_factory=list
    )

    missing_requirements: list[str] = Field(
        default_factory=list
    )

    potential_conflicts: list[str] = Field(
        default_factory=list
    )

    explanation: str
    validation_errors: list[str] = Field(
        default_factory=list
    )

    model_name: str
    requires_human_review: bool = True
