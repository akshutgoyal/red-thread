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
    token: str
    user: AuthUserRead
