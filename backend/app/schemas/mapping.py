from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MappingField(BaseModel):
    key: str
    label: str
    required: bool = False


class ColumnMappingRequest(BaseModel):
    mapping: dict[str, str | None] = Field(default_factory=dict)


class ColumnMappingResponse(BaseModel):
    supported: bool
    reason: str = ""
    headers: list[str] = Field(default_factory=list)
    fields: list[MappingField] = Field(default_factory=list)
    suggested: dict[str, str | None] = Field(default_factory=dict)
    saved_mapping: dict[str, str] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)
