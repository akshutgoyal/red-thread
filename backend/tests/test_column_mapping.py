from __future__ import annotations

from app.services import mapping_service


def _upload(client, case_id: str, name: str, content: bytes, media: str = "text/csv"):
    response = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": (name, content, media)},
    )
    assert response.status_code == 201, response.text
    return response.json()


UNMAPPED_CSV = (
    b"when_it_happened,who_called,who_answered,talk_seconds\n"
    b"2026-10-14T09:00:00Z,+91-90000-11111,+91-90000-22222,30\n"
    b"2026-10-14T09:05:00Z,+91-90000-33333,+91-90000-44444,12\n"
)


def test_mapping_preview_returns_headers_and_fields(client, case):
    evidence = _upload(client, case["id"], "custom_call_log.csv", UNMAPPED_CSV)
    response = client.get(
        f"/api/evidence/{evidence['id']}/mapping", params={"case_id": case["id"]}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["supported"] is True
    assert "when_it_happened" in body["headers"]
    keys = {field["key"] for field in body["fields"]}
    assert "timestamp" in keys
    assert body["rows"], "sample rows help confirm the mapping"


def test_mapping_is_rejected_without_a_timestamp(client, case):
    evidence = _upload(client, case["id"], "no_ts.csv", UNMAPPED_CSV)
    response = client.put(
        f"/api/evidence/{evidence['id']}/mapping",
        params={"case_id": case["id"]},
        json={"mapping": {"actor": "who_called"}},
    )
    assert response.status_code == 422
    assert "timestamp column is required" in response.json()["detail"].lower()


def test_mapping_saves_and_drives_parsing(client, case):
    evidence = _upload(client, case["id"], "custom_call_log.csv", UNMAPPED_CSV)

    saved = client.put(
        f"/api/evidence/{evidence['id']}/mapping",
        params={"case_id": case["id"]},
        json={
            "mapping": {
                "timestamp": "when_it_happened",
                "actor": "who_called",
                "target": "who_answered",
            }
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["saved_mapping"]["timestamp"] == "when_it_happened"

    parsed = client.post(
        f"/api/evidence/{evidence['id']}/parse", params={"case_id": case["id"]}
    )
    assert parsed.status_code == 200, parsed.text
    body = parsed.json()
    assert body["events_created"] >= 2
    # With a mapped timestamp the rows are no longer undated.
    assert body["records_extracted"] is not None

    events = client.get(
        f"/api/cases/{case['id']}/events", params={"evidence_id": evidence["id"]}
    ).json()["items"]
    dated = [event for event in events if event["timestamp_normalized"]]
    assert len(dated) >= 2


def test_mapping_ignores_columns_that_do_not_exist(client, case):
    evidence = _upload(client, case["id"], "custom_call_log.csv", UNMAPPED_CSV)
    saved = client.put(
        f"/api/evidence/{evidence['id']}/mapping",
        params={"case_id": case["id"]},
        json={"mapping": {"timestamp": "when_it_happened", "actor": "not_a_column"}},
    )
    assert saved.status_code == 200
    assert "actor" not in saved.json()["saved_mapping"]


def test_mapping_is_unavailable_for_images(client, case):
    # A 1x1 PNG is enough to prove the endpoint refuses non-tabular input.
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001"
    )
    evidence = _upload(client, case["id"], "pixel.png", png, media="image/png")
    response = client.get(
        f"/api/evidence/{evidence['id']}/mapping", params={"case_id": case["id"]}
    )
    assert response.status_code == 200
    assert response.json()["supported"] is False


def test_suggest_mapping_guesses_aliases():
    mapping = mapping_service.suggest_mapping(["timestamp", "sender", "recipient", "message"])
    assert mapping["timestamp"] == "timestamp"
    assert mapping["actor"] == "sender"
    assert mapping["target"] == "recipient"
    assert mapping["body"] == "message"
