
"""
Run RBI Section 46 verification with persistent caching.

Preview:
uv run python -m regintel.verification.run_llm_verification

One live comparison:
uv run python -m regintel.verification.run_llm_verification --live --limit 1 --top-k 1

Full evaluation:
uv run python -m regintel.verification.run_llm_verification --live --limit 6 --top-k 2
"""

import argparse
import json
import re
from pathlib import Path

from sqlalchemy import select

from regintel.db.session import SessionLocal
from regintel.models.obligation import RegulatoryObligation

from regintel.mapping.run_policy_mapping import (
    load_policy_sections,
)
from regintel.mapping.hybrid_retriever import (
    HybridPolicyRetriever,
)
from regintel.verification.llm_verifier import (
    LLMComplianceVerifier,
)
from regintel.cache.verification_cache import (
    VerificationCache,
    make_cache_key,
)


OUTPUT = Path(
    "data/processed/verification/"
    "llm_verification_results.json"
)


def extract_suffix(text: str) -> str | None:
    match = re.search(
        r"REs\s+shall\s*,?\s*\(([a-f])\)",
        text,
        re.IGNORECASE,
    )

    return match.group(1).lower() if match else None


def load_inputs():

    with SessionLocal() as session:
        sections = load_policy_sections(session)

        obligations = session.scalars(
            select(RegulatoryObligation).where(
                RegulatoryObligation.clause_number == "46",
                RegulatoryObligation.extraction_method
                == "rule_based_v4_1_inherited",
            )
        ).all()

        obligation_data = []

        for obligation in obligations:
            suffix = extract_suffix(
                obligation.evidence_quote
            )

            if suffix is None:
                raise ValueError(
                    "Could not identify Section 46 suffix "
                    f"for obligation {obligation.id}"
                )

            obligation_data.append({
                "id": str(obligation.id),
                "suffix": suffix,
                "evidence_quote": obligation.evidence_quote,
            })

    obligation_data.sort(
        key=lambda item: item["suffix"]
    )

    return sections, obligation_data


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--live",
        action="store_true",
        help="Run real Gemini verification.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=2,
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=2,
    )

    args = parser.parse_args()

    if not 1 <= args.limit <= 6:
        parser.error("--limit must be between 1 and 6")

    if not 1 <= args.top_k <= 6:
        parser.error("--top-k must be between 1 and 6")

    sections, obligations = load_inputs()

    if not sections or not obligations:
        raise RuntimeError(
            "No policy sections or obligations found."
        )

    retriever = HybridPolicyRetriever(sections)

    verifier = (
        LLMComplianceVerifier()
        if args.live
        else None
    )

    cache = (
        VerificationCache()
        if args.live
        else None
    )

    results = []

    for obligation in obligations[:args.limit]:

        matches = retriever.search(
            obligation_text=obligation["evidence_quote"],
            top_k=args.top_k,
        )

        for match in matches:

            print(
                f"RBI 46({obligation['suffix']}) "
                f"-> Policy Section {match.section_number}"
            )

            if not args.live:
                continue

            policy_section_id = str(
                match.policy_section_id
            )

            cache_key = make_cache_key(
                obligation_id=obligation["id"],
                obligation_text=obligation["evidence_quote"],
                policy_section_id=policy_section_id,
                policy_text=match.policy_text,
                model_name=verifier.model_name,
            )

            try:

                # ---------------------------------
                # 1. Check PostgreSQL cache
                # ---------------------------------

                cached_result = cache.get(cache_key)

                if cached_result is not None:
                    result = cached_result
                    cache_status = "hit"

                    print(
                        "  CACHE HIT:",
                        result.status.value,
                    )

                else:

                    # ---------------------------------
                    # 2. Call Gemini on cache miss
                    # ---------------------------------

                    cache_status = "miss"

                    cache.stats.api_calls += 1

                    result = verifier.verify(
                        obligation_id=obligation["id"],
                        obligation_text=obligation[
                            "evidence_quote"
                        ],
                        policy_section_id=policy_section_id,
                        policy_text=match.policy_text,
                    )

                    print(
                        "  GEMINI RESULT:",
                        result.status.value,
                    )

                    # ---------------------------------
                    # 3. Cache validated results
                    # ---------------------------------

                    if not result.validation_errors:
                        stored = cache.put(
                            cache_key=cache_key,
                            result=result,
                        )

                        print(
                            "  Cache stored:",
                            stored,
                        )

                    else:
                        print(
                            "  Not cached: evidence "
                            "validation failed."
                        )

                results.append({
                    "obligation": (
                        f"46({obligation['suffix']})"
                    ),
                    "policy_section": match.section_number,
                    "retrieval_score": match.rrf_score,
                    "cache_status": cache_status,
                    "verification": result.model_dump(
                        mode="json"
                    ),
                })

            except Exception as exc:

                # Fail closed: errors never become
                # successful compliance assessments.

                results.append({
                    "obligation": (
                        f"46({obligation['suffix']})"
                    ),
                    "policy_section": match.section_number,
                    "status": "verification_failed",
                    "error_type": type(exc).__name__,
                })

                print(
                    "  Verification failed:",
                    type(exc).__name__,
                    str(exc)[:1000],
                )

    if not args.live:
        print(
            "\nPREVIEW ONLY — no Gemini API "
            "requests were made."
        )
        return

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report = {
        "verification_method": (
            "gemini_structured_evidence_v1_cached"
        ),
        "cache_stats": {
            "hits": cache.stats.hits,
            "misses": cache.stats.misses,
            "api_calls": cache.stats.api_calls,
            "writes": cache.stats.writes,
        },
        "results": results,
    }

    OUTPUT.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nResults saved to:", OUTPUT)
    print("Assessments attempted:", len(results))

    print("\nCACHE STATISTICS")
    print("-------------------------")
    print("Cache hits:", cache.stats.hits)
    print("Cache misses:", cache.stats.misses)
    print("Gemini API calls:", cache.stats.api_calls)
    print("New cache entries:", cache.stats.writes)


if __name__ == "__main__":
    main()
