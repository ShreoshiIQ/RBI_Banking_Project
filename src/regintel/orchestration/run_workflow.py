
"""
Run the LangGraph workflow on stored RBI obligations.

Examples:
uv run python -m regintel.orchestration.run_workflow --limit 1 --top-k 1
uv run python -m regintel.orchestration.run_workflow --live --limit 1 --top-k 2
"""

import argparse
import json
from pathlib import Path

from regintel.cache.verification_cache import VerificationCache
from regintel.mapping.hybrid_retriever import HybridPolicyRetriever
from regintel.verification.llm_verifier import LLMComplianceVerifier
from regintel.verification.run_llm_verification import load_inputs
from regintel.orchestration.verification_graph import VerificationWorkflow


OUTPUT = Path(
    "data/processed/verification/langgraph_results.json"
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--top-k", type=int, default=2)
    args = parser.parse_args()

    if not 1 <= args.limit <= 6:
        parser.error("--limit must be between 1 and 6")

    if not 1 <= args.top_k <= 6:
        parser.error("--top-k must be between 1 and 6")

    sections, obligations = load_inputs()

    if not sections or not obligations:
        raise RuntimeError("No policy sections or obligations found")

    retriever = HybridPolicyRetriever(sections)
    cache = VerificationCache()

    # No Gemini client or API key is needed for preview mode.
    if args.live:
        verifier = LLMComplianceVerifier()
    else:
        class PreviewVerifier:
            model_name = "preview-only"

            def verify(self, **kwargs):
                raise RuntimeError(
                    "Gemini must not run in preview mode"
                )

        verifier = PreviewVerifier()

    workflow = VerificationWorkflow(
        verifier=verifier,
        cache=cache,
        use_llm=args.live,
    )

    results = []

    for obligation in obligations[:args.limit]:
        matches = retriever.search(
            obligation_text=obligation["evidence_quote"],
            top_k=args.top_k,
        )

        for match in matches:
            print(
                f"\nRBI 46({obligation['suffix']}) "
                f"-> Policy Section {match.section_number}"
            )

            state = workflow.invoke(
                obligation_id=obligation["id"],
                obligation_text=obligation["evidence_quote"],
                policy_section_id=str(match.policy_section_id),
                policy_text=match.policy_text,
            )

            print(
                "  Deterministic:",
                state["deterministic"]["attribute_status"],
            )
            print("  Cache:", state["cache_status"])
            print("  Final:", state["final_status"])
            print("  Trace:", " -> ".join(state["trace"]))

            results.append({
                "obligation": f"46({obligation['suffix']})",
                "policy_section": match.section_number,
                "retrieval_score": match.rrf_score,
                "workflow": state,
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "live": args.live,
        "cache_stats": {
            "hits": cache.stats.hits,
            "misses": cache.stats.misses,
            "api_calls": cache.stats.api_calls,
            "writes": cache.stats.writes,
        },
        "results": results,
    }

    OUTPUT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nSaved:", OUTPUT)
    print("Cache hits:", cache.stats.hits)
    print("Gemini API calls:", cache.stats.api_calls)


if __name__ == "__main__":
    main()
