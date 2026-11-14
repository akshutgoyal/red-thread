from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    Entity,
    Event,
    EventEntity,
    Evidence,
    GraphEdge,
    Relationship,
    RelationshipSupport,
)

#: Classifications backed by source evidence rather than analyst reasoning.
DOCUMENTED_CLASSIFICATIONS = ("observation", "correlation")
#: Classifications that are investigative leads requiring further verification.
INFERRED_CLASSIFICATIONS = ("inference", "hypothesis")


@dataclass(frozen=True)
class CaseCounts:
    """Canonical counts for one case.

    Every surface that displays a count reads this object, so the workspace, the
    dashboard and the relationship graph cannot drift apart. Each field has one
    meaning:

    ``total_relationships``
        Every persisted ``Relationship`` row in the case.
    ``documented_relationships``
        Relationships classified as an observation or a correlation, i.e. backed
        by source records.
    ``inferred_leads``
        Relationships classified as inference or hypothesis. Leads, not facts.
    ``unique_connections``
        Distinct entity pairs among persisted relationships. Two rows describing
        the same pair under different rules count once here.
    ``raw_edges``
        Persisted ``GraphEdge`` rows from the reconciliation pass, before they
        are expressed as relationships.
    ``containment_edges``
        Structural edges derived from stored rows: evidence containing an event,
        and an event mentioning an entity. Structural, not investigative.
    """

    evidence: int = 0
    events: int = 0
    dated_events: int = 0
    entities: int = 0
    entities_with_events: int = 0
    total_relationships: int = 0
    documented_relationships: int = 0
    inferred_leads: int = 0
    unreviewed_relationships: int = 0
    unique_connections: int = 0
    raw_edges: int = 0
    containment_edges: int = 0
    relationship_supports: int = 0


def case_counts(db: Session, case_id: str) -> CaseCounts:
    evidence_count = _scalar(
        db, select(func.count()).select_from(Evidence).where(Evidence.case_id == case_id)
    )
    event_count = _scalar(
        db, select(func.count()).select_from(Event).where(Event.case_id == case_id)
    )
    dated_event_count = _scalar(
        db,
        select(func.count())
        .select_from(Event)
        .where(Event.case_id == case_id, Event.timestamp_normalized.is_not(None)),
    )
    entity_count = _scalar(
        db, select(func.count()).select_from(Entity).where(Entity.case_id == case_id)
    )
    entities_with_events = _scalar(
        db,
        select(func.count(func.distinct(EventEntity.entity_id)))
        .select_from(EventEntity)
        .join(Event, Event.id == EventEntity.event_id)
        .where(Event.case_id == case_id),
    )
    mention_count = _scalar(
        db,
        select(func.count())
        .select_from(EventEntity)
        .join(Event, Event.id == EventEntity.event_id)
        .where(Event.case_id == case_id),
    )

    rows = list(
        db.execute(
            select(
                Relationship.classification,
                Relationship.source_type,
                Relationship.source_id,
                Relationship.target_type,
                Relationship.target_id,
                Relationship.review_status,
            ).where(Relationship.case_id == case_id)
        )
    )

    documented = sum(1 for row in rows if row.classification in DOCUMENTED_CLASSIFICATIONS)
    inferred = sum(1 for row in rows if row.classification in INFERRED_CLASSIFICATIONS)
    unreviewed = sum(1 for row in rows if row.review_status == "unreviewed")

    pairs = {
        _pair_key(row.source_type, row.source_id, row.target_type, row.target_id)
        for row in rows
    }

    raw_edges = _scalar(
        db, select(func.count()).select_from(GraphEdge).where(GraphEdge.case_id == case_id)
    )
    supports = _scalar(
        db,
        select(func.count())
        .select_from(RelationshipSupport)
        .join(Relationship, Relationship.id == RelationshipSupport.relationship_id)
        .where(Relationship.case_id == case_id),
    )

    return CaseCounts(
        evidence=evidence_count,
        events=event_count,
        dated_events=dated_event_count,
        entities=entity_count,
        entities_with_events=entities_with_events,
        total_relationships=len(rows),
        documented_relationships=documented,
        inferred_leads=inferred,
        unreviewed_relationships=unreviewed,
        unique_connections=len(pairs),
        raw_edges=raw_edges,
        containment_edges=evidence_count + mention_count,
        relationship_supports=supports,
    )


def _pair_key(
    source_type: str, source_id: str, target_type: str, target_id: str
) -> tuple[str, str]:
    """Order-independent key so A→B and B→A describe one connection."""

    left = f"{source_type}:{source_id}"
    right = f"{target_type}:{target_id}"
    return (left, right) if left <= right else (right, left)


def _scalar(db: Session, statement) -> int:
    return int(db.scalar(statement) or 0)
