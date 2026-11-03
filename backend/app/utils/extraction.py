from __future__ import annotations

import re

from .amounts import extract_amounts

PHONE_PATTERNS = [
    r"\+91[\s-]?\d{5}[\s-]?\d{5}",
    r"(?<!\d)[6-9]\d{9}(?!\d)",
    r"(?<!\d)\d{3}[\s-]\d{3}[\s-]\d{4}(?!\d)",
    r"(?<!\d)\+\d{10,15}(?!\d)",
]
PHONE_RE = re.compile("|".join(f"(?:{pattern})" for pattern in PHONE_PATTERNS))
UPI_OR_EMAIL_RE = re.compile(r"\b[A-Za-z0-9.\-_]+@[A-Za-z][A-Za-z0-9.\-_]*\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
UTR_RE = re.compile(r"(?i)\butr\b[^\d]{0,20}(\d{12})")
TXN_RE = re.compile(r"\b(?:TXN|UPI|TXNID)[-: ]?[A-Z0-9]{6,}\b", re.IGNORECASE)
INVOICE_RE = re.compile(r"\bINV[-/ ]?\d{4}[-/ ]?\d+\b", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)
ACCOUNT_RE = re.compile(
    r"(?i)(?:a/c|account|acct)[^\d]{0,10}(\d{9,18})"
)
FILENAME_RE = re.compile(
    r"\b[\w.\-]+\.(?:pdf|png|jpe?g|csv|txt|log|eml|json)\b", re.IGNORECASE
)
DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\b",
    re.IGNORECASE,
)


def _append_unique(
    results: list[tuple[str, str, str]], seen: set[tuple[str, str, str]], item
) -> None:
    if item and item not in seen:
        seen.add(item)
        results.append(item)


def extract_entities(text: str, *, default_role: str = "mentioned") -> list[tuple[str, str, str]]:
    """Extract conservative, labelled entity candidates from free text.

    Returns a list of ``(entity_type, value, role)`` tuples. This function does
    not decide that an entity is important; it only proposes candidates.
    """
    text = text or ""
    results: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for match in PHONE_RE.finditer(text):
        _append_unique(results, seen, ("phone", match.group(0), default_role))

    for match in UPI_OR_EMAIL_RE.finditer(text):
        value = match.group(0)
        if EMAIL_RE.fullmatch(value):
            _append_unique(results, seen, ("email", value.lower(), default_role))
        else:
            _append_unique(results, seen, ("upi_vpa", value.lower(), default_role))

    for match in UTR_RE.finditer(text):
        _append_unique(results, seen, ("utr", match.group(1), default_role))

    for match in TXN_RE.finditer(text):
        _append_unique(results, seen, ("transaction_id", match.group(0), default_role))

    for match in INVOICE_RE.finditer(text):
        _append_unique(results, seen, ("invoice_id", match.group(0), default_role))

    for match in URL_RE.finditer(text):
        _append_unique(results, seen, ("url", match.group(0), default_role))

    for match in ACCOUNT_RE.finditer(text):
        _append_unique(results, seen, ("account", match.group(1), default_role))

    for match in FILENAME_RE.finditer(text):
        _append_unique(results, seen, ("filename", match.group(0).lower(), "attachment"))

    for match in DOMAIN_RE.finditer(text):
        value = match.group(0).lower()
        if value.endswith((".pdf", ".png", ".jpg", ".jpeg", ".csv", ".txt", ".log", ".eml", ".json")):
            continue
        _append_unique(results, seen, ("domain", value, default_role))

    for raw, value, currency in extract_amounts(text):
        _append_unique(
            results,
            seen,
            ("amount", f"{value}:{currency or 'UNKNOWN'}", default_role),
        )

    return results
