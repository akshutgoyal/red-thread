from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

import pandas as pd

from ..utils.amounts import normalize_amount, parse_amount
from ..utils.extraction import UPI_OR_EMAIL_RE
from ..utils.timestamps import parse_flexible_timestamp
from .base import (
    BaseParser,
    CanonicalEventDraft,
    EntityDraft,
    ParseResult,
    ParseWarning,
    ParserContext,
)

try:
    import pdfplumber
except ImportError:  # pragma: no cover - optional dependency
    pdfplumber = None

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - optional dependency
    PdfReader = None

INVOICE_ID_RE = re.compile(
    r"(?i)\b(?:invoice\s*(?:number|no\.?|#)|inv\s*(?:number|no\.?|#))"
    r"\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]{3,})"
)
STANDALONE_INVOICE_RE = re.compile(r"(?i)\b(INV[-/ ]?\d{4}[-/ ]?\d+)\b")
DATE_RE = re.compile(
    r"(?i)\bdate\s*[:\-]?\s*"
    r"([0-9]{1,2}[-/ ][A-Za-z0-9]{2,9}[-/ ][0-9]{2,4}|[0-9]{4}-[0-9]{2}-[0-9]{2})"
)
VPA_LABEL_RE = re.compile(
    r"(?i)\b(?:vpa|upi|pay\s*to|beneficiary|payment\s*id)\b[^\n@]{0,40}?"
    r"([A-Za-z0-9.\-_]+@[A-Za-z][A-Za-z0-9.\-_]*)"
)
TOTAL_RE = re.compile(
    r"(?i)(?<!sub)\b(?:grand\s+total|total\s+due|amount\s+due|total)\b"
    r"[^\d₹Rs.INR]{0,30}([₹Rs.INR\s]*[\d,]+(?:\.\d{1,2})?)"
)
SUBTOTAL_RE = re.compile(
    r"(?i)\b(?:sub\s*total|subtotal|taxable\s+value|net\s+amount)\b"
    r"[^\d₹Rs.INR]{0,30}([₹Rs.INR\s]*[\d,]+(?:\.\d{1,2})?)"
)
TAX_RE = re.compile(
    r"(?i)\b(?P<label>CGST|SGST|IGST|GST|tax)\b"
    r"(?:\s*\(?\s*(?P<rate>\d+(?:\.\d+)?)\s*%\s*\)?)?"
    r"[^\d₹Rs.INR]{0,30}(?P<amount>[₹Rs.INR\s]*[\d,]+(?:\.\d{1,2})?)"
)
INVOICE_ALIASES = (
    "invoice_id",
    "invoice_number",
    "invoice_no",
    "inv_id",
    "number",
)
DATE_ALIASES = ("invoice_date", "date", "issued_date", "bill_date")
SUBTOTAL_ALIASES = ("subtotal", "sub_total", "taxable_value", "net_amount")
TAX_ALIASES = ("tax", "gst", "tax_amount", "total_tax")
TOTAL_ALIASES = ("total", "total_due", "amount_due", "grand_total", "invoice_total")
PAYEE_ALIASES = ("payee_vpa", "vpa", "upi", "payment_vpa", "beneficiary")
CURRENCY_ALIASES = ("currency", "ccy")
LINE_ITEM_ALIASES = ("line_items", "items", "description")


def _amount_from_match(value: str | None) -> Decimal | None:
    if not value:
        return None
    return parse_amount(value)


def _find_labeled_amount(text: str, pattern: re.Pattern) -> tuple[Decimal | None, str | None]:
    match = pattern.search(text)
    if not match:
        return None, None
    return _amount_from_match(match.group(1)), match.group(1).strip()


