"""Supervisor workflow: gap intake -> risk prioritisation -> remediation drafting -> review routing.

Produces a remediation register for officer review. It never approves reports,
edits policies, or changes review status.
"""

import argparse
import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from regintel.applicability.engine import (
    APPLICABLE,
    EXCLUDED,
    UNDETERMINED,
    determine_all,
    resolve,
)
from regintel.prioritization.risk import (
    DEFAULT_MODEL,
    gaps_from_control_test,
    gaps_from_report,
    load_risk_model,
    prioritise,
)
from regintel.remediation.planner import plan_remediation

ESCALATE_BANDS = {"critical", "high"}
NOTICE = "Prioritised remediation drafts for human review. Not a compliance certification; no report, policy, or review status was changed."


class SupervisorState(TypedDict):
    reports: list[dict]
    control_tests: list[dict]
    as_of: str
    gaps: NotRequired[list[dict]]
    excluded: NotRequired[list[dict]]
    rejected_inputs: NotRequired[list[dict]]
    prioritised: NotRequired[list[dict]]
    plans: NotRequired[dict[str, dict]]
    human_queue: NotRequired[list[dict]]
    trace: NotRequired[list[dict]]


class RemediationSupervisor:

    def __init__(self, *, risk_model: dict, drafter: Callable[[str], str] | None = None,
                 applicability: list[dict] | None = None):
        self.risk_model = risk_model
        self.drafter = drafter
        self.applicability = applicability  # engine determinations; None = not evaluated
        self.graph = self._build_graph()

    @staticmethod
    def _step(state, name, started, **detail):
        return state.get("trace", []) + [{"step": name, "ms": round((time.perf_counter() - started) * 1000, 2), **detail}]

    def intake_node(self, state: SupervisorState) -> dict:
        started, gaps, rejected = time.perf_counter(), [], []
        for report in state["reports"]:
            try:
                gaps.extend(gaps_from_report(report))
            except (KeyError, TypeError) as exc:
                rejected.append({"input": report.get("report_id", "unknown"), "error": f"{type(exc).__name__}: {exc}"})
        for test in state["control_tests"]:
            try:
                gaps.extend(gaps_from_control_test(test["result"], test_id=test["test_id"],
                                                   reference=test["reference"], requirement=test["requirement"]))
            except (KeyError, TypeError) as exc:
                rejected.append({"input": test.get("test_id", "unknown"), "error": f"{type(exc).__name__}: {exc}"})
        return {"gaps": gaps, "rejected_inputs": rejected,
                "trace": self._step(state, "intake", started, gaps=len(gaps), rejected=len(rejected))}

    def applicability_node(self, state: SupervisorState) -> dict:
        """Drop gaps against non-applicable sources; mark the rest with their determination."""
        started, kept, excluded = time.perf_counter(), [], []
        for gap in state["gaps"]:
            if self.applicability is None:
                kept.append({**gap, "applicability": {"status": "not_evaluated"}})
                continue
            found = resolve(gap.get("reference", ""), self.applicability)
            determination = ({"status": found["status"], "basis": found["basis"], "source_title": found["title"]}
                             if found else {"status": UNDETERMINED, "basis": {"rule": "source_not_resolved"}})
            if determination["status"] in EXCLUDED:
                excluded.append({"gap_id": gap["gap_id"], "requirement": gap["requirement"], "applicability": determination})
            else:
                kept.append({**gap, "applicability": determination})
        return {"gaps": kept, "excluded": excluded,
                "trace": self._step(state, "applicability", started, kept=len(kept), excluded=len(excluded))}

    def prioritise_node(self, state: SupervisorState) -> dict:
        started = time.perf_counter()
        ranked = prioritise(state["gaps"], self.risk_model, as_of=date.fromisoformat(state["as_of"]))
        bands = {}
        for gap in ranked:
            bands[gap["risk"]["band"]] = bands.get(gap["risk"]["band"], 0) + 1
        return {"prioritised": ranked, "trace": self._step(state, "prioritise", started, bands=bands)}

    @staticmethod
    def route_after_prioritise(state: SupervisorState) -> str:
        return "remediate" if state["prioritised"] else "assemble"

    def remediate_node(self, state: SupervisorState) -> dict:
        started, plans, rejected_attempts = time.perf_counter(), {}, 0
        for gap in state["prioritised"]:
            plan = plan_remediation(gap, drafter=self.drafter)
            rejected_attempts += sum(a["outcome"] != "accepted" for a in plan["attempts"])
            plans[gap["gap_id"]] = plan
        return {"plans": plans, "trace": self._step(state, "remediate", started, drafted=len(plans),
                                                   method="llm" if self.drafter else "template",
                                                   rejected_llm_attempts=rejected_attempts)}

    def route_node(self, state: SupervisorState) -> dict:
        started, queue = time.perf_counter(), []
        for gap in state["prioritised"]:
            plan, reasons = state["plans"][gap["gap_id"]], []
            if gap["risk"]["band"] in ESCALATE_BANDS:
                reasons.append(f"{gap['risk']['band']} risk")
            if plan.get("llm_abstained"):
                reasons.append("LLM draft rejected; template used")
            if gap.get("status") == "potential_conflict":
                reasons.append("interpretation required")
            if gap["applicability"]["status"] not in (APPLICABLE, "not_evaluated"):
                reasons.append(f"applicability not confirmed by an officer ({gap['applicability']['status']})")
            if reasons:
                queue.append({"gap_id": gap["gap_id"], "score": gap["risk"]["score"], "reasons": reasons})
        return {"human_queue": queue, "trace": self._step(state, "route", started, queued=len(queue))}

    def assemble_node(self, state: SupervisorState) -> dict:
        return {"trace": self._step(state, "assemble", time.perf_counter())}

    def _build_graph(self):
        builder = StateGraph(SupervisorState)
        for name in ("intake", "applicability", "prioritise", "remediate", "route", "assemble"):
            builder.add_node(name, getattr(self, f"{name}_node"))
        builder.add_edge(START, "intake")
        builder.add_edge("intake", "applicability")
        builder.add_edge("applicability", "prioritise")
        builder.add_conditional_edges("prioritise", self.route_after_prioritise, {"remediate": "remediate", "assemble": "assemble"})
        builder.add_edge("remediate", "route")
        builder.add_edge("route", "assemble")
        builder.add_edge("assemble", END)
        return builder.compile()

    def run(self, *, reports: list[dict], control_tests: list[dict] | None = None, as_of: date | None = None) -> dict:
        as_of = as_of or datetime.now(UTC).date()
        state = self.graph.invoke({"reports": reports, "control_tests": control_tests or [], "as_of": as_of.isoformat()})
        plans = state.get("plans", {})
        return {
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "as_of": as_of.isoformat(),
            "risk_model": {"version": self.risk_model["version"], "sha256": self.risk_model["sha256"], "notice": self.risk_model["notice"]},
            "items": [{**gap, "remediation": plans[gap["gap_id"]]} for gap in state.get("prioritised", [])],
            "human_queue": state.get("human_queue", []),
            "excluded_not_applicable": state.get("excluded", []),
            "rejected_inputs": state.get("rejected_inputs", []),
            "trace": state["trace"],
            "notice": NOTICE,
        }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, nargs="*", default=[], help="Stored gap report JSON files")
    parser.add_argument("--control-tests", type=Path, nargs="*", default=[],
                        help="JSON files of {test_id, reference, requirement, result} control-test records")
    parser.add_argument("--risk-model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--as-of", type=date.fromisoformat, default=None)
    parser.add_argument("--regulatory-text", type=Path, default=None,
                        help="UTF-8 text of the assessed provision, used for reports stored without regulatory_text")
    parser.add_argument("--llm", action="store_true", help="Draft remediation with Gemini (validated; falls back to templates)")
    parser.add_argument("--no-applicability", action="store_true", help="Skip applicability enforcement")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite {args.output}")
    if not args.reports and not args.control_tests:
        raise SystemExit("Supply at least one --reports or --control-tests file")
    drafter = None
    if args.llm:
        from dotenv import load_dotenv

        from regintel.remediation.planner import GeminiDrafter
        load_dotenv()
        drafter = GeminiDrafter()
    reports = [json.loads(p.read_text(encoding="utf-8")) for p in args.reports]
    if args.regulatory_text:
        text = args.regulatory_text.read_text(encoding="utf-8")
        reports = [{**r, "regulatory_text": r.get("regulatory_text") or text} for r in reports]
    tests = [record for p in args.control_tests for record in json.loads(p.read_text(encoding="utf-8"))]
    applicability = None if args.no_applicability else determine_all(args.root.resolve())
    register = RemediationSupervisor(risk_model=load_risk_model(args.risk_model), drafter=drafter, applicability=applicability).run(
        reports=reports, control_tests=tests, as_of=args.as_of)
    register["inputs"] = [{"path": str(p), "sha256": _sha256(p)} for p in [*args.reports, *args.control_tests, *filter(None, [args.regulatory_text])]]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(register, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(register['items'])} gaps prioritised, {len(register['human_queue'])} queued for review -> {args.output}")


if __name__ == "__main__":
    main()
