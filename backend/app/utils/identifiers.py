from __future__ import annotations

import ipaddress
import re
from decimal import Decimal, InvalidOperation

PHONE_SEPARATORS = re.compile(r"[\s\-().]")
UPI_RE = re.compile(r"^[A-Za-z0-9.\-_]+@[A-Za-z0-9.\-_]+$")


def normalize_entity(entity_type: str, value: str) -> tuple[str, str]:
    """Return (normalized_value, normalization_method).

    Normalization is deliberately conservative. It never invents missing
    components (for example, it does not add a country code to a phone number).
    """
    raw = (value or "").strip()
    kind = entity_type.lower()

    if kind == "phone":
        normalized = PHONE_SEPARATORS.sub("", raw)
        return normalized, "formatting_only"

    if kind == "ip":
        try:
            normalized = str(ipaddress.ip_address(raw.strip("[]")))
            return normalized, "ip_canonical"
        except ValueError:
            return raw, "raw"

    if kind == "mac":
        compact = re.sub(r"[^0-9A-Fa-f]", "", raw).upper()
        if len(compact) == 12:
            normalized = ":".join(compact[index : index + 2] for index in range(0, 12, 2))
            return normalized, "mac_canonical"
        return raw, "raw"

    if kind in {"device_id", "camera_id"}:
        return re.sub(r"\s+", "", raw).upper(), "strip_upper"

    if kind in {"imei", "imsi"}:
        compact = re.sub(r"[^0-9]", "", raw)
        if compact:
            return compact, "digits_only"
        return raw.upper(), "raw"

    if kind == "gps_point":
        return re.sub(r"\s+", "", raw), "coordinate_pair"

    if kind == "place_label":
        return raw.lower(), "lowercase"

    if kind in {"username", "host", "account"}:
        return raw, "raw"

    if kind in {"upi_vpa", "email", "url", "domain"}:
        return raw.lower(), "lowercase"

    if kind in {"utr", "transaction_id", "invoice_id"}:
        return re.sub(r"\s+", "", raw).upper(), "strip_upper"

    if kind == "amount":
        try:
            return str(Decimal(raw.replace(",", "").replace("₹", "").strip())), "decimal"
        except (InvalidOperation, ValueError):
            return raw, "raw"

    return raw, "raw"


def is_valid_upi(value: str) -> bool:
    return bool(UPI_RE.match(value.strip()))