def extract_invoice_fields(text: str) -> dict:
    normalized = text.replace("\xa0", " ").replace("\u200b", "")
    fields: dict = {}

    match = INVOICE_ID_RE.search(normalized) or STANDALONE_INVOICE_RE.search(normalized)
    if match and any(character.isdigit() for character in match.group(1)):
        fields["invoice_id"] = match.group(1).strip().upper()

    match = DATE_RE.search(normalized)
    if match:
        fields["invoice_date_raw"] = match.group(1).strip()

    subtotal, subtotal_raw = _find_labeled_amount(normalized, SUBTOTAL_RE)
    if subtotal is not None:
        fields["subtotal"] = normalize_amount(subtotal)
        fields["subtotal_raw"] = subtotal_raw

    total, total_raw = _find_labeled_amount(normalized, TOTAL_RE)
    if total is not None:
        fields["total"] = normalize_amount(total)
        fields["total_raw"] = total_raw

    tax_total = Decimal("0")
    tax_lines = []
    for match in TAX_RE.finditer(normalized):
        amount = _amount_from_match(match.group("amount"))
        if amount is None:
            continue
        tax_total += amount
        tax_lines.append(
            {
                "label": match.group("label").upper(),
                "rate": match.group("rate"),
                "amount": normalize_amount(amount),
            }
        )
    if tax_lines:
        fields["tax_lines"] = tax_lines
        fields["tax_amount"] = normalize_amount(tax_total)

    vpa_match = VPA_LABEL_RE.search(normalized)
    if vpa_match:
        fields["payee_vpa"] = vpa_match.group(1).strip().lower()
    else:
        candidates = [
            value
            for value in UPI_OR_EMAIL_RE.findall(normalized)
            if "." not in value.split("@")[-1]
        ]
        if candidates:
            fields["payee_vpa"] = candidates[0].strip().lower()

    if "₹" in normalized or re.search(r"(?i)\bINR\b", normalized):
        fields["currency"] = "INR"
    elif "$" in normalized:
        fields["currency"] = "USD"
    elif "€" in normalized:
        fields["currency"] = "EUR"

    return fields


def _invoice_entities(fields: dict, attachments: list[str] | None = None) -> list[EntityDraft]:
    entities: list[EntityDraft] = []
    if fields.get("invoice_id"):
        entities.append(
            EntityDraft("invoice_id", fields["invoice_id"], "invoice_id", fields["invoice_id"])
        )
    if fields.get("payee_vpa"):
        entities.append(EntityDraft("upi_vpa", fields["payee_vpa"], "payee", fields["payee_vpa"]))
    for key, role in (("subtotal", "subtotal"), ("tax_amount", "tax"), ("total", "total")):
        if fields.get(key):
            entities.append(EntityDraft("amount", fields[key], role, fields[key]))
    for filename in attachments or []:
        entities.append(EntityDraft("filename", filename.lower(), "invoice_file", filename))
    return entities


def _parse_tabular(path: Path, context: ParserContext) -> ParseResult:
    events: list[CanonicalEventDraft] = []
    warnings: list[ParseWarning] = []
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        rows = payload if isinstance(payload, list) else [payload]
    else:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        rows = [dict(row) for row in frame.to_dict(orient="records")]

    for index, raw_row in enumerate(rows):
        row = {
            str(key).strip().lower().replace(" ", "_"): value
            for key, value in raw_row.items()
            if key is not None
        }

        def pick(aliases):
            for alias in aliases:
                value = row.get(alias)
                if value is not None and str(value).strip() != "":
                    return str(value).strip()
            return None

        fields = {
            "invoice_id": pick(INVOICE_ALIASES),
            "invoice_date_raw": pick(DATE_ALIASES),
            "subtotal": normalize_amount(parse_amount(pick(SUBTOTAL_ALIASES))),
            "tax_amount": normalize_amount(parse_amount(pick(TAX_ALIASES))),
            "total": normalize_amount(parse_amount(pick(TOTAL_ALIASES))),
            "payee_vpa": (pick(PAYEE_ALIASES) or "").lower() or None,
            "currency": pick(CURRENCY_ALIASES) or "INR",
            "line_items_raw": pick(LINE_ITEM_ALIASES),
        }
        fields = {key: value for key, value in fields.items() if value is not None}
        locator = f"row:{index + 2}" if path.suffix.lower() == ".csv" else f"record:{index}"
        timestamp = parse_flexible_timestamp(
            fields.get("invoice_date_raw"),
            default_timezone=context.timezone,
            reference_date=context.reference_date,
            default_year=context.default_year,
        )
        events.append(
            CanonicalEventDraft(
                event_type="invoice",
                timestamp_raw=fields.get("invoice_date_raw"),
                timestamp_normalized=timestamp.normalized,
                timestamp_confidence=timestamp.confidence,
                timestamp_timezone=timestamp.timezone_name,
                source_locator=locator,
                source_snippet=json.dumps(raw_row, ensure_ascii=False)[:2000],
                attributes={**fields, "timestamp_basis": timestamp.basis},
                entities=_invoice_entities(fields, [context.source_filename]),
                warnings=list(timestamp.warnings),
            )
        )

    return ParseResult(
        parser_name="invoice",
        parser_version="1.0.0",
        events=events,
        warnings=warnings,
        metadata={"invoices_parsed": len(events), "records_total": len(rows)},
    )


