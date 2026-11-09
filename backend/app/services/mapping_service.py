from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import get_settings
from ..models import Evidence
from . import storage_service

MAX_PREVIEW_ROWS = 5

# Canonical fields a mapping can target, with the aliases used to guess them.
CANONICAL_FIELDS: dict[str, dict[str, Any]] = {
    "timestamp": {
        "label": "Timestamp",
        "required": True,
        "aliases": (
            "timestamp",
            "timestamp_raw",
            "datetime",
            "date_time",
            "date",
            "time",
            "created_at",
            "call_time",
            "event_time",
            "start_time",
        ),
    },
    "event_type": {
        "label": "Event type",
        "required": False,
        "aliases": ("event_type", "type", "event", "action", "category"),
    },
    "actor": {
        "label": "From / actor",
        "required": False,
        "aliases": (
            "caller",
            "caller_id",
            "sender",
            "from",
            "source",
            "from_number",
            "username",
            "user",
            "actor",
        ),
    },
    "target": {
        "label": "To / target",
        "required": False,
        "aliases": (
            "receiver",
            "receiver_id",
            "recipient",
            "to",
            "destination",
            "to_number",
            "callee",
            "target",
        ),
    },
    "body": {
        "label": "Message / description",
        "required": False,
        "aliases": ("message", "text", "body", "content", "description", "note"),
    },
    "latitude": {
        "label": "Latitude",
        "required": False,
        "aliases": ("latitude", "lat", "gps_lat"),
    },
    "longitude": {
        "label": "Longitude",
        "required": False,
        "aliases": ("longitude", "lon", "lng", "gps_lon"),
    },
    "amount": {
        "label": "Amount",
        "required": False,
        "aliases": ("amount", "value", "debit", "credit", "transaction_amount"),
    },
    "identifier": {
        "label": "Identifier (IP, device, account)",
        "required": False,
        "aliases": (
            "ip",
            "ip_address",
            "source_ip",
            "device_id",
            "device",
            "account",
            "account_id",
            "utr",
            "transaction_id",
        ),
    },
}

MAPPABLE_EXTENSIONS = {".csv", ".json", ".jsonl"}


def _normalize(name: str) -> str:
    return str(name).strip().lower().replace(" ", "_").replace("-", "_")


def read_headers(evidence: Evidence) -> list[str] | None:
    """Return the file's column names, or None when the format cannot be mapped."""

    suffix = Path(evidence.original_filename).suffix.lower()
    if suffix not in MAPPABLE_EXTENSIONS:
        return None
    try:
        with storage_service.materialize(evidence.relative_path) as path:
            if suffix == ".csv":
                frame = pd.read_csv(path, dtype=str, keep_default_na=False, nrows=0)
                return [str(column) for column in frame.columns]
            text = path.read_text(encoding="utf-8", errors="replace")
            if suffix == ".jsonl":
                for line in text.splitlines():
                    if line.strip():
                        payload = json.loads(line)
                        return list(payload.keys()) if isinstance(payload, dict) else None
                return []
            payload = json.loads(text)
            if isinstance(payload, list) and payload and isinstance(payload[0], dict):
                return list(payload[0].keys())
            if isinstance(payload, dict):
                for key in ("records", "data", "items", "rows"):
                    candidate = payload.get(key)
                    if isinstance(candidate, list) and candidate and isinstance(candidate[0], dict):
                        return list(candidate[0].keys())
                return list(payload.keys())
    except Exception:  # noqa: BLE001 - unreadable files have no headers
        return None
    return None


def read_sample_rows(evidence: Evidence, limit: int = MAX_PREVIEW_ROWS) -> list[dict]:
    suffix = Path(evidence.original_filename).suffix.lower()
    if suffix not in MAPPABLE_EXTENSIONS:
        return []
    try:
        with storage_service.materialize(evidence.relative_path) as path:
            if suffix == ".csv":
                frame = pd.read_csv(path, dtype=str, keep_default_na=False, nrows=limit)
                return [
                    {str(key): str(value) for key, value in row.items()}
                    for row in frame.to_dict(orient="records")
                ]
            text = path.read_text(encoding="utf-8", errors="replace")
            if suffix == ".jsonl":
                rows = []
                for line in text.splitlines():
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict):
                        rows.append({str(key): str(value) for key, value in payload.items()})
                    if len(rows) >= limit:
                        break
                return rows
            payload = json.loads(text)
            if isinstance(payload, list):
                rows = payload
            elif isinstance(payload, dict):
                rows = None
                for key in ("records", "data", "items", "rows"):
                    candidate = payload.get(key)
                    if isinstance(candidate, list):
                        rows = candidate
                        break
                if rows is None:
                    rows = [payload]
            else:
                rows = []
            return [
                {str(key): str(value) for key, value in row.items()}
                for row in rows[:limit]
                if isinstance(row, dict)
            ]
    except Exception:  # noqa: BLE001 - preview is best-effort
        return []


def suggest_mapping(headers: list[str]) -> dict[str, str | None]:
    """Guess a canonical field for each column by alias matching.

    A guess is only a starting point; the investigator confirms it.
    """

    normalized = {column: _normalize(column) for column in headers}
    mapping: dict[str, str | None] = {}
    used: set[str] = set()
    for field, spec in CANONICAL_FIELDS.items():
        match = None
        for column, key in normalized.items():
            if column in used:
                continue
            if key in spec["aliases"]:
                match = column
                break
        if match is None:
            # Fall back to a contains-match for decorated headers.
            for column, key in normalized.items():
                if column in used:
                    continue
                if any(alias in key for alias in spec["aliases"]):
                    match = column
                    break
        if match:
            used.add(match)
        mapping[field] = match
    return mapping


def normalize_mapping(payload: dict[str, Any], headers: list[str]) -> dict[str, str]:
    """Keep only canonical fields whose target is a real column."""

    header_set = {str(header) for header in headers}
    result: dict[str, str] = {}
    for field, column in payload.items():
        if field not in CANONICAL_FIELDS:
            continue
        if column is None:
            continue
        value = str(column)
        if value in header_set:
            result[field] = value
    return result


def mapping_preview(evidence: Evidence) -> dict[str, Any]:
    headers = read_headers(evidence)
    if headers is None:
        return {
            "supported": False,
            "reason": (
                "Column mapping is available for CSV, JSON and JSONL files. "
                "This file is parsed by a format-specific reader."
            ),
            "headers": [],
            "fields": [],
            "suggested": {},
            "rows": [],
            "saved_mapping": {},
        }
    saved = (evidence.metadata_json or {}).get("column_mapping") or {}
    suggested = suggest_mapping(headers)
    return {
        "supported": True,
        "reason": "",
        "headers": headers,
        "fields": [
            {
                "key": field,
                "label": spec["label"],
                "required": spec["required"],
            }
            for field, spec in CANONICAL_FIELDS.items()
        ],
        "suggested": suggested,
        "saved_mapping": saved if isinstance(saved, dict) else {},
        "rows": read_sample_rows(evidence),
    }


def csv_bytes_to_records(content: bytes, mapping: dict[str, str]) -> list[dict[str, str]]:
    """Map a CSV payload's columns onto canonical field names."""

    reader = csv.DictReader(io.StringIO(content.decode("utf-8", errors="replace")))
    records: list[dict[str, str]] = []
    for row in reader:
        record: dict[str, str] = {}
        for field, column in mapping.items():
            value = row.get(column)
            if value is not None and str(value).strip() != "":
                record[field] = str(value).strip()
        if record:
            records.append(record)
    return records


def default_timezone() -> str:
    return get_settings().default_timezone
