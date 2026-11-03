from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.utils.amounts import extract_amounts, parse_amount
from app.utils.extraction import extract_entities
from app.utils.identifiers import normalize_entity
from app.utils.timestamps import parse_flexible_timestamp


def test_identifier_normalization_is_conservative():
    assert normalize_entity("phone", "+91-98765-43210") == ("+919876543210", "formatting_only")
    assert normalize_entity("phone", "9876543210") == ("9876543210", "formatting_only")
    assert normalize_entity("upi_vpa", "Gov-Security@UPI") == ("gov-security@upi", "lowercase")
    assert normalize_entity("ip", "2001:0db8:0:0::1") == ("2001:db8::1", "ip_canonical")
    assert normalize_entity("utr", " 312 456 789 012 ") == ("312456789012", "strip_upper")


def test_extract_entities_from_payment_text():
    text = (
        "Payment Successful! Rs. 4,500 transferred to gov-security@upi. "
        "UTR: 312456789012. Contact +91-98765-43210."
    )
    entities = extract_entities(text)
    types = {entity_type for entity_type, _value, _role in entities}
    assert "amount" in types
    assert "upi_vpa" in types
    assert "utr" in types
    assert "phone" in types

    vpas = [value for entity_type, value, _ in entities if entity_type == "upi_vpa"]
    assert "gov-security@upi" in vpas
    emails = [value for entity_type, value, _ in entities if entity_type == "email"]
    assert "gov-security@upi" not in emails


def test_email_is_not_misclassified_as_vpa():
    entities = extract_entities("Contact analyst@example.com for details.")
    types = {entity_type for entity_type, _value, _role in entities}
    assert "email" in types
    assert "upi_vpa" not in types


def test_amount_parsing_and_extraction():
    assert parse_amount("₹45,000.00") == Decimal("45000.00")
    assert parse_amount("Rs. 4,500") == Decimal("4500")
    amounts = extract_amounts("Paid Rs. 4,500 and received ₹45,000.00")
    values = {str(value) for _raw, value, _currency in amounts}
    assert values == {"4500", "45000.00"}


def test_timestamp_confidence_labels():
    exact = parse_flexible_timestamp(
        "2026-10-15T10:00:00Z", default_timezone="UTC"
    )
    assert exact.confidence == "exact"
    assert exact.normalized == datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc)

    assumed = parse_flexible_timestamp(
        "2026-10-15 10:00:00", default_timezone="Asia/Kolkata"
    )
    assert assumed.confidence == "ambiguous"
    assert assumed.timezone_assumed is True

    inferred = parse_flexible_timestamp(
        "Oct 15 10:00:00",
        default_timezone="UTC",
        reference_date=datetime(2026, 10, 19, tzinfo=timezone.utc),
    )
    assert inferred.confidence == "inferred_year"
    assert inferred.year_inferred is True
    assert inferred.normalized is not None

    unknown = parse_flexible_timestamp("not a timestamp")
    assert unknown.confidence == "unknown"
    assert unknown.normalized is None
