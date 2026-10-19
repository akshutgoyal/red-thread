from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    evidence_id: str
    event_type: str
    timestamp_raw: str | None = None
    timestamp_normalized: datetime | None = None
    timestamp_confidence: str
    timestamp_timezone: str | None = None
    source_filename: str
    source_locator: str
    source_snippet: str
    attributes_json: dict[str, Any]
    warnings_json: list[Any]
    parser_name: str
    parser_version: str
    created_at: datetime


class EventListResponse(BaseModel):
    items: list[EventRead]
    total: int
    limit: int
    offset: int


class TimelineResponse(BaseModel):
    items: list[EventRead]
    undated: list[EventRead]
    total: int


class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    entity_type: str
    value_original: str
    value_normalized: str
    normalization_method: str


class GraphNodeRead(BaseModel):
    id: str
    label: str
    node_type: str
    data: dict[str, Any] = {}


class GraphEdgeRead(BaseModel):
    id: str
    source: str
    target: str
    label: str
    edge_type: str
    match_method: str
    explanation: str
    confidence: str
    supporting_event_ids: list[str] = []
    supporting_evidence_ids: list[str] = []


class GraphResponse(BaseModel):
    nodes: list[GraphNodeRead]
    edges: list[GraphEdgeRead]
