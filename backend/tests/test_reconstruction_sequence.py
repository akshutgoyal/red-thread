from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.case import Case
from app.models.event import Entity, Event, EventEntity
from app.models.evidence import Evidence
from app.models.relationship import Relationship, RelationshipSupport
from app.services import reconstruction_service


@pytest.fixture()
def sequence_case(db):
    case = Case(title="Sequence Case", description="", owner_id=None)
    db.add(case)
    db.commit()

    evidence = Evidence(
        case_id=case.id,
        original_filename="call_log.csv",
        stored_filename="call_log.csv",
        relative_path="/tmp/call_log.csv",
        sha256="a" * 64,
        size_bytes=10,
        media_type="text/csv",
        processing_status="parsed",
    )
    db.add(evidence)
    db.commit()

    caller = Entity(
        case_id=case.id,
        entity_type="phone",
        value_original="+91-99001-12233",
        value_normalized="+919900112233",
    )
    receiver = Entity(
        case_id=case.id,
        entity_type="phone",
        value_original="+91-99004-45566",
        value_normalized="+919900445566",
    )
    db.add_all([caller, receiver])
    db.commit()

    first = Event(
        case_id=case.id,
        evidence_id=evidence.id,
        event_type="call",
        timestamp_normalized=datetime(2026, 10, 14, 13, 29, tzinfo=timezone.utc),
        timestamp_confidence="exact",
        source_filename="call_log.csv",
        source_locator="row:2",
        source_snippet='{"caller": "+91-99001-12233"}',
        attributes_json={
            "caller": "+91-99001-12233",
            "receiver": "+91-99004-45566",
            "call_type": "OUTGOING",
            "duration_sec": 42,
            "cell_tower_id": "CENTRAL-01",
        },
        warnings_json=[],
        parser_name="call_log",
        parser_version="1",
    )
    second = Event(
        case_id=case.id,
        evidence_id=evidence.id,
        event_type="chat_message",
        timestamp_normalized=datetime(2026, 10, 14, 14, 10, tzinfo=timezone.utc),
        timestamp_confidence="ambiguous",
        source_filename="chat.csv",
        source_locator="row:1",
        source_snippet='{"sender": "+91-99001-12233"}',
        attributes_json={
            "sender": "+91-99001-12233",
            "message": "I am at Central Junction.",
        },
        warnings_json=[],
        parser_name="chat",
        parser_version="1",
    )
    db.add_all([first, second])
    db.commit()

    db.add_all(
        [
            EventEntity(event_id=first.id, entity_id=caller.id, role="caller"),
            EventEntity(event_id=first.id, entity_id=receiver.id, role="receiver"),
            EventEntity(event_id=second.id, entity_id=caller.id, role="sender"),
        ]
    )

    relationship = Relationship(
        case_id=case.id,
        source_type="entity",
        source_id=caller.id,
        target_type="entity",
        target_id=receiver.id,
        relationship_type="co_mention",
        correlation_rule="co_mention",
        explanation="Both numbers appear in the same call record.",
        confidence="low",
        classification="observation",
        review_status="unreviewed",
    )
    db.add(relationship)
    db.commit()
    db.add(
        RelationshipSupport(
            relationship_id=relationship.id,
            evidence_id=evidence.id,
            event_id=first.id,
            source_locator="row:2",
            snippet="caller +91-99001-12233 dialled +91-99004-45566",
            support_kind="event",
        )
    )
    db.commit()
    return case


def test_sequence_describes_events_without_raw_json(db, sequence_case):
    result = reconstruction_service.build_sequence(db, sequence_case.id)
    assert result.total == 2
    by_type = {item.event_type: item for item in result.items}

    call = by_type["call"]
    assert "Call from +91-99001-12233 to +91-99004-45566" in call.description
    assert "42s" in call.description
    assert "{" not in call.description, "raw JSON must never be shown as a description"
    assert call.category == "communication"

    chat = by_type["chat_message"]
    assert "I am at Central Junction." in chat.description
    assert "{" not in chat.description


def test_sequence_marks_confidence_and_says_why(db, sequence_case):
    result = reconstruction_service.build_sequence(db, sequence_case.id)
    by_type = {item.event_type: item for item in result.items}

    assert by_type["call"].confidence == "documented"
    assert by_type["chat_message"].confidence == "correlated"
    assert "approximate" in by_type["chat_message"].confidence_reason


def test_sequence_resolves_entities_and_relationship_counterparts(db, sequence_case):
    result = reconstruction_service.build_sequence(db, sequence_case.id)
    call = next(item for item in result.items if item.event_type == "call")

    values = {entity.value for entity in call.entities}
    assert "+91-99001-12233" in values
    assert "+91-99004-45566" in values

    assert call.relationships, "the supporting relationship should be attached"
    counterpart = call.relationships[0].counterpart_value
    assert counterpart.startswith("+91-"), "counterpart must be a readable value"


def test_sequence_never_leaks_raw_identifiers_as_counterparts(db, sequence_case):
    result = reconstruction_service.build_sequence(db, sequence_case.id)
    for item in result.items:
        for relationship in item.relationships:
            assert not (
                len(relationship.counterpart_value) == 32
                and all(c in "0123456789abcdef" for c in relationship.counterpart_value)
            ), "a raw 32-character id is not a readable counterpart"


def test_sequence_orders_dated_events_and_counts_categories(db, sequence_case):
    result = reconstruction_service.build_sequence(db, sequence_case.id)
    assert len(result.items) == 2
    assert len(result.undated) == 0
    assert result.items[0].event_type == "call"
    assert result.items[1].event_type == "chat_message"
    assert result.categories["communication"] == 2
    assert result.limitations


def test_sequence_respects_a_limit(db, sequence_case):
    result = reconstruction_service.build_sequence(db, sequence_case.id, limit=1)
    assert result.total == 1


def test_gap_detection_reports_absence_not_activity(db, sequence_case):
    from datetime import datetime, timedelta, timezone

    from app.schemas.reconstruction import SequenceEvent

    base = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
    items = [
        SequenceEvent(
            id="a",
            timestamp=base,
            event_type="call",
            category="communication",
            label="call record",
            description="",
            evidence_id="e",
            source_filename="f",
            source_locator="row:1",
            source_snippet="",
        ),
        SequenceEvent(
            id="b",
            timestamp=base + timedelta(days=3),
            event_type="call",
            category="communication",
            label="call record",
            description="",
            evidence_id="e",
            source_filename="f",
            source_locator="row:2",
            source_snippet="",
        ),
    ]
    gaps = reconstruction_service._detect_gaps(items)
    assert len(gaps) == 1
    assert "absence of evidence" in gaps[0].message
    assert "not proof that nothing happened" in gaps[0].message
