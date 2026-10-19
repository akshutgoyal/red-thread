"""Linux authentication-log parser for Red Thread.

This module preserves the useful behaviour of the original ``auth_parser.py``
(SSH login/session/sudo extraction, threshold alerts, JSON/CSV export and live
monitoring) while making the parsing logic importable by the FastAPI backend.

Design rules:
- Importing this module has no side effects.
- Raw timestamps are preserved. A missing year or timezone is never silently
  invented; the inference and its basis are recorded on the event.
- Batch and live detection share one detection engine.
- Malformed lines are reported as warnings, not silently discarded.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import json
import re
import sys
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, TextIO
from zoneinfo import ZoneInfo

PARSER_NAME = "auth_log"
PARSER_VERSION = "2.0.0"

MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

CSV_FIELDS = [
    "event_id",
    "event_type",
    "timestamp",
    "timestamp_normalized",
    "timestamp_confidence",
    "timezone",
    "ip",
    "user",
    "host",
    "status",
    "method",
    "pid",
    "port",
    "invalid_user",
    "session_event",
    "target_user",
    "command",
    "disconnect_reason",
    "source_line_number",
    "warnings",
]


@dataclass
class AuthParserConfig:
    burst_limit: int = 8
    burst_window_seconds: int = 60
    persistent_limit: int = 10
    persistent_window_seconds: int = 15 * 60
    many_users_limit: int = 5
    invalid_user_limit: int = 2
    default_year: int | None = None
    reference_date: datetime | None = None
    timezone: str = "UTC"
    success_after_failure_window_seconds: int = 15 * 60
    enable_success_after_failure: bool = True
    max_snippet_chars: int = 2000

    def zone(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.timezone)
        except Exception:
            return ZoneInfo("UTC")

    def reference(self) -> datetime:
        reference = self.reference_date or datetime.now(timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        return reference


@dataclass
class TimestampResult:
    raw: str
    normalized: datetime | None
    confidence: str
    year_inferred: bool
    timezone_assumed: bool
    basis: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class ParseWarning:
    source_line_number: int
    message: str
    raw_line: str


@dataclass
class AuthEvent:
    event_id: str
    event_type: str
    timestamp_raw: str
    timestamp_normalized: datetime | None
    timestamp_confidence: str
    timestamp_timezone: str | None
    year_inferred: bool
    source_ip: str | None
    username: str | None
    host: str | None
    auth_status: str | None
    auth_method: str | None
    pid: str | None
    port: int | None
    invalid_user: bool
    session_event: str | None
    sudo_target_user: str | None
    sudo_command: str | None
    disconnect_reason: str | None
    source_line_number: int
    raw_line: str
    warnings: list[str] = field(default_factory=list)
    attributes: dict = field(default_factory=dict)


@dataclass
class DetectionAlert:
    alert_id: str
    source_ip: str | None
    username: str | None
    score: int
    level: str
    rule_ids: list[str]
    reasons: list[str]
    first_seen: datetime | None
    last_seen: datetime | None
    event_line_numbers: list[int]
    event_count: int
    limitations: list[str] = field(default_factory=list)


@dataclass
class AuthParseResult:
    parser_name: str
    parser_version: str
    events: list[AuthEvent]
    alerts: list[DetectionAlert]
    warnings: list[ParseWarning]
    summary: dict
    lines_total: int
    lines_parsed: int
    lines_blank: int
    lines_unknown: int
    malformed_timestamps: int


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------

SYSLOG_TS_RE = re.compile(
    r"^(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})$"
)
ISO_TS_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$"
)
YEAR_TS_RE = re.compile(
    r"^(?P<year>\d{4})[-/ ]"
    r"(?P<month>[A-Z][a-z]{2}|\d{1,2})[-/ ]"
    r"(?P<day>\d{1,2})[ T]"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})"
    r"(?P<tz>Z|[+-]\d{2}:?\d{2})?$"
)


def _safe_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def _to_utc(value: datetime, zone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=zone)
    return value.astimezone(timezone.utc)


def _choose_year(
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    reference: datetime,
) -> tuple[datetime | None, str]:
    candidates: list[datetime] = []
    for year in (reference.year - 1, reference.year, reference.year + 1):
        try:
            candidates.append(datetime(year, month, day, hour, minute, second))
        except ValueError:
            continue
    if not candidates:
        return None, "invalid calendar date"
    ref_naive = reference.replace(tzinfo=None)
    past = [item for item in candidates if item <= ref_naive]
    chosen = max(past) if past else min(candidates)
    basis = (
        f"year inferred as {chosen.year} from reference date "
        f"{ref_naive.date().isoformat()}"
    )
    return chosen, basis


def parse_timestamp(raw: str, config: AuthParserConfig) -> TimestampResult:
    """Parse a log timestamp without silently inventing missing information."""
    value = (raw or "").strip()
    zone = config.zone()
    warnings: list[str] = []

    if not value:
        return TimestampResult(
            raw=raw,
            normalized=None,
            confidence="unknown",
            year_inferred=False,
            timezone_assumed=False,
            basis="empty timestamp",
            warnings=["Empty timestamp."],
        )

    # Epoch seconds.
    if value.isdigit() and len(value) >= 10:
        try:
            moment = datetime.fromtimestamp(int(value), tz=timezone.utc)
            return TimestampResult(
                raw=raw,
                normalized=moment,
                confidence="exact",
                year_inferred=False,
                timezone_assumed=False,
                basis="unix epoch",
            )
        except (OverflowError, OSError, ValueError):
            return TimestampResult(
                raw=raw,
                normalized=None,
                confidence="unknown",
                year_inferred=False,
                timezone_assumed=False,
                basis="invalid unix epoch",
                warnings=["Epoch timestamp could not be parsed."],
            )

    # ISO 8601.
    if ISO_TS_RE.match(value):
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return TimestampResult(
                raw=raw,
                normalized=None,
                confidence="unknown",
                year_inferred=False,
                timezone_assumed=False,
                basis="invalid ISO timestamp",
                warnings=["ISO timestamp could not be parsed."],
            )
        if moment.tzinfo is None:
            warnings.append(
                f"Timestamp has no timezone; interpreted as {config.timezone}."
            )
            return TimestampResult(
                raw=raw,
                normalized=_to_utc(moment, zone),
                confidence="ambiguous",
                year_inferred=False,
                timezone_assumed=True,
                basis=f"timezone assumed {config.timezone}",
                warnings=warnings,
            )
        return TimestampResult(
            raw=raw,
            normalized=moment.astimezone(timezone.utc),
            confidence="exact",
            year_inferred=False,
            timezone_assumed=False,
            basis="timestamp included timezone",
        )

    # Timestamp with an explicit year (syslog-like or compact).
    year_match = YEAR_TS_RE.match(value)
    if year_match:
        month_text = year_match.group("month")
        month = MONTHS.get(month_text) if month_text in MONTHS else int(month_text)
        try:
            naive = datetime(
                int(year_match.group("year")),
                month,
                int(year_match.group("day")),
                int(year_match.group("hour")),
                int(year_match.group("minute")),
                int(year_match.group("second")),
            )
        except ValueError:
            return TimestampResult(
                raw=raw,
                normalized=None,
                confidence="unknown",
                year_inferred=False,
                timezone_assumed=False,
                basis="invalid calendar date",
                warnings=["Timestamp contains an invalid calendar date."],
            )
        tz_text = year_match.group("tz")
        if tz_text:
            if tz_text == "Z":
                moment = naive.replace(tzinfo=timezone.utc)
            else:
                normalized_tz = tz_text if ":" in tz_text else f"{tz_text[:3]}:{tz_text[3:]}"
                moment = naive.replace(tzinfo=timezone.fromisoformat(normalized_tz))
            return TimestampResult(
                raw=raw,
                normalized=moment.astimezone(timezone.utc),
                confidence="exact",
                year_inferred=False,
                timezone_assumed=False,
                basis="timestamp included year and timezone",
            )
        warnings.append(
            f"Timestamp has no timezone; interpreted as {config.timezone}."
        )
        return TimestampResult(
            raw=raw,
            normalized=_to_utc(naive, zone),
            confidence="ambiguous",
            year_inferred=False,
            timezone_assumed=True,
            basis=f"timezone assumed {config.timezone}",
            warnings=warnings,
        )

    # Traditional syslog timestamp: no year, no timezone.
    syslog_match = SYSLOG_TS_RE.match(value)
    if syslog_match:
        month = MONTHS.get(syslog_match.group("month"))
        if month is None:
            return TimestampResult(
                raw=raw,
                normalized=None,
                confidence="unknown",
                year_inferred=False,
                timezone_assumed=False,
                basis="unknown month",
                warnings=["Timestamp contains an unknown month."],
            )
        day = int(syslog_match.group("day"))
        hour = int(syslog_match.group("hour"))
        minute = int(syslog_match.group("minute"))
        second = int(syslog_match.group("second"))

        if config.default_year is not None:
            year: int | None = config.default_year
            basis = f"year set to configured default {year}"
            year_inferred = True
        else:
            chosen, basis = _choose_year(
                month, day, hour, minute, second, config.reference()
            )
            year = chosen.year if chosen else None
            year_inferred = True

        if year is None:
            return TimestampResult(
                raw=raw,
                normalized=None,
                confidence="unknown",
                year_inferred=year_inferred,
                timezone_assumed=True,
                basis=basis,
                warnings=["Year could not be inferred; normalized timestamp is unavailable."],
            )

        try:
            naive = datetime(year, month, day, hour, minute, second)
        except ValueError:
            return TimestampResult(
                raw=raw,
                normalized=None,
                confidence="unknown",
                year_inferred=True,
                timezone_assumed=False,
                basis="invalid calendar date",
                warnings=["Timestamp contains an invalid calendar date."],
            )

        warnings.append(
            f"Year not present in source timestamp; {basis}."
        )
        warnings.append(
            f"Timezone not present in source timestamp; interpreted as {config.timezone}."
        )
        return TimestampResult(
            raw=raw,
            normalized=_to_utc(naive, zone),
            confidence="inferred_year",
            year_inferred=True,
            timezone_assumed=True,
            basis=basis,
            warnings=warnings,
        )

    return TimestampResult(
        raw=raw,
        normalized=None,
        confidence="unknown",
        year_inferred=False,
        timezone_assumed=False,
        basis="unrecognized timestamp format",
        warnings=["Unrecognized timestamp format."],
    )


# ---------------------------------------------------------------------------
# Line patterns
# ---------------------------------------------------------------------------

_TS = r"(?P<timestamp>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"
_HOST = r"(?P<host>\S+)"
_SSHD = r"sshd\[(?P<pid>\d+)\]:"
_IP = r"(?P<ip>[0-9A-Fa-f:.]+)"

SSH_LOGIN_RE = re.compile(
    rf"^{_TS}\s+{_HOST}\s+{_SSHD}\s+"
    r"(?P<status>Accepted|Failed)\s+"
    r"(?P<method>password|publickey|keyboard-interactive|hostbased|none|gssapi-with-mic)\s+"
    r"for\s+(?:(?P<invalid>invalid user)\s+)?(?P<user>\S+)\s+"
    rf"from\s+{_IP}\s+port\s+(?P<port>\d+)"
    r"(?:\s+ssh2)?(?::.*)?$"
)

SSH_INVALID_RE = re.compile(
    rf"^{_TS}\s+{_HOST}\s+{_SSHD}\s+Invalid user\s+(?P<user>\S+)\s+"
    rf"from\s+{_IP}\s+port\s+(?P<port>\d+)$"
)

SSH_CLOSED_RE = re.compile(
    rf"^{_TS}\s+{_HOST}\s+{_SSHD}\s+"
    r"(?P<event>Connection closed by|Disconnected from)\s+"
    r"(?:authenticating user\s+)?(?P<user>\S+)\s+"
    rf"{_IP}\s+port\s+(?P<port>\d+)(?:\s+\[preauth\])?$"
)

SSH_CLOSED_NO_USER_RE = re.compile(
    rf"^{_TS}\s+{_HOST}\s+{_SSHD}\s+"
    r"(?P<event>Connection closed by|Disconnected from)\s+"
    rf"{_IP}\s+port\s+(?P<port>\d+)(?:\s+\[preauth\])?$"
)

SSH_DISCONNECT_RE = re.compile(
    rf"^{_TS}\s+{_HOST}\s+{_SSHD}\s+Received disconnect from\s+"
    rf"{_IP}\s+port\s+(?P<port>\d+):\s*(?P<reason>.*)$"
)

SESSION_RE = re.compile(
    rf"^{_TS}\s+{_HOST}\s+{_SSHD}\s+"
    r"pam_unix\(sshd:session\):\s+session\s+(?P<event>opened|closed)\s+"
    r"for\s+user\s+(?P<user>[\w.\-]+)(?:\(uid=\d+\))?"
    r"(?:\s+by\s+\(uid=\d+\))?$"
)

SUDO_RE = re.compile(
    rf"^{_TS}\s+{_HOST}\s+sudo:\s+"
    r"(?P<user>\S+)\s+:\s+.*?USER=(?P<target_user>\S+)\s+;\s+"
    r"COMMAND=(?P<command>.+)$"
)

SUDO_SESSION_RE = re.compile(
    rf"^{_TS}\s+{_HOST}\s+sudo:\s+"
    r"pam_unix\(sudo:session\):\s+session\s+(?P<event>opened|closed)\s+"
    r"for\s+user\s+(?P<user>[\w.\-]+)(?:\(uid=\d+\))?(?:\s+by\s+(?P<by>\S+))?$"
)


def _canonical_ip(raw: str | None) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    value = raw.strip().strip("[],")
    value = value.split("%", 1)[0]
    try:
        return str(ipaddress.ip_address(value)), None
    except ValueError:
        return None, f"Invalid IP address: {raw}"


def _event_id(line_number: int, raw_line: str) -> str:
    digest = hashlib.sha1(f"{line_number}:{raw_line}".encode("utf-8")).hexdigest()
    return f"auth-{digest[:16]}"


def _snippet(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit] + "…"


def parse_line(
    line: str,
    line_number: int,
    config: AuthParserConfig | None = None,
) -> AuthEvent | ParseWarning | None:
    """Parse one line into an AuthEvent, a ParseWarning, or None for blanks."""
    config = config or AuthParserConfig()
    raw_line = line.rstrip("\n\r")
    stripped = raw_line.strip()
    if not stripped:
        return None

    def build_event(
        *,
        event_type: str,
        timestamp_text: str,
        username: str | None,
        source_ip: str | None,
        host: str | None,
        auth_status: str | None = None,
        auth_method: str | None = None,
        pid: str | None = None,
        port: str | None = None,
        invalid_user: bool = False,
        session_event: str | None = None,
        sudo_target_user: str | None = None,
        sudo_command: str | None = None,
        disconnect_reason: str | None = None,
    ) -> AuthEvent:
        ts = parse_timestamp(timestamp_text, config)
        canonical_ip, ip_warning = _canonical_ip(source_ip)
        warnings = list(ts.warnings)
        if ip_warning:
            warnings.append(ip_warning)
        attributes = {
            "timestamp_basis": ts.basis,
            "timestamp_year_inferred": ts.year_inferred,
            "timestamp_timezone_assumed": ts.timezone_assumed,
            "auth_status": auth_status,
            "auth_method": auth_method,
            "pid": pid,
            "port": int(port) if port and port.isdigit() else None,
            "invalid_user": invalid_user,
            "session_event": session_event,
            "sudo_target_user": sudo_target_user,
            "sudo_command": sudo_command,
            "disconnect_reason": disconnect_reason,
            "host": host,
        }
        return AuthEvent(
            event_id=_event_id(line_number, raw_line),
            event_type=event_type,
            timestamp_raw=timestamp_text,
            timestamp_normalized=ts.normalized,
            timestamp_confidence=ts.confidence,
            timestamp_timezone=config.timezone if ts.timezone_assumed else None,
            year_inferred=ts.year_inferred,
            source_ip=canonical_ip,
            username=username,
            host=host,
            auth_status=auth_status,
            auth_method=auth_method,
            pid=pid,
            port=int(port) if port and port.isdigit() else None,
            invalid_user=invalid_user,
            session_event=session_event,
            sudo_target_user=sudo_target_user,
            sudo_command=sudo_command,
            disconnect_reason=disconnect_reason,
            source_line_number=line_number,
            raw_line=_snippet(raw_line, config.max_snippet_chars),
            warnings=warnings,
            attributes=attributes,
        )

    match = SSH_LOGIN_RE.match(stripped)
    if match:
        status = "success" if match.group("status") == "Accepted" else "failure"
        return build_event(
            event_type="auth.login",
            timestamp_text=match.group("timestamp"),
            username=match.group("user"),
            source_ip=match.group("ip"),
            host=match.group("host"),
            auth_status=status,
            auth_method=match.group("method"),
            pid=match.group("pid"),
            port=match.group("port"),
            invalid_user=match.group("invalid") is not None,
        )

    match = SSH_INVALID_RE.match(stripped)
    if match:
        return build_event(
            event_type="auth.invalid_user",
            timestamp_text=match.group("timestamp"),
            username=match.group("user"),
            source_ip=match.group("ip"),
            host=match.group("host"),
            auth_status="failure",
            pid=match.group("pid"),
            port=match.group("port"),
            invalid_user=True,
        )

    match = SSH_CLOSED_NO_USER_RE.match(stripped)
    if match:
        return build_event(
            event_type="auth.connection_closed",
            timestamp_text=match.group("timestamp"),
            username=None,
            source_ip=match.group("ip"),
            host=match.group("host"),
            pid=match.group("pid"),
            port=match.group("port"),
        )

    match = SSH_CLOSED_RE.match(stripped)
    if match:
        return build_event(
            event_type="auth.connection_closed",
            timestamp_text=match.group("timestamp"),
            username=match.group("user"),
            source_ip=match.group("ip"),
            host=match.group("host"),
            pid=match.group("pid"),
            port=match.group("port"),
        )

    match = SSH_DISCONNECT_RE.match(stripped)
    if match:
        return build_event(
            event_type="auth.disconnect",
            timestamp_text=match.group("timestamp"),
            username=None,
            source_ip=match.group("ip"),
            host=match.group("host"),
            pid=match.group("pid"),
            port=match.group("port"),
            disconnect_reason=match.group("reason") or None,
        )

    match = SESSION_RE.match(stripped)
    if match:
        return build_event(
            event_type="auth.session",
            timestamp_text=match.group("timestamp"),
            username=match.group("user"),
            source_ip=None,
            host=match.group("host"),
            pid=match.group("pid"),
            session_event=match.group("event"),
        )

    match = SUDO_RE.match(stripped)
    if match:
        return build_event(
            event_type="auth.sudo",
            timestamp_text=match.group("timestamp"),
            username=match.group("user"),
            source_ip=None,
            host=match.group("host"),
            sudo_target_user=match.group("target_user"),
            sudo_command=match.group("command"),
        )

    match = SUDO_SESSION_RE.match(stripped)
    if match:
        return build_event(
            event_type="auth.sudo_session",
            timestamp_text=match.group("timestamp"),
            username=match.group("user"),
            source_ip=None,
            host=match.group("host"),
            session_event=match.group("event"),
        )

    return ParseWarning(
        source_line_number=line_number,
        message="Unrecognized authentication log line.",
        raw_line=_snippet(raw_line, config.max_snippet_chars),
    )


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

RULE_WEIGHTS = {
    "AUTH-BURST-001": 3,
    "AUTH-PERSIST-002": 2,
    "AUTH-MULTIUSER-003": 2,
    "AUTH-INVALID-004": 2,
    "AUTH-SUCCESS-AFTER-FAIL-005": 2,
}

ALERT_LIMITATIONS = [
    "Threshold-based indicator, not proof of compromise.",
    "Failed logins may be benign user error, misconfiguration, or authorized testing.",
    "Timestamps may have inferred years or assumed timezones; see each event's warnings.",
    "A successful login after failures may be legitimate; corroborate with other evidence.",
]


def _failed_logins(events: Iterable[AuthEvent]) -> list[AuthEvent]:
    return [
        event
        for event in events
        if event.event_type == "auth.login"
        and event.auth_status == "failure"
        and event.timestamp_normalized is not None
    ]


def _find_count_window(
    events: list[AuthEvent],
    limit: int,
    window_seconds: int,
    predicate: Callable[[AuthEvent], bool] | None = None,
) -> list[AuthEvent] | None:
    selected = [event for event in events if predicate is None or predicate(event)]
    left = 0
    for right in range(len(selected)):
        while (
            selected[right].timestamp_normalized
            - selected[left].timestamp_normalized
        ).total_seconds() > window_seconds:
            left += 1
        if right - left + 1 >= limit:
            return selected[left : right + 1]
    return None


def _find_distinct_user_window(
    events: list[AuthEvent],
    limit: int,
    window_seconds: int,
) -> list[AuthEvent] | None:
    left = 0
    counts: Counter[str] = Counter()
    for right in range(len(events)):
        user = events[right].username
        if user:
            counts[user] += 1
        while (
            events[right].timestamp_normalized
            - events[left].timestamp_normalized
        ).total_seconds() > window_seconds:
            old_user = events[left].username
            if old_user:
                counts[old_user] -= 1
                if counts[old_user] <= 0:
                    del counts[old_user]
            left += 1
        if len(counts) >= limit:
            return events[left : right + 1]
    return None


def _make_alert(
    ip: str,
    rule_ids: list[str],
    reasons: list[str],
    line_numbers: set[int],
    first_seen: datetime | None,
    last_seen: datetime | None,
    event_count: int,
    username: str | None = None,
) -> DetectionAlert:
    unique_rules = sorted(dict.fromkeys(rule_ids))
    score = sum(RULE_WEIGHTS[rule] for rule in unique_rules)
    if score >= 5:
        level = "HIGH SUSPICION"
    elif score >= 3:
        level = "SUSPICIOUS"
    else:
        level = "NORMAL"
    return DetectionAlert(
        alert_id=f"AUTH-{ip}-{'-'.join(unique_rules)}",
        source_ip=ip,
        username=username,
        score=score,
        level=level,
        rule_ids=unique_rules,
        reasons=reasons,
        first_seen=first_seen,
        last_seen=last_seen,
        event_line_numbers=sorted(line_numbers),
        event_count=event_count,
        limitations=list(ALERT_LIMITATIONS),
    )


def evaluate_ip(
    ip: str,
    failures: list[AuthEvent],
    successes: list[AuthEvent],
    config: AuthParserConfig,
) -> DetectionAlert | None:
    """Evaluate one IP using the shared batch/live detection rules."""
    failures = sorted(
        [event for event in failures if event.timestamp_normalized is not None],
        key=lambda event: event.timestamp_normalized,
    )
    successes = sorted(
        [event for event in successes if event.timestamp_normalized is not None],
        key=lambda event: event.timestamp_normalized,
    )

    rule_ids: list[str] = []
    reasons: list[str] = []
    line_numbers: set[int] = set()
    relevant_times: list[datetime] = []

    burst = _find_count_window(
        failures, config.burst_limit, config.burst_window_seconds
    )
    if burst:
        rule_ids.append("AUTH-BURST-001")
        reasons.append(
            f"Burst failures: {len(burst)} failures within "
            f"{config.burst_window_seconds} seconds"
        )
        line_numbers.update(event.source_line_number for event in burst)
        relevant_times.extend(event.timestamp_normalized for event in burst)

    persistent = _find_count_window(
        failures, config.persistent_limit, config.persistent_window_seconds
    )
    if persistent:
        rule_ids.append("AUTH-PERSIST-002")
        reasons.append(
            f"Persistent failures: {len(persistent)} failures within "
            f"{config.persistent_window_seconds} seconds"
        )
        line_numbers.update(event.source_line_number for event in persistent)
        relevant_times.extend(event.timestamp_normalized for event in persistent)

    many_users = _find_distinct_user_window(
        failures, config.many_users_limit, config.persistent_window_seconds
    )
    if many_users:
        window_end = failures[-1].timestamp_normalized
        window_events = [
            event
            for event in failures
            if 0
            <= (window_end - event.timestamp_normalized).total_seconds()
            <= config.persistent_window_seconds
        ]
        usernames = sorted(
            {event.username for event in window_events if event.username}
        )
        rule_ids.append("AUTH-MULTIUSER-003")
        reasons.append(
            f"Many usernames targeted: {len(usernames)} different users "
            f"within {config.persistent_window_seconds} seconds"
        )
        line_numbers.update(event.source_line_number for event in window_events)
        relevant_times.extend(event.timestamp_normalized for event in window_events)

    invalid = _find_count_window(
        failures,
        config.invalid_user_limit,
        config.persistent_window_seconds,
        predicate=lambda event: event.invalid_user,
    )
    if invalid:
        window_end = failures[-1].timestamp_normalized
        invalid_window = [
            event
            for event in failures
            if event.invalid_user
            and 0
            <= (window_end - event.timestamp_normalized).total_seconds()
            <= config.persistent_window_seconds
        ]
        rule_ids.append("AUTH-INVALID-004")
        reasons.append(
            f"Repeated invalid usernames: {len(invalid_window)} attempts within "
            f"{config.persistent_window_seconds} seconds"
        )
        line_numbers.update(event.source_line_number for event in invalid_window)
        relevant_times.extend(event.timestamp_normalized for event in invalid_window)

    if config.enable_success_after_failure:
        for success in successes:
            recent_failures = [
                failure
                for failure in failures
                if 0
                <= (
                    success.timestamp_normalized - failure.timestamp_normalized
                ).total_seconds()
                <= config.success_after_failure_window_seconds
            ]
            if len(recent_failures) >= config.burst_limit:
                rule_ids.append("AUTH-SUCCESS-AFTER-FAIL-005")
                reasons.append(
                    f"Successful login after {len(recent_failures)} failures "
                    f"within {config.success_after_failure_window_seconds} seconds"
                )
                line_numbers.add(success.source_line_number)
                line_numbers.update(
                    event.source_line_number for event in recent_failures
                )
                relevant_times.append(success.timestamp_normalized)
                relevant_times.extend(
                    event.timestamp_normalized for event in recent_failures
                )
                break

    if not rule_ids:
        return None

    first_seen = min(relevant_times) if relevant_times else None
    last_seen = max(relevant_times) if relevant_times else None
    usernames = {event.username for event in failures if event.username}
    username = sorted(usernames)[0] if len(usernames) == 1 else None
    return _make_alert(
        ip=ip,
        rule_ids=rule_ids,
        reasons=reasons,
        line_numbers=line_numbers,
        first_seen=first_seen,
        last_seen=last_seen,
        event_count=len(line_numbers),
        username=username,
    )


class LiveSecurityTracker:
    """Incremental detector used by both batch parsing and live monitoring."""

    def __init__(self, config: AuthParserConfig | None = None) -> None:
        self.config = config or AuthParserConfig()
        self.max_window = max(
            self.config.burst_window_seconds,
            self.config.persistent_window_seconds,
            self.config.success_after_failure_window_seconds,
        )
        self.failures: defaultdict[str, deque[AuthEvent]] = defaultdict(deque)
        self.successes: defaultdict[str, deque[AuthEvent]] = defaultdict(deque)
        self.last_score: dict[str, int] = {}
        self.last_rules: dict[str, tuple[str, ...]] = {}

    def _prune(self, window: deque[AuthEvent], now: datetime) -> None:
        while window and (now - window[0].timestamp_normalized).total_seconds() > self.max_window:
            window.popleft()

    def process(self, event: AuthEvent) -> DetectionAlert | None:
        if event.event_type != "auth.login":
            return None
        if event.timestamp_normalized is None or not event.source_ip:
            return None

        ip = event.source_ip
        if event.auth_status == "failure":
            self.failures[ip].append(event)
            self._prune(self.failures[ip], event.timestamp_normalized)
        elif event.auth_status == "success":
            self.successes[ip].append(event)
            self._prune(self.successes[ip], event.timestamp_normalized)
        else:
            return None

        alert = evaluate_ip(
            ip,
            list(self.failures[ip]),
            list(self.successes[ip]),
            self.config,
        )
        if alert is None:
            return None

        previous_score = self.last_score.get(ip, 0)
        previous_rules = set(self.last_rules.get(ip, ()))
        if alert.score > previous_score or not set(alert.rule_ids).issubset(previous_rules):
            self.last_score[ip] = alert.score
            self.last_rules[ip] = tuple(alert.rule_ids)
            return alert
        return None


def detect_alerts(events: Iterable[AuthEvent], config: AuthParserConfig) -> list[DetectionAlert]:
    """Batch detection that uses the same engine as live monitoring."""
    ordered = sorted(
        [event for event in events if event.timestamp_normalized is not None],
        key=lambda event: event.timestamp_normalized,
    )
    tracker = LiveSecurityTracker(config)
    emitted: dict[str, list[DetectionAlert]] = defaultdict(list)
    for event in ordered:
        alert = tracker.process(event)
        if alert is not None and alert.source_ip:
            emitted[alert.source_ip].append(alert)

    reason_prefixes = {
        "Burst failures": "AUTH-BURST-001",
        "Persistent failures": "AUTH-PERSIST-002",
        "Many usernames targeted": "AUTH-MULTIUSER-003",
        "Repeated invalid usernames": "AUTH-INVALID-004",
        "Successful login after": "AUTH-SUCCESS-AFTER-FAIL-005",
    }
    consolidated: list[DetectionAlert] = []
    for ip, alerts in emitted.items():
        final = alerts[-1]
        line_numbers = sorted({line for alert in alerts for line in alert.event_line_numbers})
        reason_by_rule: dict[str, str] = {}
        for alert in alerts:
            for reason in alert.reasons:
                for prefix, rule in reason_prefixes.items():
                    if reason.startswith(prefix):
                        reason_by_rule[rule] = reason
                        break
        rule_ids = sorted({rule for alert in alerts for rule in alert.rule_ids})
        reasons = [
            reason_by_rule[rule] for rule in rule_ids if rule in reason_by_rule
        ]
        consolidated.append(
            _make_alert(
                ip=ip,
                rule_ids=rule_ids,
                reasons=reasons,
                line_numbers=set(line_numbers),
                first_seen=min(
                    (alert.first_seen for alert in alerts if alert.first_seen),
                    default=None,
                ),
                last_seen=max(
                    (alert.last_seen for alert in alerts if alert.last_seen),
                    default=None,
                ),
                event_count=len(line_numbers),
                username=final.username,
            )
        )
    return sorted(consolidated, key=lambda alert: (alert.source_ip or "", alert.alert_id))


# ---------------------------------------------------------------------------
# Batch parsing
# ---------------------------------------------------------------------------

def _summarize(events: list[AuthEvent], lines_total: int, lines_unknown: int, malformed: int) -> dict:
    login_events = [event for event in events if event.event_type == "auth.login"]
    failures = [event for event in login_events if event.auth_status == "failure"]
    successes = [event for event in login_events if event.auth_status == "success"]
    usernames = Counter(event.username for event in login_events if event.username)
    ips = Counter(event.source_ip for event in login_events if event.source_ip)
    return {
        "total_events": len(events),
        "total_login_attempts": len(login_events),
        "successful_logins": len(successes),
        "failed_logins": len(failures),
        "session_events": sum(1 for event in events if event.event_type == "auth.session"),
        "sudo_commands": sum(1 for event in events if event.event_type == "auth.sudo"),
        "invalid_user_attempts": sum(1 for event in events if event.invalid_user),
        "top_usernames": dict(usernames.most_common(5)),
        "top_ips": dict(ips.most_common(5)),
        "lines_total": lines_total,
        "lines_unknown": lines_unknown,
        "malformed_timestamps": malformed,
    }


def parse_text(
    text: str,
    config: AuthParserConfig | None = None,
    source_name: str = "<text>",
) -> AuthParseResult:
    config = config or AuthParserConfig()
    events: list[AuthEvent] = []
    warnings: list[ParseWarning] = []
    lines_total = 0
    lines_blank = 0
    lines_unknown = 0
    malformed = 0

    for index, line in enumerate(text.splitlines(), start=1):
        lines_total += 1
        parsed = parse_line(line, index, config)
        if parsed is None:
            lines_blank += 1
            continue
        if isinstance(parsed, ParseWarning):
            lines_unknown += 1
            if len(warnings) < 100:
                warnings.append(parsed)
            continue
        events.append(parsed)
        if parsed.timestamp_normalized is None:
            malformed += 1

    alerts = detect_alerts(events, config)
    summary = _summarize(events, lines_total, lines_unknown, malformed)
    summary["source"] = source_name
    return AuthParseResult(
        parser_name=PARSER_NAME,
        parser_version=PARSER_VERSION,
        events=events,
        alerts=alerts,
        warnings=warnings,
        summary=summary,
        lines_total=lines_total,
        lines_parsed=len(events),
        lines_blank=lines_blank,
        lines_unknown=lines_unknown,
        malformed_timestamps=malformed,
    )


def parse_file(
    path: str | Path,
    config: AuthParserConfig | None = None,
) -> AuthParseResult:
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8", errors="replace") as handle:
        return parse_text(handle.read(), config=config, source_name=file_path.name)


# ---------------------------------------------------------------------------
# Serialization and export
# ---------------------------------------------------------------------------

def event_to_dict(event: AuthEvent) -> dict:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp_raw,
        "timestamp_normalized": (
            event.timestamp_normalized.isoformat() if event.timestamp_normalized else None
        ),
        "timestamp_confidence": event.timestamp_confidence,
        "timezone": event.timestamp_timezone,
        "ip": event.source_ip,
        "user": event.username,
        "host": event.host,
        "status": event.auth_status,
        "method": event.auth_method,
        "pid": event.pid,
        "port": event.port,
        "invalid_user": event.invalid_user,
        "session_event": event.session_event,
        "target_user": event.sudo_target_user,
        "command": event.sudo_command,
        "disconnect_reason": event.disconnect_reason,
        "source_line_number": event.source_line_number,
        "warnings": list(event.warnings),
        "attributes": dict(event.attributes),
        "raw_line": event.raw_line,
    }


def alert_to_dict(alert: DetectionAlert) -> dict:
    return {
        "alert_id": alert.alert_id,
        "source_ip": alert.source_ip,
        "username": alert.username,
        "score": alert.score,
        "level": alert.level,
        "rule_ids": list(alert.rule_ids),
        "reasons": list(alert.reasons),
        "first_seen": alert.first_seen.isoformat() if alert.first_seen else None,
        "last_seen": alert.last_seen.isoformat() if alert.last_seen else None,
        "event_line_numbers": list(alert.event_line_numbers),
        "event_count": alert.event_count,
        "limitations": list(alert.limitations),
    }


def export_json(path: str | Path, result: AuthParseResult) -> None:
    payload = {
        "parser": {"name": result.parser_name, "version": result.parser_version},
        "summary": result.summary,
        "security_report": [alert_to_dict(alert) for alert in result.alerts],
        "events": [event_to_dict(event) for event in result.events],
        "warnings": [
            {
                "source_line_number": warning.source_line_number,
                "message": warning.message,
                "raw_line": warning.raw_line,
            }
            for warning in result.warnings
        ],
    }
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def export_csv(path: str | Path, result: AuthParseResult) -> str:
    output = Path(path)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for event in result.events:
            row = event_to_dict(event)
            row["warnings"] = "; ".join(event.warnings)
            writer.writerow(row)

    security_path = output.with_name(f"{output.stem}_security{output.suffix or '.csv'}")
    with security_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "alert_id",
                "ip",
                "username",
                "score",
                "level",
                "rule_ids",
                "reasons",
                "first_seen",
                "last_seen",
                "event_line_numbers",
            ]
        )
        for alert in result.alerts:
            writer.writerow(
                [
                    alert.alert_id,
                    alert.source_ip,
                    alert.username,
                    alert.score,
                    alert.level,
                    "; ".join(alert.rule_ids),
                    "; ".join(alert.reasons),
                    alert.first_seen.isoformat() if alert.first_seen else "",
                    alert.last_seen.isoformat() if alert.last_seen else "",
                    ",".join(str(line) for line in alert.event_line_numbers),
                ]
            )
    return str(security_path)


def export_security_csv(path: str | Path, result: AuthParseResult) -> None:
    output = Path(path)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "alert_id",
                "ip",
                "username",
                "score",
                "level",
                "rule_ids",
                "reasons",
                "first_seen",
                "last_seen",
                "event_line_numbers",
            ]
        )
        for alert in result.alerts:
            writer.writerow(
                [
                    alert.alert_id,
                    alert.source_ip,
                    alert.username,
                    alert.score,
                    alert.level,
                    "; ".join(alert.rule_ids),
                    "; ".join(alert.reasons),
                    alert.first_seen.isoformat() if alert.first_seen else "",
                    alert.last_seen.isoformat() if alert.last_seen else "",
                    ",".join(str(line) for line in alert.event_line_numbers),
                ]
            )


# ---------------------------------------------------------------------------
# Live monitoring
# ---------------------------------------------------------------------------

def _count_existing_lines(path: Path) -> int:
    try:
        with path.open("rb") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def monitor_live(
    file_path: str | Path,
    config: AuthParserConfig | None = None,
    *,
    from_start: bool = False,
    stop_event=None,
    on_event: Callable[[AuthEvent], None] | None = None,
    on_alert: Callable[[DetectionAlert], None] | None = None,
    on_warning: Callable[[ParseWarning], None] | None = None,
    poll_interval: float = 1.0,
    quiet: bool = False,
    output: TextIO | None = None,
) -> int:
    """Tail an authorization log and emit events/alerts.

    ``stop_event`` may be a ``threading.Event``; when omitted, monitoring runs
    until Ctrl+C. The function returns a process-style exit code.
    """
    config = config or AuthParserConfig()
    output = output or sys.stdout
    path = Path(file_path)
    tracker = LiveSecurityTracker(config)

    try:
        handle = path.open("r", encoding="utf-8", errors="replace")
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.", file=output)
        return 2
    except PermissionError:
        print(f"Error: Permission denied for '{file_path}'.", file=output)
        return 3

    with handle:
        if not from_start:
            line_number = _count_existing_lines(path)
            handle.seek(0, 2)
        else:
            line_number = 0

        if not quiet:
            print("\n====== LIVE MONITORING ======", file=output)
            print("Watching for new log entries...", file=output)
            print("Press Ctrl+C to stop.\n", file=output, flush=True)

        try:
            while True:
                if stop_event is not None and stop_event.is_set():
                    break
                position = handle.tell()
                line = handle.readline()
                if not line:
                    try:
                        if path.stat().st_size < position:
                            handle.seek(0)
                            line_number = 0
                    except OSError:
                        pass
                    if stop_event is not None:
                        stop_event.wait(poll_interval)
                    else:
                        time.sleep(poll_interval)
                    continue
                if not line.endswith("\n"):
                    handle.seek(position)
                    if stop_event is not None:
                        stop_event.wait(poll_interval / 2)
                    else:
                        time.sleep(poll_interval / 2)
                    continue

                line_number += 1
                parsed = parse_line(line, line_number, config)
                if parsed is None:
                    continue
                if isinstance(parsed, ParseWarning):
                    if on_warning:
                        on_warning(parsed)
                    if not quiet:
                        print(f"[warning] line {line_number}: {parsed.message}", file=output)
                    continue

                if on_event:
                    on_event(parsed)
                if not quiet:
                    print(parsed, file=output, flush=True)

                alert = tracker.process(parsed)
                if alert is not None:
                    if on_alert:
                        on_alert(alert)
                    if not quiet:
                        print("\n!!! SECURITY ALERT !!!", file=output)
                        print(f"IP: {alert.source_ip}", file=output)
                        print(f"Score: {alert.score}", file=output)
                        print(f"Level: {alert.level}", file=output)
                        print("Rules: " + ", ".join(alert.rule_ids), file=output)
                        for reason in alert.reasons:
                            print(f"- {reason}", file=output)
                        print(file=output, flush=True)
        except KeyboardInterrupt:
            if not quiet:
                print("\nLive monitoring stopped.", file=output)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse Linux authentication logs and detect threshold-based indicators."
    )
    parser.add_argument("file", help="Path to the authentication log file")
    parser.add_argument("--live", action="store_true", help="Monitor the log for new entries")
    parser.add_argument("--from-start", action="store_true", help="In live mode, read the existing file first")
    parser.add_argument("--json", metavar="FILE", help="Export events, summary and alerts to JSON")
    parser.add_argument("--csv", metavar="FILE", help="Export events to CSV; alerts go to FILE_security.csv")
    parser.add_argument("--year", type=int, default=None, help="Year to use for syslog timestamps without a year")
    parser.add_argument("--timezone", default="UTC", help="Timezone to assume when the log omits one")
    parser.add_argument("--burst-limit", type=int, default=8)
    parser.add_argument("--burst-window", type=int, default=60, help="Burst window in seconds")
    parser.add_argument("--persistent-limit", type=int, default=10)
    parser.add_argument("--persistent-window", type=int, default=15 * 60, help="Persistent window in seconds")
    parser.add_argument("--many-users-limit", type=int, default=5)
    parser.add_argument("--invalid-user-limit", type=int, default=2)
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = AuthParserConfig(
        burst_limit=args.burst_limit,
        burst_window_seconds=args.burst_window,
        persistent_limit=args.persistent_limit,
        persistent_window_seconds=args.persistent_window,
        many_users_limit=args.many_users_limit,
        invalid_user_limit=args.invalid_user_limit,
        default_year=args.year,
        timezone=args.timezone,
    )

    if args.live:
        return monitor_live(
            args.file,
            config,
            from_start=args.from_start,
            quiet=args.quiet,
        )

    try:
        result = parse_file(args.file, config)
    except FileNotFoundError:
        print(f"Error: File '{args.file}' not found.")
        return 2
    except PermissionError:
        print(f"Error: Permission denied for '{args.file}'.")
        return 3

    if not args.quiet:
        print("\n====== PARSED EVENTS ======")
        for event in result.events:
            print(event)

        print("\n======== SUMMARY ========")
        for key in (
            "total_events",
            "total_login_attempts",
            "successful_logins",
            "failed_logins",
            "session_events",
            "sudo_commands",
            "invalid_user_attempts",
        ):
            print(f"{key.replace('_', ' ').title()}: {result.summary[key]}")
        print("\nTop targeted usernames:")
        for user, count in result.summary["top_usernames"].items():
            print(f"{user}: {count}")
        print("\nTop originating source IPs:")
        for ip, count in result.summary["top_ips"].items():
            print(f"{ip}: {count}")

        print("\n====== SECURITY REPORT ======")
        if not result.alerts:
            print("No suspicious activity detected.")
        else:
            for alert in result.alerts:
                print(f"\nIP: {alert.source_ip}")
                print(f"Score: {alert.score}")
                print(f"Level: {alert.level}")
                print("Rules: " + ", ".join(alert.rule_ids))
                for reason in alert.reasons:
                    print(f"- {reason}")

        if result.warnings:
            print(f"\nWarnings: {result.lines_unknown} unrecognized line(s), "
                  f"{result.malformed_timestamps} line(s) without a normalized timestamp.")

    try:
        if args.json:
            export_json(args.json, result)
            print(f"\nJSON exported to: {args.json}")
        if args.csv:
            security_csv = export_csv(args.csv, result)
            print(f"CSV exported to: {args.csv}")
            print(f"Security CSV exported to: {security_csv}")
    except (PermissionError, OSError) as error:
        print(f"Error: Could not write export file: {error}", file=sys.stderr)
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
