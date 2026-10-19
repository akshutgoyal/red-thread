from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..utils.amounts import normalize_amount, parse_amount
from ..utils.timestamps import parse_flexible_timestamp
from .base import (
    BaseParser,
    CanonicalEventDraft,
    EntityDraft,
    ParseResult,
    ParseWarning,
    ParserContext,
)

TXN_ALIASES = ("txn_id", "transaction_id", "transaction_ref", "txn", "transaction")
UTR_ALIASES = ("utr_number", "utr", "utr_no", "reference_number", "rrn")
TIMESTAMP_ALIASES = ("timestamp_ist", "timestamp", "datetime", "date", "transaction_time", "txn_time")
PAYER_ALIASES = ("payer_vpa", "payer", "sender", "from", "from_vpa", "debit_account")
PAYEE_ALIASES = ("payee_vpa", "payee", "receiver", "to", "to_vpa", "beneficiary", "credit_account")
AMOUNT_ALIASES = ("amount_inr", "amount", "value", "transaction_amount", "txn_amount")
CURRENCY_ALIASES = ("currency", "ccy")
STATUS_ALIASES = ("status", "transaction_status", "txn_status")


def _norm(row: dict) -> dict:
    return {
        str(key).strip().lower().replace(" ", "_"): value
        for key, value in row.items()
        if key is not None
    }


def _pick(row: dict, aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        value = row.get(alias)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None


def _rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            for key in ("transactions", "records", "data", "items", "rows"):
                candidate = payload.get(key)
                if isinstance(candidate, list):
                    return [row for row in candidate if isinstance(row, dict)]
            return [payload]
        return []
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    return [dict(row) for row in frame.to_dict(orient="records")]


class TransactionParser(BaseParser):
    name = "transaction"
    version = "1.0.0"
    supported_extensions = (".csv", ".json")

    def parse(self, path: Path, context: ParserContext) -> ParseResult:
        events: list[CanonicalEventDraft] = []
        warnings: list[ParseWarning] = []
        rows = _rows(path)
        for index, raw_row in enumerate(rows):
            row = _norm(raw_row)
            txn_id = _pick(row, TXN_ALIASES)
            utr = _pick(row, UTR_ALIASES)
            timestamp_raw = _pick(row, TIMESTAMP_ALIASES)
            payer = _pick(row, PAYER_ALIASES)
            payee = _pick(row, PAYEE_ALIASES)
            amount_raw = _pick(row, AMOUNT_ALIASES)
            currency = _pick(row, CURRENCY_ALIASES) or "INR"
            status = _pick(row, STATUS_ALIASES)
            locator = f"row:{index + 2}" if path.suffix.lower() == ".csv" else f"record:{index}"

            amount = parse_amount(amount_raw)
            if amount is None:
                warnings.append(
                    ParseWarning(
                        source_locator=locator,
                        message="Transaction record has no parseable amount.",
                        source_snippet=json.dumps(raw_row, ensure_ascii=False)[:500],
                    )
                )

            timestamp = parse_flexible_timestamp(
                timestamp_raw,
                default_timezone=context.timezone,
                reference_date=context.reference_date,
                default_year=context.default_year,
            )
            entities: list[EntityDraft] = []
            if txn_id:
                entities.append(EntityDraft("transaction_id", txn_id, "transaction_id", txn_id))
            if utr:
                entities.append(EntityDraft("utr", utr, "utr", utr))
            if payer:
                entities.append(EntityDraft("upi_vpa", payer, "payer", payer))
            if payee:
                entities.append(EntityDraft("upi_vpa", payee, "payee", payee))

            events.append(
                CanonicalEventDraft(
                    event_type="transaction",
                    timestamp_raw=timestamp_raw,
                    timestamp_normalized=timestamp.normalized,
                    timestamp_confidence=timestamp.confidence,
                    timestamp_timezone=timestamp.timezone_name,
                    source_locator=locator,
                    source_snippet=json.dumps(raw_row, ensure_ascii=False)[:2000],
                    attributes={
                        "transaction_id": txn_id,
                        "utr": utr,
                        "amount": normalize_amount(amount),
                        "amount_raw": amount_raw,
                        "currency": currency,
                        "payer_vpa": payer,
                        "payee_vpa": payee,
                        "status": status,
                        "timestamp_basis": timestamp.basis,
                    },
                    entities=entities,
                    warnings=list(timestamp.warnings),
                )
            )

        return ParseResult(
            parser_name=self.name,
            parser_version=self.version,
            events=events,
            warnings=warnings,
            metadata={
                "transactions_parsed": len(events),
                "records_total": len(rows),
                "missing_amount": sum(
                    1 for warning in warnings if "amount" in warning.message.lower()
                ),
            },
        )
