from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from ..schemas.auth_session import AuthResponse, AuthUserRead, GoogleLoginRequest
from ..services.auth_service import (
    clear_session_cookie,
    create_session_token,
    demo_principal,
    get_principal,
    principal_for_user,
    set_session_cookie,
    upsert_google_user,
    verify_google_credential,
)
from ..database import get_db
from sqlalchemy.orm import Session

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
def google_login(
    payload: GoogleLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    claims = verify_google_credential(payload.credential)
    user = upsert_google_user(db, claims)
    principal = principal_for_user(user)
    token = create_session_token(principal)
    set_session_cookie(response, token, request)
    return AuthResponse(user=_user_read(principal))


@router.post("/demo", response_model=AuthResponse)
def demo_login(request: Request, response: Response) -> AuthResponse:
    """Use the one shared synthetic demo workspace."""
    principal = demo_principal("demo-user")
    token = create_session_token(principal)
    set_session_cookie(response, token, request)
    return AuthResponse(user=_user_read(principal))


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    clear_session_cookie(response, request)
    return {"ok": True}


@router.get("/me", response_model=AuthUserRead)
def me(principal=Depends(get_principal)) -> AuthUserRead:
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return _user_read(principal)
