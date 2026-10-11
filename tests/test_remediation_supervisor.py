import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from regintel.agents.supervisor import RemediationSupervisor
from regintel.api.app import create_app
from regintel.api.dependencies import get_db
from regintel.api.routes.auth import get_current_user
from regintel.models.user import UserRecord
from regintel.prioritization.risk import (
    gaps_from_control_test,
    load_risk_model,
    prioritise,
    score_gap,
)
from regintel.remediation.planner import plan_remediation, validate_llm_plan

AS_OF = date(2026, 10, 11)


@pytest.fixture(scope="module")
def model():
    return load_risk_model()


def report():
    return {
        "report_id": "gap-test", "regulatory_reference": "RBI KYC Section 46(f)", "review_status": "pending_review",
        "findings": [
            {"requirement": "Maintenance and preservation of account information", "status": "missing", "explanation": "Not addressed.", "evidence": []},
            {"requirement": "Retrieval of data easily and quickly", "status": "partial", "explanation": "Partly addressed.",
             "evidence": [{"section_id": "sec-6", "section_number": "6", "section_title": "RECORD RETRIEVAL", "quote": "q", "requirement": "r"}]},
            {"requirement": "Retrieval upon request by competent authorities", "status": "supported", "explanation": "Covered.",
             "evidence": [{"section_id": "sec-4", "section_number": "4", "section_title": "T", "quote": "q", "requirement": "r"}]},
        ],
    }


def test_risk_model_validates_weights(tmp_path, model):
    broken = {k: v for k, v in model.items() if k != "sha256"}
    broken["weights"] = {**broken["weights"], "severity": 0.9}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(broken))
    with pytest.raises(ValueError, match="sum to 1"):
        load_risk_model(path)


def test_scoring_is_deterministic_explainable_and_ordered(model):
    from regintel.prioritization.risk import gaps_from_report
    gaps = gaps_from_report(report())
    assert [g["status"] for g in gaps] == ["missing", "partial"]  # supported findings are not gaps
    ranked = prioritise(gaps, model, as_of=AS_OF)
    assert ranked == prioritise(gaps, model, as_of=AS_OF)
    assert ranked[0]["status"] == "missing" and ranked[0]["risk"]["score"] > ranked[1]["risk"]["score"]
    risk = ranked[0]["risk"]
    assert risk["domain"] == "kyc"
    assert risk["score"] == pytest.approx(sum(risk["contributions"].values()), abs=0.1)
    assert risk["band"] in {"critical", "high", "medium", "low"} and risk["target_days"]


def test_deadline_raises_priority(model):
    gap = {"gap_id": "g", "requirement": "Vendor oversight", "status": "partial", "cited_section_ids": ["s"]}
    later = score_gap({**gap, "effective_date": "2027-06-01"}, model, as_of=AS_OF)["risk"]["score"]
    overdue = score_gap({**gap, "effective_date": "2026-09-01"}, model, as_of=AS_OF)["risk"]["score"]
    assert overdue > later


def test_control_test_gap_and_passing_test(model):
    failing = {"classification": "operating_gap", "control": "privileged_access_review", "failed_records": ["a", "b"], "synthetic": True,
               "evidence_references": [{"file_sha256": "x", "chunk_id": "c", "location": {}}]}
    gaps = gaps_from_control_test(failing, test_id="t1", reference="Synthetic cyber control", requirement="Privileged access review")
    assert gaps[0]["control_classification"] == "operating_gap"
    assert score_gap(gaps[0], model, as_of=AS_OF)["risk"]["domain"] == "cyber"
    assert gaps_from_control_test({**failing, "classification": "test_passed"}, test_id="t2", reference="r", requirement="q") == []


def scored_missing(model):
    from regintel.prioritization.risk import gaps_from_report
    return prioritise(gaps_from_report(report()), model, as_of=AS_OF)[0]


def test_template_plan_is_pending_review(model):
    plan = plan_remediation(scored_missing(model))
    assert plan["method"] == "template_v1" and plan["review_status"] == "pending_review"
    assert {a["kind"] for a in plan["actions"]} == {"policy_update", "control_design"}


