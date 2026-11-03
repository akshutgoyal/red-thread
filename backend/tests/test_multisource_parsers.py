from __future__ import annotations

from datetime import datetime, timezone

from app.parsers.base import ParserContext
from app.parsers.registry import detect_parser
from app.utils.timestamps import parse_flexible_timestamp


def context(path_name: str) -> ParserContext:
    return ParserContext(
        case_id="case-test",
        evidence_id="evidence-test",
        source_filename=path_name,
        reference_date=datetime(2026, 10, 20, tzinfo=timezone.utc),
        timezone="UTC",
    )


def test_gps_csv_is_detected_and_extracts_spatial_entities(tmp_path):
    path = tmp_path / "gps_records.csv"
    path.write_text(
        "timestamp,device_id,latitude,longitude,place\n"
        "2026-10-15T10:00:00Z,DEV-9,12.9716,77.5946,Central\n",
        encoding="utf-8",
    )

    parser = detect_parser(path)
    assert parser.name == "gps"
    result = parser.parse(path, context(path.name))

    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_type == "location_fix"
    assert event.source_locator == "row:2"
    assert event.attributes["latitude"] == 12.9716
    assert event.attributes["longitude"] == 77.5946
    entity_types = {(entity.entity_type, entity.value) for entity in event.entities}
    assert ("gps_point", "12.971600,77.594600") in entity_types
    assert ("device_id", "DEV-9") in entity_types
    assert ("place_label", "Central") in entity_types


def test_cctv_csv_is_detected_and_preserves_recording_window(tmp_path):
    path = tmp_path / "cctv_metadata.csv"
    path.write_text(
        "camera_id,site_name,latitude,longitude,recording_start,recording_end,file_name\n"
        "CAM-1,Central Junction,12.9720,77.5950,2026-10-15T10:00:00Z,2026-10-15T10:05:00Z,cam1.mp4\n",
        encoding="utf-8",
    )

    parser = detect_parser(path)
    assert parser.name == "cctv"
    result = parser.parse(path, context(path.name))

    event = result.events[0]
    assert event.event_type == "cctv_segment"
    assert event.attributes["recording_end"]
    assert event.attributes["latitude"] == 12.972
    entity_types = {entity.entity_type for entity in event.entities}
    assert {"camera_id", "place_label", "gps_point", "filename"} <= entity_types


def test_device_log_csv_extracts_device_ip_and_subscriber_entities(tmp_path):
    path = tmp_path / "device_log.csv"
    path.write_text(
        "timestamp,device_id,imei,msisdn,ip,event\n"
        "2026-10-15T10:01:00Z,DEV-9,490154203237518,+919876543210,10.20.30.40,network_attach\n",
        encoding="utf-8",
    )

    parser = detect_parser(path)
    assert parser.name == "device_log"
    result = parser.parse(path, context(path.name))

    event = result.events[0]
    assert event.event_type == "device_event"
    entity_types = {entity.entity_type for entity in event.entities}
    assert {"device_id", "imei", "phone", "ip"} <= entity_types
    ip_entity = next(entity for entity in event.entities if entity.entity_type == "ip")
    assert ip_entity.value == "10.20.30.40"


def test_email_records_csv_uses_bare_sender_address_and_row_locator(tmp_path):
    path = tmp_path / "email_records.csv"
    path.write_text(
        "from,to,subject,body,date,message_id\n"
        "Ravi <ravi@example.test>,sita@example.test,Invoice,Please review the invoice,2026-10-15T12:00:00+05:30,MSG-1\n",
        encoding="utf-8",
    )

    parser = detect_parser(path)
    assert parser.name == "email"
    result = parser.parse(path, context(path.name))

    event = result.events[0]
    assert event.event_type == "email"
    assert event.source_locator == "row:2"
    sender = [
        entity
        for entity in event.entities
        if entity.entity_type == "email" and entity.role == "sender"
    ]
    assert sender and sender[0].value == "ravi@example.test"
    assert event.timestamp_normalized is not None


def test_chat_jsonl_is_parsed_as_structured_messages(tmp_path):
    path = tmp_path / "chat_export.jsonl"
    path.write_text(
        '{"sender": "A", "recipient": "B", "message": "Meet at the junction", "timestamp": "2026-10-15T10:05:00Z"}\n'
        '{"sender": "B", "recipient": "A", "message": "Confirmed", "timestamp": "2026-10-15T10:06:00Z"}\n',
        encoding="utf-8",
    )

    parser = detect_parser(path)
    assert parser.name == "chat"
    result = parser.parse(path, context(path.name))
    assert len(result.events) == 2
    assert {event.event_type for event in result.events} == {"chat_message"}


def test_auth_parser_accepts_iso_timestamps_and_sshd_session(tmp_path):
    path = tmp_path / "auth.log"
    path.write_text(
        "2026-10-15T10:00:01Z host sshd-session[123]: Failed password for invalid user bob "
        "from 10.1.2.3 port 22 ssh2\n",
        encoding="utf-8",
    )

    parser = detect_parser(path)
    assert parser.name == "auth_log"
    result = parser.parse(path, context(path.name))

    assert result.events
    event = result.events[0]
    assert event.event_type == "auth.login"
    assert event.attributes["source_ip"] == "10.1.2.3"
    assert event.attributes["event_id"]
    assert event.timestamp_normalized is not None


def test_numeric_timezone_offset_is_not_marked_assumed():
    parsed = parse_flexible_timestamp(
        "2026-10-15T10:00:00+05:30",
        default_timezone="UTC",
        reference_date=datetime(2026, 10, 20, tzinfo=timezone.utc),
    )

    assert parsed.timezone_assumed is False
    assert parsed.timezone_name == "+05:30"
    assert parsed.normalized.hour == 4
    assert parsed.normalized.minute == 30
