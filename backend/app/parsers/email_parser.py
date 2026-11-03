from __future__ import annotations

import csv
import re
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr
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

HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\n{3,}")


def _body_text(message) -> str:
    try:
        body = message.get_body(preferencelist=("plain", "html"))
    except Exception:
        body = None
    if body is None:
        return ""
    content = body.get_content()
    if body.get_content_type() == "text/html":
        content = HTML_TAG_RE.sub(" ", content)
    return WHITESPACE_RE.sub("\n\n", content).strip()


def _attachments(message) -> list[str]:
    names: list[str] = []
    if not message.is_multipart():
        return names
    for part in message.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        if filename:
            names.append(filename)
    return names


def _address_list(value: str) -> list[str]:
    return [
        address.lower()
        for _, address in getaddresses([value or ""])
        if address and "@" in address
    ]


def _csv_value(value: str | None) -> str:
    return str(value or "").strip()


def _parse_csv(path: Path, context: ParserContext) -> ParseResult:
    events: list[CanonicalEventDraft] = []
    warnings: list[ParseWarning] = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for index, raw_row in enumerate(rows):
        row = {
            str(key).strip().lower().replace(" ", "_"): value
            for key, value in raw_row.items()
            if key is not None
        }
        locator = f"row:{index + 2}"
        subject = _csv_value(row.get("subject"))
        sender_raw = _csv_value(row.get("from") or row.get("sender"))
        recipient_raw = _csv_value(row.get("to") or row.get("recipient"))
        cc_raw = _csv_value(row.get("cc"))
        date_raw = _csv_value(row.get("date") or row.get("timestamp"))
        message_id = _csv_value(row.get("message_id") or row.get("message-id"))
        body = _csv_value(row.get("body") or row.get("body_text") or row.get("text"))
        attachment_raw = _csv_value(row.get("attachments") or row.get("attachments_list"))
        attachments = [
            item.strip()
            for item in re.split(r"[;,]", attachment_raw)
            if item.strip()
        ]
        sender_addresses = _address_list(sender_raw)
        recipient_addresses = _address_list(recipient_raw)
        cc_addresses = _address_list(cc_raw)
        timestamp = parse_flexible_timestamp(
            date_raw or None,
            default_timezone=context.timezone,
            reference_date=context.reference_date,
            default_year=context.default_year,
        )
        combined = "\n".join(
            [subject, sender_raw, recipient_raw, cc_raw, body]
        )
        entities = [
            EntityDraft(entity_type, value, role, value)
            for entity_type, value, role in extract_entities(combined)
        ]
        for address in sender_addresses:
            entities.append(EntityDraft("email", address, "sender", sender_raw))
        for address in recipient_addresses:
            entities.append(EntityDraft("email", address, "recipient", recipient_raw))
        for address in cc_addresses:
            entities.append(EntityDraft("email", address, "cc", cc_raw))
        for filename in attachments:
            entities.append(EntityDraft("filename", filename.lower(), "attachment", filename))

        events.append(
            CanonicalEventDraft(
                event_type="email",
                timestamp_raw=date_raw or None,
                timestamp_normalized=timestamp.normalized,
                timestamp_confidence=timestamp.confidence,
                timestamp_timezone=timestamp.timezone_name,
                source_locator=locator,
                source_snippet=(subject or body)[:2000],
                attributes={
                    "subject": subject,
                    "from": sender_raw,
                    "to": recipient_raw,
                    "cc": cc_raw,
                    "message_id": message_id,
                    "body": body[:10000],
                    "attachments": attachments,
                    "timestamp_basis": timestamp.basis,
                },
                entities=entities,
                warnings=list(timestamp.warnings),
            )
        )
        if not date_raw:
            warnings.append(
                ParseWarning(
                    source_locator=locator,
                    message="Email record has no timestamp.",
                )
            )
    return ParseResult(
        parser_name="email",
        parser_version="1.1.0",
        events=events,
        warnings=warnings,
        metadata={"records_total": len(rows), "emails_parsed": len(events)},
    )


class EmailParser(BaseParser):
    name = "email"
    version = "1.1.0"
    supported_extensions = (".eml", ".csv")

    def parse(self, path: Path, context: ParserContext) -> ParseResult:
        if path.suffix.lower() == ".csv":
            return _parse_csv(path, context)

        warnings: list[ParseWarning] = []
        with path.open("rb") as handle:
            message = BytesParser(policy=policy.default).parse(handle)

        subject = str(message.get("Subject", "") or "")
        sender_raw = str(message.get("From", "") or "")
        sender_address = parseaddr(sender_raw)[1].lower()
        recipients_raw = ", ".join(
            str(value) for key in ("To", "Cc") for value in (message.get_all(key) or [])
        )
        recipient_addresses = _address_list(recipients_raw)
        date_raw = str(message.get("Date", "") or "")
        message_id = str(message.get("Message-ID", "") or "")
        body = _body_text(message)
        attachments = _attachments(message)

        timestamp = parse_flexible_timestamp(
            date_raw,
            default_timezone=context.timezone,
            reference_date=context.reference_date,
            default_year=context.default_year,
        )
        combined = "\n".join([subject, sender_raw, recipients_raw, body])
        entities = [
            EntityDraft(entity_type, value, role, value)
            for entity_type, value, role in extract_entities(combined)
        ]
        if sender_address:
            entities.append(EntityDraft("email", sender_address, "sender", sender_raw))
        for address in recipient_addresses:
            entities.append(EntityDraft("email", address, "recipient", address))
        for filename in attachments:
            entities.append(EntityDraft("filename", filename.lower(), "attachment", filename))

        event = CanonicalEventDraft(
            event_type="email",
            timestamp_raw=date_raw or None,
            timestamp_normalized=timestamp.normalized,
            timestamp_confidence=timestamp.confidence,
            timestamp_timezone=timestamp.timezone_name,
            source_locator=f"email:{message_id or '1'}",
            source_snippet=(subject or body)[:2000],
            attributes={
                "subject": subject,
                "from": sender_raw,
                "from_address": sender_address,
                "to": recipients_raw,
                "message_id": message_id,
                "body": body[:10000],
                "attachments": attachments,
                "timestamp_basis": timestamp.basis,
            },
            entities=entities,
            warnings=list(timestamp.warnings),
        )
        if not body:
            warnings.append(
                ParseWarning(
                    source_locator="email:1",
                    message="Email body could not be extracted.",
                )
            )
        return ParseResult(
            parser_name=self.name,
            parser_version=self.version,
            events=[event],
            warnings=warnings,
            metadata={"attachments": len(attachments)},
        )
