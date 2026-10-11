
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SectionCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    exact_quote: str
    supported_requirement: str


class RequirementFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement: str
    assessment: Literal[
        "supported",
        "partial",
        "missing",
        "potential_conflict",
    ]
    explanation: str
    citations: list[SectionCitation] = Field(
        default_factory=list
    )


class MultiSectionAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposed_status: Literal[
        "attributes_matched",
        "partial_evidence",
        "potential_conflict",
        "needs_review",
    ]
    findings: list[RequirementFinding] = Field(
        min_length=1
    )
    missing_requirements: list[str]
    potential_conflicts: list[str]
    explanation: str
