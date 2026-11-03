from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..models import Case, Entity, Event, EventEntity, Evidence, Finding, Relationship, RelationshipSupport
from ..schemas.analysis import (
    EntityDetailResponse,
    ReconstructionCounts,
    ReconstructionResponse,
    SpatialObservation,
    SpatialResponse,
)
from ..schemas.event import EntityRead, EventRead
from ..schemas.finding import FindingRead
from ..schemas.relationship import RelationshipRead
from ..utils.geo import parse_coordinates

RECONSTRUCTION_LIMITATIONS = [
    "Deterministic relationships are correlation candidates, not identity or guilt conclusions.",
    "Temporal and spatial proximity do not prove causation, co-location, or a relationship.",
    "AI-generated text is an interpretation and may be wrong; human review is required.",
    "Only coordinates documented in evidence are plotted; routes are never inferred.",
]


def _relationship_query(case_id: str):
    return (
        select(Relationship)
        .where(Relationship.case_id == case_id)
        .options(selectinload(Relationship.supports))
    )


def entity_detail(db: Session, case_id: str, entity_id: str) -> EntityDetailResponse | None:
    entity = db.get(Entity, entity_id)
    if entity is None or entity.case_id != case_id:
        return None
    links = list(
        db.scalars(
            select(EventEntity)
            .where(EventEntity.entity_id == entity.id)
            .options(selectinload(EventEntity.event))
            .order_by(EventEntity.event_id)
        )
    )
    events: list[Event] = []
    seen_events: set[str] = set()
    for link in links:
        if link.event is not None and link.event.id not in seen_events:
            seen_events.add(link.event.id)
            events.append(link.event)
    relationships = list(
        db.scalars(
            _relationship_query(case_id).where(
                or_(
                    (Relationship.source_type == "entity")
                    & (Relationship.source_id == entity.id),
                    (Relationship.target_type == "entity")
                    & (Relationship.target_id == entity.id),
                )
            )
        )
    )
    evidence_ids = {event.evidence_id for event in events}
    for relationship in relationships:
        evidence_ids.update(
            support.evidence_id
            for support in relationship.supports
            if support.evidence_id
        )
    return EntityDetailResponse(
        entity=EntityRead.model_validate(entity),
        events=[EventRead.model_validate(event) for event in events],
        relationships=[
            RelationshipRead.model_validate(item) for item in relationships
        ],
        evidence_ids=sorted(evidence_ids),
        mention_count=len(events),
    )


def spatial_observations(
    db: Session, case_id: str, *, entity_id: str | None = None
) -> tuple[list[SpatialObservation], list[Relationship]]:
    query = (
        select(Event)
        .where(Event.case_id == case_id)
        .options(selectinload(Event.entity_links).selectinload(EventEntity.entity))
        .order_by(Event.timestamp_normalized.is_(None), Event.timestamp_normalized.asc())
    )
    if entity_id:
        query = query.where(
            Event.id.in_(
                select(EventEntity.event_id).where(EventEntity.entity_id == entity_id)
            )
        )
    observations: list[SpatialObservation] = []
    for event in db.scalars(query):
        attributes = event.attributes_json or {}
        point = parse_coordinates(
            attributes.get("latitude"), attributes.get("longitude")
        )
        if point is None:
            continue
        entity_ids: list[str] = []
        entity_values: list[str] = []
        seen: set[str] = set()
        for link in event.entity_links:
            if link.entity is None or link.entity.id in seen:
                continue
            seen.add(link.entity.id)
            entity_ids.append(link.entity.id)
            entity_values.append(link.entity.value_original)
        observations.append(
            SpatialObservation(
                event_id=event.id,
                evidence_id=event.evidence_id,
                event_type=event.event_type,
                source_filename=event.source_filename,
                source_locator=event.source_locator,
                timestamp_normalized=event.timestamp_normalized,
                latitude=point[0],
                longitude=point[1],
                label=str(
                    attributes.get("place")
                    or attributes.get("site_name")
                    or attributes.get("location")
                    or ""
                ),
                entity_ids=entity_ids,
                entity_values=entity_values,
            )
        )
    spatial_relationships = list(
        db.scalars(
            _relationship_query(case_id).where(
                Relationship.relationship_type == "spatial_proximity"
            )
        )
    )
    return observations, spatial_relationships


