from __future__ import annotations

import json
import re
from pathlib import Path

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

BRACKET_RE = re.compile(
    r"^\[(?P<timestamp>[^\]]+)\]\s*(?P<sender>[^:]{1,80}):\s*(?P<message>.*)$"
)
DASH_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)"
    r"\s+-\s+(?P<sender>[^:]{1,80}):\s*(?P<message>.*)$"
)
WHATSAPP_RE = re.compile(
    r"^(?P<timestamp>\d{1,2}[/-]\d{1,2}[/-]\d{2,4},?\s+\d{1,2}:\d{2}"
    r"(?:\s*[APap][Mm])?)\s+-\s+(?P<sender>[^:]{1,80}):\s*(?P<message>.*)$"
)
ATTACHMENT_RE = re.compile(r"<attached:\s*(?P<filename>[^>]+)>", re.IGNORECASE)


def _clean_timestamp(value: str) -> str:
    return value.strip().strip("[]").replace(",", " ", 1).strip()


def _message_entities(message: str, sender: str | None, attachment: str | None) -> list[EntityDraft]:
    entities = [
        EntityDraft(entity_type, value, role, value)
        for entity_type, value, role in extract_entities(message)
    ]
    if sender:
        phone_entities = [
            item for item in extract_entities(sender) if item[0] == "phone"
        ]
        for entity_type, value, role in phone_entities:
            entities.append(EntityDraft(entity_type, value, "sender", value))
    if attachment:
        entities.append(EntityDraft("filename", attachment.lower(), "attachment", attachment))
    return entities


def _parse_text(path: Path, context: ParserContext) -> ParseResult:
    events: list[CanonicalEventDraft] = []
    warnings: list[ParseWarning] = []
    unparsed = 0
    text = path.read_text(encoding="utf-8", errors="replace")
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        match = BRACKET_RE.match(stripped) or DASH_RE.match(stripped) or WHATSAPP_RE.match(stripped)
        if not match:
            unparsed += 1
            continue
        timestamp_raw = _clean_timestamp(match.group("timestamp"))
        sender = match.group("sender").strip()
        message = match.group("message").strip()
        attachment_match = ATTACHMENT_RE.search(message)
        attachment = attachment_match.group("filename").strip() if attachment_match else None
        timestamp = parse_flexible_timestamp(
            timestamp_raw,
            default_timezone=context.timezone,
            reference_date=context.reference_date,
            default_year=context.default_year,
        )
        events.append(
            CanonicalEventDraft(
                event_type="chat_message",
                timestamp_raw=timestamp_raw,
                timestamp_normalized=timestamp.normalized,
                timestamp_confidence=timestamp.confidence,
                timestamp_timezone=timestamp.timezone_name,
                source_locator=f"line:{line_number}",
                source_snippet=stripped[:2000],
                attributes={
                    "sender": sender,
                    "recipient": None,
                    "message": message,
                    "attachment": attachment,
                    "timestamp_basis": timestamp.basis,
                },
                entities=_message_entities(message, sender, attachment),
                warnings=list(timestamp.warnings),
            )
        )
    if unparsed:
        warnings.append(
            ParseWarning(
                source_locator="file",
                message=f"{unparsed} line(s) did not match a supported chat format.",
            )
        )
    return ParseResult(
        parser_name="chat",
        parser_version="1.0.0",
        events=events,
        warnings=warnings,
        metadata={
            "messages_parsed": len(events),
            "unparsed_lines": unparsed,
            "attachments": sum(1 for event in events if event.attributes.get("attachment")),
        },
    )


def _rows(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("messages", "chats", "data", "items", "records"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [row for row in candidate if isinstance(row, dict)]
        return [payload]
    return []


def _pick(row: dict, aliases: tuple[str, ...]) -> str | None:
    normalized = {
        str(key).strip().lower().replace(" ", "_"): value
        for key, value in row.items()
        if key is not None
    }
    for alias in aliases:
        value = normalized.get(alias)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None


def _parse_json(path: Path, context: ParserContext) -> ParseResult:
    events: list[CanonicalEventDraft] = []
    warnings: list[ParseWarning] = []
    rows = _rows(path)
    for index, row in enumerate(rows):
        timestamp_raw = _pick(row, ("timestamp", "date", "time", "datetime", "created_at"))
        sender = _pick(row, ("sender", "from", "author", "user"))
        recipient = _pick(row, ("recipient", "to", "receiver"))
        message = _pick(row, ("message", "text", "body", "content"))
        attachment = _pick(row, ("attachment", "filename", "file"))
        locator = f"message:{index}"
        if not timestamp_raw or message is None:
            warnings.append(
                ParseWarning(
                    source_locator=locator,
                    message="Chat record is missing a timestamp or message body.",
                    source_snippet=json.dumps(row, ensure_ascii=False)[:500],
                )
            )
            continue
        timestamp = parse_flexible_timestamp(
            timestamp_raw,
            default_timezone=context.timezone,
            reference_date=context.reference_date,
            default_year=context.default_year,
        )
        events.append(
            CanonicalEventDraft(
                event_type="chat_message",
                timestamp_raw=timestamp_raw,
                timestamp_normalized=timestamp.normalized,
                timestamp_confidence=timestamp.confidence,
                timestamp_timezone=timestamp.timezone_name,
                source_locator=locator,
                source_snippet=json.dumps(row, ensure_ascii=False)[:2000],
                attributes={
                    "sender": sender,
                    "recipient": recipient,
                    "message": message,
                    "attachment": attachment,
                    "timestamp_basis": timestamp.basis,
                },
                entities=_message_entities(message, sender, attachment),
                warnings=list(timestamp.warnings),
            )
        )
    return ParseResult(
        parser_name="chat",
        parser_version="1.0.0",
        events=events,
        warnings=warnings,
        metadata={
            "messages_parsed": len(events),
            "records_total": len(rows),
            "attachments": sum(1 for event in events if event.attributes.get("attachment")),
        },
    )


class ChatParser(BaseParser):
    name = "chat"
    version = "1.0.0"
    supported_extensions = (".txt", ".json", ".jsonl")

    def parse(self, path: Path, context: ParserContext) -> ParseResult:
        if path.suffix.lower() == ".json":
            return _parse_json(path, context)
        return _parse_text(path, context)
