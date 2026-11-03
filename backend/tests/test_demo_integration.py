from __future__ import annotations

from pathlib import Path

SAMPLE_ROOT = Path(__file__).resolve().parents[2] / "sample_data"
OPERATION = SAMPLE_ROOT / "operation_phishtrace"
BENIGN = SAMPLE_ROOT / "benign_control"


def _upload(client, case_id: str, path: Path) -> dict:
    with path.open("rb") as handle:
        response = client.post(
            f"/api/cases/{case_id}/evidence",
            files={"file": (path.name, handle, "application/octet-stream")},
        )
    assert response.status_code == 201, (path.name, response.text)
    return response.json()


def _parse_all(client, case_id: str, evidence: list[dict]) -> None:
    for item in evidence:
        response = client.post(
            f"/api/evidence/{item['id']}/parse", params={"case_id": case_id}
        )
        assert response.status_code == 200, (item["original_filename"], response.text)
        assert response.json()["status"] in {
            "parsed",
            "partially_parsed",
            "ocr_unavailable",
        }, (item["original_filename"], response.json())


def _finding_matches(findings: list[dict], text: str, severity: str | None = None) -> bool:
    return any(
        text.lower() in finding["title"].lower()
        and (severity is None or finding["severity"] == severity)
        for finding in findings
    )


def test_operation_phishtrace_end_to_end(client, case):
    names = [
        "call_log.csv",
        "chat_export.txt",
        "invoice_45000.pdf",
        "payment_screenshot.png",
        "upi_transaction_log.csv",
        "auth.log",
    ]
    evidence = [_upload(client, case["id"], OPERATION / name) for name in names]
    _parse_all(client, case["id"], evidence)

    reconcile = client.post(f"/api/cases/{case['id']}/reconcile")
    assert reconcile.status_code == 200, reconcile.text
    assert reconcile.json()["findings_created"] >= 4

    findings_response = client.get(f"/api/cases/{case['id']}/findings")
    assert findings_response.status_code == 200
    findings = findings_response.json()["items"]

    assert _finding_matches(findings, "Amount discrepancy", "high")
    assert _finding_matches(findings, "Payee mismatch", "high")
    assert _finding_matches(findings, "Exact UTR match", "info")
    assert _finding_matches(findings, "phone +91-98765-43210")
    assert _finding_matches(findings, "utr 312456789012")
    assert _finding_matches(findings, "upi_vpa gov-security@upi")
    assert _finding_matches(findings, "filename invoice_45000.pdf")
    assert any(finding["category"] == "authentication" for finding in findings)

    # The tool must not put a guilt/fraud verdict in a finding title.
    assert not any(
        "fraud" in finding["title"].lower() or "guilty" in finding["title"].lower()
        for finding in findings
    )

    graph = client.get(f"/api/cases/{case['id']}/graph")
    assert graph.status_code == 200
    graph_payload = graph.json()
    assert graph_payload["nodes"]
    edge_types = {edge["edge_type"] for edge in graph_payload["edges"]}
    assert "exact_utr_match" in edge_types
    assert "amount_conflict" in edge_types
    assert "payee_conflict" in edge_types
    assert "exact_identifier_match" in edge_types

    timeline = client.get(f"/api/cases/{case['id']}/timeline")
    assert timeline.status_code == 200
    assert timeline.json()["total"] > 0

    auth_events = client.get(
        f"/api/cases/{case['id']}/events", params={"event_type": "auth.login"}
    )
    assert auth_events.status_code == 200
    assert auth_events.json()["total"] >= 10

    report = client.post(
        f"/api/cases/{case['id']}/reports", json={"report_type": "json"}
    )
    assert report.status_code == 201, report.text
    report_meta = report.json()
    download = client.get(
        f"/api/reports/{report_meta['id']}/download", params={"case_id": case["id"]}
    )
    assert download.status_code == 200
    report_payload = download.json()
    assert any(
        finding["title"].startswith("Amount discrepancy")
        for finding in report_payload["findings"]
    )
    assert report_payload["evidence"]


def test_benign_control_does_not_raise_a_false_anomaly(client):
    benign_case = client.post(
        "/api/cases",
        json={"title": "Benign Control", "description": "Synthetic benign control."},
    ).json()
    evidence = [
        _upload(client, benign_case["id"], BENIGN / "invoice_legit.pdf"),
        _upload(client, benign_case["id"], BENIGN / "upi_statement.csv"),
    ]
    _parse_all(client, benign_case["id"], evidence)

    reconcile = client.post(f"/api/cases/{benign_case['id']}/reconcile")
    assert reconcile.status_code == 200, reconcile.text

    findings = client.get(
        f"/api/cases/{benign_case['id']}/findings"
    ).json()["items"]
    assert _finding_matches(findings, "Values reconcile for invoice INV-2026-9913", "info")

    reconciliation_anomalies = [
        finding
        for finding in findings
        if finding["category"] == "reconciliation"
        and finding["severity"] in {"medium", "high", "critical"}
    ]
    assert reconciliation_anomalies == []
