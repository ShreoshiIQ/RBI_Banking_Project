"""Create explicitly synthetic policy drafts and provisional review scenarios."""

import hashlib
import json
from pathlib import Path

TOPICS = [
    ("access", "Access Management", "access", "Information Security",
     "The access team records each request, verifies the manager's approval, grants only the approved role, and retains the request and provisioning record.",
     "The access team reviews privileged accounts and removes access after an employee leaves or changes responsibilities."),
    ("vendor", "Vendor Risk Management", "service provider", "Third Party Risk",
     "The vendor owner documents due diligence, information-security risks, approved services, and contractual responsibilities before onboarding a service provider.",
     "The vendor owner tracks service performance, unresolved risks, business-continuity tests, and an exit plan with data-return responsibilities."),
    ("continuity", "Business Continuity", "disaster recovery", "Technology Operations",
     "The continuity coordinator maintains the critical-service inventory, recovery dependencies, named alternates, and escalation contacts.",
     "The operations team rehearses recovery, records actual restoration results, reconciles recovered data, and assigns corrective actions for failed steps."),
    ("fraud", "Payment Fraud Monitoring", "fraud", "Payment Risk",
     "The fraud team reviews payment alerts, documents the investigation and customer contact, and routes suspicious events to the designated escalation owner.",
     "The team tracks alert resolution, customer impact, detection failures, and corrective actions without treating an alert alone as proof of fraud."),
    ("card", "Card Customer Protection", "consent", "Card Operations",
     "The card team records customer consent and the disclosed terms before activating a requested service or changing a customer-facing feature.",
     "The team registers customer complaints, preserves communications, assigns a case owner, and documents the resolution and any required remediation."),
]

VARIANTS = {
    "detailed": "Both operational procedures are documented; execution evidence must still be checked.",
    "partial": "Only the first procedure is documented; the second is intentionally omitted.",
    "vague": "A general commitment is present without a procedure or evidence requirements.",
    "conflicting": "An explicit exception contradicts the approval procedure; this is an intentional test defect.",
}


def build_text(code, title, owner, first, second, variant):
    procedures = {
        "detailed": first + "\n" + second,
        "partial": first,
        "vague": "The bank aims to maintain suitable controls for this topic. Detailed operating procedures are not specified in this document.",
        "conflicting": first + "\nAn operator may bypass the required approval and documentation when workload is high. No exception record is required.",
    }
    return (
        f"POLICY CODE: {code}\nTITLE: {title}\nOWNER: {owner}\n"
        "STATUS: SYNTHETIC DEMONSTRATION DOCUMENT - UNREVIEWED DRAFT\n\n"
        "SECTION 1: PURPOSE AND SCOPE\n"
        "Fictional commercial-bank testing policy. This is not evidence of a real institution's controls or regulatory certification. Applicability remains unreviewed.\n\n"
        "SECTION 2: OPERATING PROCEDURE\n" + procedures[variant] + "\n\n"
        "SECTION 3: OVERSIGHT\n"
        "The policy owner records review findings and assigns an action owner and target date. Implementation evidence is required separately.\n"
    )


def main():
    rows = []
    for path in sorted(Path("data/processed/expansion_reviews").glob("*_triage.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        rows.extend((report, row) for row in report["candidates"] if row["section_category"] == "potential_operational_control")
    output = Path("data/raw/policies/synthetic_drafts")
    output.mkdir(parents=True, exist_ok=True)
    policies, scenarios = [], []
    for topic, title, keyword, owner, first, second in TOPICS:
        anchors = [(report, row) for report, row in rows if keyword in row["source"]["evidence_quote"].casefold()]
        if not anchors:
            raise ValueError(f"No source topic anchor for {topic}")
        report, row = anchors[0]
        anchor = {
            "content_hash": row["source"]["content_hash"], "clause_number": row["source"]["clause_number"],
            "candidate_index": row["candidate_index"], "source_url": row["source"]["source_url"],
            "start_page": row["source"]["start_page"], "end_page": row["source"]["end_page"],
            "relationship": "topic_anchor_only_not_verified_control_mapping",
        }
        for variant, description in VARIANTS.items():
            code = f"SYN-{topic.upper()}-{variant.upper()}"
            text = build_text(code, f"{title} - {variant} testing variant", owner, first, second, variant)
            path = output / f"{code}.txt"
            if not path.exists():
                path.write_text(text, encoding="utf-8")
            elif path.read_text(encoding="utf-8") != text:
                raise ValueError(f"Preserving modified policy: {path}")
            policies.append({"policy_code": code, "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "topic": topic, "variant": variant, "design_note": description, "source_anchor": anchor, "review_status": "pending"})
            for case in ("retrieve_topic", "inspect_procedure", "check_missing_detail", "check_exceptions", "verify_execution_evidence"):
                scenarios.append({
                    "scenario_id": f"{code}-{case}", "policy_code": code, "case": case,
                    "prompt": f"Review {title.lower()} in this synthetic policy: {case.replace('_', ' ')}.",
                    "source_anchor": anchor, "reference_policy_sections": ["2"],
                    "label_type": "provisional_design_intent_not_compliance_ground_truth",
                    "review_status": "pending", "expected_compliance_status": None,
                })
    metadata = Path("data/metadata/synthetic_policy_drafts.json")
    evaluation = Path("data/evaluation/synthetic_draft_scenarios.json")
    for path, data in ((metadata, {"policies": policies}), (evaluation, {"scenarios": scenarios})):
        data.update(schema_version=1, synthetic=True, notice="Draft test data; human review required. No benchmark scores or legal conclusions.")
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != data:
                raise ValueError(f"Refusing to overwrite {path}")
        else:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Created or verified {len(policies)} policy drafts and {len(scenarios)} provisional scenarios")


if __name__ == "__main__":
    main()
