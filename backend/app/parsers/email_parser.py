from __future__ import annotations

import re
from email import policy
from email.parser import BytesParser
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


class EmailParser(BaseParser):
    name = "email"
    version = "1.0.0"
    supported_extensions = (".eml",)

    def parse(self, path: Path, context: ParserContext) -> ParseResult:
        warnings: list[ParseWarning] = []
        with path.open("rb") as handle:
            message = BytesParser(policy=policy.default).parse(handle)

        subject = str(message.get("Subject", "") or "")
        sender = str(message.get("From", "") or "")
        recipients = ", ".join(
            str(value) for key in ("To", "Cc") for value in (message.get_all(key) or [])
        )
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
        combined = "\n".join([subject, sender, recipients, body])
        entities = [
            EntityDraft(entity_type, value, role, value)
            for entity_type, value, role in extract_entities(combined)
        ]
        if sender:
            entities.append(EntityDraft("email", sender.lower(), "sender", sender))
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
                "from": sender,
                "to": recipients,
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
