from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from itertools import combinations
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    Entity,
    Event,
    EventEntity,
    Evidence,
    Finding,
    FindingEvidence,
    GraphEdge,
)
from ..utils.amounts import extract_amounts, normalize_amount, parse_amount
from ..utils.extraction import UTR_RE, extract_entities
from . import audit_service

RECONCILIATION_METHOD = "deterministic_reconciliation"
SHARED_IDENTIFIER_TYPES = {
    "phone",
    "upi_vpa",
    "utr",
    "transaction_id",
    "invoice_id",
    "ip",
    "email",
    "url",
    "filename",
    "username",
}
LOW_SEVERITY_IDENTIFIERS = {"ip", "email", "url", "filename", "username"}


def _attr(event: Event, key: str) -> Any:
    return (event.attributes_json or {}).get(key)


def _amount(event: Event) -> Decimal | None:
    return parse_amount(_attr(event, "amount"))


def _ocr_amount(event: Event) -> tuple[Decimal | None, str | None]:
    text = _attr(event, "ocr_text") or ""
    amounts = extract_amounts(text)
    if not amounts:
        return None, None
    raw, value, currency = amounts[0]
    return value, raw


def _ocr_utrs(event: Event) -> list[str]:
    text = _attr(event, "ocr_text") or ""
    return [match.group(1) for match in UTR_RE.finditer(text)]


def _ocr_vpas(event: Event) -> list[str]:
    text = _attr(event, "ocr_text") or ""
    return [
        value.lower()
        for entity_type, value, _role in extract_entities(text)
        if entity_type == "upi_vpa"
    ]


def _bbox_y(event: Event) -> int:
    locator = event.source_locator or ""
    if locator.startswith("bbox:"):
        parts = locator.split(":", 1)[1].split(",")
        if len(parts) >= 2:
            try:
                return int(parts[1])
            except ValueError:
                return 0
    return 0


def _group_image_claims(images: list[Event]) -> list[dict[str, Any]]:
    """Combine OCR line events from the same image into one claim.

    The image parser emits one event per OCR line. Amount, UTR and payee can
    appear on different lines, so reconciliation must reassemble the image
    before looking for cross-source matches.
    """
    grouped: dict[str, list[Event]] = defaultdict(list)
    for event in images:
        grouped[event.evidence_id].append(event)
    claims: list[dict[str, Any]] = []
    for evidence_id, line_events in grouped.items():
        ordered = sorted(line_events, key=_bbox_y)
        text = " ".join(
            str((event.attributes_json or {}).get("ocr_text") or "")
            for event in ordered
        )
        claims.append(
            {
                "evidence_id": evidence_id,
                "events": ordered,
                "representative": ordered[0],
                "text": text,
            }
        )
    return claims


