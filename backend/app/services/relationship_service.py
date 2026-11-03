from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..models import Case, InvestigatorAnnotation, Relationship, RelationshipSupport, ReviewDecision
from ..schemas.relationship import AnnotationCreate
from . import audit_service

RELATIONSHIP_CLASSIFICATIONS = {"observation", "correlation", "inference", "hypothesis"}
RELATIONSHIP_DECISIONS = {"needs_review", "accepted", "rejected", "needs_more_evidence"}
RELATIONSHIP_REVIEW_STATUSES = {"unreviewed"} | RELATIONSHIP_DECISIONS
ANNOTATION_TARGET_TYPES = {
    "case",
    "evidence",
    "event",
    "entity",
    "finding",
    "relationship",
    "graph_edge",
}


def _relationship_query(case_id: str):
    return select(Relationship).where(Relationship.case_id == case_id)


def _with_supports(query):
    return query.options(selectinload(Relationship.supports))


def list_relationships(
    db: Session,
    case_id: str,
    *,
    relationship_type: str | None = None,
    classification: str | None = None,
    review_status: str | None = None,
    confidence: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> tuple[list[Relationship], int]:
    query = _relationship_query(case_id)
    if relationship_type:
        query = query.where(Relationship.relationship_type == relationship_type)
    if classification:
        query = query.where(Relationship.classification == classification)
    if review_status:
        query = query.where(Relationship.review_status == review_status)
    if confidence:
        query = query.where(Relationship.confidence == confidence)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(
        db.scalars(
            _with_supports(query)
            .order_by(Relationship.created_at.desc(), Relationship.id)
            .offset(offset)
            .limit(limit)
        )
    )
    return items, total


def get_relationship(db: Session, relationship_id: str, case_id: str) -> Relationship | None:
    return db.scalar(
        _with_supports(
            select(Relationship).where(
                Relationship.id == relationship_id,
                Relationship.case_id == case_id,
            )
        )
    )


def list_reviews(
    db: Session,
    case_id: str,
    target_type: str,
    target_id: str,
) -> list[ReviewDecision]:
    return list(
        db.scalars(
            select(ReviewDecision)
            .where(
                ReviewDecision.case_id == case_id,
                ReviewDecision.target_type == target_type,
                ReviewDecision.target_id == target_id,
            )
            .order_by(ReviewDecision.created_at.desc())
        )
    )


def upsert_relationship(
    db: Session,
    *,
    case_id: str,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    relationship_type: str,
    correlation_rule: str,
    explanation: str,
    confidence: str = "medium",
    classification: str = "correlation",
    metadata: dict[str, Any] | None = None,
    supports: list[dict[str, Any]] | None = None,
) -> Relationship:
    """Create or update a data-derived relationship and its provenance."""

    if db.get(Case, case_id) is None:
        raise ValueError("Case does not exist.")
    if classification not in RELATIONSHIP_CLASSIFICATIONS:
        raise ValueError(f"Unsupported relationship classification: {classification}")

    relationship = db.scalar(
        select(Relationship).where(
            Relationship.case_id == case_id,
            Relationship.source_type == source_type,
            Relationship.source_id == source_id,
            Relationship.target_type == target_type,
            Relationship.target_id == target_id,
            Relationship.relationship_type == relationship_type,
            Relationship.correlation_rule == correlation_rule,
        )
    )
    created = relationship is None
    if relationship is None:
        relationship = Relationship(
            case_id=case_id,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relationship_type=relationship_type,
            correlation_rule=correlation_rule,
        )
        db.add(relationship)
        db.flush()
    else:
        relationship.supports.clear()
        db.flush()

    relationship.explanation = explanation
    relationship.confidence = confidence
    relationship.classification = classification
    relationship.metadata_json = metadata or {}
    for support in supports or []:
        relationship.supports.append(
            RelationshipSupport(
                evidence_id=support.get("evidence_id"),
                event_id=support.get("event_id"),
                finding_id=support.get("finding_id"),
                source_locator=str(support.get("source_locator") or ""),
                snippet=str(support.get("snippet") or ""),
                support_kind=str(support.get("support_kind") or "evidence"),
            )
        )
    audit_service.record(
        db,
        case_id,
        "relationship.created" if created else "relationship.updated",
        details={
            "relationship_id": relationship.id,
            "relationship_type": relationship_type,
            "correlation_rule": correlation_rule,
            "classification": classification,
            "support_count": len(relationship.supports),
        },
    )
    db.commit()
    db.refresh(relationship)
    return relationship


def review_relationship(
    db: Session,
    relationship_id: str,
    case_id: str,
    *,
    decision: str,
    reviewer: str = "",
    note: str = "",
) -> Relationship | None:
    if decision not in RELATIONSHIP_DECISIONS:
        raise ValueError(f"Unsupported relationship review decision: {decision}")
    relationship = get_relationship(db, relationship_id, case_id)
    if relationship is None:
        return None
    relationship.review_status = decision
    relationship.review_note = note
    db.add(
        ReviewDecision(
            case_id=case_id,
            target_type="relationship",
            target_id=relationship.id,
            decision=decision,
            reviewer=reviewer,
            note=note,
        )
    )
    audit_service.record(
        db,
        case_id,
        "relationship.reviewed",
        details={
            "relationship_id": relationship.id,
            "decision": decision,
            "reviewer": reviewer,
            "note": note,
        },
    )
    db.commit()
    return get_relationship(db, relationship_id, case_id)


def create_annotation(
    db: Session,
    case_id: str,
    payload: AnnotationCreate,
) -> InvestigatorAnnotation:
    if db.get(Case, case_id) is None:
        raise ValueError("Case does not exist.")
    if payload.target_type not in ANNOTATION_TARGET_TYPES:
        raise ValueError(f"Unsupported annotation target: {payload.target_type}")
    annotation = InvestigatorAnnotation(
        case_id=case_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        author=payload.author,
        note=payload.note,
    )
    db.add(annotation)
    audit_service.record(
        db,
        case_id,
        "annotation.created",
        details={
            "annotation_id": annotation.id,
            "target_type": payload.target_type,
            "target_id": payload.target_id,
            "author": payload.author,
        },
    )
    db.commit()
    db.refresh(annotation)
    return annotation


def list_annotations(
    db: Session,
    case_id: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
) -> list[InvestigatorAnnotation]:
    query = select(InvestigatorAnnotation).where(InvestigatorAnnotation.case_id == case_id)
    if target_type:
        query = query.where(InvestigatorAnnotation.target_type == target_type)
    if target_id:
        query = query.where(InvestigatorAnnotation.target_id == target_id)
    return list(
        db.scalars(
            query.order_by(InvestigatorAnnotation.created_at.desc(), InvestigatorAnnotation.id)
        )
    )
