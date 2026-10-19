from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CaseStatus = Literal["open", "in_review", "closed"]


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    investigator_notes: str = ""


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: CaseStatus | None = None
    investigator_notes: str | None = None


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    status: str
    investigator_notes: str
    created_at: datetime
    updated_at: datetime


class CaseSummary(CaseRead):
    evidence_count: int = 0
    event_count: int = 0
    finding_count: int = 0
    open_finding_count: int = 0
