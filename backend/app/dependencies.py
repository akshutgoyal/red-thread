from __future__ import annotations

from fastapi import Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import Case, Evidence
from .services import case_service, evidence_service


def require_case_id(
    case_id: str | None = Query(default=None),
    x_case_id: str | None = Header(default=None, alias="X-Case-ID"),
) -> str:
    value = (case_id or x_case_id or "").strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A case_id query parameter or X-Case-ID header is required.",
        )
    return value


def get_case_or_404(db: Session, case_id: str) -> Case:
    case = case_service.get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return case


def get_evidence_or_404(db: Session, evidence_id: str, case_id: str) -> Evidence:
    evidence = evidence_service.get_evidence(db, evidence_id, case_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found in this case.")
    return evidence


def db_session() -> Session:
    yield from get_db()
