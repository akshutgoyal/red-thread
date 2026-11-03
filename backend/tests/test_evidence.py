from __future__ import annotations

import hashlib

from app.services import evidence_service


def _upload(client, case_id, name="sample.csv", content=b"a,b\n1,2\n"):
    return client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": (name, content, "text/csv")},
    )


def test_upload_hashes_and_lists_evidence(client, case):
    response = _upload(client, case["id"])
    assert response.status_code == 201, response.text
    evidence = response.json()
    assert evidence["sha256"] == hashlib.sha256(b"a,b\n1,2\n").hexdigest()
    assert evidence["size_bytes"] == 8
    assert evidence["processing_status"] == "uploaded"
    assert "relative_path" not in evidence
    assert "stored_filename" not in evidence

    listed = client.get(f"/api/cases/{case['id']}/evidence")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(
        f"/api/evidence/{evidence['id']}", params={"case_id": case["id"]}
    )
    assert fetched.status_code == 200
    assert fetched.json()["id"] == evidence["id"]


def test_verify_evidence_and_detect_tampering(client, case, db):
    response = _upload(client, case["id"])
    evidence_id = response.json()["id"]

    verified = client.post(
        f"/api/evidence/{evidence_id}/verify", params={"case_id": case["id"]}
    )
    assert verified.status_code == 200
    assert verified.json()["verified"] is True

    evidence = evidence_service.get_evidence(db, evidence_id, case["id"])
    assert evidence is not None
    path = evidence_service.get_evidence_path(evidence)
    path.write_bytes(b"a,b\n1,2\nTAMPERED")

    failed = client.post(
        f"/api/evidence/{evidence_id}/verify", params={"case_id": case["id"]}
    )
    assert failed.status_code == 200
    assert failed.json()["verified"] is False
    assert "does NOT match" in failed.json()["message"]


def test_rejects_unsupported_extension(client, case):
    response = _upload(client, case["id"], name="malware.exe", content=b"MZ")
    assert response.status_code == 415


def test_rejects_empty_file(client, case):
    response = _upload(client, case["id"], name="empty.csv", content=b"")
    assert response.status_code == 422


def test_case_scope_is_enforced(client, case):
    first = _upload(client, case["id"])
    evidence_id = first.json()["id"]

    other = client.post("/api/cases", json={"title": "Other Case"})
    other_id = other.json()["id"]

    response = client.get(
        f"/api/evidence/{evidence_id}", params={"case_id": other_id}
    )
    assert response.status_code == 404


def test_text_preview(client, case):
    response = _upload(client, case["id"], name="notes.txt", content=b"hello\nworld\n")
    evidence_id = response.json()["id"]
    preview = client.get(
        f"/api/evidence/{evidence_id}/text", params={"case_id": case["id"]}
    )
    assert preview.status_code == 200
    assert preview.json()["text"] == "hello\nworld\n"
    assert preview.json()["truncated"] is False
