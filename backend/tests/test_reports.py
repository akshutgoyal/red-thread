from __future__ import annotations


def _prepare_case(client, case, auth_log_bytes):
    uploaded = client.post(
        f"/api/cases/{case['id']}/evidence",
        files={"file": ("auth.log", auth_log_bytes, "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    evidence = uploaded.json()
    parsed = client.post(
        f"/api/evidence/{evidence['id']}/parse", params={"case_id": case["id"]}
    )
    assert parsed.status_code == 200, parsed.text
    return evidence


def test_generate_json_and_pdf_reports(client, case, auth_log_bytes):
    evidence = _prepare_case(client, case, auth_log_bytes)

    json_report = client.post(
        f"/api/cases/{case['id']}/reports", json={"report_type": "json"}
    )
    assert json_report.status_code == 201, json_report.text
    report = json_report.json()
    assert report["report_type"] == "json"
    assert report["filename"].endswith(".json")
    assert report["metadata_json"]["evidence_count"] == 1
    assert "relative_path" not in report

    listing = client.get(f"/api/cases/{case['id']}/reports")
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    download = client.get(
        f"/api/reports/{report['id']}/download", params={"case_id": case["id"]}
    )
    assert download.status_code == 200
    assert "application/json" in download.headers["content-type"]
    payload = download.json()
    assert payload["case"]["id"] == case["id"]
    assert payload["evidence"][0]["sha256"] == evidence["sha256"]
    assert payload["limitations"]
    assert "DRAFT" in payload["limitations"][-1]
    assert payload["findings"]

    pdf_report = client.post(
        f"/api/cases/{case['id']}/reports", json={"report_type": "pdf"}
    )
    assert pdf_report.status_code == 201, pdf_report.text
    pdf = pdf_report.json()
    assert pdf["filename"].endswith(".pdf")

    pdf_download = client.get(
        f"/api/reports/{pdf['id']}/download", params={"case_id": case["id"]}
    )
    assert pdf_download.status_code == 200
    assert pdf_download.headers["content-type"].startswith("application/pdf")
    assert pdf_download.content.startswith(b"%PDF")
    assert len(pdf_download.content) > 1000

    audit = client.get(f"/api/cases/{case['id']}/audit")
    assert audit.status_code == 200
    assert any(item["action"] == "report.generated" for item in audit.json())


def test_report_access_is_case_scoped(client, case, auth_log_bytes):
    _prepare_case(client, case, auth_log_bytes)
    generated = client.post(
        f"/api/cases/{case['id']}/reports", json={"report_type": "json"}
    )
    report_id = generated.json()["id"]
    other = client.post("/api/cases", json={"title": "Other Case"}).json()

    metadata = client.get(
        f"/api/reports/{report_id}", params={"case_id": other["id"]}
    )
    assert metadata.status_code == 404

    download = client.get(
        f"/api/reports/{report_id}/download", params={"case_id": other["id"]}
    )
    assert download.status_code == 404
