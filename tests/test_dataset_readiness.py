from regintel.mapping.dataset_readiness import inspect_readiness


def test_related_variants_and_repeated_prompts_are_reported():
    anchor = {"content_hash": "source"}
    policies = [{"policy_code": code, "topic": "access", "source_anchor": anchor, "review_status": "pending"} for code in ("a", "b")]
    scenarios = [{"scenario_id": code, "policy_code": code, "prompt": "Review access", "source_anchor": anchor,
                  "reference_policy_sections": ["2"], "review_status": "pending", "expected_compliance_status": None} for code in ("a", "b")]
    result = inspect_readiness(policies, scenarios)
    assert result["summary"]["unique_prompts"] == 1
    assert result["repeated_prompt_groups"] == [["a", "b"]]
    assert result["topic_family_groups"]["access"] == ["a", "b"]
    assert result["ready_for_scored_compliance_evaluation"] is False
    assert result["summary"]["issue_counts"]["no_compliance_ground_truth"] == 2


def test_unknown_policy_and_duplicate_scenario_ids():
    scenarios = [{"scenario_id": "same", "policy_code": "missing", "prompt": "Query"}] * 2
    issues = inspect_readiness([], scenarios)["summary"]["issue_counts"]
    assert issues["duplicate_scenario_ids"] == 1
    assert issues["unknown_policy"] == 2
