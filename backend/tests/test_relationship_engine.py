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


def _typed_event(
    db,
    case_id: str,
    evidence_id: str,
    filename: str,
    locator: str,
    when: datetime,
    event_type: str,
    parser_name: str,
    attributes: dict | None = None,
):
    event = Event(
        case_id=case_id,
        evidence_id=evidence_id,
        event_type=event_type,
        timestamp_raw=when.isoformat(),
        timestamp_normalized=when,
        timestamp_confidence="exact",
        timestamp_timezone="UTC",
        source_filename=filename,
        source_locator=locator,
        source_snippet=f"{event_type} from {filename}",
        attributes_json=attributes or {},
        parser_name=parser_name,
        parser_version="1",
    )
    db.add(event)
    return event


def test_contextual_rules_and_idempotent_rerun(db, case):
    case_id = case["id"]
    call_evidence = _evidence(db, case_id, "call_log.csv")
    chat_evidence = _evidence(db, case_id, "chat_export.txt")
    auth_evidence = _evidence(db, case_id, "auth.log")
    device_evidence = _evidence(db, case_id, "device_log.csv")
    gps_evidence = _evidence(db, case_id, "gps_records.csv")
    cctv_evidence = _evidence(db, case_id, "cctv_metadata.csv")
    db.flush()

    call = _event(
        db, case_id, call_evidence.id, "call_log.csv", "row:2",
        datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc), {},
    )
    chat = _event(
        db, case_id, chat_evidence.id, "chat_export.txt", "message:1",
        datetime(2026, 10, 15, 10, 5, tzinfo=timezone.utc), {},
    )
    auth = _typed_event(
        db, case_id, auth_evidence.id, "auth.log", "line:1",
        datetime(2026, 10, 15, 10, 10, tzinfo=timezone.utc),
        "auth.login", "auth_log",
    )
    device_event = _typed_event(
        db, case_id, device_evidence.id, "device_log.csv", "row:2",
        datetime(2026, 10, 15, 10, 12, tzinfo=timezone.utc),
        "device_event", "device_log",
    )
    fix_one = _typed_event(
        db, case_id, gps_evidence.id, "gps_records.csv", "row:2",
        datetime(2026, 10, 15, 11, 0, tzinfo=timezone.utc),
        "location_fix", "gps", {"latitude": 12.0, "longitude": 77.0},
    )
    fix_two = _typed_event(
        db, case_id, gps_evidence.id, "gps_records.csv", "row:3",
        datetime(2026, 10, 15, 11, 5, tzinfo=timezone.utc),
        "location_fix", "gps", {"latitude": 13.0, "longitude": 78.0},
    )
    cctv_one = _typed_event(
        db, case_id, cctv_evidence.id, "cctv_metadata.csv", "row:2",
        datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc),
        "cctv_segment", "cctv",
        {"camera_id": "CAM-1", "recording_end": "2026-10-15T12:05:00+00:00"},
    )
    cctv_two = _typed_event(
        db, case_id, cctv_evidence.id, "cctv_metadata.csv", "row:3",
        datetime(2026, 10, 15, 12, 20, tzinfo=timezone.utc),
        "cctv_segment", "cctv",
        {"camera_id": "CAM-1", "recording_end": "2026-10-15T12:25:00+00:00"},
    )
    phone = _entity(db, case_id, "phone", "+919876543210")
    ip = _entity(db, case_id, "ip", "198.51.100.77")
    device = _entity(db, case_id, "device_id", "DEV-1")
    db.flush()

    links = [
        (call, phone), (chat, phone),
        (auth, ip), (device_event, ip),
        (fix_one, device), (fix_two, device),
    ]
    for event, entity in links:
        db.add(
            EventEntity(
                event_id=event.id,
                entity_id=entity.id,
                role="test",
                raw_value=entity.value_original,
            )
        )
    db.commit()

    first = relationship_engine.build_case_relationships(db, case_id)
    db.commit()
    relationships = list(
        db.scalars(select(Relationship).where(Relationship.case_id == case_id))
    )
    by_type = {item.relationship_type: item for item in relationships}

    assert "communication_sequence" in by_type
    assert by_type["communication_sequence"].classification == "hypothesis"
    assert by_type["communication_sequence"].support_count >= 2

    assert "device_auth_context" in by_type
    assert by_type["device_auth_context"].classification == "correlation"
    assert by_type["device_auth_context"].support_count == 2

    assert "geo_velocity_anomaly" in by_type
    assert by_type["geo_velocity_anomaly"].classification == "hypothesis"
    assert by_type["geo_velocity_anomaly"].support_count == 2

    assert "cctv_coverage_gap" in by_type
    assert by_type["cctv_coverage_gap"].classification == "hypothesis"
    assert by_type["cctv_coverage_gap"].support_count == 2

    second = relationship_engine.build_case_relationships(db, case_id)
    db.commit()
    rerun_relationships = list(
        db.scalars(select(Relationship).where(Relationship.case_id == case_id))
    )
    assert len(rerun_relationships) == len(relationships)
    assert second["relationships"] == first["relationships"]
