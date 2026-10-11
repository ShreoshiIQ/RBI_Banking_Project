
"""
Regulatory Obligation Extractor - Version 4.1

Features:
- Mandatory obligation detection
- Prohibition detection
- Permission detection
- Exception handling
- Hierarchical obligation extraction
- Parent modal inheritance
- Nested Roman numeral details
- Long passage deferral
- Deleted clause exclusion
- Definitions section deferral
- Backward-compatible extraction API

Important:
This is a conservative rule-based extractor.
Extracted obligations are candidates requiring review.
"""

import re

from dataclasses import dataclass, field
from uuid import UUID

from regintel.schemas.obligation import (
    ObligationExtraction,
    ObligationType,
)


# =========================================================
# 1. REGULATORY MODAL PATTERNS
# =========================================================

PROHIBITION_PATTERN = re.compile(
    r"\b(?:shall not|must not|is prohibited from)\b",
    re.IGNORECASE,
)

MANDATORY_PATTERN = re.compile(
    r"\b(?:shall|must|is required to|are required to)\b",
    re.IGNORECASE,
)

PERMISSION_PATTERN = re.compile(
    r"\b(?:may|is permitted to|are permitted to)\b",
    re.IGNORECASE,
)

EXCEPTION_PATTERN = re.compile(
    r"\b(?:shall not apply|does not apply|"
    r"shall be exempt|is exempt from)\b",
    re.IGNORECASE,
)


# =========================================================
# 2. TEXT SEGMENTATION PATTERNS
# =========================================================

SUBCLAUSE_PATTERN = re.compile(
    r"(?m)^[ \t]*(?:\([a-z]\)|\([ivx]+\))[ \t]+",
    re.IGNORECASE,
)

SENTENCE_PATTERN = re.compile(
    r"(?<=[.!?])\s+(?=[A-Z])"
)

PARENT_MODAL_PATTERN = re.compile(
    r"\b(?:shall|must)\s*[,;:]?\s*$",
    re.IGNORECASE,
)

LETTERED_PATTERN = re.compile(
    r"^\(([a-z])\)\s+",
    re.IGNORECASE,
)

ROMAN_PATTERN = re.compile(
    r"^\((i|ii|iii|iv|v|vi|vii|viii|ix|x)\)\s+",
    re.IGNORECASE,
)

MAX_EVIDENCE_LENGTH = 600


# =========================================================
# 3. DATA STRUCTURES
# =========================================================

@dataclass
class DeferredPassage:
    source_clause_id: str
    clause_number: str
    text: str
    reason: str
    review_status: str = "pending"


@dataclass
class ExtractionResult:
    obligations: list[ObligationExtraction] = field(
        default_factory=list
    )

    deferred: list[DeferredPassage] = field(
        default_factory=list
    )


# =========================================================
# 4. TEXT SEGMENTATION
# =========================================================

def segment_regulatory_text(text: str) -> list[str]:
    """
    Split regulatory text into candidate segments.

    Recognizes:
    - Lettered subclauses: (a), (b), (c)
    - Roman subclauses: (i), (ii), (iii)
    - Sentence boundaries

    Preserves original wording within each segment.
    """

    normalized = text.replace("\r\n", "\n")

    normalized = SUBCLAUSE_PATTERN.sub(
        lambda match: (
            "\n<SEGMENT>\n" + match.group(0)
        ),
        normalized,
    )

    segments = []

    for block in normalized.split("<SEGMENT>"):

        for sentence in SENTENCE_PATTERN.split(block):

            cleaned = sentence.strip()

            if cleaned:
                segments.append(cleaned)

    return segments


# =========================================================
# 5. OBLIGATION CLASSIFICATION
# =========================================================

def classify_obligation(
    text: str,
) -> ObligationType | None:
    """
    Classify an explicit regulatory statement.

    Priority:
    1. Exception -> no direct obligation
    2. Prohibition
    3. Mandatory
    4. Permission
    """

    if EXCEPTION_PATTERN.search(text):
        return None

    if PROHIBITION_PATTERN.search(text):
        return ObligationType.PROHIBITION

    if MANDATORY_PATTERN.search(text):
        return ObligationType.MANDATORY

    if PERMISSION_PATTERN.search(text):
        return ObligationType.PERMISSION

    return None


# =========================================================
# 6. DEFERRED PASSAGE HELPER
# =========================================================

def _defer(
    result: ExtractionResult,
    source_clause_id: UUID,
    clause_number: str,
    text: str,
    reason: str,
) -> None:
    """
    Record a passage requiring further analysis.
    """

    result.deferred.append(
        DeferredPassage(
            source_clause_id=str(source_clause_id),
            clause_number=clause_number,
            text=text,
            reason=reason,
        )
    )


# =========================================================
# 7. OBLIGATION CREATION HELPER
# =========================================================

def _append_obligation(
    result: ExtractionResult,
    source_clause_id: UUID,
    clause_number: str,
    text: str,
    obligation_type: ObligationType,
    method: str,
) -> None:
    """
    Add a structured obligation candidate.
    """

    result.obligations.append(
        ObligationExtraction(
            source_clause_id=source_clause_id,
            clause_number=clause_number,
            actor="Unresolved",
            action=text,
            obligation_type=obligation_type,
            evidence_quote=text,
            confidence=0.5,
            extraction_method=method,
        )
    )


