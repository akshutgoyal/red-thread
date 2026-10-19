from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from ..utils.extraction import extract_entities
from ..utils.timestamps import parse_flexible_timestamp
from .base import (
    BaseParser,
    CanonicalEventDraft,
    EntityDraft,
    ParseResult,
    ParseWarning,
    ParserContext,
)

TIMESTAMP_PREFIX_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)\s+(?P<rest>.*)$"
)
TIMESTAMP_KEYS = ("timestamp", "timestamp_raw", "datetime", "date", "time", "created_at", "date_time")


def _entities(value: str) -> list[EntityDraft]:
    return [
        EntityDraft(entity_type, entity_value, role, entity_value)
        for entity_type, entity_value, role in extract_entities(value)
    ]


def _json_safe(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class GenericTextParser(BaseParser):
    name = "generic_text"
    version = "1.0.0"
    supported_extensions = (".txt",)

    def parse(self, path: Path, context: ParserContext) -> ParseResult:
        events: list[CanonicalEventDraft] = []
        warnings: list[ParseWarning] = []
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            match = TIMESTAMP_PREFIX_RE.match(stripped)
            timestamp = parse_flexible_timestamp(
                match.group("timestamp") if match else None,
                default_timezone=context.timezone,
                reference_date=context.reference_date,
                default_year=context.default_year,
            )
            events.append(
                CanonicalEventDraft(
                    event_type="text_line",
                    timestamp_raw=match.group("timestamp") if match else None,
                    timestamp_normalized=timestamp.normalized,
                    timestamp_confidence=timestamp.confidence,
                    timestamp_timezone=timestamp.timezone_name,
                    source_locator=f"line:{line_number}",
                    source_snippet=stripped[:2000],
                    attributes={"text": stripped[:10000]},
                    entities=_entities(stripped),
                    warnings=list(timestamp.warnings) if match else [],
                )
            )
        if not events:
            warnings.append(
                ParseWarning(source_locator="file", message="No non-empty text lines found.")
            )
        return ParseResult(
            parser_name=self.name,
            parser_version=self.version,
            events=events,
            warnings=warnings,
            metadata={"lines_parsed": len(events)},
        )


class GenericCsvParser(BaseParser):
    name = "generic_csv"
    version = "1.0.0"
    supported_extensions = (".csv",)

    def parse(self, path: Path, context: ParserContext) -> ParseResult:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        rows = [dict(row) for row in frame.to_dict(orient="records")]
        events: list[CanonicalEventDraft] = []
        warnings: list[ParseWarning] = []
        for index, row in enumerate(rows):
            normalized = {
                str(key).strip().lower().replace(" ", "_"): value
                for key, value in row.items()
                if key is not None
            }
            timestamp_raw = next(
                (normalized[key] for key in TIMESTAMP_KEYS if normalized.get(key)), None
            )
            timestamp = parse_flexible_timestamp(
                timestamp_raw,
                default_timezone=context.timezone,
                reference_date=context.reference_date,
                default_year=context.default_year,
            )
            combined = " ".join(str(value) for value in row.values() if value is not None)
            events.append(
                CanonicalEventDraft(
                    event_type="csv_row",
                    timestamp_raw=timestamp_raw,
                    timestamp_normalized=timestamp.normalized,
                    timestamp_confidence=timestamp.confidence,
                    timestamp_timezone=timestamp.timezone_name,
                    source_locator=f"row:{index + 2}",
                    source_snippet=json.dumps(row, ensure_ascii=False)[:2000],
                    attributes={"columns": {key: _json_safe(value) for key, value in normalized.items()}},
                    entities=_entities(combined),
                    warnings=list(timestamp.warnings) if timestamp_raw else [],
                )
            )
        if not events:
            warnings.append(ParseWarning(source_locator="file", message="CSV contains no data rows."))
        return ParseResult(
            parser_name=self.name,
            parser_version=self.version,
            events=events,
            warnings=warnings,
            metadata={"rows_parsed": len(events), "columns": list(frame.columns)},
        )


class GenericJsonParser(BaseParser):
    name = "generic_json"
    version = "1.0.0"
    supported_extensions = (".json", ".jsonl")

    def parse(self, path: Path, context: ParserContext) -> ParseResult:
        events: list[CanonicalEventDraft] = []
        warnings: list[ParseWarning] = []
        if path.suffix.lower() == ".jsonl":
            rows = []
            for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as error:
                    warnings.append(
                        ParseWarning(
                            source_locator=f"line:{line_number}",
                            message=f"Invalid JSON line: {error}",
                            source_snippet=line[:500],
                        )
                    )
        else:
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(payload, list):
                rows = payload
            elif isinstance(payload, dict):
                for key in ("records", "data", "items", "rows"):
                    candidate = payload.get(key)
                    if isinstance(candidate, list):
                        rows = candidate
                        break
                else:
                    rows = [payload]
            else:
                rows = [payload]

        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                events.append(
                    CanonicalEventDraft(
                        event_type="json_value",
                        timestamp_raw=None,
                        timestamp_normalized=None,
                        timestamp_confidence="unknown",
                        timestamp_timezone=None,
                        source_locator=f"record:{index}",
                        source_snippet=str(row)[:2000],
                        attributes={"value": _json_safe(row)},
                    )
                )
                continue
            normalized = {
                str(key).strip().lower().replace(" ", "_"): value for key, value in row.items()
            }
            timestamp_raw = next(
                (normalized[key] for key in TIMESTAMP_KEYS if normalized.get(key)), None
            )
            timestamp = parse_flexible_timestamp(
                timestamp_raw,
                default_timezone=context.timezone,
                reference_date=context.reference_date,
                default_year=context.default_year,
            )
            combined = " ".join(str(value) for value in row.values() if value is not None)
            events.append(
                CanonicalEventDraft(
                    event_type="json_record",
                    timestamp_raw=timestamp_raw,
                    timestamp_normalized=timestamp.normalized,
                    timestamp_confidence=timestamp.confidence,
                    timestamp_timezone=timestamp.timezone_name,
                    source_locator=f"record:{index}",
                    source_snippet=json.dumps(row, ensure_ascii=False, default=str)[:2000],
                    attributes={"record": {key: _json_safe(value) for key, value in normalized.items()}},
                    entities=_entities(combined),
                    warnings=list(timestamp.warnings) if timestamp_raw else [],
                )
            )
        return ParseResult(
            parser_name=self.name,
            parser_version=self.version,
            events=events,
            warnings=warnings,
            metadata={"records_parsed": len(events)},
        )
