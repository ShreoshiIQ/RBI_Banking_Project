
import argparse
import json
from pathlib import Path

from regintel.cache.multi_section_cache import MultiSectionCache
from regintel.cache.verification_cache import VerificationCache
from regintel.orchestration.multi_section import PolicyEvidence
from regintel.orchestration.multi_section_graph import (
    MultiSectionWorkflow,
)
from regintel.verification.multi_section_verifier import (
    MultiSectionGeminiVerifier,
)
from regintel.verification.run_llm_verification import (
    load_inputs,
)


OUTPUT = Path(
    "data/processed/verification/"
    "multi_section_results.json"
)


class PreviewVerifier:
    model_name = "preview-only"

    def verify(self, **kwargs):
        raise RuntimeError(
            "Preview mode must not call Gemini"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    sections, obligations = load_inputs()

    obligation = next(
        (
            item for item in obligations
            if item["suffix"] == "f"
        ),
        None,
    )

    if obligation is None:
        raise RuntimeError("RBI Section 46(f) not found")

    selected = [
        section for section in sections
        if str(section["section_number"]) in {"4", "6"}
    ]

    if len(selected) != 2:
        raise RuntimeError(
            "Expected Policy Sections 4 and 6 "
            "from the latest policy version"
        )

    evidence = [
        PolicyEvidence(
            section_id=str(section["id"]),
            section_number=str(section["section_number"]),
            section_title=section["section_title"],
            section_text=section["section_text"],
        )
        for section in selected
    ]

    verifier = (
        MultiSectionGeminiVerifier()
        if args.live
        else PreviewVerifier()
    )

    cache = MultiSectionCache()

    workflow = MultiSectionWorkflow(
        verifier=verifier,
        cache=cache,
        use_llm=args.live,
    )

    state = workflow.invoke(
        obligation_id=obligation["id"],
        obligation_text=obligation["evidence_quote"],
        sections=evidence,
    )

    print("\nObligation: RBI 46(f)")
    print(
        "Policy sections:",
        ", ".join(s.section_number for s in evidence),
    )
    print("Cache:", state["cache_status"])
    print("Final status:", state["final_status"])
    print(
        "Trace:",
        " -> ".join(state["trace"]),
    )
    print("Gemini API calls:", cache.stats.api_calls)

    if state.get("errors"):
        print("Errors:", state["errors"])

    if state.get("citations"):
        print("\nValidated policy citations:")
        for citation in state["citations"]:
            print(
                f"  Section {citation['section_number']}: "
                f"{citation['quote']}"
            )

    report = {
        "obligation": "46(f)",
        "mode": "live" if args.live else "preview",
        "policy_sections": [
            {
                "id": s.section_id,
                "number": s.section_number,
                "title": s.section_title,
            }
            for s in evidence
        ],
        "cache_stats": {
            "hits": cache.stats.hits,
            "misses": cache.stats.misses,
            "api_calls": cache.stats.api_calls,
            "writes": cache.stats.writes,
        },
        "workflow": {
            "cache_status": state["cache_status"],
            "final_status": state["final_status"],
            "requires_human_review": (
                state["requires_human_review"]
            ),
            "citations": state.get("citations", []),
            "errors": state.get("errors", []),
            "trace": state["trace"],
            "result": state.get("result"),
        },
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nSaved:", OUTPUT)


if __name__ == "__main__":
    main()