def _parse_pdf(path: Path, context: ParserContext) -> ParseResult:
    events: list[CanonicalEventDraft] = []
    warnings: list[ParseWarning] = []
    pages_text: list[str] = []
    pages_tables: list[list] = []

    if pdfplumber is not None:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                pages_text.append(page.extract_text() or "")
                pages_tables.append(page.extract_tables() or [])
    elif PdfReader is not None:
        reader = PdfReader(str(path))
        for page in reader.pages:
            pages_text.append(page.extract_text() or "")
            pages_tables.append([])
    else:
        return ParseResult(
            parser_name="invoice",
            parser_version="1.0.0",
            events=[],
            warnings=[
                ParseWarning(
                    source_locator="file",
                    message="PDF text extraction is unavailable; install pdfplumber or pypdf.",
                )
            ],
            metadata={"pdf_parser_available": False},
        )

    for index, text in enumerate(pages_text, start=1):
        fields = extract_invoice_fields(text)
        tables = pages_tables[index - 1] if index - 1 < len(pages_tables) else []
        line_items = []
        for table in tables:
            for row in table:
                cells = [str(cell).strip() for cell in row if cell is not None]
                if len(cells) >= 2 and not any(
                    keyword in " ".join(cells).lower()
                    for keyword in ("subtotal", "total", "cgst", "sgst", "igst", "tax")
                ):
                    line_items.append(cells)

        if not text.strip():
            warnings.append(
                ParseWarning(
                    source_locator=f"page:{index}",
                    message="No text layer was extracted from this PDF page.",
                )
            )
            continue

        if not fields:
            warnings.append(
                ParseWarning(
                    source_locator=f"page:{index}",
                    message="No recognizable invoice fields were found on this page.",
                    source_snippet=text[:500],
                )
            )

        timestamp = parse_flexible_timestamp(
            fields.get("invoice_date_raw"),
            default_timezone=context.timezone,
            reference_date=context.reference_date,
            default_year=context.default_year,
        )
        attributes = {
            **fields,
            "line_items": line_items,
            "page_text": text[:10000],
            "timestamp_basis": timestamp.basis,
        }
        events.append(
            CanonicalEventDraft(
                event_type="invoice",
                timestamp_raw=fields.get("invoice_date_raw"),
                timestamp_normalized=timestamp.normalized,
                timestamp_confidence=timestamp.confidence,
                timestamp_timezone=timestamp.timezone_name,
                source_locator=f"page:{index}",
                source_snippet=text[:2000],
                attributes=attributes,
                entities=_invoice_entities(fields, [context.source_filename]),
                warnings=list(timestamp.warnings),
            )
        )

    return ParseResult(
        parser_name="invoice",
        parser_version="1.0.0",
        events=events,
        warnings=warnings,
        metadata={
            "pages_total": len(pages_text),
            "invoices_parsed": len(events),
            "pdf_parser_available": True,
        },
    )


class InvoiceParser(BaseParser):
    name = "invoice"
    version = "1.0.0"
    supported_extensions = (".pdf", ".csv", ".json")

    def parse(self, path: Path, context: ParserContext) -> ParseResult:
        if path.suffix.lower() == ".pdf":
            return _parse_pdf(path, context)
        return _parse_tabular(path, context)
