"""Deterministic, explainable gap prioritisation; orders review work, not a legal risk rating."""

import hashlib
import json
from datetime import date
from pathlib import Path

DEFAULT_MODEL = Path(__file__).with_name("risk_model_v1.json")
WEIGHT_KEYS = {"severity", "obligation", "domain", "deadline", "evidence_uncertainty"}


def load_risk_model(path: Path = DEFAULT_MODEL) -> dict:
    raw = Path(path).read_bytes()
    model = json.loads(raw)
    weights = model["weights"]
    if set(weights) != WEIGHT_KEYS or abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("Risk weights must cover every factor and sum to 1")
    if any(not 0 <= value <= 1 for table in ("status_severity", "control_severity", "obligation_type_weight", "domain_criticality", "deadline_factor") for value in model[table].values()):
        raise ValueError("Risk factors must lie between 0 and 1")
    thresholds = [threshold for threshold, _ in model["bands"]]
    if thresholds != sorted(thresholds, reverse=True) or thresholds[-1] != 0:
        raise ValueError("Bands must be descending and end at 0")
    return {**model, "sha256": hashlib.sha256(raw).hexdigest()}


def gaps_from_report(report: dict) -> list[dict]:
    """Normalise unsupported findings of a stored gap report into gap items."""
    gaps = []
    for index, finding in enumerate(report["findings"]):
        if finding["status"] == "supported":
            continue
        gaps.append({
            "gap_id": f"{report['report_id']}#{index}",
            "source": {"kind": "gap_report", "report_id": report["report_id"], "finding_index": index},
            "reference": report["regulatory_reference"],
            "requirement": finding["requirement"],
            "status": finding["status"],
            "explanation": finding["explanation"],
            "cited_section_ids": [e["section_id"] for e in finding.get("evidence", [])],
            "regulatory_text": report.get("regulatory_text"),
            "review_status": report.get("review_status", "pending_review"),
        })
    return gaps


def gaps_from_control_test(result: dict, *, test_id: str, reference: str, requirement: str) -> list[dict]:
    """Normalise a deterministic control-test result; passing tests yield no gap."""
    if result["classification"] == "test_passed":
        return []
    return [{
        "gap_id": f"{test_id}#control",
        "source": {"kind": "control_test", "test_id": test_id, "synthetic": result.get("synthetic", False)},
        "reference": reference,
        "requirement": requirement,
        "control_classification": result["classification"],
        "explanation": f"Control test {result['control']} classified as {result['classification']}; {len(result.get('failed_records', []))} failed records.",
        "cited_section_ids": [],
        "evidence_references": result.get("evidence_references", []),
        "review_status": "pending_review",
    }]


def infer_domain(gap: dict, model: dict) -> str:
    if gap.get("domain"):
        return gap["domain"]
    text = f"{gap.get('reference', '')} {gap['requirement']}".casefold()
    for domain, keywords in model["domain_keywords"].items():
        if any(keyword in text for keyword in keywords):
            return domain
    return "default"


def deadline_bucket(effective_date: str | None, as_of: date) -> str:
    if not effective_date:
        return "unknown"
    days = (date.fromisoformat(effective_date) - as_of).days
    return "overdue" if days < 0 else "within_30_days" if days <= 30 else "within_90_days" if days <= 90 else "later"


def score_gap(gap: dict, model: dict, *, as_of: date) -> dict:
    severities = []
    if "status" in gap:
        severities.append(model["status_severity"][gap["status"]])
    if "control_classification" in gap:
        severities.append(model["control_severity"][gap["control_classification"]])
    if not severities:
        raise ValueError(f"Gap {gap['gap_id']} has neither a finding status nor a control classification")
    domain = infer_domain(gap, model)
    bucket = deadline_bucket(gap.get("effective_date"), as_of)
    cited = gap.get("cited_section_ids") or gap.get("evidence_references")
    factors = {
        "severity": max(severities),
        "obligation": model["obligation_type_weight"][gap.get("obligation_type") or "unknown"],
        "domain": model["domain_criticality"].get(domain, model["domain_criticality"]["default"]),
        "deadline": model["deadline_factor"][bucket],
        # Gaps with no cited evidence are harder to verify, so they are reviewed earlier.
        "evidence_uncertainty": 0.3 if cited else 1.0,
    }
    if factors["severity"] == 0:
        return {**gap, "risk": {"score": 0.0, "band": "none", "factors": factors, "domain": domain, "deadline_bucket": bucket}}
    contributions = {name: round(model["weights"][name] * value * 100, 2) for name, value in factors.items()}
    score = round(sum(contributions.values()), 1)
    band = next(label for threshold, label in model["bands"] if score >= threshold)
    return {**gap, "risk": {
        "score": score, "band": band, "factors": factors, "contributions": contributions,
        "domain": domain, "deadline_bucket": bucket, "target_days": model["target_days"][band],
        "model_version": model["version"],
    }}


def prioritise(gaps: list[dict], model: dict, *, as_of: date) -> list[dict]:
    scored = [score_gap(gap, model, as_of=as_of) for gap in gaps]
    return sorted((g for g in scored if g["risk"]["band"] != "none"), key=lambda g: (-g["risk"]["score"], g["gap_id"]))
