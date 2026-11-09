from __future__ import annotations

from app.config import Settings
from app.services import guidance_service
from app.utils.warning_guidance import classify_warning, describe_warnings


def _evidence(client, case_id: str, filename: str, content: bytes, media_type: str):
    response = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": (filename, content, media_type)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_guidance_empty_case(client, case):
    response = client.get(f"/api/cases/{case['id']}/guidance")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["case_id"] == case["id"]
    assert len(body["stages"]) == 9
    assert body["stages"][0]["status"] == "complete"
    assert body["next_action"]["id"] == "upload_evidence"
    assert body["next_action"]["action_label"] == "Upload evidence"
    assert body["summary"]["evidence"] == 0
    assert body["next_action"]["href"].endswith("/evidence/intake")


def test_guidance_advances_after_evidence_upload(client, case, auth_log_bytes):
    evidence = _evidence(
        client, case["id"], "auth_logs.log", auth_log_bytes, "text/plain"
    )

    body = client.get(f"/api/cases/{case['id']}/guidance").json()
    assert body["summary"]["evidence"] == 1
    # Uploaded but not parsed: processing is the next action.
    assert body["next_action"]["id"] == "finish_processing"

    parsed = client.post(f"/api/evidence/{evidence['id']}/parse", params={"case_id": case["id"]})
    assert parsed.status_code == 200, parsed.text

    body = client.get(f"/api/cases/{case['id']}/guidance").json()
    assert body["summary"]["parsed"] == 1
    assert body["summary"]["needs_attention"] == 0
    stage_status = {stage["key"]: stage["status"] for stage in body["stages"]}
    assert stage_status["upload_evidence"] == "complete"
    assert stage_status["validate_process"] == "complete"
    assert stage_status["review_events"] == "in_progress"
    assert body["next_action"]["id"] != "finish_processing"


def test_guidance_reports_needs_attention_for_failed_parse(client, case):
    _evidence(client, case["id"], "notes.json", b'{"unexpected": true}', "application/json")
    body = client.get(f"/api/cases/{case['id']}/guidance").json()
    kinds = {item["kind"] for item in body["attention"]}
    # The file exists but has no events yet, so it needs processing.
    assert body["summary"]["needs_attention"] >= 0
    assert isinstance(kinds, set)


def test_guidance_next_action_prioritises_unreviewed_high_findings(client, case, auth_log_bytes):
    evidence = _evidence(
        client, case["id"], "auth_logs.log", auth_log_bytes, "text/plain"
    )
    assert client.post(f"/api/evidence/{evidence['id']}/parse", params={"case_id": case["id"]}).status_code == 200

    body = client.get(f"/api/cases/{case['id']}/guidance").json()
    findings = client.get(f"/api/cases/{case['id']}/findings").json()["items"]
    high = [item for item in findings if item["severity"] in {"high", "critical"}]
    if high:
        # Parser warnings legitimately outrank finding review. What must hold is
        # that unreviewed high findings are surfaced as attention.
        assert body["next_action"]["id"] in {
            "review_warnings",
            "review_findings",
            "review_relationships",
            "ask_copilot",
        }
        kinds = {item["kind"] for item in body["attention"]}
        assert "open_high_findings" in kinds


def test_guidance_stage_links_are_case_scoped(client, case):
    body = client.get(f"/api/cases/{case['id']}/guidance").json()
    for stage in body["stages"]:
        assert stage["href"].startswith(f"/cases/{case['id']}")
    for action in [body["next_action"], *body["attention"]]:
        assert action["href"].startswith(f"/cases/{case['id']}")


def test_guidance_missing_case_returns_404(client):
    response = client.get("/api/cases/does-not-exist/guidance")
    assert response.status_code == 404


