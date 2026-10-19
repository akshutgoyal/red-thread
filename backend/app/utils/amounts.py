from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

CURRENCY_SYMBOLS = "₹$€£"
AMOUNT_WITH_CURRENCY_RE = re.compile(
    rf"(?:(?P<prefix>₹|Rs\.?|INR|USD|EUR)\s*)?"
    rf"(?P<amount>\d{{1,3}}(?:,\d{{2,3}})*(?:\.\d{{1,2}})?|\d+(?:\.\d{{1,2}})?)"
    rf"(?:\s*(?P<suffix>₹|Rs\.?|INR|USD|EUR))?",
    re.IGNORECASE,
)
LABELED_AMOUNT_RE = re.compile(
    rf"(?:amount|total|paid|transfer(?:red)?|debited?|credited?)"
    rf"[^\d₹RsINR]{{0,20}}"
    rf"(?P<prefix>₹|Rs\.?|INR)?\s*"
    rf"(?P<amount>\d{{1,3}}(?:,\d{{2,3}})*(?:\.\d{{1,2}})?|\d+(?:\.\d{{1,2}})?)",
    re.IGNORECASE,
)


def parse_amount(value: str | int | float | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    cleaned = str(value).strip()
    cleaned = re.sub(r"(?i)\b(?:inr|usd|eur)\b", "", cleaned)
    cleaned = re.sub(r"(?i)\brs\.?", "", cleaned)
    cleaned = cleaned.replace("₹", "").replace("$", "").replace("€", "").replace("£", "")
    cleaned = cleaned.replace(",", "").strip()
    cleaned = re.sub(r"^[.\s]+", "", cleaned)
    cleaned = re.sub(r"\s+", "", cleaned)
    if cleaned.count(".") > 1:
        head, _, tail = cleaned.rpartition(".")
        cleaned = head.replace(".", "") + "." + tail
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def normalize_amount(value: Decimal | None) -> str | None:
    if value is None:
        return None
    normalized = value.quantize(Decimal("0.01"))
    return format(normalized, "f")


def extract_amounts(text: str) -> list[tuple[str, Decimal, str | None]]:
    """Return (raw_match, value, currency) for amounts found in free text."""
    results: list[tuple[str, Decimal, str | None]] = []
    seen: set[str] = set()
    for match in AMOUNT_WITH_CURRENCY_RE.finditer(text or ""):
        prefix = match.group("prefix")
        suffix = match.group("suffix")
        raw_amount = match.group("amount")
        if not prefix and not suffix:
            # Unlabelled numbers are too error-prone to treat as amounts.
            continue
        value = parse_amount(raw_amount)
        if value is None:
            continue
        currency = None
        marker = (prefix or suffix or "").upper()
        if marker in {"₹", "RS", "RS.", "INR"}:
            currency = "INR"
        elif marker == "USD":
            currency = "USD"
        elif marker == "EUR":
            currency = "EUR"
        key = f"{normalize_amount(value)}:{currency}"
        if key in seen:
            continue
        seen.add(key)
        results.append((match.group(0).strip(), value, currency))
    return results


def extract_labeled_amounts(text: str) -> list[tuple[str, Decimal, str | None]]:
    results: list[tuple[str, Decimal, str | None]] = []
    for match in LABELED_AMOUNT_RE.finditer(text or ""):
        value = parse_amount(match.group("amount"))
        if value is None:
            continue
        prefix = (match.group("prefix") or "").upper()
        currency = "INR" if prefix in {"₹", "RS", "RS.", "INR"} else None
        results.append((match.group(0).strip(), value, currency))
    return results
