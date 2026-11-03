from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    evidence_id: str | None = None
    actor: str
    action: str
    details_json: dict[str, Any]
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    database: str
    ai_provider: str
    ai_configured: bool
    ocr_available: bool


class MessageResponse(BaseModel):
    message: str
