
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from regintel.api.role_dependencies import require_roles
from regintel.api.tenancy import get_tenant_db
from regintel.models.user import UserRecord
from regintel.reporting.review_service import review_gap_report

router = APIRouter(
    prefix="/gap-reports",
    tags=["Compliance Reviews"],
)


class ReviewRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str = Field(
        min_length=1,
        max_length=2000,
    )


class ReviewResponse(BaseModel):
    report_id: str
    reviewer_id: str
    decision: str
    message: str


@router.post(
    "/{report_id}/review",
    response_model=ReviewResponse,
)
def submit_review(
    report_id: str,
    request: ReviewRequest,
    db: Annotated[Session, Depends(get_tenant_db)],
    current_user: Annotated[
        UserRecord,
        Depends(require_roles("compliance_officer")),
    ],
) -> ReviewResponse:

    try:
        review_gap_report(
            db,
            report_id=report_id,
            reviewer_id=str(current_user.id),
            decision=request.decision,
            comment=request.comment.strip(),
        )

        db.commit()

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception:
        db.rollback()
        raise

    return ReviewResponse(
        report_id=report_id,
        reviewer_id=str(current_user.id),
        decision=request.decision,
        message="Review recorded successfully",
    )
