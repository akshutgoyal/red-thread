from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.auth_service import AuthPrincipal, get_principal
from ..dependencies import get_case_or_404
from ..schemas.case import CaseCreate, CaseRead, CaseSummary, CaseUpdate
from ..services import audit_service, case_service
from ..services.demo_seed_service import DEMO_TEMPLATE_TITLES

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    principal: AuthPrincipal | None = Depends(get_principal),
) -> CaseRead:
    is_demo = bool(principal and principal.is_demo)
    owner_id = None if principal is None or principal.is_demo else principal.user_id
    case = case_service.create_case(
        db,
        payload,
        owner_id=owner_id,
        is_demo=is_demo,
    )
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
def list_cases(
    db: Session = Depends(get_db),
    principal: AuthPrincipal | None = Depends(get_principal),
) -> list[CaseSummary]:
    if principal is None:
        cases = case_service.list_cases(db)
    elif principal.is_demo:
        cases = case_service.list_cases(db, demo_templates=True)
    else:
        cases = case_service.list_cases(db, owner_id=principal.user_id)
    return [case_service.summarize_case(db, case) for case in cases]


@router.delete("/{case_id}", status_code=status.HTTP_200_OK)
def delete_case(
    case_id: str,
    db: Session = Depends(get_db),
    principal: AuthPrincipal | None = Depends(get_principal),
) -> dict[str, object]:
    """Permanently delete a case and everything derived from it.

    The shared synthetic demo templates are protected: they are re-created by the
    startup seed, and deleting one only makes the demo inconsistent until the next
    restart. Cases created *inside* a demo session are deletable, which is what
    lets a visitor clean up their own working case.
    """

    case = get_case_or_404(db, case_id)
    if case.is_demo and case.title in DEMO_TEMPLATE_TITLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The shared demo cases cannot be deleted.",
        )
    if principal is not None and not principal.is_demo and case.owner_id != principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this case.",
        )

    title = case.title
    removed = case_service.delete_case(db, case)
    return {"deleted": True, "case_id": case_id, "title": title, "removed": removed}


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
