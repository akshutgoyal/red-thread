from __future__ import annotations

import pytest

from app.services import relationship_service


def test_relationship_provenance_review_and_annotations(client, db, case):
    relationship = relationship_service.upsert_relationship(
        db,
        case_id=case["id"],
        source_type="entity",
        source_id="entity:phone:+919000000001",
        target_type="entity",
        target_id="entity:device:IMEI-123456789012345",
        relationship_type="shared_device_phone",
        correlation_rule="device_phone_exact",
        explanation="The same fictional device identifier appears in the call record and device log.",
        confidence="medium",
        classification="correlation",
        metadata={"source": "synthetic test"},
        supports=[
            {
                "source_locator": "row:2",
                "snippet": "device_id=IMEI-123456789012345 phone=+919000000001",
                "support_kind": "identifier",
            }
        ],
    )
    assert relationship.id
    assert relationship.support_count == 1
    assert relationship.review_status == "unreviewed"

    response = client.get(f"/api/cases/{case['id']}/relationships")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == relationship.id
    assert payload["items"][0]["support_count"] == 1

    detail = client.get(
        f"/api/relationships/{relationship.id}",
        params={"case_id": case["id"]},
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["supports"][0]["source_locator"] == "row:2"
    assert detail.json()["reviews"] == []

    reviewed = client.post(
        f"/api/relationships/{relationship.id}/review",
        params={"case_id": case["id"]},
        json={
            "decision": "accepted",
            "reviewer": "analyst@example.test",
            "note": "Supported by the synthetic device log.",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    reviewed_payload = reviewed.json()
    assert reviewed_payload["review_status"] == "accepted"
    assert reviewed_payload["review_note"] == "Supported by the synthetic device log."
    assert len(reviewed_payload["reviews"]) == 1
    assert reviewed_payload["reviews"][0]["decision"] == "accepted"

    annotation = client.post(
        f"/api/cases/{case['id']}/annotations",
        json={
            "target_type": "relationship",
            "target_id": relationship.id,
            "author": "analyst@example.test",
            "note": "Check the device registration source before final review.",
        },
    )
    assert annotation.status_code == 201, annotation.text
    annotations = client.get(
        f"/api/cases/{case['id']}/annotations",
        params={"target_type": "relationship", "target_id": relationship.id},
    )
    assert annotations.status_code == 200, annotations.text
    assert len(annotations.json()) == 1
    assert annotations.json()[0]["note"].startswith("Check the device")


def test_relationship_list_filters(client, db, case):
    relationship_service.upsert_relationship(
        db,
        case_id=case["id"],
        source_type="event",
        source_id="event:1",
        target_type="event",
        target_id="event:2",
        relationship_type="temporal_proximity",
        correlation_rule="identifier_gated_temporal_window",
        explanation="Two records fall inside the configured window.",
        classification="inference",
        confidence="low",
    )
    response = client.get(
        f"/api/cases/{case['id']}/relationships",
        params={"classification": "inference", "confidence": "low"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["classification"] == "inference"

    empty = client.get(
        f"/api/cases/{case['id']}/relationships",
        params={"classification": "hypothesis"},
    )
    assert empty.status_code == 200
    assert empty.json()["total"] == 0


def test_relationship_case_scoping(client, db, case):
    relationship = relationship_service.upsert_relationship(
        db,
        case_id=case["id"],
        source_type="entity",
        source_id="entity:email:a@example.test",
        target_type="entity",
        target_id="entity:phone:+919000000002",
        relationship_type="shared_identity_reference",
        correlation_rule="email_phone_reference",
        explanation="Synthetic cross-source reference.",
        classification="observation",
    )
    other = client.post(
        "/api/cases",
        json={"title": "Other case", "description": "Synthetic case scoping test."},
    )
    assert other.status_code == 201, other.text
    other_case = other.json()

    detail = client.get(
        f"/api/relationships/{relationship.id}",
        params={"case_id": other_case["id"]},
    )
    assert detail.status_code == 404

    review = client.post(
        f"/api/relationships/{relationship.id}/review",
        params={"case_id": other_case["id"]},
        json={"decision": "rejected", "note": "wrong case"},
    )
    assert review.status_code == 404


def test_invalid_relationship_values(db, case):
    with pytest.raises(ValueError):
        relationship_service.upsert_relationship(
            db,
            case_id=case["id"],
            source_type="entity",
            source_id="entity:a",
            target_type="entity",
            target_id="entity:b",
            relationship_type="test",
            correlation_rule="test",
            explanation="test",
            classification="verified_certainty",
        )

    with pytest.raises(ValueError):
        relationship_service.review_relationship(
            db,
            "missing",
            case["id"],
            decision="approved",
        )