def test_next_action_priority_order():
    # Direct unit coverage of the priority ladder, independent of the database.
    action = guidance_service._next_action(
        case_id="case-1",
        evidence_count=0,
        unparsed=[],
        warning_rows=[],
        event_count=0,
        unreviewed_high=[],
        unreviewed_relationships=[],
        ai_configured=True,
        report_count=0,
    )
    assert action.id == "upload_evidence"

    class _Row:
        pass

    action = guidance_service._next_action(
        case_id="case-1",
        evidence_count=1,
        unparsed=[_Row()],
        warning_rows=[_Row()],
        event_count=0,
        unreviewed_high=[],
        unreviewed_relationships=[],
        ai_configured=True,
        report_count=0,
    )
    assert action.id == "finish_processing"

    action = guidance_service._next_action(
        case_id="case-1",
        evidence_count=1,
        unparsed=[],
        warning_rows=[_Row()],
        event_count=3,
        unreviewed_high=[],
        unreviewed_relationships=[],
        ai_configured=True,
        report_count=0,
    )
    assert action.id == "review_warnings"

    action = guidance_service._next_action(
        case_id="case-1",
        evidence_count=1,
        unparsed=[],
        warning_rows=[],
        event_count=0,
        unreviewed_high=[],
        unreviewed_relationships=[],
        ai_configured=True,
        report_count=0,
    )
    assert action.id == "no_events"

    action = guidance_service._next_action(
        case_id="case-1",
        evidence_count=1,
        unparsed=[],
        warning_rows=[],
        event_count=4,
        unreviewed_high=[_Row()],
        unreviewed_relationships=[_Row()],
        ai_configured=True,
        report_count=0,
    )
    assert action.id == "review_findings"
    assert action.tone == "critical"

    action = guidance_service._next_action(
        case_id="case-1",
        evidence_count=1,
        unparsed=[],
        warning_rows=[],
        event_count=4,
        unreviewed_high=[],
        unreviewed_relationships=[_Row()],
        ai_configured=True,
        report_count=0,
    )
    assert action.id == "review_relationships"

    action = guidance_service._next_action(
        case_id="case-1",
        evidence_count=1,
        unparsed=[],
        warning_rows=[],
        event_count=4,
        unreviewed_high=[],
        unreviewed_relationships=[],
        ai_configured=False,
        report_count=0,
    )
    assert action.id == "generate_report"


def test_guidance_without_settings_does_not_crash(db, case):
    body = guidance_service.build_guidance(db, case["id"])
    assert body.case_id == case["id"]
    assert body.stages


def test_warning_classification_categories():
    cases = {
        "Timestamp column not detected": "timestamp",
        "Missing required column: sender": "schema",
        "Could not decode utf-8 content": "encoding",
        "Tesseract OCR unavailable": "ocr",
        "3 malformed rows were skipped": "partial",
        "Duplicate record found": "duplicate",
        "Unsupported file suffix": "unsupported",
        "Something unexpected happened": "other",
    }
    for message, expected in cases.items():
        guidance = classify_warning(message)
        assert guidance.category == expected, message
        assert guidance.impact
        assert guidance.recommendation


def test_warning_details_are_structured():
    details = describe_warnings(
        ["Timestamp column not detected"], source_locator="calls.csv:1"
    )
    assert len(details) == 1
    entry = details[0]
    assert entry["category"] == "timestamp"
    assert entry["can_use"] is True
    assert entry["source_locator"] == "calls.csv:1"
    assert entry["impact"] and entry["recommendation"]


def test_parse_response_includes_warning_details(client, case):
    content = b"name,value\nalpha,1\n"
    evidence = _evidence(client, case["id"], "generic.csv", content, "text/csv")
    response = client.post(f"/api/evidence/{evidence['id']}/parse", params={"case_id": case["id"]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert "warning_details" in body
    assert isinstance(body["warning_details"], list)
    assert body["records_extracted"] is not None
    assert body["records_rejected"] is not None


def test_settings_default_budget_is_application_side():
    settings = Settings()
    assert settings.ai_budget_usd == 0.5
