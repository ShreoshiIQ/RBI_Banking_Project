"""Conservative source-backed suggestions for human actor/applicability review."""

import re


ACTOR_PATTERN = re.compile(
    r"\b(?P<actor>regulated entities|REs|banks|banking companies|"
    r"ordering REs|beneficiary REs|intermediary REs|customers?)\s+"
    r"(?P<modal>shall|must|may)\b", re.IGNORECASE,
)
PASSIVE_PATTERN = re.compile(r"\b(?:shall|must|may)\s+(?:not\s+)?be\b", re.IGNORECASE)
CONDITION_PATTERN = re.compile(
    r"\b(?:if|unless|except|provided that|subject to|where|in case)\b", re.IGNORECASE,
)


def suggest_actor(item: dict, source_match: str) -> dict:
    evidence = item.get("evidence_quote", "")
    matches = list(ACTOR_PATTERN.finditer(evidence)) if source_match != "unmatched" else []
    actors = {match.group("actor").casefold() for match in matches}
    flags = []
    if str(item.get("clause_number")) in ("1", "2", "3"):
        flags.append("preliminary_or_applicability_text")
    if CONDITION_PATTERN.search(evidence):
        flags.append("conditional_scope_requires_review")
    if PASSIVE_PATTERN.search(evidence):
        flags.append("passive_voice_requires_review")
    if len(actors) > 1:
        flags.append("multiple_explicit_actors")
    suggestion = None
    support = None
    # Do not resolve passive duties, competing actors, or preliminary text.
    if len(actors) == 1 and not any(flag in flags for flag in (
        "preliminary_or_applicability_text", "passive_voice_requires_review",
    )):
        match = matches[0]
        suggestion = match.group("actor")
        support = {
            "quote": match.group(0), "start": match.start(), "end": match.end(),
            "offset_basis": "original_evidence_quote",
        }
    return {
        "suggested_actor": suggestion,
        "support": support,
        "method": "explicit_subject_before_modal_v1",
        "review_status": "pending",
        "applicability_status": "requires_human_review",
        "applicability_flags": flags,
    }
