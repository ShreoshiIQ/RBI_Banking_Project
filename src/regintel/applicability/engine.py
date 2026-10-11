"""Deterministic applicability determination with explicit precedence and basis.

Precedence: withdrawn source > outside the entity's regulatory perimeter >
officer decision > title entity-type rule > profile feature rule > undetermined.
Only an officer decision yields "applicable"; machine rules yield "presumed_*".
"""

import json
from pathlib import Path

APPLICABLE = "applicable"
NOT_APPLICABLE = "not_applicable"
PRESUMED_APPLICABLE = "presumed_applicable"
PRESUMED_NOT_APPLICABLE = "presumed_not_applicable"
UNDETERMINED = "undetermined"
EXCLUDED = {NOT_APPLICABLE, PRESUMED_NOT_APPLICABLE}

# Entity-type phrases in RBI titles, mapped to profile entity types.
ENTITY_PHRASES = {
    "small finance bank": "small_finance_bank", "payments bank": "payments_bank",
    "local area bank": "local_area_bank", "regional rural bank": "regional_rural_bank",
    "non-banking financial": "NBFC", "nbfc": "NBFC", "all india financial institution": "AIFI",
    "aifi": "AIFI", "co-operative bank": "cooperative_bank", "urban co-operative": "cooperative_bank",
}
ALWAYS_EXCLUDED = {"AIFI", "cooperative_bank"}
# Instrument keywords mapped to profile feature flags.
FEATURE_KEYWORDS = {
    "prepaid payment": "ppi_issuance", "credit card": "credit_and_debit_cards", "debit card": "credit_and_debit_cards",
    "outsourc": "outsourced_it_services", "digital payment": "digital_payments",
    "know your customer": "customer_accounts_and_kyc", "kyc": "customer_accounts_and_kyc",
    "foreign bank": "foreign_bank_branch",
}


def title_rule(title: str, profile: dict) -> tuple[str, dict] | None:
    lowered = title.casefold()
    named = sorted({kind for phrase, kind in ENTITY_PHRASES.items() if phrase in lowered})
    if "commercial bank" in lowered:
        return PRESUMED_APPLICABLE, {"rule": "title_names_commercial_banks"}
    excluded = set(profile.get("excluded_entity_types", [])) | ALWAYS_EXCLUDED
    if named and set(named) <= excluded:
        return PRESUMED_NOT_APPLICABLE, {"rule": "title_names_only_excluded_entity_types", "entity_types": named}
    return None


def feature_rule(title: str, profile: dict) -> tuple[str, dict] | None:
    lowered = title.casefold()
    features = profile.get("features", {})
    hits = sorted({f for keyword, f in FEATURE_KEYWORDS.items() if keyword in lowered and f in features})
    if not hits:
        return None
    if all(features[f] is False for f in hits):
        return PRESUMED_NOT_APPLICABLE, {"rule": "profile_feature_absent", "features": hits}
    if any(features[f] is True for f in hits):
        return PRESUMED_APPLICABLE, {"rule": "profile_feature_present", "features": [f for f in hits if features[f]]}
    return None


def determine(source: dict, profile: dict, decisions: dict[str, dict]) -> dict:
    """Determination for one registry source."""
    title = source.get("title", "")
    status = source.get("source_status") or source.get("status")
    status = status.get("status") if isinstance(status, dict) else status
    result = {"title": title, "regulator": source.get("regulator"), "content_hash": source.get("content_hash")}
    if status == "historical_withdrawal_marker":
        return {**result, "status": NOT_APPLICABLE, "basis": {"rule": "withdrawn_source", "note": "Historical record only."}}
    owner = (source.get("applicability") or {}).get("profile_id")
    if owner and profile.get("profile_id") and owner != profile["profile_id"]:
        return {**result, "status": NOT_APPLICABLE, "basis": {"rule": "outside_entity_perimeter", "source_profile": owner}}
    decision = decisions.get(source.get("content_hash") or "")
    if decision and decision.get("decision") not in (None, "pending"):
        mapped = {"applicable": APPLICABLE, "not_applicable": NOT_APPLICABLE, "conditional": APPLICABLE}[decision["decision"]]
        return {**result, "status": mapped, "basis": {"rule": "officer_decision", "reviewer": decision["reviewer"],
                                                      "conditions": decision.get("conditions") or None,
                                                      "cited_clause_numbers": decision.get("cited_clause_numbers", [])}}
    for rule in (title_rule, feature_rule):
        found = rule(title, profile)
        if found:
            return {**result, "status": found[0], "basis": found[1]}
    return {**result, "status": UNDETERMINED, "basis": {"rule": "no_rule_matched"}}


def load_context(root: Path) -> tuple[dict, list[dict], dict[str, dict]]:
    profile = json.loads((root / "data/metadata/demo_institution_profile.json").read_text(encoding="utf-8"))
    profile.setdefault("profile_id", "fictional-commercial-bank-demo")
    sources = json.loads((root / "data/metadata/phase1_registry_verified.json").read_text(encoding="utf-8"))["sources"]
    corpora = root / "data/metadata/phase3_official_corpora_verified.json"
    if corpora.exists():
        known = {s.get("title") for s in sources}
        sources += [s for c in json.loads(corpora.read_text(encoding="utf-8"))["corpora"] for s in c["sources"] if s.get("title") not in known]
    decisions_path = root / "data/processed/expansion_reviews/applicability_decisions.json"
    decisions = {}
    if decisions_path.exists():
        raw = json.loads(decisions_path.read_text(encoding="utf-8"))
        rows = raw.get("decisions", []) if isinstance(raw, dict) else []
        decisions = {row["content_hash"]: row for row in rows if row.get("content_hash")}
    return profile, sources, decisions


def determine_all(root: Path) -> list[dict]:
    profile, sources, decisions = load_context(root)
    return [determine(s, profile, decisions) for s in sources]


def resolve(reference: str, determinations: list[dict]) -> dict | None:
    """Match a gap's regulatory reference to one current source by instrument keywords."""
    lowered = reference.casefold()
    keys = {kw for kw in FEATURE_KEYWORDS if kw in lowered}
    current = [d for d in determinations if d["basis"].get("rule") != "withdrawn_source"]
    matches = [d for d in current if keys and any(k in d["title"].casefold() for k in keys)]
    return matches[0] if len(matches) == 1 else None