def test_llm_plan_rejects_invented_citations(model):
    gap = scored_missing(model)
    raw = json.dumps({"actions": [{"kind": "control_design", "description": "Design a retention control.", "owner_role": "control_owner",
                                   "cited_section_ids": ["sec-invented"]}], "rationale": "Because it is missing."})
    plan, errors = validate_llm_plan(raw, gap)
    assert plan is None and "not in the finding" in errors[0]


def test_llm_retry_with_feedback_then_accept(model):
    gap = scored_missing(model)
    prompts = []
    good = {"actions": [{"kind": "policy_update", "description": "Add a retention and preservation clause.", "owner_role": "policy_owner"}],
            "policy_redline": "The bank shall maintain and preserve account information for the period required.", "rationale": "Missing commitment."}
    responses = iter(["not json", json.dumps(good)])

    def drafter(prompt):
        prompts.append(prompt)
        return next(responses)

    plan = plan_remediation(gap, drafter=drafter)
    assert [a["outcome"] for a in plan["attempts"]] == ["rejected", "accepted"]
    assert "previous answer was rejected" in prompts[1]
    assert plan["policy_redline"] and plan["review_status"] == "pending_review"


def test_llm_abstains_to_template_after_repeated_failure(model):
    plan = plan_remediation(scored_missing(model), drafter=lambda prompt: "{}")
    assert plan["llm_abstained"] and plan["method"] == "template_v1" and len(plan["attempts"]) == 3


def test_supervisor_routes_and_traces(model):
    register = RemediationSupervisor(risk_model=model, drafter=lambda prompt: "{}").run(reports=[report(), {"bad": 1}], as_of=AS_OF)
    assert [s["step"] for s in register["trace"]] == ["intake", "applicability", "prioritise", "remediate", "route", "assemble"]
    assert len(register["items"]) == 2 and len(register["rejected_inputs"]) == 1
    assert all("LLM draft rejected; template used" in q["reasons"] for q in register["human_queue"])
    assert register["risk_model"]["sha256"] == model["sha256"]


def test_supervisor_with_no_gaps_skips_remediation(model):
    only_supported = {**report(), "findings": report()["findings"][2:]}
    register = RemediationSupervisor(risk_model=model).run(reports=[only_supported], as_of=AS_OF)
    assert register["items"] == [] and [s["step"] for s in register["trace"]] == ["intake", "applicability", "prioritise", "assemble"]


class FakeRecord:
    report_json = report()


class FakeSession:
    def get(self, model, key):
        return FakeRecord() if key == "gap-test" else None


def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: UserRecord(id=1, username="t", role="viewer", is_active=True)
    app.dependency_overrides[get_db] = lambda: FakeSession()
    return TestClient(app)


def test_remediation_endpoint():
    with client() as c:
        response = c.get("/api/v1/gap-reports/gap-test/remediation-plan", params={"as_of": "2026-10-11"})
        assert response.status_code == 200
        body = response.json()
        assert body["items"][0]["remediation"]["method"] == "template_v1"
        assert c.get("/api/v1/gap-reports/unknown/remediation-plan").status_code == 404


def test_remediation_endpoint_requires_auth():
    with TestClient(create_app()) as c:
        assert c.get("/api/v1/gap-reports/gap-test/remediation-plan").status_code == 401


def test_redline_cannot_invent_quantities_or_section_labels(model):
    gap = {**scored_missing(model), "regulatory_text": "REs shall preserve records for at least five years."}
    plan = lambda redline: json.dumps({"actions": [{"kind": "policy_update", "description": "Add the preservation clause.", "owner_role": "policy_owner"}],
                                       "policy_redline": redline, "rationale": "Missing commitment."})
    assert validate_llm_plan(plan("The Bank shall preserve records for at least five years."), gap)[0] is not None
    _, errors = validate_llm_plan(plan("The Bank shall preserve records for ten years."), gap)
    assert "ten years" in errors[0]
    _, errors = validate_llm_plan(plan("Section 46(f): The Bank shall preserve records."), gap)
    assert any("section number" in e for e in errors)


def test_prompt_includes_regulation_text(model):
    from regintel.remediation.planner import build_prompt
    gap = {**scored_missing(model), "regulatory_text": "evolve a system for proper maintenance"}
    assert "<regulation>\nevolve a system" in build_prompt(gap, [])
