from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AiStatusResponse(BaseModel):
    configured: bool
    provider: str
    model: str
    model_label: str
    base_url_host: str
    reason: str
    live_check: dict[str, Any] | None = None


class AiAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class AiCitationRead(BaseModel):
    kind: str
    id: str
    label: str
    evidence_id: str | None = None
    event_id: str | None = None
    source_locator: str | None = None
    verified: bool
    warning: str | None = None


class AiAnswerResponse(BaseModel):
    answer: str
    citations: list[AiCitationRead]
    uncertainties: list[str]
    alternative_explanations: list[str]
    suggested_next_steps: list[str]
    insufficient_evidence: bool
    provider: str
    model: str
    model_label: str
    ai_generated: bool = True
    usage: dict[str, Any] = Field(default_factory=dict)
