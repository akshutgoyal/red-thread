from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

WarningCategory = Literal[
    "timestamp",
    "schema",
    "encoding",
    "ocr",
    "partial",
    "duplicate",
    "unsupported",
    "other",
]


@dataclass(frozen=True)
class WarningGuidance:
    category: WarningCategory
    impact: str
    recommendation: str
    can_use: bool


_TIMESTAMP_HINTS = (
    "timestamp",
    "date column",
    "time column",
    "datetime",
    "could not parse time",
    "unparseable time",
    "missing time",
    "no time",
)
_SCHEMA_HINTS = (
    "column",
    "header",
    "field",
    "schema",
    "required",
    "missing key",
    "unknown format",
)
_ENCODING_HINTS = (
    "encoding",
    "decode",
    "utf-8",
    "utf8",
    "latin-1",
    "codec",
    "byte order",
)
_OCR_HINTS = (
    "ocr",
    "tesseract",
    "image text",
    "no text detected",
    "ocr unavailable",
)
_PARTIAL_HINTS = (
    "skipped",
    "partial",
    "partially",
    "invalid row",
    "malformed row",
    "could not parse row",
    "rejected",
)
_DUPLICATE_HINTS = ("duplicate", "already exists", "repeated record")
_UNSUPPORTED_HINTS = ("unsupported", "not supported", "no parser", "unknown suffix")


def _matches(text: str, hints: tuple[str, ...]) -> bool:
    return any(hint in text for hint in hints)


def classify_warning(message: str) -> WarningGuidance:
    """Explain a parser warning in investigator-facing terms.

    The classification is deliberately conservative: unknown warnings are
    reported as ``other`` with a recommendation to inspect the file rather
    than guessing at a cause.
    """

    text = (message or "").strip().lower()
    if _matches(text, _OCR_HINTS):
        return WarningGuidance(
            category="ocr",
            impact=(
                "Text could not be extracted from the image, so any events or "
                "identifiers shown in it are missing from the investigation."
            ),
            recommendation=(
                "Check that OCR is installed and enabled, or attach a readable "
                "copy or transcript of the same record."
            ),
            can_use=False,
        )
    if _matches(text, _ENCODING_HINTS):
        return WarningGuidance(
            category="encoding",
            impact=(
                "Some characters could not be decoded, so field values from this "
                "file may be incomplete or garbled."
            ),
            recommendation=(
                "Re-export the file as UTF-8 from the original system, then upload "
                "the corrected copy alongside the original."
            ),
            can_use=True,
        )
    if _matches(text, _TIMESTAMP_HINTS):
        return WarningGuidance(
            category="timestamp",
            impact=(
                "Events from this file may not appear in the correct position on "
                "the timeline, or may be listed as undated."
            ),
            recommendation=(
                "Confirm which column holds the timestamp and check its format. "
                "Undated events remain available in the timeline's undated section."
            ),
            can_use=True,
        )
    if _matches(text, _DUPLICATE_HINTS):
        return WarningGuidance(
            category="duplicate",
            impact=(
                "A repeated record may appear more than once, which can overstate "
                "how often an activity occurred."
            ),
            recommendation=(
                "Compare the source locators listed for the repeated records and "
                "treat repeats as a single occurrence when they are identical."
            ),
            can_use=True,
        )
    if _matches(text, _PARTIAL_HINTS):
        return WarningGuidance(
            category="partial",
            impact=(
                "Some records in this file were not extracted. The successfully "
                "parsed records are still available."
            ),
            recommendation=(
                "Review the rejected record count and the original file for rows "
                "with missing or malformed fields."
            ),
            can_use=True,
        )
    if _matches(text, _UNSUPPORTED_HINTS):
        return WarningGuidance(
            category="unsupported",
            impact="No parser could interpret this file, so it produced no events.",
            recommendation=(
                "Convert the file to a supported format, or record the information "
                "in an investigator annotation instead."
            ),
            can_use=False,
        )
    if _matches(text, _SCHEMA_HINTS):
        return WarningGuidance(
            category="schema",
            impact=(
                "Expected fields were missing or renamed, so some values may not "
                "have been extracted."
            ),
            recommendation=(
                "Compare the file header with the supported fields and re-export "
                "with the expected column names."
            ),
            can_use=True,
        )
    return WarningGuidance(
        category="other",
        impact=(
            "The parser reported a condition it could not classify. The extracted "
            "records are preserved but may be incomplete."
        ),
        recommendation=(
            "Open the source record for this file and confirm the extracted values "
            "against the original."
        ),
        can_use=True,
    )


def describe_warnings(messages: list[str], source_locator: str = "") -> list[dict]:
    """Return structured warning details for each message."""

    details: list[dict] = []
    for message in messages:
        guidance = classify_warning(message)
        details.append(
            {
                "message": message,
                "category": guidance.category,
                "impact": guidance.impact,
                "recommendation": guidance.recommendation,
                "can_use": guidance.can_use,
                "source_locator": source_locator,
            }
        )
    return details
