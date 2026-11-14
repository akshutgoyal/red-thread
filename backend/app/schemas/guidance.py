from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

StageStatus = Literal["complete", "in_progress", "not_started"]


class GuidanceStage(BaseModel):
    key: str
    index: int
    title: str
    description: str
    what_to_do: str
    output: str
    status: StageStatus
    href: str
    completed_count: int = 0
    total_count: int = 0
    next_step: str = ""
    detail: str = ""


class GuidanceAction(BaseModel):
    id: str
    title: str
    reason: str
    action_label: str
    href: str
    tone: Literal["info", "warning", "critical"] = "info"


class GuidanceAttention(BaseModel):
    kind: str
    title: str
    detail: str
    href: str
    count: int = 0


class GuidanceSummary(BaseModel):
    evidence: int = 0
    parsed: int = 0
    needs_attention: int = 0
    events: int = 0
    entities: int = 0
    open_findings: int = 0
    unreviewed_relationships: int = 0
    reports: int = 0
    # Canonical relationship counts. These are the same numbers the relationship
    # graph reports, so a connection count means one thing across the product.
    total_relationships: int = 0
    documented_relationships: int = 0
    inferred_leads: int = 0
    unique_connections: int = 0
    raw_edges: int = 0
    structural_edges: int = 0


class GuidanceResponse(BaseModel):
    case_id: str
    generated_at: datetime
    stages: list[GuidanceStage]
    next_action: GuidanceAction
    attention: list[GuidanceAttention] = Field(default_factory=list)
    summary: GuidanceSummary
    scanned_events: int = 0


class EventReviewRequest(BaseModel):
    decision: Literal["relevant", "not_relevant", "needs_review"]
    reviewer: str = Field(default="", max_length=128)
    note: str = ""


class EventReviewRead(BaseModel):
    event_id: str
    decision: str
    reviewer: str
    note: str
    reviewed_at: datetime


class EventReviewListResponse(BaseModel):
    items: list[EventReviewRead]
    total: int


class WarningDetail(BaseModel):
    message: str
    category: str
    impact: str
    recommendation: str
    can_use: bool
    source_locator: str = ""


class NarrativeItem(BaseModel):
    index: int
    statement: str
    kind: Literal["observation", "correlation", "finding", "review", "report"]
    timestamp: datetime | None = None
    event_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)
    href: str


class NarrativeResponse(BaseModel):
    case_id: str
    generated_at: datetime
    items: list[NarrativeItem] = Field(default_factory=list)
    disclaimer: str


class TimelineGroup(BaseModel):
    id: str
    title: str
    explanation: str
    event_ids: list[str] = Field(default_factory=list)
    relationship_id: str | None = None
    classification: str | None = None
    confidence: str | None = None
    start: datetime | None = None
    end: datetime | None = None


class TimelineEventMeta(BaseModel):
    finding_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)
    review_status: str | None = None
    suspicious: bool = False


class TimelineExtras(BaseModel):
    event_meta: dict[str, TimelineEventMeta] = Field(default_factory=dict)
    groups: list[TimelineGroup] = Field(default_factory=list)


class FindingEntityRef(BaseModel):
    entity_id: str
    entity_type: str
    value: str
    event_id: str | None = None


class FindingTimelineRef(BaseModel):
    event_id: str
    timestamp_normalized: datetime | None = None
    event_type: str


class AiSuggestion(BaseModel):
    question: str
    reason: str
