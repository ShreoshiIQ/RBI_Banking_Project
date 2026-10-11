from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from regintel.api.routes.auth import get_current_user
from regintel.changes.simulate import simulate

router = APIRouter(prefix="/changes", tags=["Change simulations"], dependencies=[Depends(get_current_user)])
ShortText = Annotated[str, Field(min_length=1, max_length=255)]
ClauseText = Annotated[str, Field(min_length=1, max_length=5000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Clause(StrictModel):
    clause_number: ShortText
    clause_text: ClauseText
    status: Literal["active", "deleted"] = "active"


class Baseline(StrictModel):
    document_id: ShortText
    content_hash: ShortText
    clauses: list[Clause] = Field(min_length=1, max_length=50)


class Edit(StrictModel):
    clause_number: ShortText
    operation: Literal["add", "modify", "remove"]
    clause_text: ClauseText | None = None


class Proposal(StrictModel):
    base_content_hash: ShortText
    edits: list[Edit] = Field(min_length=1, max_length=50)


class PolicySection(StrictModel):
    id: ShortText
    section_number: ShortText
    section_title: ShortText
    section_text: ClauseText
    synthetic: bool = True


class SimulationRequest(StrictModel):
    baseline: Baseline
    proposal: Proposal
    policy_sections: list[PolicySection] = Field(default_factory=list, max_length=50)


@router.post("/simulate")
def run_simulation(request: SimulationRequest) -> dict:
    try:
        return simulate(
            request.baseline.model_dump(), request.proposal.model_dump(exclude_none=True),
            [section.model_dump() for section in request.policy_sections],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
