from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ParserContext:
    case_id: str
    evidence_id: str
    source_filename: str
    reference_date: datetime | None = None
    default_year: int | None = None
    timezone: str = "UTC"


@dataclass
class EntityDraft:
    entity_type: str
    value: str
    role: str = "mentioned"
    raw_value: str | None = None


@dataclass
class CanonicalEventDraft:
    event_type: str
    timestamp_raw: str | None
    timestamp_normalized: datetime | None
    timestamp_confidence: str
    timestamp_timezone: str | None
    source_locator: str
    source_snippet: str
    attributes: dict[str, Any] = field(default_factory=dict)
    entities: list[EntityDraft] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ParseWarning:
    source_locator: str
    message: str
    source_snippet: str = ""


@dataclass
class ParseResult:
    parser_name: str
    parser_version: str
    events: list[CanonicalEventDraft] = field(default_factory=list)
    warnings: list[ParseWarning] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseParser(ABC):
    name: str = "base"
    version: str = "1.0.0"
    supported_extensions: tuple[str, ...] = ()

    @abstractmethod
    def parse(self, path: Path, context: ParserContext) -> ParseResult:
        """Parse one evidence file into canonical events and warnings."""

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.supported_extensions
