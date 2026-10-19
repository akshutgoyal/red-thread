from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_case_or_404
from ..schemas.case import CaseCreate, CaseRead, CaseSummary, CaseUpdate
from ..services import audit_service, case_service

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreate, db: Session = Depends(get_db)) -> CaseRead:
    case = case_service.create_case(db, payload)
    audit_service.record(
        db,
        case.id,
        "case.created",
        details={"title": case.title, "status": case.status},
    )
    db.commit()
    db.refresh(case)
    return case


@router.get("", response_model=list[CaseSummary])
def list_cases(db: Session = Depends(get_db)) -> list[CaseSummary]:
    return [case_service.summarize_case(db, case) for case in case_service.list_cases(db)]


@router.get("/{case_id}", response_model=CaseSummary)
def get_case(case_id: str, db: Session = Depends(get_db)) -> CaseSummary:
    case = get_case_or_404(db, case_id)
    return case_service.summarize_case(db, case)


@router.patch("/{case_id}", response_model=CaseRead)
def update_case(
    case_id: str,
    payload: CaseUpdate,
    db: Session = Depends(get_db),
) -> CaseRead:
    case = get_case_or_404(db, case_id)
    updated = case_service.update_case(db, case, payload)
    audit_service.record(
        db,
        case.id,
        "case.updated",
        details=payload.model_dump(exclude_unset=True),
    )
    db.commit()
    db.refresh(updated)
    return updated
