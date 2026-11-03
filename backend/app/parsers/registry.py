from __future__ import annotations

import json
from pathlib import Path

from .auth_adapter import AuthLogParser
from .base import BaseParser
from .call_log_parser import CallLogParser
from .cctv_parser import CctvParser
from .chat_parser import ChatParser
from .device_log_parser import DeviceLogParser
from .email_parser import EmailParser
from .generic_parser import GenericCsvParser, GenericJsonParser, GenericTextParser
from .gps_parser import GpsParser
from .image_parser import ImageParser
from .invoice_parser import InvoiceParser
from .transaction_parser import TransactionParser

PARSERS: list[BaseParser] = [
    AuthLogParser(),
    CallLogParser(),
    ChatParser(),
    TransactionParser(),
    InvoiceParser(),
    EmailParser(),
    GpsParser(),
    CctvParser(),
    DeviceLogParser(),
    ImageParser(),
    GenericCsvParser(),
    GenericJsonParser(),
    GenericTextParser(),
]

PARSER_BY_NAME = {parser.name: parser for parser in PARSERS}

HINTS = {
    "auth": "auth_log",
    "auth_log": "auth_log",
    "authentication": "auth_log",
    "call": "call_log",
    "call_log": "call_log",
    "chat": "chat",
    "message": "chat",
    "transaction": "transaction",
    "upi": "transaction",
    "bank": "transaction",
    "invoice": "invoice",
    "receipt": "invoice",
    "email": "email",
    "eml": "email",
    "gps": "gps",
    "gpx": "gps",
    "kml": "gps",
    "location": "gps",
    "cctv": "cctv",
    "camera": "cctv",
    "device": "device_log",
    "device_log": "device_log",
    "imei": "device_log",
    "image": "image",
    "ocr": "image",
    "text": "generic_text",
    "csv": "generic_csv",
    "json": "generic_json",
}

SUPPORTED_DESCRIPTION = (
    "Authentication logs (.log/.txt), call logs (.csv/.json), chat exports "
    "(.txt/.json/.jsonl), email records (.eml/.csv), GPS tracks "
    "(.csv/.json/.gpx/.kml), CCTV metadata (.csv/.json), device logs "
    "(.csv/.json/.jsonl), transaction records (.csv/.json), invoices "
    "(.pdf/.csv/.json), images (.png/.jpg/.jpeg), and generic text/CSV/JSON."
)


def _read_head(path: Path, limit: int = 4096) -> str:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.read(limit)


def _csv_header(path: Path) -> str:
    return _read_head(path, 2048).splitlines()[0].lower() if path.stat().st_size else ""


def _detect_csv(path: Path) -> BaseParser:
    header = _csv_header(path)
    if (
        any(token in header for token in ("from", "sender"))
        and any(token in header for token in ("to", "recipient"))
        and any(token in header for token in ("subject", "body", "message_id"))
    ):
        return PARSER_BY_NAME["email"]
    if any(token in header for token in ("camera_id", "cctv", "recording_start", "recording_end")):
        return PARSER_BY_NAME["cctv"]
    if any(token in header for token in ("latitude", "longitude", "gps_lat", "gps_lon")):
        return PARSER_BY_NAME["gps"]
    if any(token in header for token in ("caller", "receiver", "call_type", "duration")):
        return PARSER_BY_NAME["call_log"]
    if any(token in header for token in ("utr", "payee", "payer", "transaction", "amount")):
        return PARSER_BY_NAME["transaction"]
    if any(token in header for token in ("invoice", "subtotal", "gst", "tax", "total")):
        return PARSER_BY_NAME["invoice"]
    if any(token in header for token in ("sender", "message", "recipient")):
        return PARSER_BY_NAME["chat"]
    if any(token in header for token in ("device_id", "imei", "imsi", "mac_address")):
        return PARSER_BY_NAME["device_log"]
    return PARSER_BY_NAME["generic_csv"]


def _detect_json(path: Path) -> BaseParser:
    head = _read_head(path, 8192).lower()
    if '"camera_id"' in head or '"recording_start"' in head:
        return PARSER_BY_NAME["cctv"]
    if '"latitude"' in head and '"longitude"' in head:
        return PARSER_BY_NAME["gps"]
    if '"caller"' in head or '"receiver"' in head:
        return PARSER_BY_NAME["call_log"]
    if '"utr"' in head or '"payee"' in head or '"transaction_id"' in head:
        return PARSER_BY_NAME["transaction"]
    if '"invoice_id"' in head or '"subtotal"' in head:
        return PARSER_BY_NAME["invoice"]
    if '"sender"' in head or '"message"' in head:
        return PARSER_BY_NAME["chat"]
    if '"device_id"' in head or '"imei"' in head or '"imsi"' in head:
        return PARSER_BY_NAME["device_log"]
    return PARSER_BY_NAME["generic_json"]


def _detect_text(path: Path) -> BaseParser:
    head = _read_head(path, 8192)
    if any(
        token in head
        for token in ("sshd[", "pam_unix(sshd:session)", "Failed password", "Accepted publickey")
    ):
        return PARSER_BY_NAME["auth_log"]
    if any(
        token in head
        for token in ("<attached:", " - ", "]:", ":")
    ) and any(
        line.startswith("[") or " - " in line
        for line in head.splitlines()[:20]
    ):
        return PARSER_BY_NAME["chat"]
    return PARSER_BY_NAME["generic_text"]


def detect_parser(path: Path, filename: str | None = None, hint: str | None = None) -> BaseParser | None:
    normalized_hint = (hint or "").strip().lower()
    if normalized_hint:
        parser_name = HINTS.get(normalized_hint)
        if parser_name:
            return PARSER_BY_NAME[parser_name]

    name = (filename or path.name).lower()
    suffix = path.suffix.lower()

    if suffix == ".eml":
        return PARSER_BY_NAME["email"]
    if suffix in {".gpx", ".kml"}:
        return PARSER_BY_NAME["gps"]
    if suffix in {".png", ".jpg", ".jpeg"}:
        return PARSER_BY_NAME["image"]
    if suffix == ".log":
        return PARSER_BY_NAME["auth_log"]
    if suffix == ".pdf":
        return PARSER_BY_NAME["invoice"]
    if suffix == ".csv":
        return _detect_csv(path)
    if suffix in {".json", ".jsonl"}:
        return _detect_json(path)
    if suffix == ".txt":
        return _detect_text(path)

    # Filename hints are only a fallback for ambiguous or extensionless files.
    if "auth" in name:
        return PARSER_BY_NAME["auth_log"]
    if any(token in name for token in ("gps", "location_track", "geotrack")):
        return PARSER_BY_NAME["gps"]
    if any(token in name for token in ("cctv", "camera")):
        return PARSER_BY_NAME["cctv"]
    if any(token in name for token in ("device_log", "device-events", "imei", "handset")):
        return PARSER_BY_NAME["device_log"]
    if "email" in name:
        return PARSER_BY_NAME["email"]
    if "call" in name:
        return PARSER_BY_NAME["call_log"]
    if any(token in name for token in ("transaction", "upi", "bank", "ledger", "statement")):
        return PARSER_BY_NAME["transaction"]
    if any(token in name for token in ("invoice", "receipt")):
        return PARSER_BY_NAME["invoice"]
    if any(token in name for token in ("chat", "whatsapp", "message")):
        return PARSER_BY_NAME["chat"]
    return None
