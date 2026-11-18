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
    annotation = client.post(
        f"/api/cases/{case['id']}/annotations",
        json={
            "target_type": "case",
            "target_id": case["id"],
            "author": "Investigator",
            "note": "Verify the auth chronology before report approval.",
        },
    )
    assert annotation.status_code == 201, annotation.text

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
    assert payload["annotations"][0]["author"] == "Investigator"
    assert payload["annotations"][0]["note"].startswith("Verify the auth chronology")
    assert payload["review_decisions"] == []
    assert "unresolved" in payload

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


def test_court_report_sections_and_no_fabricated_certificate(client, case, auth_log_bytes):
    """The court-oriented draft must carry every required section, and must not
    invent a declaration, signature or certification that it cannot attest to."""

    _prepare_case(client, case, auth_log_bytes)
    generated = client.post(
        f"/api/cases/{case['id']}/reports", json={"report_type": "json"}
    )
    assert generated.status_code == 201, generated.text
    report_id = generated.json()["id"]

    download = client.get(
        f"/api/reports/{report_id}/download", params={"case_id": case["id"]}
    )
    payload = download.json()

    # Data sections the court-oriented format requires.
    assert payload["chain_of_custody"], "chain of custody must be derived from audit rows"
    assert payload["provenance"]
    assert payload["provenance"][0]["sha256"] == payload["evidence"][0]["sha256"]
    assert payload["court_disclaimer"]
    joined = " ".join(payload["court_disclaimer"]).lower()
    assert "cannot independently be submitted" in joined
    assert "does not provide legal certification" in joined

    # Every statement type must be distinguishable.
    classifications = {item["classification"] for item in payload["relationships"]}
    assert classifications <= {"observation", "correlation", "inference", "hypothesis"}

    # No fabricated attestation anywhere in the JSON.
    serialized = str(payload).lower()
    assert "digitally signed by" not in serialized
    assert "i hereby certify that this is a true copy" not in serialized


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
