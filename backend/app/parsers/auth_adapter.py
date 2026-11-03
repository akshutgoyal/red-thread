from __future__ import annotations

from pathlib import Path

from .auth_log_parser import (
    AuthParserConfig,
    alert_to_dict,
    parse_file,
)
from .base import (
    BaseParser,
    CanonicalEventDraft,
    EntityDraft,
    ParseResult,
    ParseWarning,
    ParserContext,
)


def _attributes(event) -> dict:
    return {
        **event.attributes,
        "source_ip": event.source_ip,
        "username": event.username,
        "host": event.host,
        "auth_status": event.auth_status,
        "auth_method": event.auth_method,
        "invalid_user": event.invalid_user,
        "session_event": event.session_event,
        "sudo_target_user": event.sudo_target_user,
        "sudo_command": event.sudo_command,
        "disconnect_reason": event.disconnect_reason,
        "source_line_number": event.source_line_number,
        "year_inferred": event.year_inferred,
        "timestamp_confidence": event.timestamp_confidence,
    }


class AuthLogParser(BaseParser):
    name = "auth_log"
    version = "2.0.0"
    supported_extensions = (".log", ".txt")

    def parse(self, path: Path, context: ParserContext) -> ParseResult:
        config = AuthParserConfig(
            default_year=context.default_year,
            reference_date=context.reference_date,
            timezone=context.timezone,
        )
        result = parse_file(path, config)
        events: list[CanonicalEventDraft] = []
        for event in result.events:
            entities = [
                EntityDraft("ip", event.source_ip, "source_ip", event.source_ip),
                EntityDraft("username", event.username, "username", event.username),
                EntityDraft("host", event.host, "host", event.host),
                EntityDraft("username", event.sudo_target_user, "target_user", event.sudo_target_user),
            ]
            events.append(
                CanonicalEventDraft(
                    event_type=event.event_type,
                    timestamp_raw=event.timestamp_raw,
                    timestamp_normalized=event.timestamp_normalized,
                    timestamp_confidence=event.timestamp_confidence,
                    timestamp_timezone=event.timestamp_timezone,
                    source_locator=f"line:{event.source_line_number}",
                    source_snippet=event.raw_line,
                    attributes=_attributes(event),
                    entities=[entity for entity in entities if entity.value],
                    warnings=list(event.warnings),
                )
            )

        warnings = [
            ParseWarning(
                source_locator=f"line:{warning.source_line_number}",
                message=warning.message,
                source_snippet=warning.raw_line,
            )
            for warning in result.warnings
        ]
        return ParseResult(
            parser_name=self.name,
            parser_version=self.version,
            events=events,
            warnings=warnings,
            metadata={
                "summary": result.summary,
                "alerts": [alert_to_dict(alert) for alert in result.alerts],
                "lines_total": result.lines_total,
                "lines_unknown": result.lines_unknown,
                "malformed_timestamps": result.malformed_timestamps,
            },
        )
