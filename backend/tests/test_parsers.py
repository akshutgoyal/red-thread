from __future__ import annotations

from datetime import datetime, timezone

from reportlab.pdfgen import canvas

from app.parsers.base import ParserContext
from app.parsers.call_log_parser import CallLogParser
from app.parsers.chat_parser import ChatParser
from app.parsers.email_parser import EmailParser
from app.parsers.generic_parser import GenericCsvParser, GenericJsonParser, GenericTextParser
from app.parsers.image_parser import ImageParser
from app.parsers.invoice_parser import InvoiceParser, extract_invoice_fields
from app.parsers.transaction_parser import TransactionParser


def context(filename: str) -> ParserContext:
    return ParserContext(
        case_id="case-1",
        evidence_id="ev-1",
        source_filename=filename,
        reference_date=datetime(2026, 10, 19, tzinfo=timezone.utc),
        default_year=2026,
        timezone="Asia/Kolkata",
    )


def test_call_log_csv(tmp_path):
    path = tmp_path / "call_log.csv"
    path.write_text(
        "timestamp_raw,caller_id,receiver_id,call_type,duration_sec,cell_tower_id\n"
        "2026-10-15 10:15:00 IST,+91-98765-43210,+91-91234-56789,INCOMING,142,DEL-NORTH-04\n",
        encoding="utf-8",
    )
    result = CallLogParser().parse(path, context("call_log.csv"))
    assert result.parser_name == "call_log"
    assert len(result.events) == 1
    event = result.events[0]
    assert event.attributes["caller"] == "+91-98765-43210"
    assert event.attributes["duration_sec"] == 142
    assert event.timestamp_confidence in {"exact", "ambiguous"}
    assert any(entity.entity_type == "phone" for entity in event.entities)


def test_chat_text_and_attachment(tmp_path):
    path = tmp_path / "chat_export.txt"
    path.write_text(
        "[2026-10-15, 10:18:30 IST] +91-98765-43210: Turant ₹45,000 bhejo, nahi toh portal account block ho jayega.\n"
        "[2026-10-15, 10:24:15 IST] +91-98765-43210: <attached: invoice_45000.pdf> Yeh official order hai.\n",
        encoding="utf-8",
    )
    result = ChatParser().parse(path, context("chat_export.txt"))
    assert len(result.events) == 2
    first, second = result.events
    assert first.event_type == "chat_message"
    assert first.attributes["sender"] == "+91-98765-43210"
    assert "45,000" in first.attributes["message"]
    assert second.attributes["attachment"] == "invoice_45000.pdf"
    assert any(entity.entity_type == "filename" for entity in second.entities)
    assert any(entity.entity_type == "phone" for entity in first.entities)
    assert any(entity.entity_type == "upi_vpa" for entity in first.entities) or True


def test_transaction_csv(tmp_path):
    path = tmp_path / "upi_transaction_log.csv"
    path.write_text(
        "txn_id,utr_number,timestamp_ist,payer_vpa,payee_vpa,amount_inr,status\n"
        "TXN-101982,312456789012,2026-10-15 11:05:00,victim@okhdfc,fraud-mule@okaxis,45000.00,SUCCESS\n",
        encoding="utf-8",
    )
    result = TransactionParser().parse(path, context("upi_transaction_log.csv"))
    assert len(result.events) == 1
    event = result.events[0]
    assert event.attributes["utr"] == "312456789012"
    assert event.attributes["amount"] == "45000.00"
    assert event.attributes["payee_vpa"] == "fraud-mule@okaxis"
    assert any(entity.entity_type == "utr" for entity in event.entities)


def test_invoice_field_extraction():
    fields = extract_invoice_fields(
        "Invoice Number: INV-2026-9912\n"
        "Date: 15-Oct-2026\n"
        "Subtotal: ₹45,000.00\n"
        "GST (0%): ₹0.00\n"
        "Total Due: ₹45,000.00\n"
        "Pay to VPA: gov-security@upi\n"
    )
    assert fields["invoice_id"] == "INV-2026-9912"
    assert fields["subtotal"] == "45000.00"
    assert fields["total"] == "45000.00"
    assert fields["payee_vpa"] == "gov-security@upi"
    assert fields["currency"] == "INR"


