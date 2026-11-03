from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from .event import EntityRead, EventRead
from .finding import FindingRead
from .relationship import RelationshipRead


class EntityDetailResponse(BaseModel):
    entity: EntityRead
    events: list[EventRead]
    relationships: list[RelationshipRead]
    evidence_ids: list[str]
    mention_count: int


class SpatialObservation(BaseModel):
    event_id: str
    evidence_id: str
    event_type: str
    source_filename: str
    source_locator: str
    timestamp_normalized: datetime | None = None
    latitude: float
    longitude: float
    label: str = ""
    entity_ids: list[str] = []
    entity_values: list[str] = []


class SpatialResponse(BaseModel):
    observations: list[SpatialObservation]
    relationships: list[RelationshipRead]
    total: int


class ReconstructionCounts(BaseModel):
    evidence: int
    events: int
    entities: int
    relationships: int
    findings: int
    open_findings: int
    spatial_observations: int
    unreviewed_relationships: int


class ReconstructionResponse(BaseModel):
    case_id: str
    counts: ReconstructionCounts
    relationship_types: dict[str, int]
    review_statuses: dict[str, int]
    relationships: list[RelationshipRead]
    recent_events: list[EventRead]
    conflicts: list[FindingRead]
    unresolved: list[str]
    spatial_observations: list[SpatialObservation]
    generated_at: datetime
    limitations: list[str]
