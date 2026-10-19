from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuthEventRead(BaseModel):
    event_id: str
    event_type: str
    timestamp_raw: str | None = None
    timestamp_normalized: datetime | None = None
    timestamp_confidence: str
    timestamp_timezone: str | None = None
    source_ip: str | None = None
    username: str | None = None
    auth_status: str | None = None
    auth_method: str | None = None
    pid: str | None = None
    port: int | None = None
    invalid_user: bool = False
    session_event: str | None = None
    sudo_target_user: str | None = None
    sudo_command: str | None = None
    source_line_number: int | None = None
    source_locator: str
    warnings: list[str] = []
    attributes: dict[str, Any] = {}


class AuthAlertRead(BaseModel):
    alert_id: str
    source_ip: str | None = None
    username: str | None = None
    score: int
    level: str
    rule_ids: list[str]
    reasons: list[str]
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    event_line_numbers: list[int]
    event_count: int
    limitations: list[str]


class AuthParseResponse(BaseModel):
    evidence_id: str
    parser_name: str
    parser_version: str
    events: list[AuthEventRead]
    alerts: list[AuthAlertRead]
    summary: dict[str, Any]
    warnings: list[str]