def _norm_vpa(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower()


def _event_evidence_ids(events: list[Event]) -> list[str]:
    return sorted({event.evidence_id for event in events})


def _locator_summary(event: Event) -> str:
    return f"{event.source_filename}:{event.source_locator}"


def clear_findings(db: Session, case_id: str) -> None:
    """Remove only reconciliation-produced findings and persisted graph edges."""
    _clear_reconciliation_findings(db, case_id)


def _clear_reconciliation_findings(db: Session, case_id: str) -> None:
    finding_ids = list(
        db.scalars(
            select(Finding.id).where(
                Finding.case_id == case_id,
                Finding.detection_method == RECONCILIATION_METHOD,
            )
        )
    )
    if finding_ids:
        db.execute(
            delete(FindingEvidence).where(FindingEvidence.finding_id.in_(finding_ids))
        )
        db.execute(delete(Finding).where(Finding.id.in_(finding_ids)))
    db.execute(delete(GraphEdge).where(GraphEdge.case_id == case_id))
    db.flush()


def _add_finding(
    db: Session,
    case_id: str,
    *,
    severity: str,
    category: str,
    title: str,
    explanation: str,
    confidence: str,
    events: list[Event] | None = None,
    evidence_ids: list[str] | None = None,
    limitations: str = "",
    alternatives: str = "",
) -> Finding:
    finding = Finding(
        case_id=case_id,
        severity=severity,
        category=category,
        title=title,
        explanation=explanation,
        detection_method=RECONCILIATION_METHOD,
        confidence=confidence,
        status="open",
        limitations=limitations,
        alternative_explanations=alternatives,
    )
    db.add(finding)
    db.flush()

    linked: set[tuple[str, str | None, str]] = set()
    for evidence_id in evidence_ids or []:
        key = (evidence_id, None, "supporting_evidence")
        if key not in linked:
            linked.add(key)
            db.add(
                FindingEvidence(
                    finding_id=finding.id,
                    evidence_id=evidence_id,
                    event_id=None,
                    role="supporting_evidence",
                    source_locator="",
                )
            )
    for event in events or []:
        key = (event.evidence_id, event.id, "supporting_event")
        if key not in linked:
            linked.add(key)
            db.add(
                FindingEvidence(
                    finding_id=finding.id,
                    evidence_id=event.evidence_id,
                    event_id=event.id,
                    role="supporting_event",
                    source_locator=event.source_locator,
                )
            )
    db.flush()
    return finding


def _add_edge(
    db: Session,
    case_id: str,
    source: Event,
    target: Event,
    *,
    edge_type: str,
    match_method: str,
    explanation: str,
    confidence: str,
) -> None:
    db.add(
        GraphEdge(
            case_id=case_id,
            source_type="event",
            source_id=f"event:{source.id}",
            target_type="event",
            target_id=f"event:{target.id}",
            edge_type=edge_type,
            match_method=match_method,
            explanation=explanation,
            confidence=confidence,
            supporting_event_ids_json=[source.id, target.id],
            supporting_evidence_ids_json=sorted({source.evidence_id, target.evidence_id}),
        )
    )
    db.flush()


def _load_events(db: Session, case_id: str) -> dict[str, list[Event]]:
    events = list(
        db.scalars(
            select(Event)
            .where(Event.case_id == case_id)
            .order_by(Event.created_at.asc())
        )
    )
    grouped: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        grouped[event.event_type].append(event)
    return grouped


def _check_screenshot_vs_transaction(
    db: Session, case_id: str, events: dict[str, list[Event]]
) -> list[Finding]:
    findings: list[Finding] = []
    transactions = events.get("transaction", [])
    images = events.get("image_ocr", [])
    seen_payee: set[str] = set()

    for claim in _group_image_claims(images):
        image = claim["representative"]
        claim_events = claim["events"]
        ocr_text = claim["text"]
        utrs = [match.group(1) for match in UTR_RE.finditer(ocr_text)]
        amounts = extract_amounts(ocr_text)
        image_amount = amounts[0][1] if amounts else None
        image_vpas = [
            value.lower()
            for entity_type, value, _role in extract_entities(ocr_text)
            if entity_type == "upi_vpa"
        ]
        for utr in utrs:
            matches = [
                transaction
                for transaction in transactions
                if str(_attr(transaction, "utr") or "").strip() == utr
            ]
            for transaction in matches:
                _add_edge(
                    db,
                    case_id,
                    image,
                    transaction,
                    edge_type="exact_utr_match",
                    match_method="normalized_exact",
                    explanation=(
                        f"Exact UTR match: {utr} appears in {_locator_summary(image)} "
                        f"and {_locator_summary(transaction)}."
                    ),
                    confidence="exact",
                )
                findings.append(
                    _add_finding(
                        db,
                        case_id,
                        severity="info",
                        category="correlation",
                        title=f"Exact UTR match links screenshot and transaction ({utr})",
                        explanation=(
                            f"UTR {utr} was extracted from the screenshot OCR and "
                            f"appears in the transaction ledger. This is an exact "
                            f"identifier match, not a conclusion about fraud. "
                            f"Sources: {_locator_summary(image)}; "
                            f"{_locator_summary(transaction)}."
                        ),
                        confidence="high",
                        events=[*claim_events, transaction],
                        limitations=(
                            "An exact UTR match proves the same reference identifier "
                            "was used; it does not by itself prove who initiated the payment."
                        ),
                        alternatives=(
                            "The screenshot may be unrelated to the ledger row, or the "
                            "UTR may have been copied from another transaction."
                        ),
                    )
                )

                transaction_amount = _amount(transaction)
                if (
                    image_amount is not None
                    and transaction_amount is not None
                    and image_amount != transaction_amount
                ):
                    difference = abs(transaction_amount - image_amount)
                    findings.append(
                        _add_finding(
                            db,
                            case_id,
                            severity="high",
                            category="reconciliation",
                            title="Amount discrepancy between screenshot OCR and transaction ledger",
                            explanation=(
                                f"Screenshot OCR reports {normalize_amount(image_amount)} "
                                f"for UTR {utr}, while the transaction ledger records "
                                f"{normalize_amount(transaction_amount)}. "
                                f"Difference: {normalize_amount(difference)}. "
                                f"Sources: {_locator_summary(image)}; "
                                f"{_locator_summary(transaction)}."
                            ),
                            confidence="high",
                            events=[*claim_events, transaction],
                            limitations=(
                                "OCR can misread digits or currency symbols. Confirm the "
                                "amount by inspecting the original image and bank record."
                            ),
                            alternatives=(
                                "The screenshot may be cropped, resized, or from a "
                                "different transaction; OCR may have missed a digit."
                            ),
                        )
                    )
                    _add_edge(
                        db,
                        case_id,
                        image,
                        transaction,
                        edge_type="amount_conflict",
                        match_method="conflict",
                        explanation=(
                            f"Screenshot OCR amount {normalize_amount(image_amount)} "
                            f"does not match ledger amount "
                            f"{normalize_amount(transaction_amount)} for UTR {utr}."
                        ),
                        confidence="high",
                    )

                transaction_payee = _norm_vpa(_attr(transaction, "payee_vpa"))
                image_payee = image_vpas[0] if image_vpas else None
                if (
                    image_payee
                    and transaction_payee
                    and image_payee != transaction_payee
                    and transaction.id not in seen_payee
                ):
                    seen_payee.add(transaction.id)
                    findings.append(
                        _add_finding(
                            db,
                            case_id,
                            severity="high",
                            category="reconciliation",
                            title="Payee mismatch between screenshot claim and transaction ledger",
                            explanation=(
                                f"The screenshot OCR names {image_payee} as the payee, "
                                f"while the ledger records {transaction_payee} for "
                                f"UTR {utr}. Sources: {_locator_summary(image)}; "
                                f"{_locator_summary(transaction)}."
                            ),
                            confidence="high",
                            events=[*claim_events, transaction],
                            limitations=(
                                "OCR may misread the VPA. Verify the original image and "
                                "the bank statement before drawing a conclusion."
                            ),
                            alternatives=(
                                "The payee may use multiple VPAs, or the screenshot may "
                                "show a different leg of the transaction."
                            ),
                        )
                    )
                    _add_edge(
                        db,
                        case_id,
                        image,
                        transaction,
                        edge_type="payee_conflict",
                        match_method="conflict",
                        explanation=(
                            f"Screenshot payee {image_payee} differs from ledger payee "
                            f"{transaction_payee}."
                        ),
                        confidence="high",
                    )
        if utrs and not any(
            str(_attr(transaction, "utr") or "").strip() in utrs
            for transaction in transactions
        ):
            findings.append(
                _add_finding(
                    db,
                    case_id,
                    severity="low",
                    category="data_quality",
                    title="Screenshot UTR has no matching transaction in the current evidence",
                    explanation=(
                        f"OCR extracted UTR(s) {', '.join(utrs)} from "
                        f"{_locator_summary(image)}, but no transaction row in the "
                        f"current evidence carries that UTR."
                    ),
                    confidence="medium",
                    events=[image],
                    limitations=(
                        "The corresponding bank record may not have been collected, "
                        "or OCR may have misread the UTR."
                    ),
                    alternatives=(
                        "The payment may be absent from the supplied ledger, or it may "
                        "appear in a different export."
                    ),
                )
            )
    return findings


def _check_invoice_vs_transaction(
    db: Session, case_id: str, events: dict[str, list[Event]]
) -> list[Finding]:
    findings: list[Finding] = []
    invoices = events.get("invoice", [])
    transactions = events.get("transaction", [])
    seen_payee: set[str] = set()

    for invoice in invoices:
        invoice_total = parse_amount(_attr(invoice, "total"))
        invoice_subtotal = parse_amount(_attr(invoice, "subtotal"))
        invoice_tax = parse_amount(_attr(invoice, "tax_amount"))
        invoice_payee = _norm_vpa(_attr(invoice, "payee_vpa"))
        invoice_id = _attr(invoice, "invoice_id") or invoice.source_filename

        matches = [
            transaction
            for transaction in transactions
            if invoice_total is not None and _amount(transaction) == invoice_total
        ]
        if not matches:
            findings.append(
                _add_finding(
                    db,
                    case_id,
                    severity="low",
                    category="data_quality",
                    title=f"Invoice {invoice_id} has no matching transaction in the current evidence",
                    explanation=(
                        f"No transaction in the current evidence matches invoice "
                        f"{invoice_id} total {normalize_amount(invoice_total)}. "
                        f"Source: {_locator_summary(invoice)}."
                    ),
                    confidence="medium",
                    events=[invoice],
                    limitations=(
                        "The payment record may not have been collected, or the amount "
                        "may have been split across multiple transactions."
                    ),
                    alternatives=(
                        "The invoice may be unpaid, partially paid, or paid through a "
                        "channel not represented in the evidence."
                    ),
                )
            )
            continue

        arithmetic_ok = (
            invoice_subtotal is not None
            and invoice_tax is not None
            and invoice_total is not None
            and invoice_subtotal + invoice_tax == invoice_total
        )
        if invoice_subtotal is not None and invoice_tax is not None and invoice_total is not None and not arithmetic_ok:
            findings.append(
                _add_finding(
                    db,
                    case_id,
                    severity="medium",
                    category="reconciliation",
                    title=f"Invoice {invoice_id} arithmetic does not add up",
                    explanation=(
                        f"Subtotal {normalize_amount(invoice_subtotal)} + tax "
                        f"{normalize_amount(invoice_tax)} does not equal total "
                        f"{normalize_amount(invoice_total)}. Source: "
                        f"{_locator_summary(invoice)}."
                    ),
                    confidence="high",
                    events=[invoice],
                    limitations="Tax lines may be incomplete or formatted unusually.",
                    alternatives="A discount, rounding rule, or additional charge may explain the difference.",
                )
            )

        tax_rate_ok = True
        for tax_line in _attr(invoice, "tax_lines") or []:
            rate = tax_line.get("rate")
            amount = parse_amount(tax_line.get("amount"))
            if rate is not None and amount is not None and invoice_subtotal is not None:
                expected = (invoice_subtotal * Decimal(str(rate)) / Decimal("100")).quantize(
                    Decimal("0.01")
                )
                if expected != amount.quantize(Decimal("0.01")):
                    tax_rate_ok = False

        for transaction in matches:
            transaction_payee = _norm_vpa(_attr(transaction, "payee_vpa"))
            if (
                invoice_payee
                and transaction_payee
                and invoice_payee != transaction_payee
                and transaction.id not in seen_payee
            ):
                seen_payee.add(transaction.id)
                findings.append(
                    _add_finding(
                        db,
                        case_id,
                        severity="high",
                        category="reconciliation",
                        title="Payee mismatch between invoice claim and transaction recipient",
                        explanation=(
                            f"Invoice {invoice_id} requests payment to {invoice_payee}, "
                            f"but the matching transaction credits {transaction_payee}. "
                            f"Sources: {_locator_summary(invoice)}; "
                            f"{_locator_summary(transaction)}."
                        ),
                        confidence="high",
                        events=[invoice, transaction],
                        limitations=(
                            "The invoice may have been revised, or the payer may have "
                            "used a different beneficiary VPA."
                        ),
                        alternatives=(
                            "The payee may use multiple VPAs, a payment processor may "
                            "be involved, or the invoice may be unrelated to the payment."
                        ),
                    )
                )
                _add_edge(
                    db,
                    case_id,
                    invoice,
                    transaction,
                    edge_type="payee_conflict",
                    match_method="conflict",
                    explanation=(
                        f"Invoice payee {invoice_payee} differs from transaction "
                        f"payee {transaction_payee}."
                    ),
                    confidence="high",
                )
            elif (
                arithmetic_ok
                and tax_rate_ok
                and invoice_payee
                and transaction_payee
                and invoice_payee == transaction_payee
            ):
                findings.append(
                    _add_finding(
                        db,
                        case_id,
                        severity="info",
                        category="reconciliation",
                        title=f"Values reconcile for invoice {invoice_id}",
                        explanation=(
                            f"Invoice subtotal {normalize_amount(invoice_subtotal)} plus "
                            f"declared tax {normalize_amount(invoice_tax)} equals total "
                            f"{normalize_amount(invoice_total)}, the transaction amount "
                            f"matches, and the declared tax arithmetic is consistent. "
                            f"No anomaly was detected. Sources: {_locator_summary(invoice)}; "
                            f"{_locator_summary(transaction)}."
                        ),
                        confidence="high",
                        events=[invoice, transaction],
                        limitations=(
                            "Reconciliation confirms arithmetic and identifier agreement; "
                            "it does not prove that the invoice itself is genuine."
                        ),
                        alternatives="The record may be legitimate; this is the expected result.",
                    )
                )
    return findings


def _check_shared_identifiers(
    db: Session, case_id: str, events: dict[str, list[Event]]
) -> list[Finding]:
    findings: list[Finding] = []
    entities = list(
        db.scalars(
            select(Entity).where(
                Entity.case_id == case_id,
                Entity.entity_type.in_(SHARED_IDENTIFIER_TYPES),
            )
        )
    )
    for entity in entities:
        links = list(
            db.scalars(
                select(EventEntity)
                .where(EventEntity.entity_id == entity.id)
                .options(selectinload(EventEntity.event))
            )
        )
        if not links:
            continue
        by_evidence: defaultdict[str, list[Event]] = defaultdict(list)
        for link in links:
            by_evidence[link.event.evidence_id].append(link.event)
        if len(by_evidence) < 2:
            continue
        evidence_rows = list(
            db.scalars(select(Evidence).where(Evidence.id.in_(by_evidence.keys())))
        )
        evidence_names = {evidence.id: evidence.original_filename for evidence in evidence_rows}
        sample_events = [
            events_list[0] for events_list in by_evidence.values() if events_list
        ]
        severity = "low" if entity.entity_type in LOW_SEVERITY_IDENTIFIERS else "medium"
        findings.append(
            _add_finding(
                db,
                case_id,
                severity=severity,
                category="correlation",
                title=(
                    f"Identifier shared across evidence: "
                    f"{entity.entity_type} {entity.value_original}"
                ),
                explanation=(
                    f"The {entity.entity_type} value '{entity.value_original}' "
                    f"appears in {len(by_evidence)} evidence sources: "
                    + "; ".join(
                        f"{evidence_names.get(evidence_id, evidence_id)} "
                        f"({_locator_summary(events_list[0])})"
                        for evidence_id, events_list in by_evidence.items()
                    )
                    + ". This is an exact normalized identifier match, not proof "
                    "that the records describe the same real-world actor."
                ),
                confidence="high",
                events=list({event.id: event for event in sample_events}.values()),
                evidence_ids=list(by_evidence.keys()),
                limitations=(
                    "Shared identifiers can be reused, spoofed, or belong to a "
                    "service provider rather than an individual."
                ),
                alternatives=(
                    "A phone number, VPA, IP address, or filename may be shared by "
                    "multiple people or reused across unrelated events."
                ),
            )
        )
        evidence_ids = sorted(by_evidence)
        for left, right in combinations(evidence_ids, 2):
            for source in by_evidence[left][:5]:
                for target in by_evidence[right][:5]:
                    _add_edge(
                        db,
                        case_id,
                        source,
                        target,
                        edge_type="exact_identifier_match",
                        match_method="normalized_exact",
                        explanation=(
                            f"Exact {entity.entity_type} match: "
                            f"'{entity.value_original}' appears in both evidence sources."
                        ),
                        confidence="exact",
                    )
    return findings


def _check_timestamp_quality(
    db: Session, case_id: str, events: dict[str, list[Event]]
) -> list[Finding]:
    findings: list[Finding] = []
    by_evidence: defaultdict[str, list[Event]] = defaultdict(list)
    for event_list in events.values():
        for event in event_list:
            by_evidence[event.evidence_id].append(event)
    for evidence_id, event_list in by_evidence.items():
        counts = Counter(event.timestamp_confidence for event in event_list)
        uncertain = [
            event
            for event in event_list
            if event.timestamp_confidence in {"unknown", "inferred_year", "ambiguous"}
        ]
        if not uncertain:
            continue
        evidence = db.get(Evidence, evidence_id)
        filename = evidence.original_filename if evidence else evidence_id
        findings.append(
            _add_finding(
                db,
                case_id,
                severity="low",
                category="data_quality",
                title=f"Timestamp uncertainty in {filename}",
                explanation=(
                    f"{len(uncertain)} event(s) in {filename} have uncertain timestamps "
                    f"(inferred year: {counts.get('inferred_year', 0)}, "
                    f"ambiguous: {counts.get('ambiguous', 0)}, "
                    f"unknown: {counts.get('unknown', 0)}). "
                    "Normalized ordering may be affected."
                ),
                confidence="high",
                events=uncertain[:20],
                evidence_ids=[evidence_id],
                limitations=(
                    "The source log may omit the year or timezone. The parser records "
                    "the inference but cannot guarantee chronological accuracy."
                ),
                alternatives=(
                    "The log may be from a different year than the reference date, or "
                    "the source system may use a different timezone."
                ),
            )
        )
    return findings


def run(db: Session, case_id: str) -> list[Finding]:
    """Run deterministic reconciliation and rebuild persisted graph edges."""
    _clear_reconciliation_findings(db, case_id)
    events = _load_events(db, case_id)
    findings: list[Finding] = []
    findings.extend(_check_screenshot_vs_transaction(db, case_id, events))
    findings.extend(_check_invoice_vs_transaction(db, case_id, events))
    findings.extend(_check_shared_identifiers(db, case_id, events))
    findings.extend(_check_timestamp_quality(db, case_id, events))
    audit_service.record(
        db,
        case_id,
        "reconciliation.completed",
        details={
            "findings_created": len(findings),
            "event_types": {key: len(value) for key, value in events.items()},
        },
    )
    db.flush()
    return findings
