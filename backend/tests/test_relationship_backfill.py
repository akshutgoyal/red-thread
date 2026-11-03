from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models import Event, Evidence, GraphEdge, Relationship
from app.services import relationship_service


def test_legacy_graph_edge_backfill_is_idempotent(db, case):
    case_id = case["id"]
    evidence = Evidence(
        case_id=case_id,
        original_filename="auth.log",
        stored_filename="auth.log",
        relative_path=f"evidence/{case_id}/auth.log",
        media_type="text/plain",
        size_bytes=120,
        sha256="b" * 64,
        processing_status="parsed",
    )
    db.add(evidence)
    db.flush()

    first = Event(
        case_id=case_id,
        evidence_id=evidence.id,
        event_type="auth.login",
        timestamp_raw="2026-10-15T10:00:00Z",
        timestamp_normalized=datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc),
        timestamp_confidence="exact",
        timestamp_timezone="UTC",
        source_filename="auth.log",
        source_locator="line:1",
        source_snippet="Authentication event one",
        parser_name="auth_log",
        parser_version="1",
    )
    second = Event(
        case_id=case_id,
        evidence_id=evidence.id,
        event_type="auth.login",
        timestamp_raw="2026-10-15T10:05:00Z",
        timestamp_normalized=datetime(2026, 10, 15, 10, 5, tzinfo=timezone.utc),
        timestamp_confidence="exact",
        timestamp_timezone="UTC",
        source_filename="auth.log",
        source_locator="line:2",
        source_snippet="Authentication event two",
        parser_name="auth_log",
        parser_version="1",
    )
    db.add_all([first, second])
    db.flush()

    edge = GraphEdge(
        case_id=case_id,
        source_type="event",
        source_id=first.id,
        target_type="event",
        target_id=second.id,
        edge_type="shared_ip",
        match_method="exact_identifier",
        explanation="Legacy graph edge linking two events.",
        confidence="high",
        supporting_event_ids_json=[first.id, second.id],
        supporting_evidence_ids_json=[evidence.id],
    )
    db.add(edge)
    db.commit()

    first_run = relationship_service.backfill_legacy_graph_edges(db, case_id=case_id)
    second_run = relationship_service.backfill_legacy_graph_edges(db, case_id=case_id)

    relationships = list(
        db.scalars(select(Relationship).where(Relationship.case_id == case_id))
    )
    backfilled = [item for item in relationships if item.source_type == "event"]

    assert len(backfilled) == 1
    assert first_run["relationships"] == 1
    assert second_run["relationships"] == 1
    assert backfilled[0].correlation_rule == "exact_identifier"
    assert backfilled[0].classification == "correlation"
    assert backfilled[0].support_count == 2
    assert {support.source_locator for support in backfilled[0].supports} == {
        "line:1",
        "line:2",
    }