def spatial(
    db: Session, case_id: str, *, entity_id: str | None = None
) -> SpatialResponse:
    observations, relationships = spatial_observations(
        db, case_id, entity_id=entity_id
    )
    return SpatialResponse(
        observations=observations,
        relationships=[RelationshipRead.model_validate(item) for item in relationships],
        total=len(observations),
    )


def reconstruction(db: Session, case_id: str) -> ReconstructionResponse:
    case = db.get(Case, case_id)
    if case is None:
        raise ValueError("Case not found.")
    evidence_count = (
        db.scalar(select(func.count(Evidence.id)).where(Evidence.case_id == case_id))
        or 0
    )
    event_count = (
        db.scalar(select(func.count(Event.id)).where(Event.case_id == case_id)) or 0
    )
    entity_count = (
        db.scalar(select(func.count(Entity.id)).where(Entity.case_id == case_id)) or 0
    )
    finding_count = (
        db.scalar(select(func.count(Finding.id)).where(Finding.case_id == case_id))
        or 0
    )
    open_findings = (
        db.scalar(
            select(func.count(Finding.id)).where(
                Finding.case_id == case_id, Finding.status == "open"
            )
        )
        or 0
    )
    relationships = list(db.scalars(_relationship_query(case_id)))
    relationship_types = dict(Counter(item.relationship_type for item in relationships))
    review_statuses = dict(Counter(item.review_status for item in relationships))
    unreviewed = sum(
        1 for item in relationships if item.review_status == "unreviewed"
    )
    observations, _spatial_relationships = spatial_observations(db, case_id)

    recent_events = list(
        db.scalars(
            select(Event)
            .where(Event.case_id == case_id)
            .order_by(Event.timestamp_normalized.is_(None), Event.timestamp_normalized.asc())
            .limit(25)
        )
    )
    conflict_filters = [
        Finding.case_id == case_id,
        or_(
            Finding.severity.in_(["high", "critical"]),
            Finding.category.ilike("%conflict%"),
            Finding.category.ilike("%discrep%"),
        ),
    ]
    conflicts = list(
        db.scalars(
            select(Finding)
            .where(*conflict_filters)
            .options(selectinload(Finding.evidence_links))
            .order_by(Finding.created_at.desc())
            .limit(20)
        )
    )
    undated = (
        db.scalar(
            select(func.count(Event.id)).where(
                Event.case_id == case_id, Event.timestamp_normalized.is_(None)
            )
        )
        or 0
    )
    unresolved: list[str] = []
    if open_findings:
        unresolved.append(f"{open_findings} finding(s) remain open for investigator review.")
    if unreviewed:
        unresolved.append(f"{unreviewed} relationship(s) have not been reviewed.")
    if undated:
        unresolved.append(f"{undated} event(s) lack a normalized timestamp.")
    if not relationships:
        unresolved.append("No deterministic relationships have been generated yet.")
    if not observations:
        unresolved.append("No documented coordinates are available for spatial reconstruction.")

    counts = ReconstructionCounts(
        evidence=evidence_count,
        events=event_count,
        entities=entity_count,
        relationships=len(relationships),
        findings=finding_count,
        open_findings=open_findings,
        spatial_observations=len(observations),
        unreviewed_relationships=unreviewed,
    )
    return ReconstructionResponse(
        case_id=case_id,
        counts=counts,
        relationship_types=relationship_types,
        review_statuses=review_statuses,
        relationships=[RelationshipRead.model_validate(item) for item in relationships[:60]],
        recent_events=[EventRead.model_validate(event) for event in recent_events],
        conflicts=[FindingRead.model_validate(item) for item in conflicts],
        unresolved=unresolved,
        spatial_observations=observations[:40],
        generated_at=datetime.now(timezone.utc),
        limitations=RECONSTRUCTION_LIMITATIONS,
    )
