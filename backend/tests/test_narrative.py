from __future__ import annotations

from app.services import narrative_service, suggestion_service


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


def test_narrative_empty_case(client, case):
    body = client.get(f"/api/cases/{case['id']}/narrative").json()
    assert body["case_id"] == case["id"]
    assert body["items"] == []
    assert body["disclaimer"]


def test_narrative_orders_observations_chronologically(client, case, auth_log_bytes):
    evidence = _evidence(client, case["id"], "auth_logs.log", auth_log_bytes, "text/plain")
    _parse(client, evidence["id"], case["id"])

    body = client.get(f"/api/cases/{case['id']}/narrative").json()
    observations = [item for item in body["items"] if item["kind"] == "observation"]
    assert observations, body
    timestamps = [item["timestamp"] for item in observations if item["timestamp"]]
    assert timestamps == sorted(timestamps)
    for item in body["items"]:
        assert item["href"].startswith(f"/cases/{case['id']}")
        assert item["index"] >= 1


def test_narrative_includes_review_and_report_kinds(client, case, auth_log_bytes):
    evidence = _evidence(client, case["id"], "auth_logs.log", auth_log_bytes, "text/plain")
    _parse(client, evidence["id"], case["id"])
    assert client.post(f"/api/cases/{case['id']}/reconcile").status_code == 200

    relationships = client.get(f"/api/cases/{case['id']}/relationships").json()["items"]
    if relationships:
        client.post(
            f"/api/relationships/{relationships[0]['id']}/review",
            headers={"X-Case-ID": case["id"]},
            json={"decision": "accepted", "reviewer": "analyst"},
        )

    report = client.post(f"/api/cases/{case['id']}/reports", json={"report_type": "json"})
    assert report.status_code in (200, 201), report.text

    body = client.get(f"/api/cases/{case['id']}/narrative").json()
    kinds = {item["kind"] for item in body["items"]}
    assert "observation" in kinds
    assert "report" in kinds
    if relationships:
        assert "review" in kinds


def test_narrative_never_claims_guilt_or_proof(client, case, auth_log_bytes):
    evidence = _evidence(client, case["id"], "auth_logs.log", auth_log_bytes, "text/plain")
    _parse(client, evidence["id"], case["id"])
    body = client.get(f"/api/cases/{case['id']}/narrative").json()
    text = " ".join(item["statement"] for item in body["items"]).lower()
    for forbidden in ("guilty", "committed the crime", "proves that", "fraudulent"):
        assert forbidden not in text


def test_narrative_missing_case_returns_404(client):
    assert client.get("/api/cases/nope/narrative").status_code == 404


def test_ai_suggestions_default_for_empty_case(client, case):
    body = client.get(f"/api/cases/{case['id']}/ai/suggestions").json()
    assert body["items"]
    questions = [item["question"] for item in body["items"]]
    assert any("Summarize" in question for question in questions)


def test_ai_suggestions_reflect_real_state(client, case, auth_log_bytes):
    evidence = _evidence(client, case["id"], "auth_logs.log", auth_log_bytes, "text/plain")
    _parse(client, evidence["id"], case["id"])

    body = client.get(f"/api/cases/{case['id']}/ai/suggestions").json()
    questions = " ".join(item["question"] for item in body["items"]).lower()
    assert "authentication" in questions or "sign-in" in questions


def test_findings_are_enriched_with_entities_and_timeline(client, case, auth_log_bytes):
    evidence = _evidence(client, case["id"], "auth_logs.log", auth_log_bytes, "text/plain")
    _parse(client, evidence["id"], case["id"])

    findings = client.get(f"/api/cases/{case['id']}/findings").json()["items"]
    assert findings, "expected auth findings"
    enriched = [item for item in findings if item["timeline_refs"] or item["related_entities"]]
    assert enriched, "expected at least one finding with event context"
    for item in findings:
        assert item["classification"] in {
            "observation",
            "correlation",
            "inference",
            "hypothesis",
        }
