"""Deterministic contradiction and divergence detectors for a pair of provisions.

Outputs are candidates for legal review, never confirmed conflicts.
"""

import re

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "twelve": 12, "fifteen": 15, "eighteen": 18, "twenty": 20, "twenty four": 24, "twenty-four": 24,
    "thirty": 30, "forty five": 45, "forty-five": 45, "sixty": 60, "ninety": 90,
}
UNIT_HOURS = {"hour": 1, "day": 24, "working day": 24, "business day": 24, "week": 168, "month": 730, "year": 8760}
QUANTITY = re.compile(
    r"\b(?P<num>\d+(?:\.\d+)?|" + "|".join(sorted(map(re.escape, NUMBER_WORDS), key=len, reverse=True)) + r")"
    r"(?:\s*\(\s*\d+\s*\))?\s*(?P<unit>working days?|business days?|hours?|days?|weeks?|months?|years?)\b",
    re.IGNORECASE,
)
ACTION_CLASSES = {
    "reporting": r"\b(?:report|notif|inform|intimat|submit)\w*",
    "retention": r"\b(?:retain|retention|preserv|maintain(?:ed)? (?:the )?records?|store[ds]?|kept)\w*",
    "review": r"\b(?:review|audit|assess|test|evaluat)\w*",
    "resolution": r"\b(?:resolv|redress|respond|restor|recover)\w*",
}
NEGATIVE = re.compile(r"\b(?:shall not|must not|should not|not be permitted|not permitted|prohibited|no \w+ shall)\b", re.IGNORECASE)
POSITIVE = re.compile(r"\b(?:shall|must|required to|mandatory)\b", re.IGNORECASE)
RETAIN = re.compile(r"\b(?:retain|retention|preserv\w*|maintain\w* records?)\b", re.IGNORECASE)
ERASE = re.compile(r"\b(?:delet\w*|eras\w*|purg\w*|destroy\w*|dispos\w* of)\b", re.IGNORECASE)
SUBJECTS = re.compile(r"\b(?:logs?|records?|data|information|documents?)\b", re.IGNORECASE)


def quantities(text: str) -> dict[str, list[dict]]:
    """Durations keyed by the action class found in the same sentence."""
    found = {}
    for sentence in re.split(r"(?<=[.;])\s+", text):
        classes = [name for name, pattern in ACTION_CLASSES.items() if re.search(pattern, sentence, re.IGNORECASE)]
        if len(classes) != 1:  # ambiguous or no action context: do not guess
            continue
        for match in QUANTITY.finditer(sentence):
            raw = match["num"].lower()
            value = float(NUMBER_WORDS.get(raw, raw))
            unit = re.sub(r"s$", "", match["unit"].lower())
            found.setdefault(classes[0], []).append({"text": match.group(0), "hours": value * UNIT_HOURS[unit]})
    return found


PREDICATE_WORDS = 8
FILLER = {"the", "a", "an", "any", "of", "to", "and", "or", "be", "by", "with", "for", "in", "on", "its", "their", "such", "other", "all", "also"}


def _predicates(text: str, modal: re.Pattern) -> list[set[str]]:
    """Content words of the clause that follows each modal verb."""
    out = []
    for match in modal.finditer(text):
        tail = re.findall(r"[a-z]+", text[match.end():].lower())[:PREDICATE_WORDS]
        out.append({w for w in tail if w not in FILLER and len(w) > 2})
    return out


def _polarity_overlap(negative_text: str, positive_text: str) -> list[str]:
    """Shared predicate words when one text prohibits what the other requires."""
    negatives = _predicates(negative_text, NEGATIVE)
    positives = _predicates(re.sub(NEGATIVE, " ", positive_text), POSITIVE)
    if NEGATIVE.search(positive_text) and not positives:
        return []
    best = max((n & p for n in negatives for p in positives), key=len, default=set())
    return sorted(best) if len(best) >= 2 else []


def detect(a: dict, b: dict) -> list[dict]:
    """Compare two provisions from different documents; return candidate findings."""
    findings = []
    qa, qb = quantities(a["text"]), quantities(b["text"])
    for action in sorted(set(qa) & set(qb)):
        va = {q["hours"] for q in qa[action]}
        vb = {q["hours"] for q in qb[action]}
        if len(va) == 1 and len(vb) == 1 and va != vb:
            ha, hb = va.pop(), vb.pop()
            stricter = a if (ha < hb) != (action == "retention") else b
            findings.append({
                "type": "quantitative_divergence", "action": action,
                "values": {a["provision_id"]: qa[action][0]["text"], b["provision_id"]: qb[action][0]["text"]},
                "explanation": f"Different {action} periods for related provisions. Where both apply, the stricter requirement ({stricter['provision_id']}) normally governs; confirm scope and applicability.",
                "severity": "medium",
            })
    for neg, pos in ((a, b), (b, a)):
        shared = _polarity_overlap(neg["text"], pos["text"])
        if shared:
            findings.append({
                "type": "polarity_conflict", "shared_terms": shared,
                "explanation": "One provision prohibits an action that the related provision requires. This may be a genuine conflict or a difference in scope or exception.",
                "severity": "high",
            })
            break
    ra, rb = bool(RETAIN.search(a["text"])), bool(RETAIN.search(b["text"]))
    ea, eb = bool(ERASE.search(a["text"])), bool(ERASE.search(b["text"]))
    if ((ra and eb and not ea) or (rb and ea and not eb)) and SUBJECTS.search(a["text"]) and SUBJECTS.search(b["text"]):
        findings.append({
            "type": "retention_erasure_tension",
            "explanation": "One provision requires retaining records or data that the related provision requires deleting. Confirm which data categories and periods each covers.",
            "severity": "high",
        })
    return findings
