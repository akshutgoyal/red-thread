from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ReportCreate(BaseModel):
    report_type: Literal["pdf", "json"] = "pdf"


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    report_type: str
    filename: str
    status: str
    generated_at: datetime
    metadata_json: dict[str, Any]
