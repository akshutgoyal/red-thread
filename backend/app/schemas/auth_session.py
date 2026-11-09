from __future__ import annotations

from pydantic import BaseModel, Field


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=1)


class AuthUserRead(BaseModel):
    id: str
    email: str
    name: str
    picture: str | None = None
    is_demo: bool = False


class AuthResponse(BaseModel):
    """Login response.

    ``token`` is intentionally omitted: the session lives in an HttpOnly cookie
    so page scripts and XSS payloads cannot read it. The field remains optional
    so older clients that read it do not crash.
    """

    token: str | None = None
    user: AuthUserRead
