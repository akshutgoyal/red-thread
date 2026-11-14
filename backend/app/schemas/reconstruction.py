from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

ConfidenceLevel = Literal["documented", "supported", "correlated", "uncertain"]


class SequenceEntity(BaseModel):
    id: str
    entity_type: str
    value: str
    role: str


class SequenceRelationship(BaseModel):
    id: str
    relationship_type: str
    explanation: str
    confidence: str
    classification: str
    review_status: str
    counterpart_type: str = ""
    counterpart_value: str = ""


class SequenceEvent(BaseModel):
    id: str
    timestamp: datetime | None = None
    timestamp_raw: str | None = None
    timestamp_confidence: str = "unknown"
    timestamp_timezone: str | None = None
    event_type: str
    category: str
    label: str
    description: str
    evidence_id: str
    source_filename: str
    source_locator: str
    source_snippet: str
    entities: list[SequenceEntity] = []
    relationships: list[SequenceRelationship] = []
    finding_ids: list[str] = []
    review_status: str = "unreviewed"
    review_note: str = ""
    group_ids: list[str] = []
    confidence: ConfidenceLevel = "uncertain"
    confidence_reason: str = ""


class SequenceGap(BaseModel):
    kind: str
    message: str
    start: datetime | None = None
    end: datetime | None = None


class ReconstructionSequenceResponse(BaseModel):
    case_id: str
    items: list[SequenceEvent]
    undated: list[SequenceEvent]
    total: int
    categories: dict[str, int] = {}
    groups: list[Any] = []
    gaps: list[SequenceGap] = []
    limitations: list[str] = []
