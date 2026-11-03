from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..utils.geo import format_gps_point, parse_coordinates
from ..utils.timestamps import parse_flexible_timestamp
from .base import (
    BaseParser,
    CanonicalEventDraft,
    EntityDraft,
    ParseResult,
    ParseWarning,
    ParserContext,
)

CAMERA_ALIASES = ("camera_id", "camera", "cctv_id", "device_id")
PLACE_ALIASES = ("site_name", "site", "place", "location", "address", "camera_location")
LAT_ALIASES = ("latitude", "lat", "camera_lat", "y")
LON_ALIASES = ("longitude", "lon", "lng", "camera_lon", "x")
START_ALIASES = (
    "recording_start",
    "start_time",
    "timestamp",
    "observed_at",
    "datetime",
    "time",
)
END_ALIASES = ("recording_end", "end_time", "ended_at", "to")
FILE_ALIASES = ("filename", "file", "file_name", "video_file", "recording_file", "source_file")
STATUS_ALIASES = ("status", "state", "retention_status")
COVERAGE_ALIASES = ("coverage", "field_of_view", "area")


def _row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key).strip().lower().replace(" ", "_"): value
        for key, value in row.items()
        if key is not None
    }


def _pick(row: dict[str, Any], aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        value = row.get(alias)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None


def _rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("records", "cameras", "segments", "data", "items"):
                candidate = payload.get(key)
                if isinstance(candidate, list):
                    return [item for item in candidate if isinstance(item, dict)]
            return [payload]
        return []
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    return [dict(item) for item in frame.to_dict(orient="records")]


class CctvParser(BaseParser):
    name = "cctv"
    version = "1.0.0"
    supported_extensions = (".csv", ".json")

    def parse(self, path: Path, context: ParserContext) -> ParseResult:
        events: list[CanonicalEventDraft] = []
        warnings: list[ParseWarning] = []
        rows = _rows(path)
        for index, raw_row in enumerate(rows):
            row = _row(raw_row)
            locator = f"row:{index + 2}" if path.suffix.lower() == ".csv" else f"record:{index}"
            snippet = json.dumps(raw_row, ensure_ascii=False, default=str)[:1200]
            camera_id = _pick(row, CAMERA_ALIASES)
            start_raw = _pick(row, START_ALIASES)
            end_raw = _pick(row, END_ALIASES)
            place = _pick(row, PLACE_ALIASES)
            latitude_raw = _pick(row, LAT_ALIASES)
            longitude_raw = _pick(row, LON_ALIASES)
            filename = _pick(row, FILE_ALIASES)
            status = _pick(row, STATUS_ALIASES)
            coverage = _pick(row, COVERAGE_ALIASES)

            if not start_raw:
                warnings.append(
                    ParseWarning(
                        source_locator=locator,
                        message="CCTV record has no recording start timestamp.",
                        source_snippet=snippet,
                    )
                )
                continue

            start = parse_flexible_timestamp(
                start_raw,
                default_timezone=context.timezone,
                reference_date=context.reference_date,
                default_year=context.default_year,
            )
            end = (
                parse_flexible_timestamp(
                    end_raw,
                    default_timezone=context.timezone,
                    reference_date=context.reference_date,
                    default_year=context.default_year,
                )
                if end_raw
                else None
            )
            coordinates = parse_coordinates(latitude_raw, longitude_raw)
            point = format_gps_point(*coordinates) if coordinates else None

            entities: list[EntityDraft] = []
            if camera_id:
                entities.append(EntityDraft("camera_id", camera_id, "camera", camera_id))
            if place:
                entities.append(EntityDraft("place_label", place, "place", place))
            if point:
                entities.append(EntityDraft("gps_point", point, "camera_location", point))
            if filename:
                entities.append(EntityDraft("filename", filename, "source_file", filename))

            duration_seconds = None
            if start.normalized and end and end.normalized:
                duration_seconds = (end.normalized - start.normalized).total_seconds()

            events.append(
                CanonicalEventDraft(
                    event_type="cctv_segment",
                    timestamp_raw=start_raw,
                    timestamp_normalized=start.normalized,
                    timestamp_confidence=start.confidence,
                    timestamp_timezone=start.timezone_name,
                    source_locator=locator,
                    source_snippet=snippet,
                    attributes={
                        "camera_id": camera_id,
                        "place": place,
                        "latitude": coordinates[0] if coordinates else None,
                        "longitude": coordinates[1] if coordinates else None,
                        "gps_point": point,
                        "recording_start": start_raw,
                        "recording_end": end_raw,
                        "duration_seconds": duration_seconds,
                        "filename": filename,
                        "status": status,
                        "coverage": coverage,
                        "coordinate_source": "cctv_metadata",
                        "timestamp_basis": start.basis,
                    },
                    entities=entities,
                    warnings=list(start.warnings) + (list(end.warnings) if end else []),
                )
            )

        if not events and not warnings:
            warnings.append(
                ParseWarning(source_locator="file", message="No usable CCTV metadata found.")
            )
        return ParseResult(
            parser_name=self.name,
            parser_version=self.version,
            events=events,
            warnings=warnings,
            metadata={
                "records_total": len(rows),
                "segments_parsed": len(events),
                "segments_skipped": len(rows) - len(events),
            },
        )
