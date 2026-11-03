from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Case, Event, Evidence, Finding
from ..schemas.case import CaseCreate, CaseSummary, CaseUpdate


def create_case(db: Session, payload: CaseCreate) -> Case:
    case = Case(
        title=payload.title.strip(),
        description=payload.description,
        investigator_notes=payload.investigator_notes,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def list_cases(db: Session) -> list[Case]:
    return list(db.scalars(select(Case).order_by(Case.created_at.desc())))


def get_case(db: Session, case_id: str) -> Case | None:
    return db.get(Case, case_id)


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
        created_at=case.created_at,
        updated_at=case.updated_at,
        evidence_count=evidence_count,
        event_count=event_count,
        finding_count=finding_count,
        open_finding_count=open_finding_count,
    )