# =========================================================
# 8. ATTACH NESTED DETAILS
# =========================================================

def _attach_nested_details(
    obligation: ObligationExtraction,
    details: list[str],
) -> None:
    """
    Attach Roman numeral details to their parent obligation.

    Example:

    (e) maintain transaction information including:

        (i) transaction type
        (ii) transaction amount
        (iii) transaction date

    These details are attached to obligation (e)
    rather than extracted as independent obligations.
    """

    if not details:
        return

    suffix = "\n" + "\n".join(details)

    obligation.action += suffix
    obligation.evidence_quote += suffix


# =========================================================
# 9. MAIN EXTRACTION FUNCTION
# =========================================================

def extract_with_tracking(
    source_clause_id: UUID,
    clause_number: str,
    clause_text: str,
    status: str,
) -> ExtractionResult:
    """
    Extract obligations and track deferred passages.

    Supports:
    - Explicit obligations
    - Parent-child inheritance
    - Roman numeral details
    - Hierarchy boundaries
    """

    result = ExtractionResult()

    # -----------------------------------------------------
    # Skip deleted clauses
    # -----------------------------------------------------

    if status != "active":
        return result

    # -----------------------------------------------------
    # Defer definitions section
    # -----------------------------------------------------

    if clause_number == "3":

        _defer(
            result,
            source_clause_id,
            clause_number,
            clause_text,
            "definitions_section",
        )

        return result

    # -----------------------------------------------------
    # Segment the clause
    # -----------------------------------------------------

    segments = segment_regulatory_text(
        clause_text
    )

    parent_modal = None
    current_obligation = None
    nested_details = []

    # -----------------------------------------------------
    # Attach pending nested details
    # -----------------------------------------------------

    def flush_nested_details():

        nonlocal nested_details

        if current_obligation is not None:

            _attach_nested_details(
                current_obligation,
                nested_details,
            )

        nested_details = []

    # -----------------------------------------------------
    # Process segments
    # -----------------------------------------------------

    for segment in segments:

        # -------------------------------------------------
        # A. Parent modal detection
        # -------------------------------------------------

        if PARENT_MODAL_PATTERN.search(segment):

            flush_nested_details()

            parent_modal = segment
            current_obligation = None

            continue

        # -------------------------------------------------
        # B. Detect Roman numeral details
        # -------------------------------------------------

        roman_match = ROMAN_PATTERN.match(
            segment
        )

        lettered_match = LETTERED_PATTERN.match(
            segment
        )

        if (
            roman_match
            and current_obligation is not None
        ):

            nested_details.append(
                segment
            )

            continue

        # -------------------------------------------------
        # C. Detect inherited lettered obligations
        # -------------------------------------------------

        if (
            lettered_match
            and parent_modal is not None
        ):

            flush_nested_details()

            if len(segment) > MAX_EVIDENCE_LENGTH:

                _defer(
                    result,
                    source_clause_id,
                    clause_number,
                    segment,
                    "long_inherited_passage",
                )

                current_obligation = None

                continue

            evidence = (
                parent_modal
                + "\n"
                + segment
            )

            _append_obligation(
                result,
                source_clause_id,
                clause_number,
                evidence,
                ObligationType.MANDATORY,
                "rule_based_v4_1_inherited",
            )

            current_obligation = (
                result.obligations[-1]
            )

            continue

        # -------------------------------------------------
        # D. Stop hierarchy at unrelated text
        # -------------------------------------------------

        flush_nested_details()

        parent_modal = None
        current_obligation = None

        # -------------------------------------------------
        # E. Classify explicit obligations
        # -------------------------------------------------

        obligation_type = classify_obligation(
            segment
        )

        # -------------------------------------------------
        # F. Defer long passages
        # -------------------------------------------------

        if len(segment) > MAX_EVIDENCE_LENGTH:

            _defer(
                result,
                source_clause_id,
                clause_number,
                segment,
                "long_passage",
            )

            continue

        # -------------------------------------------------
        # G. Extract explicit obligation
        # -------------------------------------------------

        if obligation_type is not None:

            _append_obligation(
                result,
                source_clause_id,
                clause_number,
                segment,
                obligation_type,
                "rule_based_v4_1_explicit",
            )

            continue

        # -------------------------------------------------
        # H. Defer unclassified passages
        # -------------------------------------------------

        if EXCEPTION_PATTERN.search(segment):

            reason = (
                "exception_or_applicability"
            )

        else:

            reason = (
                "no_explicit_modal"
            )

        _defer(
            result,
            source_clause_id,
            clause_number,
            segment,
            reason,
        )

    # -----------------------------------------------------
    # Attach remaining nested details
    # -----------------------------------------------------

    flush_nested_details()

    return result


# =========================================================
# 10. BACKWARD-COMPATIBLE EXTRACTION FUNCTION
# =========================================================

def extract_obligations(
    source_clause_id: UUID,
    clause_number: str,
    clause_text: str,
    status: str,
) -> list[ObligationExtraction]:
    """
    Maintain compatibility with existing tests and callers.
    """

    return extract_with_tracking(
        source_clause_id=source_clause_id,
        clause_number=clause_number,
        clause_text=clause_text,
        status=status,
    ).obligations
