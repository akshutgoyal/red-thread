from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    uploaded_at: datetime
    parser_name: str | None = None
    parser_version: str | None = None
    processing_status: str
    processing_error: str | None = None
    metadata_json: dict[str, Any]
    hash_verified: bool
    hash_verified_at: datetime | None = None


class HashVerifyResponse(BaseModel):
    evidence_id: str
    expected_sha256: str
    actual_sha256: str
    verified: bool
    checked_at: datetime
    message: str


class ParseResponse(BaseModel):
    evidence_id: str
    parser_name: str
    parser_version: str
    events_created: int
    findings_created: int
    warnings: list[str]
    summary: dict[str, Any]
    status: str