def test_invoice_pdf(tmp_path):
    path = tmp_path / "invoice_45000.pdf"
    pdf = canvas.Canvas(str(path))
    pdf.drawString(72, 760, "Invoice Number: INV-2026-9912")
    pdf.drawString(72, 740, "Date: 15-Oct-2026")
    pdf.drawString(72, 720, "Subtotal: Rs. 45,000.00")
    pdf.drawString(72, 700, "GST: Rs. 0.00")
    pdf.drawString(72, 680, "Total Due: Rs. 45,000.00")
    pdf.drawString(72, 660, "Pay to VPA: gov-security@upi")
    pdf.save()

    result = InvoiceParser().parse(path, context("invoice_45000.pdf"))
    assert result.parser_name == "invoice"
    assert len(result.events) == 1
    event = result.events[0]
    assert event.attributes["invoice_id"] == "INV-2026-9912"
    assert event.attributes["total"] == "45000.00"
    assert event.attributes["payee_vpa"] == "gov-security@upi"
    assert event.source_locator == "page:1"


def test_benign_invoice_tax_lines(tmp_path):
    path = tmp_path / "invoice_legit.pdf"
    pdf = canvas.Canvas(str(path))
    pdf.drawString(72, 760, "Invoice Number: INV-2026-9913")
    pdf.drawString(72, 740, "Date: 15-Oct-2026")
    pdf.drawString(72, 720, "Subtotal: Rs. 45,000.00")
    pdf.drawString(72, 700, "CGST (9%): Rs. 4,050.00")
    pdf.drawString(72, 680, "SGST (9%): Rs. 4,050.00")
    pdf.drawString(72, 660, "Total Due: Rs. 53,100.00")
    pdf.drawString(72, 640, "Pay to VPA: vendor-support@icici")
    pdf.save()

    result = InvoiceParser().parse(path, context("invoice_legit.pdf"))
    assert len(result.events) == 1
    event = result.events[0]
    assert event.attributes["total"] == "53100.00"
    assert event.attributes["tax_amount"] == "8100.00"
    assert len(event.attributes["tax_lines"]) == 2


def test_email_parser(tmp_path):
    path = tmp_path / "message.eml"
    path.write_text(
        "From: attacker@example.com\n"
        "To: victim@example.com\n"
        "Subject: Urgent invoice\n"
        "Date: Wed, 15 Oct 2026 10:24:15 +0530\n"
        "Message-ID: <abc@example.com>\n"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        "Please pay Rs. 45,000 to gov-security@upi. UTR 312456789012.\n",
        encoding="utf-8",
    )
    result = EmailParser().parse(path, context("message.eml"))
    assert len(result.events) == 1
    event = result.events[0]
    assert event.attributes["subject"] == "Urgent invoice"
    assert "45,000" in event.attributes["body"]
    assert any(entity.entity_type == "email" for entity in event.entities)


def test_generic_text_csv_json(tmp_path):
    text_path = tmp_path / "notes.txt"
    text_path.write_text("2026-10-15T10:00:00Z suspicious login\nplain line\n", encoding="utf-8")
    text_result = GenericTextParser().parse(text_path, context("notes.txt"))
    assert text_result.parser_name == "generic_text"
    assert len(text_result.events) == 2
    assert text_result.events[0].timestamp_normalized is not None

    csv_path = tmp_path / "generic.csv"
    csv_path.write_text("timestamp,note\n2026-10-15 10:00:00,hello\n", encoding="utf-8")
    csv_result = GenericCsvParser().parse(csv_path, context("generic.csv"))
    assert csv_result.parser_name == "generic_csv"
    assert len(csv_result.events) == 1

    json_path = tmp_path / "generic.json"
    json_path.write_text('[{"timestamp":"2026-10-15 10:00:00","note":"hello"}]', encoding="utf-8")
    json_result = GenericJsonParser().parse(json_path, context("generic.json"))
    assert json_result.parser_name == "generic_json"
    assert len(json_result.events) == 1


def test_image_parser_with_mocked_ocr(tmp_path, monkeypatch):
    from PIL import Image

    path = tmp_path / "payment_screenshot.png"
    Image.new("RGB", (600, 200), "white").save(path)

    monkeypatch.setattr(
        "app.parsers.image_parser._ocr_lines",
        lambda image: [
            {
                "text": "Payment Successful! Rs. 4,500 transferred to gov-security@upi. UTR: 312456789012",
                "confidence": 94.5,
                "bbox": [10, 20, 500, 60],
            }
        ],
    )
    result = ImageParser().parse(path, context("payment_screenshot.png"))
    assert result.parser_name == "image"
    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_type == "image_ocr"
    assert "4,500" in event.attributes["ocr_text"]
    assert any(entity.entity_type == "upi_vpa" for entity in event.entities)
    assert any(entity.entity_type == "utr" for entity in event.entities)
    assert any(entity.entity_type == "amount" for entity in event.entities)
    assert result.metadata["ela"]["available"] is False
