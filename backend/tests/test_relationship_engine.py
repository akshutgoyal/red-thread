from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models import Entity, Event, EventEntity, Evidence, Relationship
from app.services import relationship_engine


def _evidence(db, case_id: str, filename: str):
    evidence = Evidence(
        case_id=case_id,
        original_filename=filename,
        stored_filename=filename,
        relative_path=f"evidence/{case_id}/{filename}",
        media_type="text/csv",
        size_bytes=100,
        sha256="a" * 64,
        processing_status="parsed",
    )
    db.add(evidence)
    return evidence


def _event(db, case_id: str, evidence_id: str, filename: str, locator: str, when: datetime, attributes: dict):
    event = Event(
        case_id=case_id,
        evidence_id=evidence_id,
        event_type="call" if filename.startswith("call") else "chat",
        timestamp_raw=when.isoformat(),
        timestamp_normalized=when,
        timestamp_confidence="exact",
        timestamp_timezone="UTC",
        source_filename=filename,
        source_locator=locator,
        source_snippet=f"event from {filename}",
        attributes_json=attributes,
        parser_name="test",
        parser_version="1",
    )
    db.add(event)
    return event


def _entity(db, case_id: str, entity_type: str, value: str):
    entity = Entity(
        case_id=case_id,
        entity_type=entity_type,
        value_original=value,
        value_normalized=value,
        normalization_method="test",
    )
    db.add(entity)
    return entity


def test_correlation_engine_builds_provenance_backed_relationships(db, case):
    case_id = case["id"]
    call_evidence = _evidence(db, case_id, "call_log.csv")
    chat_evidence = _evidence(db, case_id, "chat_export.txt")
    db.flush()

    first = _event(
        db,
        case_id,
        call_evidence.id,
        "call_log.csv",
        "row:2",
        datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc),
        {"latitude": 12.9716, "longitude": 77.5946},
    )
    second = _event(
        db,
        case_id,
        chat_evidence.id,
        "chat_export.txt",
        "message:1",
        datetime(2026, 10, 15, 10, 10, tzinfo=timezone.utc),
        {"latitude": 12.9720, "longitude": 77.5950},
    )
    phone = _entity(db, case_id, "phone", "+919876543210")
    device = _entity(db, case_id, "device_id", "DEV-1")
    db.flush()

    db.add_all(
        [
            EventEntity(event_id=first.id, entity_id=phone.id, role="participant", raw_value=phone.value_original),
            EventEntity(event_id=first.id, entity_id=device.id, role="device", raw_value=device.value_original),
            EventEntity(event_id=second.id, entity_id=phone.id, role="participant", raw_value=phone.value_original),
        ]
    )
    db.commit()

    summary = relationship_engine.build_case_relationships(db, case_id)
    db.commit()

    assert summary["relationships"] >= 4
    relationships = list(
        db.scalars(select(Relationship).where(Relationship.case_id == case_id))
    )
    by_type = {item.relationship_type: item for item in relationships}

    assert "shared_identifier" in by_type
    shared = by_type["shared_identifier"]
    assert shared.correlation_rule == "exact_phone_match"
    assert shared.classification == "correlation"
    assert shared.review_status == "unreviewed"
    assert shared.support_count == 2
    assert {support.evidence_id for support in shared.supports} == {
        call_evidence.id,
        chat_evidence.id,
    }
    assert {support.source_locator for support in shared.supports} == {
        "row:2",
        "message:1",
    }

    assert "co_mention" in by_type
    co_mention = by_type["co_mention"]
    assert co_mention.classification == "observation"
    assert co_mention.support_count == 1
    assert co_mention.source_type == "entity"
    assert co_mention.target_type == "entity"

    assert "temporal_association" in by_type
    assert by_type["temporal_association"].correlation_rule == (
        "temporal_window_same_identifier"
    )
    assert by_type["temporal_association"].support_count == 2

    assert "spatial_proximity" in by_type
    assert by_type["spatial_proximity"].classification == "correlation"
    assert by_type["spatial_proximity"].support_count == 2
