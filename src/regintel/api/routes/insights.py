"""Read-only views of measured results and monitoring outputs for the web app.

Files live under the data root (DATA_ROOT, default: working directory).
A missing file yields {"available": false} rather than an error, so the app works
in deployments without the data volume.
"""

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from regintel.api.routes.auth import get_current_user
from regintel.core.config import get_settings

router = APIRouter(prefix="/insights", tags=["Insights"], dependencies=[Depends(get_current_user)])

EVIDENCE = "data/processed/validation/evidence_pack_v2/summary.json"
RETRIEVAL = "data/processed/validation/ai_labelled_retrieval_summary.json"
CROSSREG = "data/processed/crossreg/cross_regulation_report.json"
EVENTS = "data/processed/watch/events.jsonl"
GATES = "eval_gates.json"


def root() -> Path:
    return Path(get_settings().data_root or ".").resolve()


def read_json(relative: str) -> dict | None:
    path = root() / relative
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def unavailable(relative: str) -> dict:
    return {"available": False, "reason": f"{relative} not found under the data root"}


@router.get("/summary")
def summary():
    evidence, retrieval, gates = read_json(EVIDENCE), read_json(RETRIEVAL), read_json(GATES)
    return {
        "evidence": {"available": True, **evidence} if evidence else unavailable(EVIDENCE),
        "retrieval": {"available": True, **retrieval} if retrieval else unavailable(RETRIEVAL),
        "gates": {"available": True, **gates} if gates else unavailable(GATES),
    }


@router.get("/watch-events")
def watch_events(limit: Annotated[int, Query(ge=1, le=200)] = 50):
    path = root() / EVENTS
    if not path.is_file():
        return {**unavailable(EVENTS), "items": []}
    lines = path.read_text(encoding="utf-8").splitlines()
    items = [json.loads(line) for line in reversed(lines) if line.strip()][:limit]
    keep = ("event_id", "detected_at", "notification_id", "title", "link", "published",
            "classification", "applicability", "impact", "review_status")
    return {"available": True, "total": len(lines), "items": [{k: e.get(k) for k in keep} for e in items]}


@router.get("/applicability")
def applicability():
    from regintel.applicability.engine import determine_all
    try:
        items = determine_all(root())
    except FileNotFoundError as exc:
        return {"available": False, "reason": str(exc), "items": []}
    return {"available": True, "items": items,
            "notice": "Only an officer decision yields 'applicable'; machine rules yield presumed statuses."}


@router.get("/cross-regulation")
def cross_regulation(families: Annotated[int, Query(ge=1, le=100)] = 25):
    report = read_json(CROSSREG)
    if report is None:
        return {**unavailable(CROSSREG), "families": [], "contradiction_candidates": []}
    return {"available": True, "summary": report["summary"], "corpus": report["corpus"], "method": report["method"],
            "families": report["families"][:families], "contradiction_candidates": report["contradiction_candidates"],
            "notice": report["notice"]}
