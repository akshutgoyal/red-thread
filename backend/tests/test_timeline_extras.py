from __future__ import annotations

from app.services.correlation_service import relationship_label


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


def test_relationship_labels_cover_every_known_type():
    expectations = {
        "shared_identifier": "Same identifier in both sources",
        "co_mention": "Appears in the same event",
        "temporal_association": "Occurs close in time",
        "spatial_proximity": "Documented nearby",
        "communication_sequence": "Communication sequence",
        "device_auth_context": "Device or sign-in context",
        "evidence_contains_event": "Contains event",
    }
    for edge_type, expected in expectations.items():
        assert relationship_label(edge_type) == expected


def test_relationship_label_falls_back_to_readable_text():
    assert relationship_label("event_mentions_sender") == "Mentions sender"
    assert relationship_label("custom_edge") == "Custom edge"
    assert relationship_label(None) == "Related"


def test_graph_edges_carry_sentence_labels(client, case, auth_log_bytes):
    evidence = _evidence(client, case["id"], "auth_logs.log", auth_log_bytes, "text/plain")
    _parse(client, evidence["id"], case["id"])

    graph = client.get(f"/api/cases/{case['id']}/graph").json()
    assert graph["edges"], "expected graph edges"
    for edge in graph["edges"]:
        # No edge should surface a raw snake_case type as its label.
        assert "_" not in edge["label"], edge["label"]
        assert edge["label"][0].isupper()


def test_timeline_includes_event_meta_and_groups(client, case, auth_log_bytes):
    evidence = _evidence(client, case["id"], "auth_logs.log", auth_log_bytes, "text/plain")
    _parse(client, evidence["id"], case["id"])

    timeline = client.get(f"/api/cases/{case['id']}/timeline").json()
    assert "event_meta" in timeline
    assert "groups" in timeline
    assert timeline["items"]
    first_id = timeline["items"][0]["id"]
    assert first_id in timeline["event_meta"]
    meta = timeline["event_meta"][first_id]
    assert set(meta) == {"finding_ids", "relationship_ids", "review_status", "suspicious"}


def test_timeline_event_review_status_is_exposed(client, case, auth_log_bytes):
    evidence = _evidence(client, case["id"], "auth_logs.log", auth_log_bytes, "text/plain")
    _parse(client, evidence["id"], case["id"])
    timeline = client.get(f"/api/cases/{case['id']}/timeline").json()
    event_id = timeline["items"][0]["id"]

    client.post(
        f"/api/cases/{case['id']}/events/{event_id}/review",
        json={"decision": "relevant"},
    )
    timeline = client.get(f"/api/cases/{case['id']}/timeline").json()
    assert timeline["event_meta"][event_id]["review_status"] == "relevant"


def test_timeline_filters_by_evidence_and_range(client, case, auth_log_bytes):
    evidence = _evidence(client, case["id"], "auth_logs.log", auth_log_bytes, "text/plain")
    _parse(client, evidence["id"], case["id"])

    filtered = client.get(
        f"/api/cases/{case['id']}/timeline",
        params={"evidence_id": evidence["id"], "limit": 1000},
    ).json()
    assert all(item["evidence_id"] == evidence["id"] for item in filtered["items"])

    ranged = client.get(
        f"/api/cases/{case['id']}/timeline",
        params={"start": "2026-10-15T10:00:00Z", "end": "2026-10-15T10:10:00Z"},
    ).json()
    assert all(
        item["timestamp_normalized"] is not None for item in ranged["items"]
    )
