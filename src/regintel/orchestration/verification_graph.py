
"""
LangGraph workflow for one regulatory obligation
and one internal policy section.

Pipeline:
    deterministic checks
    -> cache lookup
    -> cached result OR Gemini verification
    -> human-review classification

No automatic compliance approval.
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from regintel.cache.verification_cache import (
    VerificationCache,
    make_cache_key,
)
from regintel.verification.attribute_verifier import (
    verify_attributes,
)
from regintel.verification.retention_verifier import (
    verify_retention,
)
from regintel.orchestration.state import VerificationState


class VerificationWorkflow:

    def __init__(
        self,
        *,
        verifier: Any,
        cache: VerificationCache,
        use_llm: bool = True,
    ):
        self.verifier = verifier
        self.cache = cache
        self.use_llm = use_llm
        self.graph = self._build_graph()

    def deterministic_node(
        self,
        state: VerificationState,
    ) -> dict:

        obligation_text = state["obligation_text"]
        policy_text = state["policy_text"]

        attribute_result = verify_attributes(
            obligation_text=obligation_text,
            policy_text=policy_text,
            policy_section_id=state["policy_section_id"],
        )

        retention_result = verify_retention(
            obligation_id=state["obligation_id"],
            obligation_text=obligation_text,
            policy_section_id=state["policy_section_id"],
            policy_text=policy_text,
        )

        return {
            "deterministic": {
                "attribute_status": attribute_result.status,
                "matched_attributes": (
                    attribute_result.matched_attributes
                ),
                "missing_attributes": (
                    attribute_result.missing_attributes
                ),
                "attribute_explanation": (
                    attribute_result.explanation
                ),
                "retention_status": (
                    retention_result.status.value
                ),
                "retention_explanation": (
                    retention_result.explanation
                ),
            },
            "trace": ["deterministic_checks"],
        }

    def cache_lookup_node(
        self,
        state: VerificationState,
    ) -> dict:

        cache_key = make_cache_key(
            obligation_id=state["obligation_id"],
            obligation_text=state["obligation_text"],
            policy_section_id=state["policy_section_id"],
            policy_text=state["policy_text"],
            model_name=self.verifier.model_name,
        )

        cached = self.cache.get(cache_key)

        if cached is not None:
            return {
                "cache_key": cache_key,
                "cache_status": "hit",
                "route": "cached",
                "result": cached.model_dump(mode="json"),
                "trace": state["trace"] + ["cache_hit"],
            }

        return {
            "cache_key": cache_key,
            "cache_status": "miss",
            "route": "llm" if self.use_llm else "review",
            "trace": state["trace"] + ["cache_miss"],
        }

    @staticmethod
    def route_after_cache(
        state: VerificationState,
    ) -> str:
        return state["route"]

    def gemini_node(
        self,
        state: VerificationState,
    ) -> dict:

        try:
            self.cache.stats.api_calls += 1

            result = self.verifier.verify(
                obligation_id=state["obligation_id"],
                obligation_text=state["obligation_text"],
                policy_section_id=state["policy_section_id"],
                policy_text=state["policy_text"],
            )

            stored = self.cache.put(
                cache_key=state["cache_key"],
                result=result,
            )

            return {
                "result": result.model_dump(mode="json"),
                "trace": state["trace"] + [
                    "gemini_verification",
                    "cache_written" if stored
                    else "cache_not_written",
                ],
            }

        except Exception as exc:
            return {
                "result": None,
                "errors": [
                    f"{type(exc).__name__}: {str(exc)[:300]}"
                ],
                "trace": state["trace"] + [
                    "gemini_verification_failed"
                ],
            }

    @staticmethod
    def review_node(
        state: VerificationState,
    ) -> dict:

        result = state.get("result")
        errors = state.get("errors", [])

        if errors:
            final_status = "verification_failed"

        elif result is None:
            final_status = "needs_review"

        elif result.get("validation_errors"):
            final_status = "needs_review"

        else:
            # This is an evidence-assessment status,
            # never a legal compliance certification.
            final_status = result["status"]

        return {
            "final_status": final_status,
            "requires_human_review": True,
            "trace": state["trace"] + ["human_review"],
        }

    def _build_graph(self):

        builder = StateGraph(VerificationState)

        builder.add_node(
            "deterministic",
            self.deterministic_node,
        )

        builder.add_node(
            "cache_lookup",
            self.cache_lookup_node,
        )

        builder.add_node(
            "gemini",
            self.gemini_node,
        )

        builder.add_node(
            "review",
            self.review_node,
        )

        builder.add_edge(
            START,
            "deterministic",
        )

        builder.add_edge(
            "deterministic",
            "cache_lookup",
        )

        builder.add_conditional_edges(
            "cache_lookup",
            self.route_after_cache,
            {
                "cached": "review",
                "llm": "gemini",
                "review": "review",
            },
        )

        builder.add_edge(
            "gemini",
            "review",
        )

        builder.add_edge(
            "review",
            END,
        )

        return builder.compile()

    def invoke(
        self,
        *,
        obligation_id: str,
        obligation_text: str,
        policy_section_id: str,
        policy_text: str,
    ) -> VerificationState:

        if not obligation_text.strip():
            raise ValueError("Empty obligation text")

        if not policy_text.strip():
            raise ValueError("Empty policy text")

        return self.graph.invoke({
            "obligation_id": obligation_id,
            "obligation_text": obligation_text,
            "policy_section_id": policy_section_id,
            "policy_text": policy_text,
            "errors": [],
            "trace": [],
        })
