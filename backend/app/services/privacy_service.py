"""Pseudonymisation layer between Red Thread and an external LLM.

The external provider must never receive raw personal identifiers. Every value
that looks like a person, phone number, email, account, device or location is
replaced with a stable token such as ``PHONE_01`` for the duration of a single
request.

The token-to-value mapping lives only in memory inside this process. It is never
persisted, logged, or included in the outbound payload. The model's answer is
mapped back server-side, so the investigator still sees real identifiers while
the provider only ever saw tokens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..utils.extraction import extract_entities

#: Human-readable prefixes per entity type. Anything not listed falls back to a
#: generic, still-typed token so the model can tell categories apart.
PREFIXES = {
    "phone": "PHONE",
    "email": "EMAIL",
    "upi_vpa": "UPI",
    "account": "ACCOUNT",
    "ip": "IP",
    "mac": "MAC",
    "domain": "DOMAIN",
    "url": "URL",
    "utr": "UTR",
    "transaction_id": "TXN",
    "invoice_id": "INVOICE",
    "filename": "FILE",
    "amount": "AMOUNT",
    "person": "PERSON",
    "device_id": "DEVICE",
    "imei": "DEVICE",
    "imsi": "DEVICE",
    "location": "LOCATION",
    "gps_point": "LOCATION",
    "camera_id": "CAMERA",
    "username": "USER",
}

#: Free-text names are the hardest to detect reliably, so we only tokenise
#: capitalised two-token sequences that are not obviously an organisation or a
#: known technical term.
NAME_RE = re.compile(r"\b([A-Z][a-z]{1,20})\s+([A-Z][a-z]{1,20})\b")
IDENTIFIER_RE = re.compile(
    r"(?<!\w)(?:[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"  # email
    r"|(?:\+91[\s-]?\d{5}[\s-]?\d{5}|(?<!\d)[6-9]\d{9}(?!\d)|\+\d{10,15})"  # phone
    r"|(?:\d{1,3}\.){3}\d{1,3}"  # ip
    r"|(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2})"  # mac
)
NAME_STOPWORDS = {
    "Red Thread",
    "Bharatiya Sakshya",
    "Section",
    "Part A",
    "Part B",
    "Case ID",
    "Source Locator",
    "Chain Of",
}

#: Keys whose *values* are opaque Red Thread record IDs. They are pseudonymised
#: as record tokens so the model cannot correlate records across cases.
ID_KEYS = {"id", "evidence_id", "event_id", "finding_id", "relationship_id"}

#: Keys that identify a person or account by their own name rather than by
#: their content. A bare value such as ``"account": "123456789012"`` has no
#: recognisable text pattern, so the key tells us what it is.
PII_KEYS = {
    "account": "ACCOUNT",
    "account_number": "ACCOUNT",
    "phone": "PHONE",
    "phone_number": "PHONE",
    "msisdn": "PHONE",
    "email": "EMAIL",
    "email_address": "EMAIL",
    "name": "PERSON",
    "full_name": "PERSON",
    "person": "PERSON",
    "owner": "PERSON",
    "holder": "PERSON",
    "sender": "PERSON",
    "recipient": "PERSON",
    "card_number": "ACCOUNT",
    "imei": "DEVICE",
    "imsi": "DEVICE",
    "device_id": "DEVICE",
    "mac": "MAC",
    "ip": "IP",
    "ip_address": "IP",
    "username": "USER",
    "upi_vpa": "UPI",
    "vpa": "UPI",
}


@dataclass
class Pseudonymizer:
    """Per-request, in-memory pseudonymisation map."""

    enabled: bool = True
    counters: dict[str, int] = field(default_factory=dict)
    forward: dict[str, str] = field(default_factory=dict)
    reverse: dict[str, str] = field(default_factory=dict)
    _token_re: re.Pattern[str] | None = None

    def register(self, entity_type: str, value: str) -> str:
        """Register a known identifier discovered from stored entities.

        Pattern matching alone misses short bare values such as a username
        ``root``. The entity table already knows what is an identifier, so it is
        the authoritative source for what must be tokenised.
        """

        if not self.enabled or not value or len(value) < 2:
            return value
        prefix = PREFIXES.get(entity_type, "IDENTIFIER")
        return self._next_token(prefix, value)

    def _next_token(self, prefix: str, value: str) -> str:
        existing = self.forward.get(value)
        if existing:
            return existing
        count = self.counters.get(prefix, 0) + 1
        self.counters[prefix] = count
        token = f"{prefix}_{count:02d}"
        # A value could theoretically normalise to the same token; disambiguate.
        while token in self.reverse and self.reverse[token] != value:
            count += 1
            self.counters[prefix] = count
            token = f"{prefix}_{count:02d}"
        self.forward[value] = token
        self.reverse[token] = value
        return token

    def token_for(self, prefix: str, value: str) -> str:
        if not self.enabled or not value:
            return value
        return self._next_token(prefix, value)

    def scrub_text(self, text: str) -> str:
        """Replace every recognisable identifier in a free-text value."""

        if not self.enabled or not text:
            return text

        result = text
        # Values registered from the entity table take precedence: they are the
        # authoritative list of this case's identifiers.
        for value in sorted(self.forward, key=len, reverse=True):
            if value and value in result:
                result = result.replace(value, self.forward[value])

        for entity_type, value, _role in extract_entities(result):
            prefix = PREFIXES.get(entity_type, "IDENTIFIER")
            token = self.token_for(prefix, value)
            if token != value:
                result = result.replace(value, token)

        for match in IDENTIFIER_RE.finditer(result):
            value = match.group(0)
            prefix = "EMAIL" if "@" in value else "NUMBER"
            if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value):
                prefix = "IP"
            elif re.fullmatch(r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}", value):
                prefix = "MAC"
            result = result.replace(value, self.token_for(prefix, value))

        for match in NAME_RE.finditer(result):
            value = match.group(0)
            if value in NAME_STOPWORDS:
                continue
            result = result.replace(value, self.token_for("PERSON", value))
        return result

    def scrub(self, value: Any, *, key: str | None = None) -> Any:
        """Recursively pseudonymise a JSON-like structure.

        The structure is preserved exactly so the model can still reason about
        relationships between records; only the leaf values change.
        """

        if not self.enabled:
            return value
        if isinstance(value, str):
            if key in ID_KEYS:
                return self.token_for("RECORD", value)
            # A bare identifier under a known key has no textual pattern, so the
            # key itself is the only signal that it is personal data.
            if key in PII_KEYS and value.strip():
                return self.token_for(PII_KEYS[key], value)
            return self.scrub_text(value)
        if isinstance(value, dict):
            return {
                item_key: self.scrub(item_value, key=item_key)
                for item_key, item_value in value.items()
            }
        if isinstance(value, list):
            return [self.scrub(item) for item in value]
        return value

    def restore(self, value: Any) -> Any:
        """Map tokens back to real identifiers in the model's answer.

        Tokens this request never issued are left untouched and reported, so a
        model cannot invent an identity that it was never given.
        """

        if not self.enabled or not self.reverse:
            return value
        if isinstance(value, str):
            return self._restore_text(value)
        if isinstance(value, dict):
            return {key: self.restore(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.restore(item) for item in value]
        return value

    def _restore_text(self, text: str) -> str:
        if not text:
            return text
        if self._token_re is None:
            self._token_re = re.compile(
                r"\b(?:"
                + "|".join(sorted(map(re.escape, PREFIXES.values()), key=len, reverse=True))
                + r"|IDENTIFIER|NUMBER|RECORD)_\d{2,}\b"
            )
        return self._token_re.sub(
            lambda match: self.reverse.get(match.group(0), match.group(0)), text
        )

    def unknown_tokens(self, text: str) -> list[str]:
        """Return issued-looking tokens in ``text`` that this request never made.

        Used to flag a model that attempts to reference an identity it was not
        given, without silently fabricating a mapping for it.
        """

        if not self.enabled or not text:
            return []
        if self._token_re is None:
            self._restore_text("")
        assert self._token_re is not None
        return [
            token
            for token in self._token_re.findall(text)
            if token not in self.reverse
        ]

    @property
    def token_count(self) -> int:
        return len(self.reverse)
