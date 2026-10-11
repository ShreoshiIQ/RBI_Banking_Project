from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from regintel.api.routes.auth import get_current_user
from regintel.crossreg.contradictions import detect

router = APIRouter(prefix="/cross-regulation", tags=["Cross-regulation"], dependencies=[Depends(get_current_user)])
ShortText = Annotated[str, Field(min_length=1, max_length=255)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Provision(StrictModel):
    regulator: ShortText
    ref: ShortText
    text: Annotated[str, Field(min_length=1, max_length=5000)]


class CompareRequest(StrictModel):
    a: Provision
    b: Provision


@router.post("/compare")
def compare_provisions(request: CompareRequest):
    # Deterministic detectors only; no model calls on the request path.
    a = {**request.a.model_dump(), "provision_id": f"a:{request.a.regulator}:{request.a.ref}"}
    b = {**request.b.model_dump(), "provision_id": f"b:{request.b.regulator}:{request.b.ref}"}
    return {
        "findings": [{**f, "status": "candidate", "review_status": "pending"} for f in detect(a, b)],
        "notice": "Detector candidates for legal review; not confirmed conflicts or applicability decisions.",
    }
