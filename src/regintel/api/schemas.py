
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class GapReportListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: str
    regulatory_reference: str
    assessment_status: str
    review_status: str
    created_at: datetime


class GapReportListResponse(BaseModel):
    items: list[GapReportListItem]
    total: int
    limit: int
    offset: int


class GapReportDetailResponse(BaseModel):
    report_id: str
    regulatory_reference: str
    assessment_status: str
    review_status: str
    report: dict[str, Any]


class ReviewHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_id: str
    reviewer_id: str
    previous_status: str
    new_status: str
    comment: str
    reviewed_at: datetime


class ReviewHistoryResponse(BaseModel):
    report_id: str
    reviews: list[ReviewHistoryItem]
