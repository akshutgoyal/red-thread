from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from dateutil import parser as dateutil_parser

TZ_ALIASES = {
    "IST": ZoneInfo("Asia/Kolkata"),
    "UTC": timezone.utc,
    "GMT": timezone.utc,
    "Z": timezone.utc,
    "EST": ZoneInfo("America/New_York"),
    "EDT": ZoneInfo("America/New_York"),
    "PST": ZoneInfo("America/Los_Angeles"),
    "PDT": ZoneInfo("America/Los_Angeles"),
}

YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")


@dataclass
class ParsedTimestamp:
    raw: str
    normalized: datetime | None
    confidence: str
    timezone_name: str | None
    timezone_assumed: bool
    year_inferred: bool
    basis: str
    warnings: list[str] = field(default_factory=list)


def _unknown(raw: str, warning: str) -> ParsedTimestamp:
    return ParsedTimestamp(
        raw=raw,
        normalized=None,
        confidence="unknown",
        timezone_name=None,
        timezone_assumed=False,
        year_inferred=False,
        basis=warning,
        warnings=[warning],
    )


def parse_flexible_timestamp(
    raw: str | None,
    *,
    default_timezone: str = "UTC",
    reference_date: datetime | None = None,
    default_year: int | None = None,
    dayfirst: bool = True,
) -> ParsedTimestamp:
    """Parse common evidence timestamps while recording uncertainty.

    Supported: ISO 8601, RFC-ish timestamps, Indian/UK day-first dates,
    US-style dates when unambiguous, syslog timestamps, and common timezone
    abbreviations. A missing year or timezone is recorded, never hidden.
    """
    text = (raw or "").strip()
    if not text:
        return _unknown(text, "Empty timestamp.")

    reference = reference_date or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    year_present = bool(YEAR_RE.search(text))
    warnings: list[str] = []
    inferred_year = False
    if default_year is not None and not year_present:
        reference = reference.replace(year=default_year)

    # Detect an explicit timezone abbreviation at the end.
    timezone_assumed = True
    timezone_name: str | None = default_timezone
    tz_match = re.search(r"\b([A-Z]{2,4})$", text)
    if tz_match and tz_match.group(1) in TZ_ALIASES:
        timezone_name = tz_match.group(1)
        timezone_assumed = False
        text = text[: tz_match.start()].strip().rstrip(",")
    elif text.endswith("Z"):
        timezone_name = "UTC"
        timezone_assumed = False

    # ISO 8601 dates start with a four-digit year and must be parsed
    # month-first. Applying day-first parsing to "2026-10-11" would turn it
    # into 10 November 2026, which is a silent and serious date corruption.
    iso_like = bool(re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", text))
    try:
        parsed = dateutil_parser.parse(
            text,
            dayfirst=False if iso_like else dayfirst,
            default=reference.replace(tzinfo=None),
            tzinfos=TZ_ALIASES,
        )
    except (ValueError, OverflowError, TypeError) as error:
        return _unknown(raw or "", f"Timestamp could not be parsed: {error}")

    if parsed.tzinfo is None:
        try:
            zone = ZoneInfo(default_timezone)
        except Exception:
            zone = timezone.utc
            warnings.append(
                f"Unknown default timezone {default_timezone!r}; using UTC."
            )
        parsed = parsed.replace(tzinfo=zone)
        timezone_assumed = True
        timezone_name = default_timezone
        warnings.append(
            f"Timezone not present in source timestamp; interpreted as {default_timezone}."
        )
    else:
        timezone_name = getattr(parsed.tzinfo, "key", None) or str(parsed.tzinfo)
        if timezone_assumed is False:
            timezone_name = tz_match.group(1) if tz_match else "UTC"
        else:
            timezone_name = str(parsed.tzinfo)

    normalized = parsed.astimezone(timezone.utc)

    if not year_present:
        inferred_year = True
        warnings.append(
            f"Year not present in source timestamp; inferred {normalized.year} "
            f"from reference date {reference.date().isoformat()}."
        )

    # Flag genuinely ambiguous numeric dates where day and month are both <= 12.
    ambiguous_date = False
    date_match = NUMERIC_DATE_RE.search(text)
    if date_match:
        first, second = int(date_match.group(1)), int(date_match.group(2))
        if first <= 12 and second <= 12 and first != second:
            ambiguous_date = True
            warnings.append(
                "Date components could be day/month or month/day; "
                "day-first interpretation was used."
            )

    if not year_present:
        confidence = "inferred_year"
    elif ambiguous_date or timezone_assumed:
        confidence = "ambiguous"
    else:
        confidence = "exact"

    basis_parts = []
    if not year_present:
        basis_parts.append("year inferred")
    if timezone_assumed:
        basis_parts.append(f"timezone assumed {default_timezone}")
    if ambiguous_date:
        basis_parts.append("day-first date interpretation")
    if not basis_parts:
        basis_parts.append("timestamp included year and timezone")

    return ParsedTimestamp(
        raw=raw or "",
        normalized=normalized,
        confidence=confidence,
        timezone_name=timezone_name,
        timezone_assumed=timezone_assumed,
        year_inferred=inferred_year,
        basis="; ".join(basis_parts),
        warnings=warnings,
    )


def iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
