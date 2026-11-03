from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..utils.timestamps import parse_flexible_timestamp
from .base import (
    BaseParser,
    CanonicalEventDraft,
    EntityDraft,
    ParseResult,
    ParseWarning,
    ParserContext,
)

CALLER_ALIASES = ("caller_id", "caller", "from", "source", "phone_number", "calling_number")
RECEIVER_ALIASES = ("receiver_id", "receiver", "to", "destination", "called_number")
TIMESTAMP_ALIASES = ("timestamp_raw", "timestamp", "datetime", "date_time", "call_time", "start_time")
DURATION_ALIASES = ("duration_sec", "duration_seconds", "duration", "call_duration")
STATUS_ALIASES = ("call_type", "call_status", "status", "type")
TOWER_ALIASES = ("cell_tower_id", "cell_tower", "tower", "location", "cell_id")


def _normalized_row(row: dict) -> dict:
    return {
        str(key).strip().lower().replace(" ", "_"): value
        for key, value in row.items()
        if key is not None
    }


def _pick(row: dict, aliases: tuple[str, ...]) -> tuple[str | None, str | None]:
    for alias in aliases:
        value = row.get(alias)
        if value is not None and str(value).strip() != "":
            return str(value).strip(), alias
    return None, None


def _rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            for key in ("records", "calls", "data", "items", "rows"):
                candidate = payload.get(key)
                if isinstance(candidate, list):
                    return [row for row in candidate if isinstance(row, dict)]
            return [payload]
        return []
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    return [dict(row) for row in frame.to_dict(orient="records")]


class CallLogParser(BaseParser):
    name = "call_log"
    version = "1.0.0"
    supported_extensions = (".csv", ".json")

    def parse(self, path: Path, context: ParserContext) -> ParseResult:
        events: list[CanonicalEventDraft] = []
        warnings: list[ParseWarning] = []
        rows = _rows(path)
        for index, raw_row in enumerate(rows):
            row = _normalized_row(raw_row)
            caller, _ = _pick(row, CALLER_ALIASES)
            receiver, _ = _pick(row, RECEIVER_ALIASES)
            timestamp_raw, _ = _pick(row, TIMESTAMP_ALIASES)
            duration_raw, _ = _pick(row, DURATION_ALIASES)
            status, _ = _pick(row, STATUS_ALIASES)
            tower, _ = _pick(row, TOWER_ALIASES)

            locator = f"row:{index + 2}" if path.suffix.lower() == ".csv" else f"record:{index}"
            if not timestamp_raw:
                warnings.append(
                    ParseWarning(
                        source_locator=locator,
                        message="Call record has no timestamp.",
                        source_snippet=json.dumps(raw_row, ensure_ascii=False)[:500],
                    )
                )
                continue

            timestamp = parse_flexible_timestamp(
                timestamp_raw,
                default_timezone=context.timezone,
                reference_date=context.reference_date,
                default_year=context.default_year,
            )
            entities: list[EntityDraft] = []
            if caller:
                entities.append(EntityDraft("phone", caller, "caller", caller))
            if receiver:
                entities.append(EntityDraft("phone", receiver, "receiver", receiver))
            if tower:
                entities.append(EntityDraft("cell_tower", tower, "cell_tower", tower))

            attributes = {
                "caller": caller,
                "receiver": receiver,
                "duration_sec": int(duration_raw) if duration_raw and duration_raw.isdigit() else duration_raw,
                "call_type": status,
                "cell_tower_id": tower,
                "timestamp_basis": timestamp.basis,
            }
            events.append(
                CanonicalEventDraft(
                    event_type="call",
                    timestamp_raw=timestamp_raw,
                    timestamp_normalized=timestamp.normalized,
                    timestamp_confidence=timestamp.confidence,
                    timestamp_timezone=timestamp.timezone_name,
                    source_locator=locator,
                    source_snippet=json.dumps(raw_row, ensure_ascii=False)[:2000],
                    attributes=attributes,
                    entities=entities,
                    warnings=list(timestamp.warnings),
                )
            )

        return ParseResult(
            parser_name=self.name,
            parser_version=self.version,
            events=events,
            warnings=warnings,
            metadata={
                "rows_total": len(rows),
                "events_parsed": len(events),
                "missing_timestamp": len(warnings),
            },
        )
