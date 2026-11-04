from __future__ import annotations

from pathlib import Path

SAMPLE_ROOT = Path(__file__).resolve().parents[2] / "sample_data"
DIGITAL = SAMPLE_ROOT / "operation_digital_trail"

FILES = [
    "call_log.csv",
    "chat_export.txt",
    "email_records.csv",
    "gps_records.csv",
    "cctv_metadata.csv",
    "device_log.csv",
    "auth.log",
]


def _upload(client, case_id: str, path: Path) -> dict:
    with path.open("rb") as handle:
        response = client.post(
            f"/api/cases/{case_id}/evidence",
            files={"file": (path.name, handle, "application/octet-stream")},
        )
    assert response.status_code == 201, (path.name, response.text)
    return response.json()


def test_operation_digital_trail_end_to_end(client, case):
    evidence = [_upload(client, case["id"], DIGITAL / name) for name in FILES]
    for item in evidence:
        response = client.post(
            f"/api/evidence/{item['id']}/parse", params={"case_id": case["id"]}
        )
        assert response.status_code == 200, (item["original_filename"], response.text)
        assert response.json()["events_created"] >= 0

    reconcile = client.post(f"/api/cases/{case['id']}/reconcile")
    assert reconcile.status_code == 200, reconcile.text

    relationships_response = client.get(
        f"/api/cases/{case['id']}/relationships",
        params={"limit": 500},
    )
    assert relationships_response.status_code == 200, relationships_response.text
    relationships = relationships_response.json()["items"]
    assert relationships
    types = {item["relationship_type"] for item in relationships}
    assert {"shared_identifier", "co_mention", "temporal_association", "spatial_proximity"} <= types
    assert all(item["support_count"] > 0 for item in relationships)

    detail = client.get(
        f"/api/relationships/{relationships[0]['id']}",
        params={"case_id": case["id"]},
    )
    assert detail.status_code == 200, detail.text
    supports = detail.json()["supports"]
    assert supports
    assert any(support["source_locator"] for support in supports)

    spatial = client.get(f"/api/cases/{case['id']}/spatial")
    assert spatial.status_code == 200, spatial.text
    spatial_payload = spatial.json()
    assert spatial_payload["observations"]
    assert any(point["event_type"] == "location_fix" for point in spatial_payload["observations"])
    assert spatial_payload["relationships"]

    review_target = relationships[0]
    review = client.post(
        f"/api/relationships/{review_target['id']}/review",
        params={"case_id": case["id"]},
        json={
            "decision": "accepted",
            "reviewer": "analyst@example.test",
            "note": "Synthetic review decision for report coverage.",
        },
    )
    assert review.status_code == 200, review.text
    assert review.json()["review_status"] == "accepted"

    annotation = client.post(
        f"/api/cases/{case['id']}/annotations",
        json={
            "target_type": "case",
            "target_id": case["id"],
            "author": "Investigator",
            "note": "Review the synthetic Digital Trail chronology before sign-off.",
        },
    )
    assert annotation.status_code == 201, annotation.text

    report = client.post(
        f"/api/cases/{case['id']}/reports", json={"report_type": "json"}
    )
    assert report.status_code == 201, report.text
    download = client.get(
        f"/api/reports/{report.json()['id']}/download",
        params={"case_id": case["id"]},
    )
    assert download.status_code == 200
    payload = download.json()
    assert payload["relationships"]
    assert any(item["supports"] for item in payload["relationships"])
    assert payload["spatial_observations"]
    assert payload["review_decisions"][0]["decision"] == "accepted"
    assert payload["annotations"][0]["note"].startswith("Review the synthetic")
    assert payload["annotations"][0]["target_type"] == "case"
    assert payload["unresolved"]
    assert payload["limitations"]
    assert "DRAFT" in payload["limitations"][-1]
