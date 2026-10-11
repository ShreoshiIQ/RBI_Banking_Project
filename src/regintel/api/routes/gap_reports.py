
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from regintel.agents.supervisor import RemediationSupervisor
from regintel.api.routes.auth import get_current_user
from regintel.api.schemas import (
    GapReportDetailResponse,
    GapReportListItem,
    GapReportListResponse,
    ReviewHistoryItem,
    ReviewHistoryResponse,
)
from regintel.api.tenancy import get_tenant_db
from regintel.models.gap_report import RegulatoryGapReportRecord
from regintel.prioritization.risk import load_risk_model
from regintel.reporting.review_service import get_review_history

router = APIRouter(
    prefix="/gap-reports",
    tags=["Regulatory Gap Reports"],
    dependencies=[Depends(get_current_user)],
)

DbSession = Annotated[Session, Depends(get_tenant_db)]


@router.get(
    "",
    response_model=GapReportListResponse,
)
def list_gap_reports(
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    total = db.scalar(
        select(func.count())
        .select_from(RegulatoryGapReportRecord)
    ) or 0

    records = db.scalars(
        select(RegulatoryGapReportRecord)
        .order_by(
            RegulatoryGapReportRecord.created_at.desc(),
            RegulatoryGapReportRecord.report_id,
        )
        .limit(limit)
        .offset(offset)
    ).all()

    return GapReportListResponse(
        items=[
            GapReportListItem.model_validate(record)
            for record in records
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{report_id}",
    response_model=GapReportDetailResponse,
)
def get_gap_report_detail(
    report_id: str,
    db: DbSession,
):
    record = db.get(
        RegulatoryGapReportRecord,
        report_id,
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Gap report not found",
        )

    return GapReportDetailResponse(
        report_id=record.report_id,
        regulatory_reference=record.regulatory_reference,
        assessment_status=record.assessment_status,
        review_status=record.review_status,
        report=record.report_json,
    )


@router.get("/{report_id}/remediation-plan")
def get_remediation_plan(
    report_id: str,
    db: DbSession,
    as_of: date | None = None,
):
    # Template drafts only: no model calls on the request path.
    record = db.get(
        RegulatoryGapReportRecord,
        report_id,
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Gap report not found",
        )

    return RemediationSupervisor(
        risk_model=load_risk_model(),
    ).run(
        reports=[record.report_json],
        as_of=as_of,
    )


@router.get(
    "/{report_id}/reviews",
    response_model=ReviewHistoryResponse,
)
def list_report_reviews(
    report_id: str,
    db: DbSession,
):
    record = db.get(
        RegulatoryGapReportRecord,
        report_id,
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Gap report not found",
        )

    reviews = get_review_history(
        db,
        report_id,
    )

    return ReviewHistoryResponse(
        report_id=report_id,
        reviews=[
            ReviewHistoryItem.model_validate(review)
            for review in reviews
        ],
    )
