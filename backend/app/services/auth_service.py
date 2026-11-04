from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..database import get_db
from ..models import Case, User

PUBLIC_PATH_PREFIXES = ("/api/auth/", "/api/auth", "/api/health", "/docs", "/redoc", "/openapi.json")


@dataclass(frozen=True)
class AuthPrincipal:
    user_id: str
    email: str
    name: str
    picture: str | None = None
    is_demo: bool = False


def _settings() -> Settings:
    return get_settings()


def create_session_token(principal: AuthPrincipal, settings: Settings | None = None) -> str:
    settings = settings or _settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": principal.user_id,
        "email": principal.email,
        "name": principal.name,
        "picture": principal.picture,
        "is_demo": principal.is_demo,
        "iat": now,
        "exp": now + timedelta(hours=settings.session_ttl_hours),
    }
    return jwt.encode(payload, settings.session_secret, algorithm="HS256")


def decode_session_token(token: str, settings: Settings | None = None) -> AuthPrincipal:
    settings = settings or _settings()
    try:
        payload = jwt.decode(token, settings.session_secret, algorithms=["HS256"])
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session.") from error
    user_id = str(payload.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session.")
    return AuthPrincipal(
        user_id=user_id,
        email=str(payload.get("email") or ""),
        name=str(payload.get("name") or ""),
        picture=payload.get("picture"),
        is_demo=bool(payload.get("is_demo")),
    )


def get_principal(request: Request) -> AuthPrincipal | None:
    """Return the authenticated principal, or None when auth is disabled."""
    settings = _settings()
    authorization = request.headers.get("Authorization", "")
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    if token:
        return decode_session_token(token, settings)
    if settings.auth_required:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return None


def _is_public_path(path: str) -> bool:
    if path == "/":
        return True
    return any(path == prefix or path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def authorize_request(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthPrincipal | None:
    """Global auth gate; also blocks cross-account case access."""
    settings = _settings()
    if _is_public_path(request.url.path):
        return None

    principal = get_principal(request)
    request.state.principal = principal
    if principal is None:
        return None

    case_id = (
        request.path_params.get("case_id")
        or request.query_params.get("case_id")
        or request.headers.get("X-Case-ID")
    )
    if not case_id:
        return principal

    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")
    if principal.is_demo:
        allowed = case.is_demo
    else:
        allowed = case.owner_id == principal.user_id
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this case.")
    return principal


def verify_google_credential(credential: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or _settings()
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured on this server.",
        )
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        claims = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except Exception as error:  # noqa: BLE001 - provider failures become 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google credential could not be verified.",
        ) from error
    if not claims.get("email_verified"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google email is not verified.")
    return claims


def upsert_google_user(db: Session, claims: dict[str, Any]) -> User:
    google_sub = str(claims.get("sub") or "")
    if not google_sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google subject is missing.")
    user = db.scalar(select(User).where(User.google_sub == google_sub))
    if user is None:
        user = User(
            google_sub=google_sub,
            email=str(claims.get("email") or ""),
            name=str(claims.get("name") or claims.get("email") or ""),
            picture=claims.get("picture"),
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
    else:
        user.email = str(claims.get("email") or user.email)
        user.name = str(claims.get("name") or user.name)
        user.picture = claims.get("picture") or user.picture
        user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def principal_for_user(user: User) -> AuthPrincipal:
    return AuthPrincipal(
        user_id=user.id,
        email=user.email,
        name=user.name,
        picture=user.picture,
        is_demo=False,
    )


DEMO_PRINCIPAL = AuthPrincipal(
    user_id="demo-user",
    email="demo@red-thread.local",
    name="Demo Investigator",
    is_demo=True,
)
