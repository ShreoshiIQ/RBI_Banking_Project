
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GapStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    MISSING = "missing"
    POTENTIAL_CONFLICT = "potential_conflict"


class ReviewStatus(str, Enum):
    PENDING = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    section_number: str
    section_title: str
    quote: str
    requirement: str


class GapFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement: str
    status: GapStatus
    explanation: str
    evidence: list[EvidenceReference] = Field(default_factory=list)
    suggested_action: str


class GapSummary(BaseModel):
    total: int
    supported: int
    partial: int
    missing: int
    potential_conflicts: int


class RegulatoryGapReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    regulatory_reference: str
    regulatory_text: str | None = None

    assessment_status: str
    findings: list[GapFinding]
    summary: GapSummary

    source_policy_sections: list[str]
    missing_requirements: list[str]
    potential_conflicts: list[str]

    overall_explanation: str

    review_status: ReviewStatus = ReviewStatus.PENDING
    requires_human_review: Literal[True] = True

    source_cache_status: str | None = None
