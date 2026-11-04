from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.auth_session import AuthResponse, AuthUserRead, GoogleLoginRequest
from ..services.auth_service import (
    DEMO_PRINCIPAL,
    create_session_token,
    get_principal,
    principal_for_user,
    upsert_google_user,
    verify_google_credential,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_read(principal) -> AuthUserRead:
    return AuthUserRead(
        id=principal.user_id,
        email=principal.email,
        name=principal.name,
        picture=principal.picture,
        is_demo=principal.is_demo,
    )


@router.post("/google", response_model=AuthResponse)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    claims = verify_google_credential(payload.credential)
    user = upsert_google_user(db, claims)
    principal = principal_for_user(user)
    return AuthResponse(token=create_session_token(principal), user=_user_read(principal))


@router.post("/demo", response_model=AuthResponse)
def demo_login() -> AuthResponse:
    return AuthResponse(token=create_session_token(DEMO_PRINCIPAL), user=_user_read(DEMO_PRINCIPAL))


@router.get("/me", response_model=AuthUserRead)
def me(principal=Depends(get_principal)) -> AuthUserRead:
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return _user_read(principal)
