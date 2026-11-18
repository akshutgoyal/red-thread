from __future__ import annotations

import json

from app.services.privacy_service import Pseudonymizer


def test_pseudonyms_are_stable_and_reversible():
    scrubber = Pseudonymizer()
    payload = {
        "events": [
            {
                "id": "abc123",
                "source_snippet": "Call from +91-99001-12233 to rahul.sharma@example.com",
                "attributes": {"account": "123456789012", "latitude": 18.5},
            }
        ]
    }

    outbound = scrubber.scrub(payload)
    text = json.dumps(outbound)

    assert "+91-99001-12233" not in text
    assert "rahul.sharma@example.com" not in text
    assert "123456789012" not in text
    assert "PHONE_01" in text
    assert "EMAIL_01" in text
    assert "ACCOUNT_01" in text
    assert "RECORD_01" in text

    # Same value twice maps to the same token, so cross-source reasoning works.
    again = scrubber.scrub({"snippet": "+91-99001-12233"})
    assert again["snippet"].count("PHONE_01") == 1


def test_reverse_mapping_restores_real_values():
    scrubber = Pseudonymizer()
    scrubber.scrub_text("+91-99001-12233 called")
    restored = scrubber.restore("The token PHONE_01 appears twice: PHONE_01.")
    assert restored.count("+91-99001-12233") == 2


def test_unknown_tokens_are_not_invented():
    scrubber = Pseudonymizer()
    scrubber.scrub_text("+91-99001-12233")
    restored = scrubber.restore("PHONE_99 is not a real token")
    assert restored == "PHONE_99 is not a real token"
    assert scrubber.unknown_tokens("PHONE_99 and PHONE_01") == ["PHONE_99"]


def test_disabled_pseudonymizer_is_a_no_op():
    scrubber = Pseudonymizer(enabled=False)
    payload = {"phone": "+91-99001-12233"}
    assert scrubber.scrub(payload) == payload
    assert scrubber.restore("PHONE_01") == "PHONE_01"
    assert scrubber.token_count == 0


def test_structure_is_preserved():
    scrubber = Pseudonymizer()
    payload = {
        "case": {"id": "case1", "title": "Operation Trail"},
        "events": [{"id": "e1", "attributes": {"latitude": 18.5, "longitude": 73.8}}],
    }
    outbound = scrubber.scrub(payload)
    assert outbound.keys() == payload.keys()
    assert len(outbound["events"]) == len(payload["events"])
    # Non-identifier values survive so the model can still analyse structure.
    assert outbound["events"][0]["attributes"]["latitude"] == 18.5
