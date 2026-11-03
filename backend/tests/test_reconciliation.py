from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from PIL import Image
from sqlalchemy import select

from app.models import Event, Finding, GraphEdge
from app.services import entity_service, reconciliation_service


def _upload(client, case_id, filename, content):
    response = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": (filename, content, "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (1080, 2400), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _event(db, case, evidence, event_type, attributes, locator):
    event = Event(
        case_id=case["id"],
        evidence_id=evidence["id"],
        event_type=event_type,
        timestamp_raw=attributes.get("timestamp_raw", "2026-10-15 10:00:00"),
        timestamp_normalized=datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc),
        timestamp_confidence="exact",
        timestamp_timezone="Asia/Kolkata",
        source_filename=evidence["original_filename"],
        source_locator=locator,
        source_snippet=str(attributes)[:500],
        attributes_json=attributes,
        warnings_json=[],
        parser_name="test_fixture",
        parser_version="1.0.0",
    )
    db.add(event)
    db.flush()
    return event


def _link(db, case_id, event, entity_type, value, role):
    entity = entity_service.get_or_create_entity(
        db, case_id, entity_type, value, role=role
    )
    entity_service.link_event_entity(db, event, entity, role=role, raw_value=value)


def test_operation_phishtrace_reconciliation(client, case, db):
    phone = "+91-98765-43210"
    call = _upload(
        client,
        case["id"],
        "call_log.csv",
        f"timestamp_raw,caller_id,receiver_id\n2026-10-15 10:15:00 IST,{phone},+91-91234-56789\n".encode(),
    )
    chat = _upload(
        client,
        case["id"],
        "chat_export.txt",
        (
            f"[2026-10-15, 10:18:30 IST] {phone}: Turant ₹45,000 bhejo.\n"
            f"[2026-10-15, 10:24:15 IST] {phone}: <attached: invoice_45000.pdf>\n"
        ).encode(),
    )
    invoice = _upload(client, case["id"], "invoice_45000.pdf", b"%PDF-1.4\n")
    screenshot = _upload(client, case["id"], "payment_screenshot.png", _png_bytes())
    ledger = _upload(
        client,
        case["id"],
        "upi_transaction_log.csv",
        (
            "txn_id,utr_number,timestamp_ist,payer_vpa,payee_vpa,amount_inr,status\n"
            "TXN-101982,312456789012,2026-10-15 11:05:00,"
            "victim@okhdfc,fraud-mule@okaxis,45000.00,SUCCESS\n"
        ).encode(),
    )
    benign_invoice = _upload(
        client, case["id"], "invoice_legit.pdf", b"%PDF-1.4\n"
    )
    benign_ledger = _upload(
        client,
        case["id"],
        "upi_statement.csv",
        (
            "txn_id,utr_number,timestamp_ist,payer_vpa,payee_vpa,amount_inr,status\n"
            "TXN-200001,412456789099,2026-10-16 12:00:00,"
            "victim@okhdfc,vendor-support@icici,53100.00,SUCCESS\n"
        ).encode(),
    )

    call_event = _event(
        db,
        case,
        call,
        "call",
        {
            "caller": phone,
            "receiver": "+91-91234-56789",
            "duration_sec": 142,
            "call_type": "INCOMING",
        },
        "row:4",
    )
    _link(db, case["id"], call_event, "phone", phone, "caller")

    chat_event = _event(
        db,
        case,
        chat,
        "chat_message",
        {
            "sender": phone,
            "message": "Turant ₹45,000 bhejo.",
            "attachment": "invoice_45000.pdf",
        },
        "line:12",
    )
    _link(db, case["id"], chat_event, "phone", phone, "sender")
    _link(db, case["id"], chat_event, "filename", "invoice_45000.pdf", "attachment")

    invoice_event = _event(
        db,
        case,
        invoice,
        "invoice",
        {
            "invoice_id": "INV-2026-9912",
            "subtotal": "45000.00",
            "tax_amount": "0.00",
            "total": "45000.00",
            "payee_vpa": "gov-security@upi",
            "currency": "INR",
        },
        "page:1",
    )
    _link(db, case["id"], invoice_event, "invoice_id", "INV-2026-9912", "invoice_id")
    _link(db, case["id"], invoice_event, "upi_vpa", "gov-security@upi", "payee")

    image_event = _event(
        db,
        case,
        screenshot,
        "image_ocr",
        {
            "ocr_text": (
                "Payment Successful! Rs. 4,500 transferred to gov-security@upi. "
                "UTR: 312456789012"
            ),
            "ocr_confidence": 95.0,
            "bbox": [142, 320, 110, 45],
        },
        "bbox:142,320,110,45",
    )
    _link(db, case["id"], image_event, "utr", "312456789012", "ocr_utr")
    _link(db, case["id"], image_event, "upi_vpa", "gov-security@upi", "mentioned")

    transaction_event = _event(
        db,
        case,
        ledger,
        "transaction",
        {
            "transaction_id": "TXN-101982",
            "utr": "312456789012",
            "amount": "45000.00",
            "currency": "INR",
            "payer_vpa": "victim@okhdfc",
            "payee_vpa": "fraud-mule@okaxis",
            "status": "SUCCESS",
        },
        "row:19",
    )
    _link(db, case["id"], transaction_event, "utr", "312456789012", "utr")
    _link(db, case["id"], transaction_event, "upi_vpa", "fraud-mule@okaxis", "payee")
    _link(db, case["id"], transaction_event, "transaction_id", "TXN-101982", "transaction_id")

    benign_invoice_event = _event(
        db,
        case,
        benign_invoice,
        "invoice",
        {
            "invoice_id": "INV-2026-9913",
            "subtotal": "45000.00",
            "tax_amount": "8100.00",
            "total": "53100.00",
            "payee_vpa": "vendor-support@icici",
            "currency": "INR",
            "tax_lines": [
                {"label": "CGST", "rate": "9", "amount": "4050.00"},
                {"label": "SGST", "rate": "9", "amount": "4050.00"},
            ],
        },
        "page:1",
    )
    _link(db, case["id"], benign_invoice_event, "invoice_id", "INV-2026-9913", "invoice_id")
    _link(db, case["id"], benign_invoice_event, "upi_vpa", "vendor-support@icici", "payee")

    benign_transaction_event = _event(
        db,
        case,
        benign_ledger,
        "transaction",
        {
            "transaction_id": "TXN-200001",
            "utr": "412456789099",
            "amount": "53100.00",
            "currency": "INR",
            "payer_vpa": "victim@okhdfc",
            "payee_vpa": "vendor-support@icici",
            "status": "SUCCESS",
        },
        "row:2",
    )
    _link(db, case["id"], benign_transaction_event, "utr", "412456789099", "utr")
    _link(db, case["id"], benign_transaction_event, "upi_vpa", "vendor-support@icici", "payee")

    db.commit()

    findings = reconciliation_service.run(db, case["id"])
    db.commit()

    titles = [finding.title for finding in findings]
    assert any("Amount discrepancy" in title for title in titles)
    assert any("Payee mismatch" in title for title in titles)
    assert any("Exact UTR match" in title for title in titles)
    assert any("Identifier shared across evidence" in title for title in titles)
    assert any("Values reconcile for invoice INV-2026-9913" in title for title in titles)

    high_findings = [finding for finding in findings if finding.severity == "high"]
    assert any("Amount discrepancy" in finding.title for finding in high_findings)
    assert any("Payee mismatch" in finding.title for finding in high_findings)

    benign_findings = [
        finding
        for finding in findings
        if finding.category == "reconciliation"
        and (
            "INV-2026-9913" in finding.title
            or "vendor-support@icici" in finding.explanation
        )
    ]
    assert benign_findings
    assert all(finding.severity == "info" for finding in benign_findings)

    for finding in findings:
        lowered = finding.title.lower()
        assert "fraud" not in lowered
        assert "guilty" not in lowered
        assert "fake" not in lowered

    edges = list(db.scalars(select(GraphEdge).where(GraphEdge.case_id == case["id"])))
    edge_types = {edge.edge_type for edge in edges}
    assert "exact_utr_match" in edge_types
    assert "amount_conflict" in edge_types
    assert "payee_conflict" in edge_types
    assert "exact_identifier_match" in edge_types

    stored_findings = list(
        db.scalars(select(Finding).where(Finding.case_id == case["id"]))
    )
    assert stored_findings
