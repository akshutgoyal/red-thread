from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

FindingStatus = Literal["open", "needs_review", "accepted", "rejected", "needs_more_evidence"]


class FindingEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evidence_id: str
    event_id: str | None = None
    role: str
    source_locator: str


class FindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    severity: str
    category: str
    title: str
    explanation: str
    detection_method: str
    confidence: str
    status: str
    limitations: str
    alternative_explanations: str
    reviewer_note: str
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    evidence_links: list[FindingEvidenceRead] = []


class FindingListResponse(BaseModel):
    items: list[FindingRead]
    total: int


class FindingReviewRequest(BaseModel):
    status: FindingStatus
    reviewer_note: str = ""
