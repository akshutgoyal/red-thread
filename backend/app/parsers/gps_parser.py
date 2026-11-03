from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

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

TIMESTAMP_ALIASES = ("timestamp", "time", "datetime", "recorded_at", "observed_at", "date_time")
DEVICE_ALIASES = ("device_id", "device", "source_device", "handset_id", "imei")
PHONE_ALIASES = ("phone", "msisdn", "phone_number", "subscriber")
LAT_ALIASES = ("latitude", "lat", "gps_lat", "y")
LON_ALIASES = ("longitude", "lon", "lng", "gps_lon", "x")
ACCURACY_ALIASES = ("accuracy_m", "accuracy", "hdop")
PLACE_ALIASES = ("place", "location", "label", "address", "site", "site_name")
SPEED_ALIASES = ("speed_mps", "speed", "velocity")


def _normalized_row(row: dict[str, Any]) -> dict[str, Any]:
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


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _csv_rows(path: Path) -> list[dict[str, Any]]:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    return [dict(row) for row in frame.to_dict(orient="records")]


def _json_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("records", "points", "data", "items", "rows"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [row for row in candidate if isinstance(row, dict)]
        return [payload]
    return []


def _tag(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", 1)[-1].lower()


def _child_text(element: ElementTree.Element, name: str) -> str | None:
    for child in element.iter():
        if _tag(child) == name and child.text and child.text.strip():
            return child.text.strip()
    return None


def _gpx_rows(path: Path) -> list[dict[str, Any]]:
    root = ElementTree.parse(path).getroot()
    rows: list[dict[str, Any]] = []
    track_name = None
    for element in root.iter():
        if _tag(element) in {"trk", "rte"}:
            track_name = _child_text(element, "name")
    for point in (element for element in root.iter() if _tag(element) == "trkpt"):
        rows.append(
            {
                "timestamp": _child_text(point, "time"),
                "latitude": point.get("lat"),
                "longitude": point.get("lon"),
                "device_id": track_name,
                "place": _child_text(point, "name") or track_name,
            }
        )
    return rows


def _kml_rows(path: Path) -> list[dict[str, Any]]:
    root = ElementTree.parse(path).getroot()
    rows: list[dict[str, Any]] = []
    for placemark in (element for element in root.iter() if _tag(element) == "placemark"):
        coordinates = _child_text(placemark, "coordinates")
        if not coordinates:
            continue
        first = coordinates.split()[0]
        parts = first.split(",")
        if len(parts) < 2:
            continue
        rows.append(
            {
                "timestamp": _child_text(placemark, "when"),
                "longitude": parts[0],
                "latitude": parts[1],
                "place": _child_text(placemark, "name"),
            }
        )
    return rows


def _rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _csv_rows(path)
    if suffix == ".json":
        return _json_rows(path)
    if suffix == ".gpx":
        return _gpx_rows(path)
    if suffix == ".kml":
        return _kml_rows(path)
    return []


class GpsParser(BaseParser):
    name = "gps"
    version = "1.0.0"
    supported_extensions = (".csv", ".json", ".gpx", ".kml")

    def parse(self, path: Path, context: ParserContext) -> ParseResult:
        events: list[CanonicalEventDraft] = []
        warnings: list[ParseWarning] = []
        rows = _rows(path)
        for index, raw_row in enumerate(rows):
            row = _normalized_row(raw_row)
            timestamp_raw = _pick(row, TIMESTAMP_ALIASES)
            latitude_raw = _pick(row, LAT_ALIASES)
            longitude_raw = _pick(row, LON_ALIASES)
            locator = f"row:{index + 2}" if path.suffix.lower() == ".csv" else f"record:{index}"
            snippet = json.dumps(raw_row, ensure_ascii=False, default=str)[:1000]
            coordinates = parse_coordinates(latitude_raw, longitude_raw)
            if coordinates is None:
                warnings.append(
                    ParseWarning(
                        source_locator=locator,
                        message="GPS record does not contain valid documented coordinates.",
                        source_snippet=snippet,
                    )
                )
                continue
            if not timestamp_raw:
                warnings.append(
                    ParseWarning(
                        source_locator=locator,
                        message="GPS record has no timestamp.",
                        source_snippet=snippet,
                    )
                )
                continue

            latitude, longitude = coordinates
            timestamp = parse_flexible_timestamp(
                timestamp_raw,
                default_timezone=context.timezone,
                reference_date=context.reference_date,
                default_year=context.default_year,
            )
            device_id = _pick(row, DEVICE_ALIASES)
            phone = _pick(row, PHONE_ALIASES)
            accuracy = _number(_pick(row, ACCURACY_ALIASES))
            speed = _number(_pick(row, SPEED_ALIASES))
            place = _pick(row, PLACE_ALIASES)
            point_value = format_gps_point(latitude, longitude)

            entities: list[EntityDraft] = [
                EntityDraft("gps_point", point_value, "location", point_value)
            ]
            if device_id:
                entities.append(EntityDraft("device_id", device_id, "device", device_id))
            if phone:
                entities.append(EntityDraft("phone", phone, "subscriber", phone))
            if place:
                entities.append(EntityDraft("place_label", place, "place", place))

            events.append(
                CanonicalEventDraft(
                    event_type="location_fix",
                    timestamp_raw=timestamp_raw,
                    timestamp_normalized=timestamp.normalized,
                    timestamp_confidence=timestamp.confidence,
                    timestamp_timezone=timestamp.timezone_name,
                    source_locator=locator,
                    source_snippet=snippet,
                    attributes={
                        "latitude": latitude,
                        "longitude": longitude,
                        "gps_point": point_value,
                        "accuracy_m": accuracy,
                        "speed_mps": speed,
                        "device_id": device_id,
                        "phone": phone,
                        "place": place,
                        "coordinate_source": "gps",
                        "timestamp_basis": timestamp.basis,
                    },
                    entities=entities,
                    warnings=list(timestamp.warnings),
                )
            )

        if not events and not warnings:
            warnings.append(
                ParseWarning(source_locator="file", message="No usable GPS observations found.")
            )
        return ParseResult(
            parser_name=self.name,
            parser_version=self.version,
            events=events,
            warnings=warnings,
            metadata={
                "records_total": len(rows),
                "observations_parsed": len(events),
                "records_skipped": len(rows) - len(events),
            },
        )
