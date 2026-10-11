from datetime import date

import pytest

from regintel.agents.supervisor import RemediationSupervisor
from regintel.applicability.engine import determine, resolve
from regintel.prioritization.risk import load_risk_model

PROFILE = {"profile_id": "bank", "excluded_entity_types": ["payments_bank"],
           "features": {"ppi_issuance": False, "customer_accounts_and_kyc": True}}


def src(title, **extra):
    return {"title": title, "regulator": "RBI", "content_hash": title[:8], **extra}


@pytest.mark.parametrize(("source", "decisions", "status", "rule"), [
    (src("Old KYC", status="historical_withdrawal_marker"), {}, "not_applicable", "withdrawn_source"),
    (src("SEBI CSCRF", applicability={"profile_id": "broker"}), {}, "not_applicable", "outside_entity_perimeter"),
    (src("Reserve Bank of India (Payments Banks - Capital)"), {}, "presumed_not_applicable", "title_names_only_excluded_entity_types"),
    (src("Reserve Bank of India (Commercial Banks - Cyber)"), {}, "presumed_applicable", "title_names_commercial_banks"),
    (src("Master Directions on Prepaid Payment Instruments"), {}, "presumed_not_applicable", "profile_feature_absent"),
    (src("Master Direction - KYC 2016"), {}, "presumed_applicable", "profile_feature_present"),
    (src("Foreign Exchange Management"), {}, "undetermined", "no_rule_matched"),
])
def test_precedence_rules(source, decisions, status, rule):
    result = determine(source, PROFILE, decisions)
    assert (result["status"], result["basis"]["rule"]) == (status, rule)


def test_officer_decision_overrides_rules_but_not_withdrawal():
    decision = {"Master D": {"decision": "not_applicable", "reviewer": "officer", "cited_clause_numbers": ["2"]}}
    assert determine(src("Master Direction - KYC 2016"), PROFILE, decision)["status"] == "not_applicable"
    withdrawn = src("Master Direction - KYC 2016", status="historical_withdrawal_marker")
    approve = {"Master D": {"decision": "applicable", "reviewer": "officer"}}
    assert determine(withdrawn, PROFILE, approve)["basis"]["rule"] == "withdrawn_source"
    assert determine(src("Master Direction - KYC 2016"), PROFILE, approve)["status"] == "applicable"


def test_resolve_ignores_withdrawn_and_ambiguous():
    determinations = [determine(s, PROFILE, {}) for s in (
        src("Master Direction - KYC 2016"), src("KYC 2009", status="historical_withdrawal_marker"))]
    assert resolve("RBI KYC Section 46(f)", determinations)["title"] == "Master Direction - KYC 2016"
    assert resolve("Unrelated control", determinations) is None


def report(reference):
    return {"report_id": f"r-{reference[:3]}", "regulatory_reference": reference, "review_status": "pending_review",
            "findings": [{"requirement": "Keep records", "status": "missing", "explanation": "Absent.", "evidence": []}]}


def test_supervisor_excludes_non_applicable_and_flags_presumed():
    determinations = [determine(s, PROFILE, {}) for s in (
        src("Master Direction - KYC 2016"), src("Master Directions on Prepaid Payment Instruments"))]
    register = RemediationSupervisor(risk_model=load_risk_model(), applicability=determinations).run(
        reports=[report("RBI KYC Section 46(f)"), report("PPI Prepaid Payment clause 9"), report("Unmapped reference")],
        as_of=date(2026, 10, 11))
    assert [e["applicability"]["status"] for e in register["excluded_not_applicable"]] == ["presumed_not_applicable"]
    statuses = {i["reference"]: i["applicability"]["status"] for i in register["items"]}
    assert statuses == {"RBI KYC Section 46(f)": "presumed_applicable", "Unmapped reference": "undetermined"}
    assert all(any("applicability not confirmed" in r for r in q["reasons"]) for q in register["human_queue"])
