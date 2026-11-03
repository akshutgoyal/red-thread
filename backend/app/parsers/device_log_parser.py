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

TIMESTAMP_ALIASES = ("timestamp", "time", "datetime", "event_time", "created_at", "date_time")
DEVICE_ALIASES = ("device_id", "device", "handset_id", "source_device")
IMEI_ALIASES = ("imei", "device_imei")
IMSI_ALIASES = ("imsi", "subscriber_id")
PHONE_ALIASES = ("phone", "msisdn", "phone_number", "subscriber_msisdn")
ACCOUNT_ALIASES = ("account_id", "account", "username", "user")
EMAIL_ALIASES = ("email", "email_address", "account_email")
IP_ALIASES = ("ip", "ip_address", "source_ip", "remote_ip")
MAC_ALIASES = ("mac", "mac_address", "wifi_mac")
EVENT_ALIASES = ("event", "event_type", "activity", "action")
APP_ALIASES = ("app", "application", "package")
LAT_ALIASES = ("latitude", "lat")
LON_ALIASES = ("longitude", "lon", "lng")


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
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        return [dict(row) for row in frame.to_dict(orient="records")]
    if suffix == ".jsonl":
        rows = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                payload = json.loads(line)
                if isinstance(payload, dict):
                    rows.append(payload)
        return rows
    payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("records", "events", "data", "items"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
        return [payload]
    return []


class DeviceLogParser(BaseParser):
    name = "device_log"
    version = "1.0.0"
    supported_extensions = (".csv", ".json", ".jsonl")

    def parse(self, path: Path, context: ParserContext) -> ParseResult:
        events: list[CanonicalEventDraft] = []
        warnings: list[ParseWarning] = []
        rows = _rows(path)
        for index, raw_row in enumerate(rows):
            row = _row(raw_row)
            locator = f"row:{index + 2}" if path.suffix.lower() == ".csv" else f"record:{index}"
            snippet = json.dumps(raw_row, ensure_ascii=False, default=str)[:1200]
            timestamp_raw = _pick(row, TIMESTAMP_ALIASES)
            if not timestamp_raw:
                warnings.append(
                    ParseWarning(
                        source_locator=locator,
                        message="Device record has no timestamp.",
                        source_snippet=snippet,
                    )
                )
                continue
            timestamp = parse_flexible_timestamp(
                timestamp_raw,
                default_timezone=context.timezone,
                reference_date=context.reference_date,
                default_year=context.default_year,
            )
            device_id = _pick(row, DEVICE_ALIASES)
            imei = _pick(row, IMEI_ALIASES)
            imsi = _pick(row, IMSI_ALIASES)
            phone = _pick(row, PHONE_ALIASES)
            account = _pick(row, ACCOUNT_ALIASES)
            email = _pick(row, EMAIL_ALIASES)
            ip = _pick(row, IP_ALIASES)
            mac = _pick(row, MAC_ALIASES)
            event_type = _pick(row, EVENT_ALIASES)
            app = _pick(row, APP_ALIASES)
            coordinates = parse_coordinates(_pick(row, LAT_ALIASES), _pick(row, LON_ALIASES))
            point = format_gps_point(*coordinates) if coordinates else None

            entities: list[EntityDraft] = []
            if device_id:
                entities.append(EntityDraft("device_id", device_id, "device", device_id))
            if imei:
                entities.append(EntityDraft("imei", imei, "device_identifier", imei))
            if imsi:
                entities.append(EntityDraft("imsi", imsi, "subscriber_identifier", imsi))
            if phone:
                entities.append(EntityDraft("phone", phone, "subscriber", phone))
            if account:
                entities.append(EntityDraft("account", account, "account", account))
            if email:
                entities.append(EntityDraft("email", email, "account", email))
            if ip:
                entities.append(EntityDraft("ip", ip, "network", ip))
            if mac:
                entities.append(EntityDraft("mac", mac, "network", mac))
            if point:
                entities.append(EntityDraft("gps_point", point, "device_location", point))

            events.append(
                CanonicalEventDraft(
                    event_type="device_event",
                    timestamp_raw=timestamp_raw,
                    timestamp_normalized=timestamp.normalized,
                    timestamp_confidence=timestamp.confidence,
                    timestamp_timezone=timestamp.timezone_name,
                    source_locator=locator,
                    source_snippet=snippet,
                    attributes={
                        "device_id": device_id,
                        "imei": imei,
                        "imsi": imsi,
                        "phone": phone,
                        "account": account,
                        "email": email,
                        "ip": ip,
                        "mac": mac,
                        "activity": event_type,
                        "app": app,
                        "latitude": coordinates[0] if coordinates else None,
                        "longitude": coordinates[1] if coordinates else None,
                        "gps_point": point,
                        "coordinate_source": "device_log" if coordinates else None,
                        "timestamp_basis": timestamp.basis,
                    },
                    entities=entities,
                    warnings=list(timestamp.warnings),
                )
            )

        if not events and not warnings:
            warnings.append(
                ParseWarning(source_locator="file", message="No usable device records found.")
            )
        return ParseResult(
            parser_name=self.name,
            parser_version=self.version,
            events=events,
            warnings=warnings,
            metadata={
                "records_total": len(rows),
                "events_parsed": len(events),
                "records_skipped": len(rows) - len(events),
            },
        )
