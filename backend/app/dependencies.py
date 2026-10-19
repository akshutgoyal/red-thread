from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import Case, Evidence
from .services import case_service, evidence_service


def require_api_token(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    access_token: str | None = Query(default=None, include_in_schema=False),
) -> None:
    settings = get_settings()
    if not settings.api_token:
        return
    token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_api_key:
        token = x_api_key.strip()
    elif access_token:
        token = access_token.strip()
    if token != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token.",
        )


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
