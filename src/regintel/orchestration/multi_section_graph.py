
from typing import Any, TypedDict

from langgraph.graph import START, END, StateGraph

from regintel.orchestration.multi_section import (
    PolicyEvidence,
    build_evidence_bundle,
    multi_section_cache_key,
)
from regintel.verification.multi_section_schemas import (
    MultiSectionAssessment,
)
from regintel.verification.multi_section_validator import (
    validate_multi_section_assessment,
)


class MultiSectionState(TypedDict, total=False):
    obligation_id: str
    obligation_text: str
    sections: list[PolicyEvidence]
    evidence_bundle: str
    cache_key: str
    cache_status: str
    route: str
    result: dict[str, Any] | None
    citations: list[dict]
    errors: list[str]
    final_status: str
    requires_human_review: bool
    trace: list[str]


class MultiSectionWorkflow:

    def __init__(
        self,
        *,
        verifier,
        cache,
        use_llm=True,
    ):
        self.verifier = verifier
        self.cache = cache
        self.use_llm = use_llm
        self.graph = self._build_graph()

    def prepare(self, state):
        sections = sorted(
            state["sections"],
            key=lambda s: s.section_id,
        )

        bundle = build_evidence_bundle(sections)

        key = multi_section_cache_key(
            obligation_id=state["obligation_id"],
            obligation_text=state["obligation_text"],
            sections=sections,
            model_name=self.verifier.model_name,
        )

        return {
            "sections": sections,
            "evidence_bundle": bundle,
            "cache_key": key,
            "trace": ["prepare_evidence"],
        }

    def lookup(self, state):
        if not self.use_llm:
            return {
                "cache_status": "not_checked",
                "route": "review",
                "trace": state["trace"] + ["preview"],
            }

        try:
            cached = self.cache.get(state["cache_key"])
        except ValueError as exc:
            return {
                "cache_status": "invalid",
                "route": "review",
                "errors": [str(exc)],
                "trace": state["trace"] + [
                    "invalid_cache_entry"
                ],
            }

        if cached is not None:
            # Revalidate stored quotations against the
            # current source sections before reuse.
            assessment = MultiSectionAssessment(
                proposed_status=cached["proposed_status"],
                findings=cached["findings"],
                missing_requirements=(
                    cached["missing_requirements"]
                ),
                potential_conflicts=(
                    cached["potential_conflicts"]
                ),
                explanation=cached["explanation"],
            )

            validated = validate_multi_section_assessment(
                assessment=assessment,
                sections=state["sections"],
            )

            if validated["validation_errors"]:
                return {
                    "cache_status": "invalid",
                    "route": "review",
                    "errors": validated["validation_errors"],
                    "trace": state["trace"] + [
                        "invalid_cache_entry"
                    ],
                }

            return {
                "cache_status": "hit",
                "route": "review",
                "result": validated,
                "citations": validated["citations"],
                "trace": state["trace"] + ["cache_hit"],
            }

        return {
            "cache_status": "miss",
            "route": "gemini",
            "trace": state["trace"] + ["cache_miss"],
        }

    @staticmethod
    def route(state):
        return state["route"]

    def gemini(self, state):
        try:
            self.cache.stats.api_calls += 1

            result = self.verifier.verify(
                obligation_id=state["obligation_id"],
                obligation_text=state["obligation_text"],
                sections=state["sections"],
            )

            if result["validation_errors"]:
                return {
                    "result": result,
                    "citations": result["citations"],
                    "errors": result["validation_errors"],
                    "trace": state["trace"] + [
                        "gemini_verification",
                        "evidence_rejected",
                    ],
                }

            stored = self.cache.put(
                state["cache_key"],
                result,
            )

            return {
                "result": result,
                "citations": result["citations"],
                "trace": state["trace"] + [
                    "gemini_verification",
                    "cache_written" if stored
                    else "cache_not_written",
                ],
            }

        except Exception as exc:
            return {
                "errors": [
                    f"{type(exc).__name__}: {str(exc)[:300]}"
                ],
                "trace": state["trace"] + [
                    "gemini_failed"
                ],
            }

    @staticmethod
    def review(state):
        result = state.get("result")
        errors = state.get("errors", [])

        if errors or result is None:
            status = "needs_review"
        elif result.get("validation_errors"):
            status = "needs_review"
        else:
            status = result["status"]

        return {
            "final_status": status,
            "requires_human_review": True,
            "trace": state["trace"] + ["human_review"],
        }

    def _build_graph(self):
        builder = StateGraph(MultiSectionState)

        builder.add_node("prepare", self.prepare)
        builder.add_node("lookup", self.lookup)
        builder.add_node("gemini", self.gemini)
        builder.add_node("review", self.review)

        builder.add_edge(START, "prepare")
        builder.add_edge("prepare", "lookup")

        builder.add_conditional_edges(
            "lookup",
            self.route,
            {
                "gemini": "gemini",
                "review": "review",
            },
        )

        builder.add_edge("gemini", "review")
        builder.add_edge("review", END)

        return builder.compile()

    def invoke(
        self,
        *,
        obligation_id,
        obligation_text,
        sections,
    ):
        if not obligation_id.strip():
            raise ValueError("Missing obligation ID")

        if not obligation_text.strip():
            raise ValueError("Empty regulatory obligation")

        if not sections:
            raise ValueError("No policy evidence supplied")

        return self.graph.invoke({
            "obligation_id": obligation_id,
            "obligation_text": obligation_text,
            "sections": sections,
            "errors": [],
            "citations": [],
            "result": None,
            "trace": [],
        })
