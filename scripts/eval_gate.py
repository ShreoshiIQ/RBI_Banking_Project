"""Fail the build when measured reliability regresses below eval_gates.json.

Offline only: no model calls. Live-OCR results are checked from their stored summary.
"""

import json
import sys
from datetime import date
from pathlib import Path

from regintel.agents.supervisor import RemediationSupervisor
from regintel.evidence.pack import build_pack
from regintel.evidence.pack_eval import evaluate
from regintel.mapping.relevance_review import score_packet
from regintel.prioritization.risk import load_risk_model

ROOT = Path(__file__).resolve().parents[1]


def check(name, ok, detail, failures):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not ok:
        failures.append(name)


def main() -> int:
    gates = json.loads((ROOT / "eval_gates.json").read_text(encoding="utf-8"))
    failures = []

    offline = gates["offline_evidence_pack"]
    for seed in offline["seeds"]:
        files, truth = build_pack(seed)
        result = evaluate(files, truth)
        native = [f for f in result["per_file"].values() if f["method"] == "native"]
        recall = min(f["record_recall"] for f in native)
        accuracy = min(f["field_accuracy"] for f in native)
        precision = result["defect_detection_accepted_only"]["precision"]
        check(f"seed {seed} native recall", recall >= offline["native_record_recall_min"], recall, failures)
        check(f"seed {seed} native accuracy", accuracy >= offline["native_field_accuracy_min"], accuracy, failures)
        check(f"seed {seed} silent errors", len(result["silent_errors"]) <= offline["silent_errors_max"], len(result["silent_errors"]), failures)
        check(f"seed {seed} defect precision", precision >= offline["defect_precision_accepted_min"], precision, failures)

    live = gates["live_ocr_summary"]
    path = ROOT / live["path"]
    if path.exists():
        summary = json.loads(path.read_text(encoding="utf-8"))
        ocr = summary["extraction"]["ocr_overall"]
        check("live OCR silent errors", summary["silent_errors"] <= live["silent_errors_max"], summary["silent_errors"], failures)
        check("live OCR field accuracy", ocr["field_accuracy"] >= live["ocr_field_accuracy_min"], ocr["field_accuracy"], failures)
        check("live OCR record recall", ocr["record_recall"] >= live["ocr_record_recall_min"], ocr["record_recall"], failures)
    else:
        print(f"[SKIP] live OCR summary not present: {live['path']}")

    risk = gates["risk_scoring"]
    report_path = ROOT / risk["report"]
    if report_path.exists():
        register = RemediationSupervisor(risk_model=load_risk_model()).run(
            reports=[json.loads(report_path.read_text(encoding="utf-8"))], as_of=date.fromisoformat(risk["as_of"]))
        for item in register["items"]:
            expected = risk["expected_scores"][item["status"]]
            check(f"risk score {item['gap_id']}", item["risk"]["score"] == expected, f"{item['risk']['score']} (expected {expected})", failures)
    else:
        print(f"[SKIP] risk scoring report not present: {risk['report']}")

    retrieval = gates["ai_labelled_retrieval"]
    if (ROOT / retrieval["labels"]).exists():
        packet = json.loads((ROOT / retrieval["packet"]).read_text(encoding="utf-8"))["packet"]
        labels = json.loads((ROOT / retrieval["labels"]).read_text(encoding="utf-8"))
        results = json.loads((ROOT / retrieval["results"]).read_text(encoding="utf-8"))
        scored = score_packet(packet, labels, results)  # also verifies corpus and ranking hashes
        target = next(t for t in results["targets"] if t["size"] == packet["size"] and t["status"] == "measured")
        relevant = {c["scenario_id"]: set(c["relevant_section_ids"]) for c in labels["cases"]}
        top5 = [set(target["methods"]["hybrid"][0]["attempts"][i]["ids"][:5]) for i in range(len(packet["queries"]))]
        precision = sum(len(t & relevant[q["scenario_id"]]) / 5 for t, q in zip(top5, packet["queries"], strict=True)) / len(top5)
        mrr = scored["recall_scores"]["10"]["methods"]["hybrid"]["mrr_at_k"]
        check("hybrid precision@5 (AI labels)", precision >= retrieval["hybrid_precision_at_5_min"], round(precision, 4), failures)
        check("hybrid MRR@10 (AI labels)", mrr >= retrieval["hybrid_mrr_at_10_min"], round(mrr, 4), failures)
    else:
        print(f"[SKIP] relevance labels not present: {retrieval['labels']}")

    print(f"\n{len(failures)} gate(s) failed" if failures else "\nAll gates passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
