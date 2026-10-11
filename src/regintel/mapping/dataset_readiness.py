"""Check draft evaluation data without computing benchmark scores."""

import json
from collections import Counter, defaultdict
from pathlib import Path


def inspect_readiness(policies: list[dict], scenarios: list[dict]) -> dict:
    codes = [policy["policy_code"] for policy in policies]
    lookup = {policy["policy_code"]: policy for policy in policies}
    issues = Counter()
    prompts = defaultdict(list)
    families = defaultdict(list)
    sources = defaultdict(list)
    ids = Counter(scenario["scenario_id"] for scenario in scenarios)
    if len(set(codes)) != len(codes):
        issues["duplicate_policy_codes"] += len(codes) - len(set(codes))
    issues["duplicate_scenario_ids"] += sum(count - 1 for count in ids.values())
    for scenario in scenarios:
        scenario_id = scenario["scenario_id"]
        policy = lookup.get(scenario.get("policy_code"))
        prompts[" ".join(scenario.get("prompt", "").split()).casefold()].append(scenario_id)
        if policy is None:
            issues["unknown_policy"] += 1
            continue
        families[policy["topic"]].append(scenario_id)
        sources[scenario["source_anchor"]["content_hash"]].append(scenario_id)
        if scenario.get("source_anchor") != policy.get("source_anchor"):
            issues["policy_source_anchor_mismatch"] += 1
        if scenario.get("review_status") != "approved":
            issues["scenario_pending_review"] += 1
        if policy.get("review_status") != "approved":
            issues["policy_pending_review"] += 1
        if scenario.get("expected_compliance_status") is None:
            issues["no_compliance_ground_truth"] += 1
        if not scenario.get("reference_policy_sections"):
            issues["missing_reference_sections"] += 1
    duplicate_prompts = [values for values in prompts.values() if len(values) > 1]
    return {
        "schema_version": 1, "ready_for_scored_compliance_evaluation": False,
        "notice": "Structural checks do not validate regulatory labels; no metrics were computed.",
        "summary": {
            "policies": len(policies), "scenarios": len(scenarios),
            "unique_prompts": len(prompts), "topic_families": len(families),
            "source_versions": len(sources), "issue_counts": {key: value for key, value in issues.items() if value},
        },
        "repeated_prompt_groups": duplicate_prompts,
        "topic_family_groups": dict(families),
        "source_version_groups": dict(sources),
        "split_instruction": "Keep related policy variants together; also inspect source-version overlap before assigning train, validation, or test splits.",
    }


def main():
    policies = json.loads(Path("data/metadata/synthetic_policy_drafts.json").read_text(encoding="utf-8"))["policies"]
    scenarios = json.loads(Path("data/evaluation/synthetic_draft_scenarios.json").read_text(encoding="utf-8"))["scenarios"]
    result = inspect_readiness(policies, scenarios)
    path = Path("data/evaluation/synthetic_draft_readiness.json")
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
