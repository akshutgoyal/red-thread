from __future__ import annotations

def _evidence(client, case_id: str, filename: str, content: bytes, media_type: str):
    response = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": (filename, content, media_type)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _parse(client, evidence_id: str, case_id: str):
    response = client.post(
        f"/api/evidence/{evidence_id}/parse", params={"case_id": case_id}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_event_review_round_trip(client, case, auth_log_bytes):
    evidence = _evidence(client, case["id"], "auth_logs.log", auth_log_bytes, "text/plain")
    _parse(client, evidence["id"], case["id"])

    events = client.get(f"/api/cases/{case['id']}/events?limit=5").json()["items"]
    assert events, "expected extracted events"
    event_id = events[0]["id"]

    response = client.post(
        f"/api/cases/{case['id']}/events/{event_id}/review",
        json={"decision": "relevant", "reviewer": "analyst", "note": "Confirms the login burst."},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["event_id"] == event_id
    assert body["decision"] == "relevant"

    listing = client.get(f"/api/cases/{case['id']}/event-reviews").json()
    assert listing["total"] == 1
    assert listing["items"][0]["event_id"] == event_id

    # Updating the decision keeps one current row per event.
    response = client.post(
        f"/api/cases/{case['id']}/events/{event_id}/review",
        json={"decision": "not_relevant", "reviewer": "analyst"},
    )
    assert response.status_code == 200
    listing = client.get(f"/api/cases/{case['id']}/event-reviews").json()
    assert listing["total"] == 1
    assert listing["items"][0]["decision"] == "not_relevant"


def test_event_review_writes_audit_row(client, case, auth_log_bytes):
    evidence = _evidence(client, case["id"], "auth_logs.log", auth_log_bytes, "text/plain")
    _parse(client, evidence["id"], case["id"])
    event_id = client.get(f"/api/cases/{case['id']}/events?limit=1").json()["items"][0]["id"]

    client.post(
        f"/api/cases/{case['id']}/events/{event_id}/review",
        json={"decision": "needs_review"},
    )
    audit = client.get(f"/api/cases/{case['id']}/audit").json()
    actions = [item["action"] for item in audit]
    assert "event.reviewed" in actions


def test_event_review_rejects_unknown_event(client, case):
    response = client.post(
        f"/api/cases/{case['id']}/events/does-not-exist/review",
        json={"decision": "relevant"},
    )
    assert response.status_code == 422


def test_event_review_is_case_scoped(client, case, auth_log_bytes):
    evidence = _evidence(client, case["id"], "auth_logs.log", auth_log_bytes, "text/plain")
    _parse(client, evidence["id"], case["id"])
    event_id = client.get(f"/api/cases/{case['id']}/events?limit=1").json()["items"][0]["id"]

    other = client.post(
        "/api/cases",
        json={"title": "Unrelated case", "description": "No shared events."},
    ).json()

    response = client.post(
        f"/api/cases/{other['id']}/events/{event_id}/review",
        json={"decision": "relevant"},
    )
    assert response.status_code == 422
