from __future__ import annotations

import json


def _upload_auth(client, case_id, auth_log_bytes):
    return client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("auth.log", auth_log_bytes, "text/plain")},
    )


def test_auth_upload_parse_events_findings_and_reports(client, case, auth_log_bytes):
    uploaded = _upload_auth(client, case["id"], auth_log_bytes)
    assert uploaded.status_code == 201, uploaded.text
    evidence = uploaded.json()

    verified = client.post(
        f"/api/evidence/{evidence['id']}/verify", params={"case_id": case["id"]}
    )
    assert verified.status_code == 200
    assert verified.json()["verified"] is True

    parsed = client.post(
        f"/api/evidence/{evidence['id']}/parse", params={"case_id": case["id"]}
    )
    assert parsed.status_code == 200, parsed.text
    result = parsed.json()
    assert result["events_created"] == 16
    assert result["findings_created"] >= 1
    assert result["status"] == "parsed"

    events = client.get(
        f"/api/cases/{case['id']}/events",
        params={"event_type": "auth.login"},
    )
    assert events.status_code == 200
    assert events.json()["total"] >= 10

    findings = client.get(
        f"/api/cases/{case['id']}/findings",
        params={"category": "authentication"},
    )
    assert findings.status_code == 200
    assert findings.json()["total"] >= 1
    finding = findings.json()["items"][0]
    assert finding["severity"] in {"low", "medium", "high"}
    assert finding["status"] == "open"

    reviewed = client.post(
        f"/api/findings/{finding['id']}/review",
        params={"case_id": case["id"]},
        json={"status": "accepted", "reviewer_note": "Confirmed as an indicator."},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "accepted"

    timeline = client.get(f"/api/cases/{case['id']}/timeline")
    assert timeline.status_code == 200
    assert timeline.json()["total"] > 0

    graph = client.get(f"/api/cases/{case['id']}/graph")
    assert graph.status_code == 200
    assert len(graph.json()["nodes"]) > 0
    assert len(graph.json()["edges"]) > 0

    exported_json = client.get(
        f"/api/cases/{case['id']}/auth/export", params={"format": "json"}
    )
    assert exported_json.status_code == 200
    payload = exported_json.json()
    assert payload["case_id"] == case["id"]
    assert len(payload["events"]) == 16

    exported_csv = client.get(
        f"/api/cases/{case['id']}/auth/export", params={"format": "csv"}
    )
    assert exported_csv.status_code == 200
    assert "event_id" in exported_csv.text
    assert "finding_id" in exported_csv.text
    assert "Authentication indicator" in exported_csv.text

    findings_only = client.get(
        f"/api/cases/{case['id']}/auth/export",
        params={"format": "csv", "kind": "findings"},
    )
    assert findings_only.status_code == 200
    assert "event_id" not in findings_only.text
    assert "finding_id" in findings_only.text


def test_reparse_replaces_derived_events(client, case, auth_log_bytes):
    uploaded = _upload_auth(client, case["id"], auth_log_bytes)
    evidence_id = uploaded.json()["id"]

    first = client.post(
        f"/api/evidence/{evidence_id}/parse", params={"case_id": case["id"]}
    )
    assert first.status_code == 200
    first_count = first.json()["events_created"]

    duplicate = client.post(
        f"/api/evidence/{evidence_id}/parse", params={"case_id": case["id"]}
    )
    assert duplicate.status_code == 409

    second = client.post(
        f"/api/evidence/{evidence_id}/parse",
        params={"case_id": case["id"], "reparse": "true"},
    )
    assert second.status_code == 200
    assert second.json()["events_created"] == first_count

    events = client.get(f"/api/cases/{case['id']}/events")
    assert events.json()["total"] == first_count


def test_generic_text_parser_is_explicitly_labelled(client, case):
    uploaded = client.post(
        f"/api/cases/{case['id']}/evidence",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    evidence_id = uploaded.json()["id"]
    parsed = client.post(
        f"/api/evidence/{evidence_id}/parse", params={"case_id": case["id"]}
    )
    assert parsed.status_code == 200
    payload = parsed.json()
    assert payload["parser_name"] == "generic_text"
    assert payload["events_created"] == 1
    assert payload["status"] == "parsed"


def test_auth_export_is_case_scoped(client, case, auth_log_bytes):
    uploaded = _upload_auth(client, case["id"], auth_log_bytes)
    client.post(
        f"/api/evidence/{uploaded.json()['id']}/parse",
        params={"case_id": case["id"]},
    )
    other = client.post("/api/cases", json={"title": "Other Case"})
    response = client.get(
        f"/api/cases/{other.json()['id']}/auth/export", params={"format": "json"}
    )
    assert response.status_code == 200
    assert response.json()["events"] == []
