from __future__ import annotations

import logging

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

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
from ..schemas.case import CaseCreate, CaseSummary, CaseUpdate
from . import storage_service

logger = logging.getLogger("uvicorn.error")


def _safe_delete_object(key: str) -> None:
    try:
        storage_service.delete(key)
    except Exception:  # noqa: BLE001 - deletion must continue past a missing object
        logger.exception("Could not delete storage object %s", key)


def create_case(
    db: Session,
    payload: CaseCreate,
    *,
    owner_id: str | None = None,
    is_demo: bool = False,
) -> Case:
    case = Case(
        title=payload.title.strip(),
        description=payload.description,
        investigator_notes=payload.investigator_notes,
        owner_id=owner_id,
        is_demo=is_demo,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def list_cases(
    db: Session,
    *,
    owner_id: str | None = None,
    is_demo: bool | None = None,
    demo_templates: bool = False,
) -> list[Case]:
    statement = select(Case)
    if demo_templates:
        statement = statement.where(Case.is_demo.is_(True), Case.owner_id.is_(None))
    elif is_demo is True:
        statement = statement.where(Case.is_demo.is_(True))
    elif owner_id:
        statement = statement.where(Case.owner_id == owner_id)
    return list(db.scalars(statement.order_by(Case.created_at.desc())))


def get_case(db: Session, case_id: str) -> Case | None:
    return db.get(Case, case_id)


def delete_case(db: Session, case: Case) -> dict[str, int]:
    """Permanently remove a case and everything derived from it.

    Children are deleted explicitly rather than relying on database cascades, so
    the behaviour is identical on SQLite and Postgres. Stored evidence files and
    generated reports are removed from the storage backend first; a failure
    there is logged and does not block the database cleanup.

    Returns a summary of what was removed, for the audit record.
    """

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

    removed = {
        "evidence": int(
            db.scalar(select(func.count(Evidence.id)).where(Evidence.case_id == case.id))
            or 0
        ),
        "events": int(
            db.scalar(select(func.count(Event.id)).where(Event.case_id == case.id)) or 0
        ),
        "findings": int(
            db.scalar(select(func.count(Finding.id)).where(Finding.case_id == case.id))
            or 0
        ),
        "relationships": int(
            db.scalar(
                select(func.count(Relationship.id)).where(Relationship.case_id == case.id)
            )
            or 0
        ),
    }

    db.execute(
        delete(RelationshipSupport).where(
            RelationshipSupport.relationship_id.in_(relationship_ids)
        )
    )
    db.execute(delete(Relationship).where(Relationship.case_id == case.id))
    db.execute(delete(GraphEdge).where(GraphEdge.case_id == case.id))
    db.execute(delete(ReviewDecision).where(ReviewDecision.case_id == case.id))
    db.execute(
        delete(InvestigatorAnnotation).where(InvestigatorAnnotation.case_id == case.id)
    )
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
    return removed


def update_case(db: Session, case: Case, payload: CaseUpdate) -> Case:
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is not None:
            setattr(case, key, value)
    db.commit()
    db.refresh(case)
    return case


def summarize_case(db: Session, case: Case) -> CaseSummary:
    evidence_count = db.scalar(
        select(func.count(Evidence.id)).where(Evidence.case_id == case.id)
    ) or 0
    event_count = db.scalar(
        select(func.count(Event.id)).where(Event.case_id == case.id)
    ) or 0
    finding_count = db.scalar(
        select(func.count(Finding.id)).where(Finding.case_id == case.id)
    ) or 0
    open_finding_count = db.scalar(
        select(func.count(Finding.id)).where(
            Finding.case_id == case.id, Finding.status.in_(["open", "needs_review"])
        )
    ) or 0
    return CaseSummary(
        id=case.id,
        title=case.title,
        description=case.description,
        status=case.status,
        investigator_notes=case.investigator_notes,
        is_demo=case.is_demo,
        created_at=case.created_at,
        updated_at=case.updated_at,
        evidence_count=evidence_count,
        event_count=event_count,
        finding_count=finding_count,
        open_finding_count=open_finding_count,
    )
