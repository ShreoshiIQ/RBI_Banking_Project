
import re
from dataclasses import dataclass, field


AMENDMENT_PATTERN = re.compile(
    r"\b(?:Amended|Inserted|Substituted|Deleted)\s+vide\b",
    re.IGNORECASE,
)

HISTORICAL_PATTERN = re.compile(
    r"\b(?:Deleted portion read as|"
    r"Prior to amendment|"
    r"Earlier provision read as)\b",
    re.IGNORECASE,
)

MODAL_PATTERN = re.compile(
    r"\b(?:shall|must|may|required to|permitted to)\b",
    re.IGNORECASE,
)

INCOMPLETE_PATTERN = re.compile(
    r"\b(?:shall|must|may|shall not|must not)\s*"
    r"[:;,]?\s*$",
    re.IGNORECASE,
)


@dataclass
class QualityResult:
    status: str = "candidate"
    reasons: list[str] = field(default_factory=list)


def evaluate_obligation(text: str) -> QualityResult:
    reasons = []

    if HISTORICAL_PATTERN.search(text):
        reasons.append("historical_or_deleted_text")

    if AMENDMENT_PATTERN.search(text):
        reasons.append("contains_amendment_metadata")

    if INCOMPLETE_PATTERN.search(text):
        reasons.append("incomplete_obligation")

    if len(MODAL_PATTERN.findall(text)) > 1:
        reasons.append("multiple_modal_keywords")

    if len(text.strip()) < 25:
        reasons.append("very_short_evidence")

    return QualityResult(
        status="needs_review" if reasons else "candidate",
        reasons=reasons,
    )
