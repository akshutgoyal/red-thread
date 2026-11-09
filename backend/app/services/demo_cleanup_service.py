from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (
    AiQuery,
    AuditEvent,
    Case,
    Entity,
    Event,
    EventEntity,
    Evidence,
    Finding,
    FindingEvidence,
    GraphEdge,
    InvestigatorAnnotation,
    Relationship,
    RelationshipSupport,
    Report,
    ReviewDecision,
)
from . import storage_service

logger = logging.getLogger("uvicorn.error")


def _safe_delete_object(key: str) -> None:
    try:
        storage_service.delete(key)
    except Exception:  # noqa: BLE001 - cleanup must continue
        logger.exception("Could not delete demo storage object %s", key)


def _delete_demo_case(db: Session, case: Case) -> None:
    evidence_keys = list(
        db.scalars(select(Evidence.relative_path).where(Evidence.case_id == case.id))
    )
    report_keys = list(
        db.scalars(select(Report.relative_path).where(Report.case_id == case.id))
    )
    for key in evidence_keys + report_keys:
        _safe_delete_object(key)

    relationship_ids = select(Relationship.id).where(Relationship.case_id == case.id)
    finding_ids = select(Finding.id).where(Finding.case_id == case.id)
    evidence_ids = select(Evidence.id).where(Evidence.case_id == case.id)
    event_ids = select(Event.id).where(Event.case_id == case.id)
    entity_ids = select(Entity.id).where(Entity.case_id == case.id)

    db.execute(
        delete(RelationshipSupport).where(
            RelationshipSupport.relationship_id.in_(relationship_ids)
        )
    )
    db.execute(delete(Relationship).where(Relationship.case_id == case.id))
    db.execute(delete(GraphEdge).where(GraphEdge.case_id == case.id))
    db.execute(delete(ReviewDecision).where(ReviewDecision.case_id == case.id))
    db.execute(delete(InvestigatorAnnotation).where(InvestigatorAnnotation.case_id == case.id))
    db.execute(
        delete(FindingEvidence).where(
            or_(
                FindingEvidence.finding_id.in_(finding_ids),
                FindingEvidence.evidence_id.in_(evidence_ids),
            )
        )
    )
    db.execute(
        delete(EventEntity).where(
            or_(
                EventEntity.event_id.in_(event_ids),
                EventEntity.entity_id.in_(entity_ids),
            )
        )
    )
    db.execute(delete(AiQuery).where(AiQuery.case_id == case.id))
    db.execute(delete(AuditEvent).where(AuditEvent.case_id == case.id))
    db.execute(delete(Finding).where(Finding.case_id == case.id))
    db.execute(delete(Entity).where(Entity.case_id == case.id))
    db.execute(delete(Event).where(Event.case_id == case.id))
    db.execute(delete(Evidence).where(Evidence.case_id == case.id))
    db.execute(delete(Report).where(Report.case_id == case.id))
    db.delete(case)
    db.commit()


def cleanup_expired_demo_copies(db: Session, older_than_hours: int | None = None) -> int:
    """Remove abandoned visitor-owned demo cases and their stored objects.

    The shared demo templates have no owner and are never removed. Only old
    visitor copies created by the former per-visitor demo implementation match.
    """
    settings = get_settings()
    ttl = settings.demo_copy_ttl_hours if older_than_hours is None else older_than_hours
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, ttl))
    cases = list(
        db.scalars(
            select(Case).where(
                Case.is_demo.is_(True),
                Case.owner_id.is_not(None),
                Case.created_at < cutoff,
            )
        )
    )
    for case in cases:
        _delete_demo_case(db, case)
    if cases:
        logger.info("Removed %s abandoned demo visitor copies.", len(cases))
    return len(cases)
